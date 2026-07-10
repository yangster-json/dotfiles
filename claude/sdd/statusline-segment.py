#!/usr/bin/env python3
"""sdd statusline segment.

invoked by ~/.claude/sdd/statusline.sh, which appends this segment to
the base statusline (statusline-command.py). prints the sdd progress segment
when the project has an active sdd feature, nothing otherwise — cost display
is the base statusline's job.

side job: caches claude code's as-billed session totals into
<claude-config>/projects/<munged-root>/cost-actuals.json (NEVER inside the
project — a cache file must not dirty a repo), which ~/.claude/sdd/cost uses
to auto-calibrate its estimates.

state.md parsing lives in statelib.py (shared with watch + quality).
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import statelib as st  # noqa: E402

DIM, BLD, RST = "\033[2m", "\033[1m", "\033[0m"
GRN, YLW, RED, CYN = "\033[32m", "\033[33m", "\033[31m", "\033[36m"
SEP = f" {DIM}│{RST} "


def cache_actual(root, session):
    """persist claude code's as-billed session cost for sdd-cost calibration."""
    sid = session.get("session_id") or session.get("sessionId")
    usd = (session.get("cost") or {}).get("total_cost_usd")
    if not sid or not isinstance(usd, (int, float)) or usd <= 0:
        return
    path = st.actuals_path(root)
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = {}
    if abs(usd - (data.get(sid) or {}).get("usd", 0)) < 0.01:
        return  # throttle: rewrite only when the total moves a cent
    data[sid] = {"usd": round(usd, 4), "ts": int(time.time())}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def main():
    try:
        session = json.load(sys.stdin)
    except Exception:
        session = {}
    ws = session.get("workspace") or {}
    root = ws.get("project_dir") or ws.get("current_dir") or os.getcwd()
    try:
        cache_actual(root, session)
    except Exception:
        pass  # the statusline must never fail on cache trouble

    state = st.read_state(root)
    if not state:
        return  # no active sdd feature — print nothing, base line stands alone
    _, slug, text = state

    phase = st.field(text, "phase", "?")
    parts = [f"{BLD}sdd:{slug}{RST} ▸ {CYN}{phase}{RST}"]

    rows = st.task_rows(text)
    if rows:
        done = sum(1 for r in rows if r["status"] == "done")
        blocked = sum(1 for r in rows if r["status"] == "blocked")
        seg = f"tasks {GRN}{done}{RST}/{len(rows)}"
        if blocked:
            seg += f" ({RED}{blocked} blocked{RST})"
        parts.append(seg)

    def gate(flag):
        return f"{GRN}✔{RST}" if flag else f"{DIM}─{RST}"

    parts.append(
        f"gates plan {gate(st.flag(text, 'plan_approved'))} "
        f"review {gate(st.flag(text, 'review_approved'))}"
    )

    testbed = st.field(text, "hw_testbed")
    if testbed and testbed != "none":
        parts.append(f"hw {testbed}/{st.field(text, 'hw_bay')}")

    print(SEP.join(parts))


if __name__ == "__main__":
    main()
