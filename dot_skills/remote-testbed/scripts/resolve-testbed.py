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
SENSITIVE_TEXT = re.compile(
    r"((?:pass(?:word|phrase)?|secret|token|(?:api|ssh|private)[ _-]?key|"
    r"cred(?:ential)?s?|auth(?:orization)?|cookie)\s*[:=]\s*(?:bearer\s+)?|bearer\s+)"
    r"[^\s,;]+",
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
    for candidate in candidates:
        node = get_node(candidate)
        if node:
            return [node], "direct"

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


def summarize(node):
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
    return {
        "ras_name": node.get("name"),
        "physical_hosts": hosts,
        "controller_count": len(hosts),
        "hyperscaler_host": bool(node.get("hm_computenode")),
        "jump_host": env.get("JUMP_HOST"),
        "partitioned_slots": env.get("PARTITIONED_SLOTS"),
        "testlauncher_profile": env.get("TESTLAUNCHER_PROFILE"),
        "shared_testbed": bool(tags & SHARED_LABELS) or claim.get("claimant") == "shared_testbed",
        "claimant": claim.get("claimant"),
        "claim_msg": claim.get("claim_msg"),
        "status": node.get("status"),
        "platform_labels": sorted(t for t in tags if re.match(
            r"flashblade|wssd_legend|hyper(scale)?:|split_node|has_two_controllers|encltype:|shared", t)),
        "env": env,
        "notes": redact_text((notes or "")[:600]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("testbed")
    parser.add_argument("--json", action="store_true", help="print raw RAS records (may contain credentials)")
    args = parser.parse_args()

    try:
        nodes, how = lookup(args.testbed)
    except URLError as error:
        raise SystemExit(f"RAS unreachable ({error}); see fallbacks.md and confirm topology with the user")

    if not nodes:
        raise SystemExit(
            f"RAS target not found: {args.testbed} (tried <name>, lp-<name>, lp-<name>-node0..{MAX_NODES - 1}); "
            "see fallbacks.md, get topology from the user, and use testlauncher --server <host>"
        )

    if args.json:
        print(json.dumps(nodes, indent=2, sort_keys=True))
        return

    result = {"requested": args.testbed, "match": how, "records": [summarize(n) for n in nodes]}
    if how == "partition":
        result["note"] = (
            "partition nodes of one physical host; pick the node whose partitioned_slots "
            "contains the target slot and pass it to --testbed"
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    sys.exit(main())
