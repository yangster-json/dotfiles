#!/usr/bin/env python3
"""SDD guard: block source mutations until the plan is approved.

PreToolUse hook for Edit|Write|NotebookEdit|Bash (registered in
~/.claude/settings.json). No-op when no SDD feature is active. Exit code 2
blocks the tool call and feeds stderr back to Claude as the reason.

Bash coverage is a heuristic against accidental writes (redirections, tee,
mv/rm/cp, sed -i, git apply, ...), not a sandbox: mutating commands are
blocked unless every target they touch is in an allowed area (specs/,
.claude/, /tmp, /dev, or outside the project). Read-only commands always
pass. The guard protects the process from mistakes, not from adversaries.

Self-contained on purpose (no imports beyond stdlib, no statelib): a hook
that cannot fail to import cannot brick a session. Fail-open everywhere
except a recognizably mutating Bash command whose targets can't be shown
safe. Tested by ~/.claude/sdd/tests/test_hook.py.
"""
import json
import os
import re
import sys

# anchored at line start so a log line quoting the phrase can't unlock the
# gate; tolerates markdown emphasis on the key so a restyled state.md can't
# falsely re-lock it
APPROVED = re.compile(r"^[*_]{0,2}plan_approved[*_]{0,2}\s*:\s*[*_]{0,2}yes\b",
                      re.M | re.I)

# command words that mutate the filesystem wherever they point
MUTATORS = {"tee", "mv", "rm", "cp", "dd", "truncate", "install", "patch",
            "rsync", "shred", "unlink"}
GIT_MUTATORS = {"apply", "am", "checkout", "restore", "clean", "stash"}
# sed/perl only mutate with an -i style flag
INPLACE = re.compile(r"\b(?:sed|perl)\b[^|;&]*\s-[a-zA-Z]*i")
# redirection targets: `> f`, `>> f`, `2> f` — but not fd dups like `2>&1`
REDIRECT = re.compile(r"(?<![<>])\d*>{1,2}(?!\s*&)\s*([^\s;|&<>]+)")


def _read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return None


def active_state(project):
    """(slug, state_text) for the active feature, following one
    `worktree:` pointer; None when no feature is active/readable."""
    slug = _read(os.path.join(project, "specs", "ACTIVE"))
    if slug is None:
        return None
    slug = slug.strip()
    if slug.startswith("worktree:"):
        project = os.path.join(project, slug.split(":", 1)[1].strip())
        slug = (_read(os.path.join(project, "specs", "ACTIVE")) or "").strip()
    if not slug or slug.startswith("worktree:"):
        return None
    state = _read(os.path.join(project, "specs", slug, "state.md"))
    if state is None:
        return None
    return slug, state


def path_allowed(path, project):
    """pre-approval, an in-project target is fine only under specs/ or
    .claude/; anything outside the project (/tmp, /dev/null, other repos)
    is not this guard's business."""
    if not path:
        return True
    abspath = os.path.abspath(os.path.join(project, path))
    rel = os.path.relpath(abspath, project)
    if rel.startswith(".."):
        return True
    return (rel == "specs" or rel.startswith("specs" + os.sep)
            or rel == ".claude" or rel.startswith(".claude" + os.sep))


def bash_verdict(command, project):
    """None if the command looks safe pre-approval, else a short reason."""
    for target in REDIRECT.findall(command):
        if not path_allowed(target.strip("'\""), project):
            return f"redirects into the source tree ({target})"

    words = re.findall(r"[^\s;|&()<>]+", command)
    mutator = None
    for i, w in enumerate(words):
        base = os.path.basename(w.strip("'\""))
        if base in MUTATORS:
            mutator = base
            break
        if base == "git" and i + 1 < len(words) and words[i + 1] in GIT_MUTATORS:
            mutator = f"git {words[i + 1]}"
            break
    if mutator is None and INPLACE.search(command):
        mutator = "in-place edit (-i)"
    if mutator is None:
        return None

    # a mutator is fine only if we can see targets and all are allowed
    pathish = [w.strip("'\"") for w in words
               if not w.startswith("-")
               and ("/" in w or ("." in w and len(w) > 1))
               and os.path.basename(w.strip("'\"")) not in MUTATORS
               and w != "git"]
    if pathish and all(path_allowed(p, project) for p in pathish):
        return None
    return f"`{mutator}` targets the source tree (or targets are unclear)"


def decide(data, project):
    """(exit_code, message_or_None) for one hook invocation."""
    state = active_state(project)
    if state is None:
        return 0, None
    slug, text = state
    if APPROVED.search(text):
        return 0, None

    tool = data.get("tool_name") or ""
    tool_input = data.get("tool_input") or {}

    if tool == "Bash":
        reason = bash_verdict(tool_input.get("command") or "", project)
        if reason is None:
            return 0, None
        detail = f"Blocked Bash command: {reason}."
    else:
        path = tool_input.get("file_path") or tool_input.get("notebook_path")
        if path_allowed(path, project):
            return 0, None
        detail = f"Blocked edit of {path}."

    return 2, (
        f"SDD guard: feature '{slug}' has not passed gate 1 (plan approval) "
        f"— see specs/{slug}/state.md. {detail} Source mutations are blocked "
        f"until the plan is approved at gate 1 of /sdd:run; before then only "
        f"specs/ and .claude/ may be modified."
    )


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # fail open: never brick the session on malformed input
    project = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    code, message = decide(data, project)
    if message:
        print(message, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
