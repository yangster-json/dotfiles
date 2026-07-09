#!/usr/bin/env python3
"""SDD guard: block source edits until the plan is approved.

PreToolUse hook for Edit|Write|NotebookEdit (see .claude/settings.json).
No-op when no SDD feature is active. Exit code 2 blocks the tool call and
feeds stderr back to Claude as the reason.
"""
import json
import os
import sys


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # fail open: never brick the session on malformed input

    path = (data.get("tool_input") or {}).get("file_path") or ""
    project = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

    active_file = os.path.join(project, "specs", "ACTIVE")
    if not os.path.isfile(active_file):
        return 0  # no SDD feature in progress — allow everything

    with open(active_file) as f:
        slug = f.read().strip()
    state_file = os.path.join(project, "specs", slug, "state.md")
    if not os.path.isfile(state_file):
        return 0

    with open(state_file) as f:
        state = f.read()
    if "plan_approved: yes" in state:
        return 0

    # Pre-approval: only specs/ and .claude/ are editable inside the project.
    if not path:
        return 0
    rel = os.path.relpath(os.path.abspath(path), project)
    if rel.startswith("..") or rel.startswith("specs" + os.sep) or rel.startswith(".claude" + os.sep):
        return 0

    print(
        f"SDD guard: the plan for feature '{slug}' is not approved yet "
        f"(see specs/{slug}/state.md). Source edits are blocked until "
        f"/sdd:plan is run and approved. Only specs/ and .claude/ may be "
        f"edited before then.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
