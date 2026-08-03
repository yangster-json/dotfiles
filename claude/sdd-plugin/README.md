# sdd — spec-driven development plugin for Claude Code

A gated, multi-agent pipeline that takes a feature from description to
committed code: research → spec → plan → **gate 1** → implement → review →
**gate 2** → test → commit. The orchestrator never writes code; specialized
subagents do, and independent verifiers and combative reviewers check them.
All state lives on disk, so any point is resumable and the gates are safe
`/clear` points.

This is packaged as a self-contained Claude Code **plugin**: commands,
subagents, the gate-1 hook, the CLIs, templates, and workflow scripts all
ship together. Nothing needs to be added to your `settings.json`.

## commands

| command | what it does |
|---|---|
| `/sdd:run <feature>` | full pipeline; empty args resume `specs/ACTIVE` |
| `/sdd:quick <change>` | fast path — mini-spec, one implementer/verifier |
| `/sdd:status [slug]` | read-only progress report |
| `/sdd:cleanup [slug]` | after the PR merges: remove worktrees, harvest learnings, merge the spec into `specs/base/` |

## install

Development / testing (loads in-place, this session only, no install):

```
claude --plugin-dir /path/to/sdd-plugin
```

Permanent, via this repo acting as its own marketplace:

```
/plugin marketplace add jasyang/dotfiles      # or: /plugin marketplace add ~/.claude
/plugin install sdd@jasyang-dotfiles
```

To keep it out of your **global** settings.json, enable it at project or
local scope — the `enabledPlugins` entry lands in the repo's
`.claude/settings.json` (shared) or `.claude/settings.local.json` (personal,
gitignored) instead of `~/.claude/settings.json`.

Plugins are copied to a versioned cache on install, so after editing the
source run `/plugin update sdd` to refresh (or use `--plugin-dir` during
development to run the source in place).

## layout (`${CLAUDE_PLUGIN_ROOT}`)

```
.claude-plugin/plugin.json    manifest (name: sdd)
commands/                     run, quick, status, cleanup
agents/                       the 12 subagents — EFFORT pinned in frontmatter;
                              MODEL tier defaults there but config.models overrides it
bin/                          sdd-git sdd-state sdd-cost sdd-quality sdd-status
                              sdd-path  (on the Bash PATH while enabled;
                              sdd-watch is an alias of `sdd-status --full`)
hooks/hooks.json + require-plan-approval.py   gate-1 enforcement (PreToolUse)
templates/                    state, spec, tasks, research, subspec, learning, base-spec
workflows/                    research.js, review.js — Workflow fan-out scripts
pipeline.yaml                 stages, gates, routing, config (project may override)
tests/                        unittest suite for the scripts
```

Personal/team pipeline **deltas** live *outside* the plugin, in
`<claude-config>/sdd-profiles/<name>/` — a profile carries only its overrides
and inherits the rest via `extends: plugin` (resolved through `sdd-path`), so
`/plugin update` never touches it. A project opts into one with a local,
git-excluded `.claude/sdd/pipeline.yaml` that `extends:` the profile. See
run.md's "## extends" for the merge/chaining rules.

The commands resolve bundled files through the `sdd-path` helper
(e.g. `sdd-path templates/state.md`, `sdd-path pipeline.yaml`) so nothing
depends on the plugin's versioned cache path. Agents reference bundled files
via `${CLAUDE_PLUGIN_ROOT}` (expanded in agent content). Subagents are
invoked as `sdd:sdd-<name>`.

## persistent data (outside the plugin cache)

Learnings must survive `/plugin update`, so they live under the Claude config
dir, never in the cache:

- `<claude-config>/sdd-learnings/<munged-repo>/` — per-project learnings
  (`sdd-git learnings-dir`)
- `<claude-config>/sdd-learnings/_global/` — cross-project learnings
  (`sdd-git learnings-dir --global`)

## status display

There is no persistent statusline (a plugin can't register one). View status
on demand with one command:

- `sdd-status` — the compact one-liner (phase / tasks / gates / tier / hw / age)
- `sdd-status --full [slug]` — the full dashboard (a still frame; taller than
  the window, it goes through `$PAGER` so it scrolls)
- `sdd-status --loop [sec]` — a live animated dashboard for a tmux side pane
- `sdd-status --logs [slug]` — the entire log, wrapped, through `$PAGER`
- `sdd-status --show [name]` — one artifact (state.md, spec, tasks, a subspec)

(`sdd-watch` stays as a thin alias for `sdd-status --full`.)

The dashboard shows, in order: the phase ladder with both gates (a yellow
`✔auto` marks a gate autopilot or `gate1_skip_if_simple` passed, not a human);
this run's policies (`autopilot`, `findings_policy`, `test_fail_policy`, `pr`,
the `tier_offset` read, the adaptive stage-skips); the task table with a
progress gauge; the non-zero `## metrics` counters; git state (branch, commits
ahead of `base_ref` and how many are still `wip(sdd)`, dirty files); the
artifacts on disk with each one's age — a per-stage timeline the day-resolution
log can't give; amendments (flagging `(assumption)` ones still owed a gate
veto), waived findings, tests run; and the log tail. A stale `state.md` in an
unfinished phase gets an explicit "waiting at a gate, or stalled" note.

Dashboard flags: `--cost` adds the `sdd-cost` money line AND the context
gauge (both throttled to one refresh per 30s under `--loop`; `x` toggles the
gauge alone, `--context` shows just it), `--log N` sets how many log lines to show
(`0` = all), `--width N` forces the layout width, `--no-color` (or `NO_COLOR`)
drops the ANSI, `--no-anim` makes `--loop` a static redraw. The layout adapts
to the terminal width down to ~52 columns, so a narrow side pane never wraps
mid-field.

### a window smaller than the dashboard

A full dashboard runs 30-45 lines, which a short pane cannot hold. It is never
allowed to overflow the window:

- In `--loop`, the header block (feature, ladder, gates) stays pinned and
  everything under it becomes one scrollable body — `j`/`k`, `space`/`b`,
  `g`/`G`, the same keys the log and viewer panes use, with no pane to switch
  into first. A footer-side marker says what is hidden: `1-14 of 39 · ↓ 25 ·
  j/k scroll`. The frame is clipped to the terminal rather than scrolling its
  own top away, which also keeps redraws from painting over an old frame.
- `--full` hands output to `$PAGER` when it is taller than the window and
  prints it plainly when it fits, so `sdd-watch` in a tall pane behaves exactly
  as before. `--no-pager` always prints.

### reading the log, and the artifacts

The pipeline logs per *event* now, not per stage (see `config.logging`), so a
feature accumulates 30-60 timestamped lines. Two ways to read them, plus a
viewer for everything else the run produced:

- `sdd-status --logs` — the whole log, wrapped and never clipped, piped to
  `$PAGER` (`less -RFX`). `--no-pager` writes it straight to stdout.
- `sdd-status --show [name]` — one artifact through `$PAGER`: `state.md` by
  default, or the first whose name matches (`spec`, `tasks`, `research`, `T3`,
  `digest`). A miss lists what there is instead of guessing.
- In `--loop`: **`l`** expands the log to fill the pane; **`v`** opens the
  artifact viewer and **`n`**/**`p`** cycle through `state.md`, `research.md`,
  `spec.md`, `tasks.md`, every task subspec, and the standards digest — the raw
  files, so you can read the plan and the subspec an implementer was actually
  handed without leaving the pane.

  Scroll any of the three — dashboard, log, viewer — with `j`/`k` (arrows too),
  `space`/`b` by page, `g`/`G` to the ends. `+`/`-` resize the dashboard's log section, `c` toggles cost, `q` quits.
  The header says where you are (`12-18 of 21 · 3 back`, `2/7 · 1-17 of 58`),
  and the feature/phase block stays visible in every pane so you never lose
  context. Keys need a terminal; piping `--loop` still works, just unkeyed.

### the animation (`--loop` only)

The motion is a status signal, not decoration, and `--full` is always a still
frame:

- a **fast spinner** on the current phase (and on each `in_progress` task) means
  the run is moving; the **slow pulse** means it is parked at a gate or stalled
  — the same threshold that raises the "waiting at a gate, or stalled" note, so
  the two never disagree. A `done` feature sparkles and nothing spins.
- a bright cell **sweeps the task gauge** through the in-progress run, and a
  faint one marches through the pending tail.
- a task row that just changed status is marked **`✦ just now`** for 3s, and log
  entries that just arrived get a green **`▸`** — so you see *what* moved, not
  just that something did. A newly appended gate-2 fix task counts as a change.
- a cell travels along the top rule while the run is active: the one thing that
  moves even when state.md doesn't, so you can tell the pane is still live.

Frames run at 8 fps while the costly lookups (git, artifact stats, cost) honor
the `--loop` interval; state.md is re-read every frame so changes show up
immediately. Redraws erase per line rather than clearing the screen, so the
pane doesn't strobe.

## note: where the cost figure comes from

The session total is **as billed** — Claude Code's own `cost.total_cost_usd` —
whenever a statusline has cached it, and a **price-table estimate** otherwise.
The dashboard's cost section says which, every time.

Claude Code hands that number to the statusline command on every render, and to
nothing else; there is no per-session cost on disk to read. So the statusline
persists it: `statusline-command.py` writes
`<claude-config>/statusline-cache/<session>.json` (one file per session, written
atomically), and `sdd-cost`'s `billed()` picks up the entries belonging to this
repo — by session id against the project's transcripts, or by cwd for a
worktree session, whose transcripts live under a different project dir. A
statusline that doesn't write the cache simply gets the estimate; nothing
breaks. To wire up your own, cache those fields the same way.

Two things stay estimates, and are labelled as such:

- the **orch / agents split**, because Claude Code bills a session, not the
  agents inside it. Token counts behind it are exact and cover the whole
  session — subagents keep separate `<session>/subagents/agent-<id>.jsonl`
  transcripts and write nothing into the parent, so reading only the top-level
  file reports `$0.00` for them.
- everything in `sdd-cost --agents` and `--sessions`, for the same reason.

The estimate runs a few percent under the billed figure. If rates change,
update the `PRICES` table at the top of `bin/sdd-cost`.

A cached total that has stopped moving means that session ended; the section
marks it `updated 2.0h ago` rather than presenting a frozen number as live.

## note: context and clear points

`sdd-cost --context` reports how full the ORCHESTRATOR's window is — the only
one that accumulates across a run, since each subagent's window dies with it.
Occupancy only grows (every tool result appends; nothing is evicted), so a long
run climbs steadily; a session transcript outlives `/clear` and `/compact`, so
occupancy is measured within the current lifetime, split at each reset.

sdd prefers a **clear point** over compaction. The run's state is on disk
(state.md, spec.md, tasks.md, subspecs), so at a stage boundary `/clear` then
`/sdd:run` resumes from `phase:` and loses nothing, where auto-compact replaces
the conversation with a lossy summary. `/sdd:run` measures at each `stage_end`,
announces the boundary, and recommends a clear point past
`config.context.clear_point_at_pct` (default 75). Nothing in a plugin can
trigger compaction itself — `/clear` and `/compact` are user-typed, and no hook
can start one — so the pipeline's job is to make the boundary visible.

The biggest avoidable source of growth is re-reading: `spec.md` and `tasks.md`
are read once at implement setup to write the subspecs, and are spent after
that. See run.md's "### your own window".

## migrating from a global `~/.claude/sdd` install

This plugin supersedes the older layout where commands lived in
`~/.claude/commands/sdd/`, agents in `~/.claude/agents/sdd/`, scripts in
`~/.claude/sdd/`, and the hook + statusline were registered in
`~/.claude/settings.json`. After verifying the plugin with `--plugin-dir`,
cut over by removing those global copies and the two `settings.json` entries
(hook + statusLine). Migrate any existing global learnings from
`~/.claude/sdd/learnings/` to `<claude-config>/sdd-learnings/_global/`.

## tests

```
cd tests && python3 -m unittest discover
```
