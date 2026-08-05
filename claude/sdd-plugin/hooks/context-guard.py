#!/usr/bin/env python3
"""SDD guard: measure the orchestrator's window at every stage boundary, and
enforce the stop the config asks for.

Two modes, both registered in hooks/hooks.json:

  --post  PostToolUse(Bash) — fires only on an `sdd-state` command that SETS
          phase, i.e. exactly a stage boundary. Reads occupancy pinned to this
          session and feeds it back as additionalContext: a note, a clear-point
          recommendation, or a stop directive per config.context.
  --pre   PreToolUse(Task|Workflow) — while a stop is in force, blocks new
          agent/workflow spawns so the next stage cannot start in a window that
          was supposed to be cleared.

WHY a hook: the threshold used to live only in run.md prose, so it depended on
the orchestrator remembering to run `sdd-cost --context` at every stage_end. A
measured run reached 44% with not one occupancy figure in its log — the check
was simply never made. A hook cannot be forgotten.

The stop is cheap by construction: it happens with the NEW phase already
written to state.md, so `/clear` then `/sdd:run` resumes at exactly the stage
that was about to start. A denied spawn strands nothing — an interrupted stage
re-runs its workflow from the top (run.md, "## workflow stages").

Self-contained like require-plan-approval.py: stdlib only, and fail-open on
every unexpected path (bad json, missing sdd-cost, unreadable config). A guard
that cannot brick a session is worth more than one that catches every case.
Tested by tests/test_context_guard.py.
"""
import json
import os
import re
import subprocess
import sys

# `sdd-state set phase implement` / `sdd-state event --set phase=review ...`
# — a WRITE only; `state get phase` must not trip the boundary
PHASE_SET = re.compile(r"sdd-state\b[^|;&]*?(?:\bset\s+phase\s+|--set\s+phase=)"
                       r"([a-z_]+)")

# used when the pipeline config cannot be read — the bundled defaults
FALLBACK = {"clear_point_at_pct": 20, "hard_stop_at_pct": 35,
            "stop_at_every_stage": False, "stop_floor_pct": 8,
            "announce_clear_points": True}

# `done` has no next stage, so there is nothing a stop could save — and it is
# where /sdd:quick lands, which is a single-turn path by design
TERMINAL = ("done",)

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "bin")


def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def marker_path(session):
    return os.path.join(config_dir(), "sdd-context", f"{session}.json")


def read_marker(session):
    try:
        with open(marker_path(session)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_marker(session, data):
    try:
        os.makedirs(os.path.dirname(marker_path(session)), exist_ok=True)
        with open(marker_path(session), "w") as f:
            json.dump(data, f)
    except OSError:
        pass  # enforcement degrades to advice; never break the turn over it


def clear_marker(session):
    try:
        os.unlink(marker_path(session))
    except OSError:
        pass


def run(argv, cwd):
    """stdout of a short-lived helper, or None. never raises."""
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                           timeout=15)
        return p.stdout if p.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def occupancy(session, cwd):
    """this session's context reading, or None when it cannot be measured."""
    out = run([sys.executable, os.path.join(BIN, "sdd-cost"), "--context",
               "--json", "--session", session], cwd)
    try:
        data = json.loads(out) if out else None
    except ValueError:
        return None
    return data if isinstance(data, dict) and "pct" in data else None


def context_config(cwd):
    """config.context from the resolved pipeline (project overrides + extends),
    falling back to the bundled defaults."""
    cfg = dict(FALLBACK)
    out = run([sys.executable, os.path.join(BIN, "sdd-pipeline"),
               "--section", "config", "--json"], cwd)
    try:
        data = json.loads(out) if out else {}
    except ValueError:
        data = {}
    if isinstance(data, dict):
        block = (data.get("config") or data).get("context")
        if isinstance(block, dict):
            for k in cfg:
                if k in block:
                    cfg[k] = block[k]
    return cfg


def tok(n):
    return f"{n / 1e6:.1f}M" if n >= 1_000_000 else f"{n // 1000}k"


def figure(c):
    return (f"context {c['pct']:.0f}% ({tok(c['used'])}/{tok(c['window'])},"
            f" {c['requests']} requests)")


def verdict(c, cfg, phase):
    """(kind, message) for one boundary. kind: stop | recommend | note."""
    where = f"phase: {phase}" if phase else "this stage boundary"
    hard = cfg.get("hard_stop_at_pct") or 0
    floor = cfg.get("stop_floor_pct", 8)
    if phase in TERMINAL:
        return "note", (f"sdd context guard: {figure(c)} at {where} — nothing "
                        f"follows this phase, so no clear point is needed.")
    if cfg.get("stop_at_every_stage") and c["pct"] >= floor:
        why = "config.context.stop_at_every_stage is on"
    elif hard > 0 and c["pct"] > hard:
        why = f"{c['pct']:.0f}% is past config.context.hard_stop_at_pct ({hard})"
    else:
        why = None
    if why:
        return "stop", (
            f"sdd context guard: {figure(c)} — STOP HERE, {why}. {where} is "
            f"already written to state.md, so `/clear` then `/sdd:run` resumes "
            f"at exactly this stage and loses nothing. Log a `stop` event "
            f"naming the resume phase, end the turn with the resume "
            f"instruction, and start no further work — new Task/Workflow "
            f"spawns are blocked until the window is cleared.")
    if c["pct"] >= cfg.get("clear_point_at_pct", 20):
        return "recommend", (
            f"sdd context guard: {figure(c)} — at or past "
            f"config.context.clear_point_at_pct. A clear point is ADVISED "
            f"here: say so in one line with the figure, note that `/clear` "
            f"then `/sdd:run` resumes from {where}, and keep working. Do not "
            f"stop and do not ask.")
    return "note", (
        f"sdd context guard: {figure(c)} — healthy. The run is safely "
        f"resumable from {where}; mention that in one line at this boundary "
        f"and move on.")


def post(data):
    """(exit, stdout_json) for a PostToolUse call."""
    if (data.get("tool_name") or "") != "Bash":
        return 0, None
    command = (data.get("tool_input") or {}).get("command") or ""
    m = PHASE_SET.search(command)
    if not m:
        return 0, None
    session = data.get("session_id") or ""
    cwd = data.get("cwd") or os.getcwd()
    c = occupancy(session, cwd)
    if not c:
        return 0, None  # unmeasurable: say nothing rather than guess
    cfg = context_config(cwd)
    kind, message = verdict(c, cfg, m.group(1))
    if kind == "stop":
        write_marker(session, {"kind": "stop", "used": c["used"],
                               "pct": c["pct"], "phase": m.group(1),
                               "limit": cfg.get("hard_stop_at_pct") or 0,
                               "every_stage": bool(cfg.get("stop_at_every_stage"))})
    else:
        clear_marker(session)
    if kind == "note" and not cfg.get("announce_clear_points", True):
        return 0, None
    out = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                  "additionalContext": message}}
    if kind != "note":
        out["systemMessage"] = message.split(" — ", 1)[0] + f" — {kind}"
    return 0, out


def still_stopped(mark, c):
    """does the stop the marker recorded still apply?

    a /clear keeps the session id (one transcript holds several context
    lifetimes), so the marker cannot be trusted on its own — the drop in
    occupancy is the evidence that the clear point was actually taken. Within a
    turn the window only grows, so the stop holds until then. The 10% slack
    matches cost.context_lifetimes' reset heuristic.
    """
    if c is None:
        return True  # measured once, unmeasurable now: keep the stop
    if c["used"] < mark.get("used", 0) * 0.9:
        return False
    if mark.get("every_stage"):
        return True  # not a threshold at all — only a fresh window lifts it
    limit = mark.get("limit") or 0
    return limit <= 0 or c["pct"] > limit


def pre(data):
    """(exit, stderr_message) for a PreToolUse call."""
    session = data.get("session_id") or ""
    mark = read_marker(session)
    if not mark:
        return 0, None  # the common case pays nothing: no marker, no subprocess
    c = occupancy(session, data.get("cwd") or os.getcwd())
    if not still_stopped(mark, c):
        clear_marker(session)
        return 0, None
    now = figure(c) if c else f"context {mark.get('pct', 0):.0f}%"
    why = ("config.context.stop_at_every_stage" if mark.get("every_stage")
           else f"config.context.hard_stop_at_pct ({mark.get('limit')})")
    return 2, (
        f"SDD context guard: {now} — this run stopped at the "
        f"{mark.get('phase') or 'stage'} boundary per {why}, so no new agent "
        f"or workflow may start in this window. End the turn with the resume "
        f"instruction: `/clear`, then `/sdd:run` picks up at phase "
        f"{mark.get('phase') or 'the recorded phase'}. Nothing is lost and "
        f"nothing needs re-doing first.")


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # fail open: never brick a session on malformed input
    try:
        if "--pre" in sys.argv:
            code, message = pre(data)
            if message:
                print(message, file=sys.stderr)
            return code
        code, out = post(data)
        if out:
            print(json.dumps(out))
        return code
    except Exception:  # noqa: BLE001 — a guard must not be the thing that fails
        return 0


if __name__ == "__main__":
    sys.exit(main())
