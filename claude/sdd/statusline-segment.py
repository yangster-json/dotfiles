#!/usr/bin/env python3
"""sdd statusline segment.

invoked by ~/.claude/sdd/statusline.sh, which appends this segment to
the base statusline (statusline-command.py). prints the sdd progress segment
when the project has an active sdd feature, nothing otherwise — cost display
is the base statusline's job.

side job: caches claude code's as-billed session totals into
<project>/.claude/.cost-actuals.json, which ~/.claude/sdd/cost uses to
auto-calibrate its estimates. only caches into projects that already have a
.claude/ or specs/ directory, so it never litters unrelated repos.
"""
import json
import os
import re
import sys
import time

DIM, BLD, RST = "\033[2m", "\033[1m", "\033[0m"
GRN, YLW, RED, CYN = "\033[32m", "\033[33m", "\033[31m", "\033[36m"
SEP = f" {DIM}│{RST} "


def field(text, key, default=""):
    m = re.search(rf"^{key}:\s*(\S+)", text, re.M)
    return m.group(1) if m else default


def task_rows(text):
    rows = []
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and re.fullmatch(r"[TFQ]\d+", cells[0]):
            rows.append({"id": cells[0], "status": cells[3]})
    return rows


def cache_actual(root, session):
    """persist claude code's as-billed session cost for sdd-cost calibration."""
    sid = session.get("session_id") or session.get("sessionId")
    usd = (session.get("cost") or {}).get("total_cost_usd")
    if not sid or not isinstance(usd, (int, float)) or usd <= 0:
        return
    claude_dir = os.path.join(root, ".claude")
    if not os.path.isdir(claude_dir):
        if not os.path.isdir(os.path.join(root, "specs")):
            return  # not an sdd-using project — don't litter it
        os.makedirs(claude_dir, exist_ok=True)
    path = os.path.join(claude_dir, ".cost-actuals.json")
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = {}
    if abs(usd - (data.get(sid) or {}).get("usd", 0)) < 0.01:
        return  # throttle: rewrite only when the total moves a cent
    data[sid] = {"usd": round(usd, 4), "ts": int(time.time())}
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

    try:
        with open(os.path.join(root, "specs", "ACTIVE")) as f:
            slug = f.read().strip()
        if slug.startswith("worktree:"):
            # feature lives in a spun-off worktree; follow the pointer
            root = os.path.join(root, slug.split(":", 1)[1].strip())
            with open(os.path.join(root, "specs", "ACTIVE")) as f:
                slug = f.read().strip()
        with open(os.path.join(root, "specs", slug, "state.md")) as f:
            text = f.read()
    except OSError:
        return  # no active sdd feature — print nothing, base line stands alone

    phase = field(text, "phase", "?")
    parts = [f"{BLD}sdd:{slug}{RST} ▸ {CYN}{phase}{RST}"]

    rows = task_rows(text)
    if rows:
        done = sum(1 for r in rows if r["status"] == "done")
        blocked = sum(1 for r in rows if r["status"] == "blocked")
        seg = f"tasks {GRN}{done}{RST}/{len(rows)}"
        if blocked:
            seg += f" ({RED}{blocked} blocked{RST})"
        parts.append(seg)

    def gate(flag):
        return f"{GRN}✔{RST}" if flag == "yes" else f"{DIM}─{RST}"

    parts.append(
        f"gates plan {gate(field(text, 'plan_approved'))} "
        f"review {gate(field(text, 'review_approved'))}"
    )

    testbed, bay = field(text, "hw_testbed"), field(text, "hw_bay")
    if testbed and testbed != "none":
        parts.append(f"hw {testbed}/{bay}")

    print(SEP.join(parts))


if __name__ == "__main__":
    main()
