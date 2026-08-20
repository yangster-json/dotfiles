"""read the subagent transcripts claude code writes, so a run can be watched.

state.md's `## log` is written by the orchestrator BETWEEN spawns, so it says
"3 reviewers dispatched" and, much later, what came back — never what any one
of them is doing right now. Claude Code itself keeps that, one file per
subagent, appended as the agent works:

  <config>/projects/<munged-cwd>/<session>/subagents/agent-<id>.jsonl
  <config>/projects/<munged-cwd>/<session>/subagents/agent-<id>.meta.json

An agent spawned from inside a Workflow script lands one level deeper, under
`subagents/workflows/wf_<run>/`, with the run's `journal.jsonl` beside it —
the implement, review and research stages all run that way, so both layouts
have to be read or a run reads as having stalled at the last stage that used
the Task tool.

The jsonl is the agent's turns (every tool call, with its input); the meta
sidecar names the agent type, the spawn description and the model. Both are
claude code's — nothing here writes, and nothing here may depend on a record
carrying any particular field: a transcript format that gains or drops keys
must degrade to a thinner row, never an exception.

DISCOVERY is by directory, ATTRIBUTION is by prompt, and the two must not be
confused. A transcript is filed under the ORCHESTRATOR's project dir: sdd runs
implementers in worktrees, so one feature's agents are spread over the repo's
own dir plus one per worktree (`project_dirs()` covers them by munged prefix,
then each agent is checked against its own recorded `cwd`, because a sibling
`master-2` shares `master`'s prefix). But which FEATURE an agent belongs to
comes from its spawn prompt, never from `cwd`/`gitBranch` — those describe the
session, and a run with no worktree sits on whatever branch it started on while
a run driving a worktree in another repo records that other repo entirely.
`agents()` widens the scan to every project dir when this repo's hold none of
the named feature's agents, for exactly that last case.

reading is INCREMENTAL: each file is re-read from the byte offset the last pass
stopped at, so an 8 fps pane costs one short read per agent per frame instead of
re-parsing half a megabyte of tool results. used by sdd-agents and sdd-status's
`a` pane; tested by tests/test_agents.py.
"""
import glob
import json
import os
import re
import time
from collections import deque
from datetime import datetime

import statelib as st

# no new record for this long and a still-unfinished agent has stopped being
# live — a spinner on a dead agent is the one thing a live pane must not show.
# past ABANDONED it is not "quiet" any more, it never finished: killed with its
# session, or the run was interrupted. the two read differently in a history
# view, where every unfinished agent would otherwise be flagged as if it might
# still come back.
STALE_SECONDS = 90
ABANDONED_SECONDS = 1800

# how long a soft end (see `_absorb`) must hold before it counts as done. a
# streamed turn is split across records that SHARE a requestId — a text block
# flushed on its own, then the tool call — so a text-only record is not proof
# the agent has stopped, only that it has said something. measured gaps between
# the halves of a split run to 33s, so a grace comfortably past that turns the
# ambiguous case into a wait rather than a wrong "done".
SPLIT_GRACE = 60

# events kept per agent. the whole point is the recent past, and an implementer
# can run hundreds of tool calls — enough for the detail view, bounded for the
# --follow case that never exits.
MAX_EVENTS = 400

# the input field worth showing for a tool call, in preference order
ARG_KEYS = ("command", "file_path", "pattern", "path", "url", "notebook_path",
            "description", "prompt")

_TASK = re.compile(r"\btask\s+([A-Za-z]{1,2}\d+)\b", re.I)
_WS = re.compile(r"\s+")

# which feature an agent is working on, in falling order of certainty. it is
# read from the SPAWN PROMPT, never from the record's `cwd`/`gitBranch`: those
# describe the orchestrator's session, and an sdd run whose worktree lives in
# another repo (or which runs with no worktree at all, on a branch named after
# something else entirely) records a cwd and a branch that have nothing to do
# with the feature. the prompt always names it — most stages open with a
# `slug:` line, and every one of them cites a specs/<slug>/ path.
SLUG_SOURCES = (re.compile(r"^\s*slug\s*:\s*([\w.-]+)", re.M),
                re.compile(r"^\s*workdir\s*:\s*\S*?worktrees/sdd/([\w.-]+)",
                           re.M),
                re.compile(r"worktrees/sdd/([\w.-]+)"),
                re.compile(r"\bfeature\s+[`'\"]([\w.-]+)[`'\"]"),
                re.compile(r"\bspecs/([\w.-]+)/"))

_WORKDIR = re.compile(r"^\s*(?:workdir|worktree)\s*:\s*(\S+)", re.M | re.I)

# the workflow stages hand their agents a one-line json contract instead of the
# `key: value` header the directly-spawned stages use:
#   inputs: {"workdir":"…/worktrees/sdd/<slug>-T1","subspec":"specs/<slug>/…"}
# it is the only place an implementer's workdir appears, and without it every
# path in the pane keeps its 60-column worktree prefix.
_INPUTS = re.compile(r"^\s*inputs\s*:\s*(\{.*\})\s*$", re.M)

# a workflow agent's meta sidecar carries its type and model but no spawn
# description, so the `what` column is empty for every stage that fans out —
# six identical `reviewer —` rows say nothing about which is which. the prompt
# does: an `inputs:` key, or the angle a scout was handed.
DESC_KEYS = ("stance", "angle", "title")
_ANGLE = re.compile(r"^\s*your one research angle\s*:\s*(.+)$", re.M)

# a per-task worktree is `<slug>-<task>` (sdd-git wt_path), so a slug read off
# a worktree path carries the task id and matches no feature by that name —
# every implementer and verifier of a run drops out of a `--slug` view.
_WT_TASK = re.compile(r"-([A-Za-z]{1,2}\d+)$")

# `specs/<slug>/tasks/<id>.md` — the subspec names the task it covers
_SUBSPEC_TASK = re.compile(r"/tasks/([A-Za-z]{1,2}\d+)\b")

# `specs/` entries that are not a feature directory, so a prompt citing one of
# them is not thereby claiming a slug
NOT_SLUGS = {"templates", "base", "ACTIVE"}


# ---- discovery -------------------------------------------------------------

def project_dirs(root):
    """claude code project dirs that could hold this repo's agents.

    the munged path of a worktree under `root` starts with the munged path of
    `root`, so one prefix glob covers the repo and every worktree — and also
    any sibling whose name extends it, which `agents()` filters out by cwd.
    """
    pat = st.munge(root) + "*"
    return sorted(d for d in glob.glob(os.path.join(st.config_dir(),
                                                    "projects", pat))
                  if os.path.isdir(d))


def all_project_dirs():
    """every project dir claude code has. the widened scan (see `agents`)."""
    base = os.path.join(st.config_dir(), "projects")
    return sorted(d for d in glob.glob(os.path.join(base, "*"))
                  if os.path.isdir(d))


def agent_paths(dirs):
    """every subagent transcript under those dirs, oldest write first.

    TWO layouts, because sdd spawns agents two ways. an agent spawned by the
    Task/Agent tool lands directly in `<session>/subagents/`; an agent spawned
    from inside a Workflow script lands one level deeper, in
    `<session>/subagents/workflows/wf_<run>/`. the implement, review and
    research stages all run as workflows, so globbing only the flat layout
    shows the spec and plan agents and then nothing — a run reads as having
    stalled at the plan while three reviewers are working.

    resolved through realpath and deduped: claude code SYMLINKS an agent's
    transcript into a second session's dir when the agent is handed on, and the
    same agent listed twice reads as two agents doing identical work.
    """
    out = set()
    for pdir in dirs:
        for parts in (("*", "subagents", "agent-*.jsonl"),
                      ("*", "subagents", "workflows", "*", "agent-*.jsonl")):
            for path in glob.glob(os.path.join(pdir, *parts)):
                out.add(os.path.realpath(path))
    return sorted(out, key=lambda p: (mtime(p), p))


def mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


# ---- one agent -------------------------------------------------------------

_cache = {}

# one workflow run's journal, per wf_ dir: {"offset": bytes read, "done":
# {agent id: result}}. read incrementally, exactly like a transcript.
_journals = {}


def reset():
    """drop every cached read. for the tests, and for a caller that has just
    moved the config dir under itself."""
    _cache.clear()
    _journals.clear()


def _journal(wf):
    """{agent id: returned result} for the workflow run in directory `wf`."""
    j = _journals.setdefault(wf, {"offset": 0, "done": {}})
    path = os.path.join(wf, "journal.jsonl")
    try:
        size = os.path.getsize(path)
    except OSError:
        return j["done"]
    if size < j["offset"]:                 # rewritten under us
        j["offset"], j["done"] = 0, {}
    if size == j["offset"]:
        return j["done"]
    try:
        with open(path, "rb") as f:
            f.seek(j["offset"])
            chunk = f.read()
    except OSError:
        return j["done"]
    parts = chunk.split(b"\n")
    j["offset"] += len(chunk) - len(parts[-1])
    for raw in parts[:-1]:
        if not raw.strip():
            continue
        try:
            rec = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("type") == "result" \
                and rec.get("agentId"):
            j["done"][rec["agentId"]] = str(rec.get("result") or "")
    return j["done"]


def _blank(path):
    return {"path": path, "id": os.path.basename(path)[6:-6], "type": "",
            "desc": "", "model": "", "cwd": "", "workdir": "", "branch": "",
            "slug": "", "task": "", "prompt": "", "final": "",
            "started": "", "last": "",
            "turns": 0, "tools": 0, "errors": 0, "ended": False,
            "closed": False,
            "events": deque(maxlen=MAX_EVENTS), "offset": 0, "size": 0,
            "pending": {}, "seq": 0}


def _meta(agent):
    """the sidecar: agent type, spawn description, model. absent for an agent
    still being set up, so its absence is never an error."""
    try:
        with open(agent["path"][:-6] + ".meta.json") as f:
            m = json.load(f)
    except (OSError, ValueError):
        return
    if isinstance(m, dict):
        agent["type"] = m.get("agentType") or agent["type"]
        agent["desc"] = m.get("description") or agent["desc"]
        agent["model"] = m.get("model") or agent["model"]


def read(path):
    """the agent at `path`, parsed from wherever the last read stopped.

    returns None only when the file cannot be read at all. a truncated final
    line (the file is being appended to as we read) is left for the next call.
    """
    agent = _cache.get(path)
    try:
        size = os.path.getsize(path)
    except OSError:
        return agent
    if agent is None or size < agent["offset"]:
        agent = _cache[path] = _blank(path)   # new, or rotated under us
        _meta(agent)
    if size == agent["offset"]:
        # the journal is still worth a look: an agent that has stopped writing
        # is exactly the one whose result is about to be recorded
        _returned(agent)
        return agent
    try:
        with open(path, "rb") as f:
            f.seek(agent["offset"])
            chunk = f.read()
    except OSError:
        return agent
    parts = chunk.split(b"\n")
    agent["offset"] += len(chunk) - len(parts[-1])
    agent["size"] = size
    if not agent["type"] or not agent["desc"]:
        _meta(agent)                          # sidecar may land after line 1
    for raw in parts[:-1]:
        if not raw.strip():
            continue
        try:
            _absorb(agent, json.loads(raw.decode("utf-8", "replace")))
        except ValueError:
            continue
    _returned(agent)
    return agent


def _returned(agent, wf=None):
    """a workflow agent's end, taken from the run's journal rather than guessed.

    an agent the workflow gave a schema to answers by CALLING StructuredOutput,
    so its transcript ends on a tool call and none of the transcript's own
    end-of-turn signals ever fire — three reviewers that had returned their
    findings read as `stale` and then `gone`. the journal next to them records a
    `result` per agent id when it hands its value back, which is the fact
    itself. absent or unparseable, the transcript heuristics stand.
    """
    wf = os.path.dirname(agent["path"]) if wf is None else wf
    if os.path.basename(os.path.dirname(wf)) != "workflows":
        return
    result = _journal(wf).get(agent["id"])
    if result is None:
        return
    agent["ended"] = True
    agent["final"] = agent["final"] or _gist(result)


def _absorb(agent, rec):
    """fold one transcript record into the agent's running summary."""
    ts = rec.get("timestamp") or ""
    if ts:
        agent["last"] = ts
        agent["started"] = agent["started"] or ts
    for key, field in (("cwd", "cwd"), ("branch", "gitBranch"),
                       ("type", "attributionAgent"), ("id", "agentId")):
        agent[key] = rec.get(field) or agent[key]
    msg = rec.get("message") or {}
    body = msg.get("content")
    kind = rec.get("type")

    if kind == "user":
        # the spawn prompt is the one string-bodied user record; everything
        # after it is a list of tool results
        if isinstance(body, str):
            if not agent["prompt"]:
                agent["prompt"] = body
                _identify(agent)
            return
        for block in body if isinstance(body, list) else []:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                _result(agent, block)
        return

    if kind != "assistant":
        return
    agent["turns"] += 1
    # end_turn is re-read every assistant record, not latched: a resumed agent
    # that ends a turn and then keeps working is running again
    agent["ended"] = msg.get("stop_reason") == "end_turn"
    said, called = [], False
    for block in body if isinstance(body, list) else []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_use":
            called = True
            agent["tools"] += 1
            ev = _event(agent, ts, "tool", block.get("name") or "?",
                        _arg(block.get("input"), agent))
            if block.get("id"):
                agent["pending"][block["id"]] = ev
        elif block.get("type") == "text":
            text = (block.get("text") or "").strip()
            if text:
                said.append(text)
                _event(agent, ts, "say", "", _line(text))
    # a SOFT end: it spoke and called nothing, so as far as this record goes it
    # has handed its answer back. claude code does not always stamp the last
    # record of a finished agent with a stop_reason — a 37-minute planner that
    # returned its summary was reading as `gone` on stop_reason alone — but a
    # mid-turn streaming flush looks identical, so `status` holds it for
    # SPLIT_GRACE. re-read per record like `ended`, never latched.
    agent["closed"] = bool(said) and not called
    if (agent["ended"] or agent["closed"]) and said:
        agent["final"] = _gist(said[-1])


def _result(agent, block):
    """a failed tool call is marked on the call itself, so the timeline shows
    the command once with a ✗ rather than the command and then an error row."""
    if not block.get("is_error"):
        return
    agent["errors"] += 1
    ev = agent["pending"].pop(block.get("tool_use_id"), None)
    if ev is not None:
        ev["err"] = True


def _event(agent, ts, kind, name, arg):
    # seq never resets and outlives eviction from the deque, so --follow can
    # ask "anything past what I have shown?" without keeping the events itself
    agent["seq"] += 1
    ev = {"seq": agent["seq"], "ts": ts, "kind": kind, "name": name,
          "arg": arg, "err": False, "agent": agent}
    agent["events"].append(ev)
    return ev


def _identify(agent):
    """task id, feature slug and workdir, all from the spawn prompt."""
    contract = _inputs(agent)            # the workflow stages' json contract
    if not agent["workdir"]:
        m = _WORKDIR.search(agent["prompt"])
        if m:
            agent["workdir"] = m.group(1).rstrip("/")
    if not agent["desc"]:
        m = _ANGLE.search(agent["prompt"])
        if m:
            agent["desc"] = _line(m.group(1))
    if not agent["task"] and not contract:
        # prose, and only where there is no contract to contradict: a
        # combat-round reviewer is handed no task, and the findings quoted into
        # its prompt would otherwise put a stray `F2` in its task column
        m = _TASK.search(agent["prompt"]) or _TASK.search(agent["desc"])
        if m:
            agent["task"] = m.group(1).upper()
    if agent["slug"]:
        return
    for pattern in SLUG_SOURCES:
        for m in pattern.finditer(agent["prompt"]):
            slug, task = _split_task(m.group(1))
            if slug not in NOT_SLUGS:
                agent["slug"] = slug
                agent["task"] = agent["task"] or task
                return


def _inputs(agent):
    """workdir, slug, task and description out of the `inputs: {…}` line.

    returns whether the prompt carries such a contract at all — a stage that
    states its inputs has stated all of them, so nothing read out of the
    surrounding prose may override what is missing from them.
    """
    m = _INPUTS.search(agent["prompt"])
    if not m:
        return False
    try:
        inp = json.loads(m.group(1))
    except ValueError:
        return True
    if not isinstance(inp, dict):
        return True
    for key, field in (("workdir", "workdir"), ("slug", "slug")):
        val = inp.get(field)
        if isinstance(val, str) and val.strip():
            agent[key] = val.strip().rstrip("/")
    subspec = inp.get("subspec")
    if isinstance(subspec, str):
        found = _SUBSPEC_TASK.search(subspec)
        if found:
            agent["task"] = found.group(1).upper()
    for key in DESC_KEYS:
        val = inp.get(key)
        if not agent["desc"] and isinstance(val, str) and val.strip():
            agent["desc"] = _line(val)
    return True


def _split_task(name):
    """`feat-T3` -> ("feat", "T3"); anything else -> (name, "")."""
    m = _WT_TASK.search(name)
    if not m:
        return name, ""
    return name[:m.start()], m.group(1).upper()


def _line(text):
    """the first line of a block of prose, whitespace collapsed."""
    for line in text.splitlines():
        line = _WS.sub(" ", line).strip()
        if line:
            return line
    return ""


def _gist(text):
    """the line of a returned message that actually says something. an agent
    that signs off with a bare `## Findings` heading has told a pane nothing,
    so markdown scaffolding is skipped in favour of the first real sentence."""
    for line in text.splitlines():
        line = _WS.sub(" ", line).strip()
        if not line or line.startswith(("#", "```", "---", "|", "===")):
            continue
        return line.lstrip("-*> ").strip() or line
    return _line(text)


def clip(text, width):
    """truncate visibly — a hard cut reads as the agent's real name."""
    return text if len(text) <= width else text[:max(1, width - 1)] + "…"


def _arg(inp, agent):
    """the one field of a tool input worth a single line, with the directory the
    agent works in stripped off the paths — a worktree path eats 60 columns on
    its own. both the prompt's workdir and the recorded cwd are stripped: for a
    run driving a worktree in another repo they are different directories, and
    the workdir is the one the paths are actually in."""
    if not isinstance(inp, dict):
        return ""
    for key in ARG_KEYS:
        val = inp.get(key)
        if isinstance(val, str) and val.strip():
            val = _WS.sub(" ", val).strip()
            for prefix in (agent["workdir"], agent["cwd"]):
                # every occurrence, not just a leading one: a Bash command
                # names absolute paths mid-string, and one worktree prefix
                # repeated twice in a `grep -n … <path>` eats the whole column
                if prefix:
                    val = val.replace(prefix + os.sep, "")
                    # the directory itself, with nothing under it: every one of
                    # these commands opens `cd <workdir> && …`, which is 60
                    # columns saying only "in the worktree, as always"
                    val = val.replace(prefix, ".")
            return val
    return ""


# ---- the collection --------------------------------------------------------

def agents(root, slug=None, since=0, now=None):
    """this repo's subagents, oldest first.

    `slug` keeps only one feature's; `since` drops any whose transcript has
    been quiet for more than that many seconds.

    a transcript is filed under the ORCHESTRATOR's project dir, which is not
    always this repo's: a run can drive a worktree that lives in a different
    repo entirely. so when a slug is named and this repo's dirs hold none of
    its agents, the scan widens to every project dir and attributes purely by
    slug. the widened pass is only reached when the cheap one came up empty,
    and reads incrementally after the first, so it costs a fraction of a second
    on a corpus of tens of megabytes.
    """
    root = os.path.abspath(root)
    found = _scan(project_dirs(root), root, slug, since, now)
    if found:
        return found
    if slug:
        return _scan(all_project_dirs(), None, slug, since, now)
    # no slug to attribute by — the active pointer is gone, or `--any` asked for
    # every feature. widening on the slug's evidence is not available, so the
    # prompt's workdir is: an agent told to work in a directory under this repo
    # is this repo's, wherever its orchestrator happened to be sitting.
    return _scan(all_project_dirs(), root, None, since, now, strict=True)


def _scan(dirs, root, slug, since, now, strict=False):
    wall = time.time() if now is None else now
    out = []
    for path in agent_paths(dirs):
        # the window is applied to the file's mtime BEFORE it is opened, so
        # `since` is cheap on a repo with a year of finished features behind it
        # rather than a full parse followed by a filter
        if since and wall - mtime(path) > since:
            continue
        agent = read(path)
        if not agent or not agent["turns"]:
            continue
        if root and not _in_repo(agent, root, strict):
            continue
        if slug and not _is_feature(agent, slug):
            continue
        out.append(agent)
    out.sort(key=lambda a: (a["started"], a["id"]))
    return out


def _in_repo(agent, root, strict=False):
    """the cwd check that separates `master` from a sibling `master-2`, widened
    to the workdir the prompt named: an orchestrator in another repo records its
    own cwd, and only the workdir points back here.

    an agent with neither recorded is kept — a thin record beats a dropped one —
    except under `strict`, where the whole corpus is being scanned and a record
    that names nothing is evidence of nothing.
    """
    for path in (agent["cwd"], agent["workdir"]):
        if path and (path == root or path.startswith(root + os.sep)):
            return True
    return not strict and not agent["cwd"] and not agent["workdir"]


def _is_feature(agent, slug):
    """the prompt's slug decides. failing that — a non-sdd agent spawned inside
    a feature's worktree, say — the paths around it are the only evidence
    there is, and the recorded branch is the orchestrator's, not the agent's."""
    if agent["slug"]:
        return agent["slug"] == slug
    return f"{os.sep}{slug}" in agent["cwd"] or slug in agent["branch"]


def timeline(agent_list, limit=40):
    """every agent's events merged into one stream, oldest first."""
    evs = [e for a in agent_list for e in a["events"]]
    evs.sort(key=lambda e: e["ts"])
    return evs[-limit:] if limit else evs


def status(agent, now=None):
    """running / done / stale / gone — what a pane should mark this agent as."""
    if agent["ended"]:
        return "done"
    quiet = age(agent, now)
    if agent["closed"] and quiet > SPLIT_GRACE:
        return "done"
    if quiet > ABANDONED_SECONDS:
        return "gone"
    return "stale" if quiet > STALE_SECONDS else "running"


def counts(agent_list, now=None):
    """{status: n} for a headline, in the order a reader cares about."""
    out = {}
    for agent in agent_list:
        key = status(agent, now)
        out[key] = out.get(key, 0) + 1
    return {k: out[k] for k in ("running", "stale", "gone", "done")
            if k in out}


def age(agent, now=None):
    """seconds since the transcript last grew. `now` is a WALL clock (the
    transcript's own mtime is what it is compared against), so the tests can
    age an agent without sleeping."""
    return max(0.0, (time.time() if now is None else now)
               - mtime(agent["path"]))


def elapsed(agent):
    """seconds from the agent's first record to its last, 0 if untimed."""
    start, last = epoch(agent["started"]), epoch(agent["last"])
    return max(0.0, last - start) if start and last else 0.0


def epoch(ts):
    """an iso-8601 transcript timestamp as unix seconds, 0 when unparseable."""
    if not ts:
        return 0.0
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


# ---- presentation (tones, not colors — each caller owns its palette) -------

def label(agent):
    """the agent type, short enough for a column: the `sdd:sdd-` prefix every
    one of them shares carries no information in an sdd dashboard."""
    kind = agent["type"] or "agent"
    # `sdd:sdd-implementer` is how a plugin agent is invoked now; older runs
    # recorded `sdd-implementer`. one column, one spelling.
    for prefix in ("sdd:sdd-", "sdd:", "sdd-"):
        if kind.startswith(prefix):
            return kind[len(prefix):]
    return kind


def what(agent):
    """what this agent was handed: its task id, else the spawn description."""
    if agent["task"]:
        # "Implement F6 teardown fix" -> "F6 teardown fix", never "F6 F6 ..."
        return f"{agent['task']} {_strip_task(agent)}".strip()
    return _WS.sub(" ", agent["desc"]).strip() or "—"


def _strip_task(agent):
    """the description without the task id it already carries — "Implement T1"
    under an id column of T1 is one word of information, not three."""
    desc = _TASK.sub("", agent["desc"])
    desc = re.sub(rf"\b{re.escape(agent['task'])}\b", "", desc, flags=re.I)
    return _WS.sub(" ", desc).strip(" :-") or _WS.sub(" ",
                                                      agent["desc"]).strip()


def doing(agent, now=None):
    """the one-line answer to "what is it doing": the live tool call, or how
    the finished agent finished."""
    state = status(agent, now)
    if state == "done":
        return ("done", agent["final"] or "finished")
    for ev in reversed(agent["events"]):
        if ev["kind"] == "tool":
            mark = "✗ " if ev["err"] else ""
            return ("err" if ev["err"] else state,
                    f"{mark}{ev['name']} {ev['arg']}".strip())
    return (state, agent["events"][-1]["arg"] if agent["events"] else "…")


GLYPH = {"running": "▸", "done": "✔", "stale": "⚠", "gone": "⊘", "err": "✗"}
TONE = {"running": "live", "done": "good", "stale": "warn", "gone": "dim",
        "err": "bad"}


def dur(seconds):
    """a duration in the width a column can spare: 48s, 1m12s, 2h3m."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{seconds % 3600 // 60:02d}m"


def row(agent, width, now=None):
    """one agent as [(text, tone)] segments — the caller maps tone to color.

    fixed columns first so a list of agents reads as a table, then the live
    action taking whatever is left.
    """
    state, action = doing(agent, now)
    tone = TONE.get(state, "plain")
    lw, ww = (16, 20) if width >= 78 else (12, 14)
    segs = [(GLYPH.get(state, "·"), tone),
            (f" {clip(label(agent), lw):<{lw}}", "accent"),
            (f" {clip(what(agent), ww):<{ww}}", "plain"),
            (f" {dur(elapsed(agent)):>6}", "dim"),
            (f" {agent['tools']:>3}t", "dim")]
    if agent["errors"]:
        segs.append((f" {agent['errors']}✗", "bad"))
    used = sum(len(t) for t, _ in segs)
    room = max(8, width - used - 2)
    segs.append((f"  {clip(action, room)}",
                 tone if state != "running" else "plain"))
    return segs


def event_row(ev, width, with_agent=True):
    """one timeline row: clock, which agent, the call."""
    tone = "bad" if ev["err"] else ("sub" if ev["kind"] == "say" else "plain")
    segs = [(ev["ts"][11:19] or "--:--:--", "dim")]
    if with_agent:
        segs.append((f" {clip(label(ev['agent']), 16):<16}", "accent"))
    if ev["kind"] == "tool":
        segs.append((f" {'✗' if ev['err'] else ' '}"
                     f"{clip(ev['name'], 9):<9}", tone))
    else:
        segs.append((f"  {'say':<9}", "sub"))
    used = sum(len(t) for t, _ in segs)
    segs.append((f" {clip(ev['arg'], max(8, width - used - 2))}", tone))
    return segs


def flow(head, tail, width, indent=None):
    """fixed columns + a word-wrapped tail -> a list of segment lines.

    the columns stay on the first line and the wrapped text hangs under them,
    so a wrapped roster still reads as a table. words carry their own tone, so
    a two-tone tail (what the agent was handed, then what it is running) keeps
    both hues across the fold.
    """
    lead = sum(len(t) for t, _ in head) if indent is None else indent
    lead = max(0, min(lead, max(0, width - 24)))
    room = max(16, width - lead - 2)
    lines, cur, used = [], [], 0
    for text, tone in tail:
        for word in _WS.sub(" ", text).split(" "):
            # a 200-column path has no spaces to break at — cut it into
            # room-sized pieces rather than let one word blow the width
            for piece in (word[i:i + room] for i in range(0, len(word), room)):
                if cur and used + 1 + len(piece) > room:
                    lines.append(cur)
                    cur, used = [], 0
                sep = " " if cur else ""
                if cur and cur[-1][1] == tone:  # one escape per run, not word
                    cur[-1] = (cur[-1][0] + sep + piece, tone)
                else:
                    cur.append((sep + piece, tone))
                used += len(sep) + len(piece)
    lines.append(cur)
    pad = " " * lead
    return [(head if i == 0 else [(pad, "dim")]) + [(" ", "dim")] + line
            for i, line in enumerate(lines)]


def rows(agent, width, now=None, wrap=False):
    """one agent as display LINES, each a [(text, tone)] list.

    wrapped, the description and the live call move into a flowed tail — the
    two fields a single line has to clip — while the columns that make the
    roster a table stay fixed on the left.
    """
    if not wrap:
        return [row(agent, width, now)]
    state, action = doing(agent, now)
    tone = TONE.get(state, "plain")
    lw = 16 if width >= 78 else 12
    head = [(GLYPH.get(state, "·"), tone),
            (f" {clip(label(agent), lw):<{lw}}", "accent"),
            (f" {dur(elapsed(agent)):>6}", "dim"),
            (f" {agent['tools']:>3}t", "dim")]
    if agent["errors"]:
        head.append((f" {agent['errors']}✗", "bad"))
    tail = [(what(agent), "plain"), (f" · {action}", tone)]
    return flow(head, tail, width)


def event_rows(ev, width, with_agent=True, wrap=False):
    """one timeline entry as display lines — the twin of rows()."""
    if not wrap:
        return [event_row(ev, width, with_agent)]
    segs = event_row(ev, width, with_agent)
    # every column but the argument is already short enough to keep; only the
    # argument was clipped, so only the argument is re-flowed
    return flow(segs[:-1], [(ev["arg"], segs[-1][1])], width)


def plain(segs):
    """segments as an uncolored string — the --no-color path, and the tests."""
    return "".join(t for t, _ in segs).rstrip()


def public(agent, now=None):
    """the agent as plain json-able data (no deque, no parser bookkeeping)."""
    out = {k: v for k, v in agent.items()
           if k not in ("events", "pending", "offset", "size", "prompt")}
    out["status"] = status(agent, now)
    out["label"] = label(agent)
    out["elapsed"] = round(elapsed(agent), 1)
    out["age"] = round(age(agent, now), 1)
    out["doing"] = doing(agent, now)[1]
    out["events"] = [{k: v for k, v in e.items() if k != "agent"}
                     for e in agent["events"]]
    return out
