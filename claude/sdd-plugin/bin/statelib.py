"""shared, format-tolerant parsing for sdd state files and paths.

used by the sdd-* CLIs (sdd-git, sdd-state, sdd-cost, sdd-quality,
sdd-status). state.md is written by an LLM orchestrator, so
nothing here may depend on exact spacing, column order, emphasis, or case —
parse by structure (headers, anchored keys), never by position.

tested by tests/test_statelib.py.
"""
import os
import re

_EMPH = re.compile(r"[*`]")

# canonical task-table column names -> the aliases an orchestrator might use
_COLUMNS = {
    "id": ("id", "task", "task id"),
    "title": ("title", "name", "description"),
    "complexity": ("complexity", "cx"),
    "status": ("status", "state"),
    "depends": ("depends_on", "depends", "deps"),
    "parallel": ("parallel_ok", "parallel"),
}
_ALIAS = {a: canon for canon, aliases in _COLUMNS.items() for a in aliases}

_TASK_ID = re.compile(r"[A-Za-z]{1,2}\d+")


def strip_md(s):
    """drop markdown emphasis and surrounding whitespace. underscores are
    only stripped at the edges — values like in_progress keep theirs."""
    return _EMPH.sub("", s).strip().strip("_")


def field(text, key, default=""):
    """value of a `key: value` line, tolerant of emphasis, a leading list
    dash, mixed case, and a trailing html comment."""
    pat = (rf"^\s*(?:-\s+)?[*_]*{re.escape(key)}[*_]*\s*:\s*"
           rf"(.*?)\s*(?:<!--.*)?$")
    m = re.search(pat, text, re.M | re.I)
    if not m:
        return default
    return strip_md(m.group(1)) or default


def flag(text, key):
    """True when a field's value starts with yes/true (any case/emphasis)."""
    return field(text, key).lower().startswith(("yes", "true"))


def sections(text):
    """map of lowercased `## heading` -> list of body lines."""
    out, name = {}, None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.*)", line)
        if m:
            name = strip_md(m.group(1)).lower()
            out[name] = []
        elif name is not None:
            out[name].append(line)
    return out


def _cells(line):
    return [strip_md(c) for c in line.strip().strip("|").split("|")]


def _is_separator(cells):
    return all(re.fullmatch(r":?-{2,}:?", c) or c == "" for c in cells)


def task_rows(text):
    """task rows as dicts keyed by canonical column names.

    finds every markdown table whose header includes both an id and a
    status column (any order, any aliases, any emphasis); other tables are
    ignored. rows whose id doesn't look like a task id (T1, F2, Q1...) are
    skipped. every returned row has at least id/title/complexity/status
    keys (missing cells default to "").
    """
    rows, header = [], None
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            header = None
            continue
        cells = _cells(line)
        if header is None:
            cols = [_ALIAS.get(c.lower().replace(" ", "_"), None)
                    for c in cells]
            header = cols if ("id" in cols and "status" in cols) else False
            continue
        if header is False or _is_separator(cells):
            continue
        row = {"id": "", "title": "", "complexity": "", "status": "",
               "depends": "", "parallel": ""}
        for col, cell in zip(header, cells):
            if col:
                row[col] = cell
        if _TASK_ID.fullmatch(row["id"]):
            rows.append(row)
    return rows


def metrics(text):
    """integer counters from the `## metrics` section, {} if absent."""
    out = {}
    for line in sections(text).get("metrics", []):
        m = re.match(r"^\s*(?:-\s+)?[*_]*([a-zA-Z][\w]*)[*_]*\s*:\s*(\d+)",
                     line)
        if m:
            out[m.group(1).lower()] = int(m.group(2))
    return out


def resolve_active(root):
    """follow specs/ACTIVE (and one `worktree:` pointer) -> (root, slug).

    returns None when there is no readable active feature.
    """
    def read_active(r):
        try:
            with open(os.path.join(r, "specs", "ACTIVE")) as f:
                return f.read().strip()
        except OSError:
            return None

    val = read_active(root)
    if not val:
        return None
    if val.startswith("worktree:"):
        root = os.path.join(root, val.split(":", 1)[1].strip())
        val = read_active(root)
        if not val or val.startswith("worktree:"):
            return None
    return root, val


def read_state(root):
    """(root, slug, state_text) for the active feature, else None."""
    resolved = resolve_active(root)
    if not resolved:
        return None
    root, slug = resolved
    try:
        with open(os.path.join(root, "specs", slug, "state.md")) as f:
            return root, slug, f.read()
    except OSError:
        return None


def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def munge(root):
    """claude code's project-directory name for a path."""
    return re.sub(r"[^a-zA-Z0-9]", "-", os.path.abspath(root))


def learnings_base():
    """root of the sdd learnings store. under the claude config dir but NOT
    inside the plugin cache (wiped on /plugin update) or the old ~/.claude/sdd
    install — so lessons persist across plugin updates and installs."""
    return os.path.join(config_dir(), "sdd-learnings")


def project_learnings_path(root):
    """this project's sdd learnings directory — under learnings_base(), keyed
    by the project's own identity (munged absolute path), NOT inside the
    project itself — the never-dirties-a-repo convention, so sdd "connects" a
    learnings bucket to its repo without ever writing into that repo's working
    tree."""
    return os.path.join(learnings_base(), munge(root))


def global_learnings_path():
    """the cross-project (global-scope) learnings directory — a fixed bucket
    under learnings_base(), shared by every project on this machine."""
    return os.path.join(learnings_base(), "_global")
