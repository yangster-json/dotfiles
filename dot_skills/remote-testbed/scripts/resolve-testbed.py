#!/usr/bin/env python3
"""Resolve a testbed nickname through RAS without third-party dependencies.

Tries <name>, lp-<name>, then partition nodes lp-<name>-node<N>. A node is a
slot partition of one physical host, not a separate testbed.
"""

import argparse
import json
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

RAS_URL = "https://ras.dev.purestorage.com/api/node/{}"
MAX_NODES = 8
SHARED_LABELS = {"shared_testbed", "wssd_shared_testbed"}
SENSITIVE_KEY = re.compile(
    r"(?:pass(?:word|phrase)?|secret|token|(?:api|ssh|private)[_-]?key|"
    r"(?:^|[_-])key(?:$|[_-])|cred(?:ential)?s?|auth(?:orization)?|cookie)",
    re.IGNORECASE,
)
# keyword, optional <=40-char qualifier ending in ":"/"="/"is"/"are", then the value:
# "password (root): x", "password for BMC is x", "pw x", "creds root/x"
SENSITIVE_TEXT = re.compile(
    r"((?<![a-z])(?:pass(?:wd|word|phrase)?|pwd?|secret|token|(?:api|ssh|private)[ _-]?key|"
    r"cred(?:ential)?s?|auth(?:orization)?|cookie)(?![a-z])"
    r"(?:[^:=\n]{0,40}?(?:[:=]|(?<![a-z])(?:is|are)(?![a-z])))?"
    r"[ \t:=-]*(?:bearer[ \t]+)?"
    r"|(?<![a-z])bearer[ \t]+)"
    r"(?:\"[^\"\n]*\"?|'[^'\n]*'?|[^\s,;\"']+)",
    re.IGNORECASE,
)


def get_node(name):
    """Return the RAS record, or None on 404."""
    try:
        with urlopen(RAS_URL.format(name), timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code == 404:
            return None
        raise


def base_name(name):
    return re.sub(r"-node\d+$", "", re.sub(r"^lp-", "", name))


def lookup(requested):
    """Return (records, how): direct hit, or every partition node."""
    candidates = [requested]
    if not requested.startswith("lp-"):
        candidates.append(f"lp-{requested}")
    if not re.match(r"(lp-|fw-|hw-|hyper-)", requested):
        candidates += [f"lp-hw-{requested}", f"lp-fw-{requested}"]
    for candidate in candidates:
        node = get_node(candidate)
        if node and not re.search(r"-node\d+$", candidate):
            return [node], "direct"
        if node:
            break  # a named node still needs its siblings

    # a node is a partition, keep probing to list them all
    base = base_name(requested)
    nodes = [get_node(f"lp-{base}-node{n}") for n in range(MAX_NODES)]
    nodes = [node for node in nodes if node]
    return nodes, "partition"


def labels(node):
    found = set(node.get("user_labels") or [])
    if isinstance(node.get("labels"), list):
        found.update(node["labels"])
    return found


def redact_text(text):
    return SENSITIVE_TEXT.sub(r"\1<in RAS>", text)


EXTRACTED_ENV = {"PS_HA_CONTROLLER0", "PS_HA_CONTROLLER1", "HM_COMPUTENODE",
                 "JUMP_HOST", "PARTITIONED_SLOTS", "TESTLAUNCHER_PROFILE"}


def platform(node, tags, env):
    if "flashblade" in tags or "wssd_legend" in tags:
        return "FlashBlade"
    if node.get("hm_computenode") or any(t.startswith(("hyper:", "hyperscale:")) for t in tags):
        return "Endurance"
    if node.get("controllers") or "PS_HA_CONTROLLER0" in env:
        return "FlashArray"
    return "unknown"


def summarize(node):
    """Compact record: only fields an agent routes on; empty fields dropped."""
    env = {
        key: ("<in RAS>" if SENSITIVE_KEY.search(key) else value)
        for key, value in (node.get("env") or {}).items()
    }
    raw_hosts = node.get("controllers") or node.get("hm_computenode") or []
    hosts = [raw_hosts] if isinstance(raw_hosts, str) else raw_hosts
    claim = node.get("claim") or {}
    tags = labels(node)
    notes = node.get("notes")
    if isinstance(notes, dict):
        notes = notes.get("msg", "")
    summary = {
        "ras_name": node.get("name"),
        "platform": platform(node, tags, env),
        "hosts": hosts,
        "ssh": [f"ssh -J {env['JUMP_HOST']} root@{h}" if env.get("JUMP_HOST")
                else f"ssh -J root@{node.get('name')} root@{h}" for h in hosts],
        "jump_host": env.get("JUMP_HOST"),
        "partitioned_slots": env.get("PARTITIONED_SLOTS"),
        "testlauncher_profile": env.get("TESTLAUNCHER_PROFILE"),
        "shared_testbed": bool(tags & SHARED_LABELS) or claim.get("claimant") == "shared_testbed",
        "claimant": claim.get("claimant"),
        "claim_msg": claim.get("claim_msg"),
        "status": node.get("status"),
        "env": {k: v for k, v in env.items() if k not in EXTRACTED_ENV},
        "notes": redact_text(notes or "")[:600],
    }
    return {k: v for k, v in summary.items() if v not in (None, "", [], {}, False)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("testbed")
    parser.add_argument("--json", action="store_true", help="raw RAS records (large, holds credentials); BMC/console actions only")
    args = parser.parse_args()

    try:
        nodes, how = lookup(args.testbed)
    except URLError as error:
        raise SystemExit(f"RAS unreachable ({error}); see fallbacks.md and confirm topology with the user")

    if not nodes:
        raise SystemExit(
            f"RAS target not found: {args.testbed} (tried <name>, lp-<name>, lp-hw-/lp-fw-<name>, lp-<name>-node0..{MAX_NODES - 1}); "
            "do not guess or suggest host names (no <name>-ct0 even as an example); ask the user for platform + hosts, then testlauncher --server <host>"
        )

    if args.json:
        print(json.dumps(nodes, indent=2, sort_keys=True))
        return

    records = [summarize(n) for n in nodes]
    for later in records[1:]:  # partitions share one notes blob
        if later.get("notes") == records[0].get("notes"):
            later.pop("notes", None)
    result = {"requested": args.testbed, "match": how, "records": records}
    if how == "partition":
        result["note"] = (
            "partition nodes of one physical host; pick the node whose partitioned_slots "
            "contains the target slot and pass it to --testbed; BMC/power actions hit every node"
        )
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    sys.exit(main())
