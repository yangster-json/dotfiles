#!/usr/bin/env python3
"""SDD output diet: strip waste from a tool result BEFORE it enters the window.

Two reductions, both on PostToolUse (registered in hooks/hooks.json):

  dedupe  a Read/Bash/Grep call whose input AND output are byte-identical to an
          earlier call in this session is replaced by a one-line pointer. the
          content is already in context; a second copy buys nothing and is then
          re-sent on every subsequent request.
  shrink  a large output from a known-noisy command (test runners, builds, git
          status/diff, log dumps) keeps its head, its tail, and every signal
          line; the rest is elided with a note saying how to get it back.

WHY a hook rather than an instruction: this mirrors what the context guard
already learned the hard way. CLAUDE.md tells the model "before re-reading a
file you have already read this session, ask whether anything changed it" —
prose it is free to skip, and does. AgentDiet (arXiv 2509.23586) found the same
thing from the other end: given an explicit erase tool, agents essentially never
used it, so reduction has to be invoked externally. Its three waste classes are
useless / redundant / expired; dedupe covers redundant, shrink covers useless,
and clear points (hooks/context-guard.py) already cover expired.

WHY it is safe to hide a result:
  - dedupe fires only on an EXACT output match, so changed content is never
    hidden — a re-read after an edit passes straight through.
  - asking twice in a row for the same key serves the full output. if the
    window was cleared and the pointer now points at nothing, the escape
    hatch costs one extra tool call, not a wrong answer.
  - shrink never touches a command outside config.diet.shrink_commands.

WHY thresholds: AgentDiet only reflects on steps over ~500 tokens and only
applies a reduction that saves more than that, so the mechanism cannot cost
more than it returns. Same rule here, and no model is invoked at all — both
passes are deterministic, which is why the overhead is one interpreter start.

Self-contained like context-guard.py: stdlib only, fail-open on every
unexpected path. The resolved config is cached in the session ledger so only
the first tool call of a session pays a subprocess. Tested by
tests/test_output_diet.py.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

# commands whose bulk is boilerplate around a few signal lines. anything not
# matching here is passed through untouched — shrink is opt-in by pattern
# because a `cat`/`sed` of a specific file is usually bulk the model ASKED for.
SHRINK_COMMANDS = [
    r"\b(pytest|ctest|unittest|tox|nosetests)\b",
    r"\b(make|ninja|cmake|scons|bazel)\b",
    r"\bgit\s+(status|diff|log|show)\b",
    r"\b(npm|yarn|pnpm)\s+(test|run)\b",
    r"\bcargo\s+(test|build|clippy)\b",
    r"_debug_dump\.log\b",
    r"\b(dmesg|journalctl)\b",
]

# lines worth keeping out of a middle that is otherwise elided
SIGNAL = re.compile(
    r"\b(error|errors|fail|failed|failure|assert|assertion|panic|fatal|"
    r"watchdog|traceback|exception|warning|warn|timeout|timed out|"
    r"segfault|core dump|abort)\b", re.I)

FALLBACK = {
    "enabled": True,
    "min_tokens": 500,        # AgentDiet's theta: below this, do nothing
    "dedupe": True,
    "shrink": True,
    "head_lines": 40,
    "tail_lines": 60,
    "max_signal_lines": 80,
    "shrink_commands": SHRINK_COMMANDS,
    "ledger_entries": 400,
}

# only these results are ever rewritten. an Edit/Write result also carries a
# `content` key, and hiding one would hide the model's own diff — so the tool
# list is explicit here as well as in the hooks.json matcher.
TARGET_TOOLS = ("Bash", "Read", "Grep", "Glob")

# where a tool result's text actually lives. verified against real transcripts:
# Bash is {stdout, stderr, ...}, Read is {type, file: {content, ...}}. a shape
# not listed here is passed through rather than guessed at.
TEXT_KEYS = ("stdout", "content", "output", "text", "result")
NESTED_KEYS = ("file", "data")

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "bin")


def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def ledger_path(session):
    return os.path.join(config_dir(), "sdd-diet", f"{session}.json")


def read_ledger(session):
    try:
        with open(ledger_path(session)) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_ledger(session, data):
    try:
        os.makedirs(os.path.dirname(ledger_path(session)), exist_ok=True)
        with open(ledger_path(session), "w") as f:
            json.dump(data, f)
    except OSError:
        pass  # a ledger we cannot persist just means no dedupe; never fail


def diet_config(cwd, ledger):
    """config.diet from the resolved pipeline, cached in the ledger.

    the sibling guard can afford a subprocess because it runs at stage
    boundaries; this hook runs on every tool call, so the resolve happens once
    per session and is read back from the ledger after that.
    """
    cached = ledger.get("cfg")
    if isinstance(cached, dict):
        return cached
    cfg = dict(FALLBACK)
    try:
        p = subprocess.run([sys.executable, os.path.join(BIN, "sdd-pipeline"),
                            "--section", "config", "--json"],
                           cwd=cwd, capture_output=True, text=True, timeout=15)
        data = json.loads(p.stdout) if p.returncode == 0 else {}
    except (OSError, subprocess.SubprocessError, ValueError):
        data = {}
    if isinstance(data, dict):
        block = (data.get("config") or data).get("diet")
        if isinstance(block, dict):
            for k in cfg:
                if k in block:
                    cfg[k] = block[k]
    ledger["cfg"] = cfg
    return cfg


def est(text):
    return len(text) // 4  # good enough to compare against a threshold


def tok(n):
    return f"{n / 1000:.0f}k" if n >= 1000 else str(n)


def text_of(response):
    """(text, where) for a tool response, or (None, None).

    `where` is the key path the text came from, for the tests and for anyone
    reading a systemMessage; None when the response was already a bare string.
    """
    if isinstance(response, str):
        return response, None
    if not isinstance(response, dict):
        return None, None
    for k in TEXT_KEYS:
        v = response.get(k)
        if isinstance(v, str) and v:
            return v, k
    for outer in NESTED_KEYS:      # Read hides its body one level down
        inner = response.get(outer)
        if isinstance(inner, dict):
            for k in TEXT_KEYS:
                v = inner.get(k)
                if isinstance(v, str) and v:
                    return v, f"{outer}.{k}"
    return None, None


def key_of(tool, tool_input, cwd):
    """stable identity for "the same call again" — same tool, same arguments,
    same directory."""
    blob = json.dumps({"t": tool, "i": tool_input, "c": cwd}, sort_keys=True,
                      default=str)
    return hashlib.sha256(blob.encode("utf-8", "replace")).hexdigest()[:16]


def digest(text):
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


def pointer(tool, prior, text):
    return (f"[sdd diet] identical to the earlier {tool} result for these exact "
            f"arguments at step {prior['step']} — {len(text.splitlines())} "
            f"lines, ~{tok(est(text))} tokens, already in this context and "
            f"unchanged since. nothing was re-sent. if that content is NOT in "
            f"the window (it was cleared), run the same call again and the full "
            f"output comes back.")


def dedupe(tool, text, key, ledger, cfg):
    """the pointer to send instead of `text`, or None to pass it through.

    an exact-match-only rule: `seen` holds the output digest, so an edited file
    or a command with new output never hits this path. asking twice in a row
    serves the real thing — that is the recovery path when the window no longer
    holds what the pointer names.
    """
    seen = ledger.setdefault("seen", {})
    prior = seen.get(key)
    step = ledger.get("step", 0)
    if not prior or prior.get("hash") != digest(text):
        seen[key] = {"hash": digest(text), "step": step, "asks": 0}
        return None
    prior["asks"] = prior.get("asks", 0) + 1
    if prior["asks"] > 1:
        prior["asks"] = 0   # second ask in a row: it really wants the content
        return None
    return pointer(tool, prior, text)


def shrink(command, text, cfg):
    """the trimmed output, or None to pass it through."""
    if not any(re.search(p, command, re.I) for p in cfg["shrink_commands"]):
        return None
    lines = text.splitlines()
    head, tail = int(cfg["head_lines"]), int(cfg["tail_lines"])
    if len(lines) <= head + tail + 10:
        return None  # nothing meaningful to elide
    middle = lines[head:len(lines) - tail]
    signal = [(i + head, ln) for i, ln in enumerate(middle) if SIGNAL.search(ln)]
    dropped = len(middle) - len(signal)
    kept = [f"[sdd diet] {dropped} of {len(lines)} lines elided from the middle "
            f"of this output; head, tail and every error/fail/warn line are "
            f"kept. re-run with a grep or a tail to see the rest."]
    kept += lines[:head]
    if signal:
        kept.append(f"--- {len(signal)} signal lines from the elided middle ---")
        for n, ln in signal[:int(cfg["max_signal_lines"])]:
            kept.append(f"{n + 1}: {ln}")
        if len(signal) > int(cfg["max_signal_lines"]):
            kept.append(f"--- {len(signal) - int(cfg['max_signal_lines'])} more "
                        f"signal lines not shown ---")
    kept.append(f"--- last {tail} lines ---")
    kept += lines[len(lines) - tail:]
    return "\n".join(kept)


def reduce_text(tool, command, text, key, ledger, cfg):
    """(new_text, which) for one result, or (None, None) to leave it alone."""
    if cfg.get("dedupe", True):
        out = dedupe(tool, text, key, ledger, cfg)
        if out:
            return out, "dedupe"
    if cfg.get("shrink", True) and command:
        out = shrink(command, text, cfg)
        # the second half of AgentDiet's threshold rule: a reduction that does
        # not clear theta is not worth the confusion it causes
        if out and est(text) - est(out) > int(cfg["min_tokens"]):
            return out, "shrink"
    return None, None


def post(data):
    """(exit, stdout_json) for a PostToolUse call."""
    tool = data.get("tool_name") or ""
    session = data.get("session_id") or ""
    if tool not in TARGET_TOOLS or not session:
        return 0, None
    text, _where = text_of(data.get("tool_response"))
    if not text:
        return 0, None  # unrecognized shape: pass through rather than guess
    ledger = read_ledger(session)
    cfg = diet_config(data.get("cwd") or os.getcwd(), ledger)
    if not cfg.get("enabled", True):
        return 0, None
    if est(text) < int(cfg["min_tokens"]):
        return 0, None  # small results are not where the waste is
    cwd = data.get("cwd") or ""
    tool_input = data.get("tool_input") or {}
    command = tool_input.get("command") or tool_input.get("file_path") or ""
    ledger["step"] = ledger.get("step", 0) + 1
    new, which = reduce_text(tool, command, text, key_of(tool, tool_input, cwd),
                             ledger, cfg)
    prune(ledger, int(cfg["ledger_entries"]))
    write_ledger(session, ledger)
    if not new:
        return 0, None
    saved = est(text) - est(new)
    return 0, {
        "hookSpecificOutput": {"hookEventName": "PostToolUse",
                               "updatedToolOutput": new},
        "systemMessage": f"sdd diet: {which} on {tool} — ~{tok(saved)} tokens "
                         f"kept out of the window",
    }


def prune(ledger, limit):
    """keep the ledger bounded — oldest keys go first."""
    seen = ledger.get("seen") or {}
    if len(seen) <= limit:
        return
    for key in sorted(seen, key=lambda k: seen[k].get("step", 0))[:len(seen) - limit]:
        seen.pop(key, None)


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # fail open: never brick a session on malformed input
    try:
        code, out = post(data)
        if out:
            print(json.dumps(out))
        return code
    except Exception:  # noqa: BLE001 — a diet must not be the thing that fails
        return 0


if __name__ == "__main__":
    sys.exit(main())
