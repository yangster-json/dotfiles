# sdd — spec-driven development plugin for Claude Code

A gated, multi-agent pipeline that takes a feature from a one-line description
to committed code: research → spec → plan → **gate 1** → implement → review →
**gate 2** → test → commit. The orchestrator never writes code; specialized
subagents do, and independent verifiers and combative reviewers check them. All
state lives on disk, so any point is resumable and the gates are safe `/clear`
points.

Everything ships together as a self-contained plugin — commands, subagents,
both guard hooks, the CLIs, templates, workflow scripts. Nothing needs to be
added to your `settings.json`.

---

# commands

| command | what it does |
|---|---|
| `/sdd:run <feature>` | full pipeline; empty args resume `specs/ACTIVE` |
| `/sdd:quick <change>` | fast path — mini-spec, one implementer/verifier, no research/critics/combative review |
| `/sdd:status [slug]` | read-only progress report |
| `/sdd:cleanup [slug]` | after the PR merges: remove worktrees, harvest learnings, merge the spec into the living base |

---

# how it operates

## the division of labour

Three things run a feature, and the split is deliberate:

- **the orchestrator** — your main session. It owns judgment and shell access:
  intake, gate adjudication, git choreography, scope-stop and ambiguity calls,
  the final diagnosis-first retry. It never edits source itself.
- **subagents** (`agents/*.md`, 13 of them) — each does one job in its own
  window, which dies when it returns. Implementers, verifiers, critics,
  reviewers, scouts.
- **workflow scripts** (`workflows/*.js`) — deterministic fan-outs. Every
  multi-agent stage is a script, so parallelism, retry ladders and conditional
  rounds are *executed*, not prompted. The script spawns the agents and returns
  the orchestrator a **digest** — never the raw agent output. This is the main
  reason a run doesn't drown its own context.

## the stages

| stage | who runs | produces | gate |
|---|---|---|---|
| research | 2-4 scouts in parallel (`sdd-researcher` for enumeration, `sdd-researcher-deep` for cross-file reasoning), angles chosen by the orchestrator | `research.md` | — |
| spec | `sdd-spec-writer`, then two critics in parallel (feasibility/edge-cases, testability/consistency), plus one conditional revision round | `spec.md` | — |
| plan | `sdd-planner` | `tasks.md` + the task table mirrored into `state.md`, each task tagged `simple` or `standard` | **gate 1** |
| implement | per task: `sdd-implementer` (standard) or `sdd-implementer-lite` (simple), then `sdd-verifier` for standard tasks | committed `wip(sdd)` commits on the feature branch | — |
| review | round 0 by the orchestrator, then 3 combative reviewers + `sdd-review-judge` + `sdd-test-recommender` | confirmed findings | **gate 2** |
| test | orchestrator (via fw-skills when installed) | test results in `state.md` | — |
| commit | orchestrator | real commits, `wip(sdd)` dissolved | — |

Research and the spec critics are **optional** (`config.adaptive`): a small
change in a well-understood area skips them, and the skip plus its one-line
reason is recorded in `state.md` and restated at gate 1. A skipped research
stage still gets a stub `research.md`, so downstream stages never lose their
input contract.

## the two gates

Gate 1 (after plan) is the only thing that unlocks source edits — enforced by
`hooks/require-plan-approval.py`, a PreToolUse hook on Edit/Write/Bash, not by
prose. It presents the plan, the coverage map, unresolved spec blockers, the
adaptive skips, the tier read, and every intake auto-decision for veto. Routes:
approve / modify (the orchestrator reroutes to the right stage) / abort.

Gate 2 (after review) presents confirmed findings, the rejected count, and test
recommendations. Routes: approve / "spec or plan wrong" (reroute) / "just fix
the code" (findings become F-tasks, run through the implement loop, delta
re-reviewed) / waive.

Both can run unattended (`config.autopilot`), and gate 1 auto-approves when
every task is simple and nothing is disputed (`gate1_skip_if_simple`, default
true). Whatever a skipped gate would have shown moves forward: to gate 2 if it
still asks, otherwise into the final report — an unattended run trades the
gates for a post-commit inspection, never for silence.

## how a task gets implemented

1. **Setup, once per feature.** A ~50-line standards digest is distilled from
   the repo's coding standard. `sdd-subspec-writer` then reads `spec.md` and
   `tasks.md` and writes one subspec per task (`specs/<slug>/tasks/<id>.md`:
   verbatim requirements, file list, verify command, grepped interfaces). A
   `sdd-git snapshot` commits `specs/` so task worktrees carry them.
   Implementers and verifiers read **only** their subspec.
2. **Batching.** Tasks run in dependency order. A solo task runs in the feature
   worktree; a concurrent group (max 3, file sets pairwise disjoint) each gets
   an isolated worktree — `sdd-git task-start` → `.claude/worktrees/sdd/<slug>-<id>`.
   Isolation makes scope checks exact and lets builds and tests run without
   racing.
3. **Verify.** Standard tasks get an independent `sdd-verifier` in the same
   worktree (requirement compliance, scope, test honesty). Simple tasks get no
   spawn — the orchestrator re-runs the verify command, checks scope with `git
   status`/`diff`, and greps the diff for sdd leakage. A spawn exists only where
   judgment is needed.
4. **The retry ladder** (`config.recovery.task_attempts`, default 3). The script
   takes the first attempts-1 rungs, re-spawning the implementer with the
   failure evidence at effort bumped one tier. The **last** attempt is
   diagnosis-first and belongs to the orchestrator: root-cause the repeated
   failure (stale interfaces? wrong verify command? task too big?), amend the
   subspec or decompose the task, then try once more. Only then is a task
   marked blocked — surfaced at gate 2, never a hard halt.
5. **Merge.** `sdd-git wip` commits the diff, `task-merge` merges `--no-ff` and
   removes the worktree. A conflict means the plan's file sets overlapped;
   recovery re-runs the task serially against the merged code. After each merge
   the subspec writer re-greps interfaces for the dependents that were given
   them as `(planned — …)`.

The feature branch HEAD always contains all completed work; the commit stage
dissolves the `wip(sdd)` commits into real ones at the end.

## how review works

- **Round 0** — orchestrator, no spawn: grep the added lines of the feature diff
  for stub markers (TODO, FIXME, "not implemented", hardcoded-empty returns).
  Hits are objective, skip the debate, and go to gate 2 confirmed.
- **Round 1** — three reviewers in parallel with distinct stances: *breaker*
  (correctness, edge cases, races), *guardian* (spec compliance, test honesty),
  *attacker* (security, robustness, failure modes). The test recommender runs
  alongside.
- **Round 2** — conditional combat. Zero findings means round 2 and the judge
  are both skipped. Otherwise only the reviewers with opponent findings to
  contest are re-spawned; each must refute, concede or escalate every opponent
  finding and defend or withdraw its own.
- **The judge** runs only on findings that survive round 2. Only confirmed
  findings reach the user.

## test and commit

Recommended tests run via fw-skills when installed. A failure is diagnosed
before it is fixed: flaky or environmental → re-run once; genuine → a fix task
through the implement loop, up to `config.recovery.test_fix_rounds` (default 2).
Still red after that, `test_fail_policy` decides — `halt` (default) stops and
reports, `proceed` commits anyway with the red tests *leading* the final report.
A pass is never faked.

Commit groups the diff into logical commits, dissolving the `wip(sdd)` commits
first (`sdd-git dissolve`). It never pushes; a PR is opened only when intake
said so.

## what never reaches the deliverable

`specs/` is never committed (`config.specs_tracking: untracked` — gitignore it),
the living base specs live outside the repo (`sdd-git base-specs-dir`), and
neither the code, the comments, the test names nor the commit message may
reference a spec, requirement id, or task id. That last rule travels to
implementers inside the standards digest, and the verifier greps for violations
like any other check — a comment pointing at a spec dangles the moment the
commit lands.

## everything is on disk

`specs/<slug>/state.md` is the run: header fields (`phase`, both gate flags,
policies, `base_ref`, hw testbed), the feature description verbatim, the task
table with statuses, `## metrics` counters, amendments, waived findings, tests
run, and a timestamped `## log` written per event as things happen. `sdd-state`
makes every write a single command rather than a prose markdown edit.

So `/sdd:run` with no arguments reads `phase:` and resumes exactly where it
stopped — which is what makes a stage boundary a lossless `/clear` point, and
what makes an interrupted run recoverable rather than restarted.

## model routing

`config.models` maps each role to a tier alias (`haiku`/`sonnet`/`opus`) in one
place, overriding the agent files' own frontmatter. Rebalancing which role runs
on which tier is a one-line edit here rather than a sweep across `agents/*.md`,
and because it lives in config it layers through `extends:`. Reasoning **effort**
deliberately stays pinned in each agent's frontmatter — it is tied to that
agent's behavior, not to a budget decision. `config.auto_route` (off by default)
shifts the whole map up or down a rung based on a difficulty read taken at
intake.

---

# install

Development (loads in place, this session only):

```
claude --plugin-dir /path/to/sdd-plugin
```

Permanent, via this repo acting as its own marketplace:

```
/plugin marketplace add jasyang/dotfiles      # or: /plugin marketplace add ~/.claude
/plugin install sdd@jasyang-dotfiles
```

To keep it out of your **global** settings.json, enable it at project or local
scope — the `enabledPlugins` entry then lands in the repo's
`.claude/settings.json` (shared) or `.claude/settings.local.json` (personal).

Install copies the plugin to a versioned cache, so after editing the source run
`/plugin update sdd` (or use `--plugin-dir` to run the source in place).

---

# configuration

## pipeline.yaml

Single source of truth for how `/sdd:run` executes — the stage graph, the gate
definitions, and a `config:` block. The keys worth knowing:

| key | default | what it controls |
|---|---|---|
| `models` | haiku/sonnet/opus per role | role → model-tier routing; overrides agent frontmatter |
| `gate1_skip_if_simple` | `true` | auto-approve gate 1 when every task is `simple`, coverage is complete, and no critic blocker stands |
| `autopilot.gate1` / `.gate2` | `ask` | `skip` runs that gate unattended |
| `adaptive.enabled` | `true` | allow research and the spec critics to be skipped when the change doesn't need them |
| `auto_route.enabled` | `false` | shift the whole run a model tier for a hard codebase |
| `recovery` | 3 attempts / `rerun` / 2 test-fix rounds | how hard a failing task or test is rescued before it's called blocked |
| `worktree.enabled` | `true` | isolated worktrees for concurrent tasks |
| `specs_tracking` | `untracked` | whether `specs/` ever enters a commit |
| `logging.level` | `verbose` | per-event logging (30-60 lines a feature) rather than per stage |
| `intake.questions` | 10 questions | what `/sdd:run` asks up front (gates, depth, tier, hw testbed, on-findings, on-test-fail, pr …) |
| `context.*` | see below | clear points and stage-boundary stops |
| `coding_standard` / `comment_style` / `commit_standard` | — | what the standards digest and the commit stage enforce |
| `fw_skills` | — | which skills to use for unit tests, hw pytests, commit, pr |

## profiles and project overrides

Personal or team **deltas** live outside the plugin, in
`<claude-config>/sdd-profiles/<name>/` — a profile carries only its overrides
and inherits the rest via `extends: plugin`, so `/plugin update` never touches
it. A project opts in with a local, git-excluded `.claude/sdd/pipeline.yaml`
that `extends:` the profile.

The merge rules, which `sdd-pipeline` implements (the orchestrator never walks
the chain itself, and a cycle is an error rather than a loop):

- `extends: plugin` is a **sentinel** for the bundled default, so it survives
  `/plugin update` moving that file into a versioned cache. A filesystem path
  points at a team-shared base instead.
- Chaining is allowed: `<project> extends <profile> extends plugin` resolves
  plugin → profile → project, **outermost applied last**.
- `config:` merges by top-level key, `pipeline:` by `stage:` name. An entry
  present in the outer file replaces the base's value **entirely**; one that is
  absent inherits unchanged, with the base's stage order preserved; an
  unrecognized `stage:` name appends at the end.

`sdd-pipeline --chain` shows which file each resolved value came from.

---

# what's in the plugin

```
.claude-plugin/plugin.json    manifest (name: sdd)
commands/                     run, quick, status, cleanup
agents/                       the 13 subagents — EFFORT pinned in frontmatter;
                              MODEL tier defaults there but config.models wins
bin/                          sdd-git sdd-state sdd-status sdd-agents sdd-cost
                              sdd-quality sdd-pipeline sdd-path (on the Bash
                              PATH while enabled; sdd-watch aliases
                              `sdd-status --full`. statelib/agentlib are the
                              shared parsers, not CLIs)
hooks/hooks.json              two guards: require-plan-approval.py (gate 1,
                              PreToolUse) and context-guard.py (stage-boundary
                              occupancy + stop enforcement, Post/PreToolUse)
templates/                    state, spec, tasks, research, subspec, learning, base-spec
workflows/                    research, spec, plan, implement, review
pipeline.yaml                 stages, gates, routing, config
tests/                        unittest suite + .mjs workflow-script tests
```

The commands resolve bundled files through `sdd-path` (e.g. `sdd-path
templates/state.md`) so nothing depends on the versioned cache path. Agents
reference bundled files via `${CLAUDE_PLUGIN_ROOT}`. Subagents are invoked as
`sdd:sdd-<name>`.

## data that lives outside the plugin cache

Learnings must survive `/plugin update`, so they live under the Claude config
dir:

- `<claude-config>/sdd-learnings/<munged-repo>/` — per-project (`sdd-git learnings-dir`)
- `<claude-config>/sdd-learnings/_global/` — cross-project (`sdd-git learnings-dir --global`)

Living base specs sit outside the repo too (`sdd-git base-specs-dir`);
`/sdd:cleanup` merges a finished feature's spec into them.

---

# watching a run

## the commands

A plugin can't register a statusline, so status is on demand:

- `sdd-status` — compact one-liner (phase / tasks / gates / tier / hw / age)
- `sdd-status --full [slug]` — the full dashboard, a still frame (through
  `$PAGER` when taller than the window; `--no-pager` always prints)
- `sdd-status --loop [sec]` — live animated dashboard for a tmux side pane
- `sdd-status --logs [slug]` — the entire log, wrapped, through `$PAGER`
- `sdd-status --show [name]` — one artifact (`state.md`, `spec`, `tasks`, `T3`,
  `digest`); a miss lists what there is
- `sdd-agents [slug]` — one row per subagent (see below)
- `sdd-quality` — pipeline health across features: retry rate, block rate,
  review precision, waive rate, from the `## metrics` counters

## the dashboard

It shows, in order: the phase ladder with both gates (a yellow `✔auto` marks an
autopilot or `gate1_skip_if_simple` pass, not a human); this run's policies
(`autopilot`, `findings_policy`, `test_fail_policy`, `pr`, `tier_offset`,
adaptive stage-skips); the task table with a progress gauge; the agents working
right now, if any; non-zero metrics counters; git state (branch, commits ahead
of `base_ref` and how many are still `wip(sdd)`, dirty files); the artifacts on
disk with each one's age — a per-stage timeline the day-resolution log can't
give; amendments (flagging `(assumption)` ones still owed a gate veto), waived
findings, tests run; and the log tail. A stale `state.md` in an unfinished phase
gets an explicit "waiting at a gate, or stalled" note.

Flags: `--cost` adds the money line and the context gauge (both throttled to one
refresh per 30s under `--loop`; `--context` shows just the gauge), `--log N`
sets log lines (`0` = all), `--width N` forces the width, `--no-color` (or
`NO_COLOR`), `--no-anim`. The layout adapts down to ~52 columns, so a narrow
side pane never wraps mid-field.

`--loop` bounds: `--frames N` draws N frames and exits, `--for SEC` exits after
SEC seconds, and it retires itself once its parent exits. Use `--frames` for any
scripted capture — a bare `--loop` only stops on a keypress, and a harness that
can't deliver one leaves it repainting forever. It runs on the alternate screen
so repaints never enter scrollback (on the primary screen a wrapped frame
scrolled its own top rows into history and grew a 200 MiB tmux buffer).

## color

The palette is **Catppuccin Mocha**, the same one nvim, tmux and the statusline
use, so the pane reads as part of the terminal. Each hue means one thing:

| hue | means |
|---|---|
| green | done, clean, approved |
| sapphire | in progress |
| mauve | the phase you are on |
| yellow | wants a human — auto-passed gate, unvetoed assumption, dirty files, friction counter |
| peach | parked or running out of room — stalled run, un-squashed `wip(sdd)`, context past 65% |
| red | broken — blocked tasks, failures, context past 75% |
| teal / sky / lavender / pink | category accents (git, context, log, cost/viewer) |

Every section header carries its own hue, so a 40-line frame is scanned rather
than read; the log tints only the entries that report an outcome. A `▸` on a
just-arrived log entry and `✦ just now` on a task row are **pink** — "arrived"
is not "succeeded".

Truecolor is detected from `COLORTERM`, with xterm-256 and basic-8 fallbacks;
`SDD_COLOR_DEPTH=truecolor|256|basic` forces one. The basic tier merges
neighbouring hues, so color is never the only signal — each is also carried by a
glyph or a word.

## keys, and a window smaller than the dashboard

A full dashboard runs 30-45 lines. In `--loop` it is clipped to the terminal,
never allowed to scroll its own top away: the header block (feature, ladder,
gates) stays pinned, everything under it scrolls, and a marker says what is
hidden (`1-14 of 39 · ↓ 25 · j/k scroll`).

Four panes share one set of keys — dashboard, log (`l`), agents (`a`), artifact
viewer (`v`): `j`/`k` (or arrows), `space`/`b` by page, `g`/`G` to the ends.
`n`/`p` cycle the viewer through `state.md`, `research.md`, `spec.md`,
`tasks.md`, every task subspec, and the standards digest — the raw files, so you
can read the subspec an implementer was actually handed. `+`/`-` resize the log
section, `c` toggles cost, `x` the context gauge, `q` quits.

**`w`** toggles clipping, in every pane at once. Off (the default), a too-long
row is cut with a `…` so columns stay aligned and the pane holds the most rows.
On, nothing is cut and long rows fold with a hanging indent under their own
columns — the whole shell command an agent is running, the whole finding it
returned. A page still steps by what the pane actually showed. `--wrap` starts
that way; `sdd-agents --wrap` is the same on the command line. Keys need a
terminal; piping `--loop` still works, just unkeyed.

## the subagents

The log is the *orchestrator's* account, written between spawns: "3 reviewers
dispatched" and, minutes later, what came back. What each agent does in between
lives in Claude Code's own per-subagent transcripts:

```
<claude-config>/projects/<munged-cwd>/<session>/subagents/agent-<id>.jsonl
                                                          agent-<id>.meta.json
```

`bin/agentlib.py` reads them incrementally, from the byte offset the last pass
stopped at, so an 8 fps pane costs one short read per agent per frame. It
dedupes the symlink Claude Code leaves when a transcript is handed to a second
session, and keeps **discovery** and **attribution** separate:

- *Discovery* is by directory. A feature spans the repo's own project dir plus
  one per worktree — found by munged prefix, then confirmed against each
  record's `cwd` so a sibling `repo-2` is not dragged in.
- *Attribution* is by **spawn prompt** — the `slug:` line, the `workdir:`, or a
  cited `specs/<slug>/` path. Never by `cwd`/`gitBranch`: those describe the
  session, not the feature. A run with no worktree sits on whatever branch it
  started on, and a run driving a worktree in *another* repo files its
  transcripts under the orchestrator's repo — for that case the scan widens to
  every project dir when this repo's hold none of the named feature's agents.

Commands:

- **`sdd-agents [slug]`** — one row per agent: status glyph, type, task,
  elapsed, calls, failures, and the tool call it is running right now, then a
  merged activity tail. Defaults to the active feature and the last 2h
  (`--since MIN`, `--all`, `--any`, `--live`).
- **`sdd-agents --agent <who>`** — one agent in full: the prompt it was handed,
  every call, what it returned. `who` is an id prefix, an agent type, or a task
  id. The "why did T4 fail?" view.
- **`sdd-agents --follow [sec]`** — a stream, `tail -f` style. `--json` dumps
  the same data for scripting.
- **`a`** in `--loop` — the same rows under the pinned phase/gate header: the
  roster stays put (an agent that keeps its row can be watched; a scrolling one
  cannot) and the activity tail scrolls under it. The dashboard also grows a
  compact `agents` section whenever an agent is working.

Status is derived, not reported: `end_turn` means **done**; still working means
**running**; quiet for 90s means **stale**; quiet past 30m means **gone** — it
died with an interrupted run. A spinner on a dead agent is the one thing a live
pane must not show.

## the animation (`--loop` only)

Motion is a status signal, not decoration, and `--full` is always a still frame:

- a **fast spinner** on the current phase (and each `in_progress` task) means the
  run is moving; the **slow pulse** means it is parked at a gate or stalled — the
  same threshold that raises the "waiting at a gate, or stalled" note. A `done`
  feature sparkles and nothing spins.
- a bright cell **sweeps the task gauge** through the in-progress run, a faint
  one marches through the pending tail.
- a task row that just changed is marked **`✦ just now`** for 3s and new log
  entries get a pink **`▸`** — so you see *what* moved. A newly appended gate-2
  fix task counts as a change.
- a cell travels along the top rule while the run is active: the one thing that
  moves even when state.md doesn't.

Frames run at 8 fps while the costly lookups (git, artifact stats, cost) honor
the `--loop` interval; state.md is re-read every frame. Redraws erase per line
rather than clearing the screen, so the pane doesn't strobe.

---

# cost

The session total is **as billed** — Claude Code's own `cost.total_cost_usd` —
whenever a statusline has cached it, and a **price-table estimate** otherwise.
The dashboard's cost section says which, every time.

Claude Code hands that number to the statusline command on every render and to
nothing else, so the statusline persists it: `statusline-command.py` writes
`<claude-config>/statusline-cache/<session>.json` (one file per session,
atomically), and `sdd-cost`'s `billed()` picks up the entries belonging to this
repo — by session id against the project's transcripts, or by cwd for a worktree
session, whose transcripts live under a different project dir. A statusline that
doesn't write the cache simply gets the estimate. To wire up your own, cache
those fields the same way.

Two things stay estimates and are labelled as such: the **orch / agents split**
(Claude Code bills a session, not the agents inside it) and everything in
`sdd-cost --agents` / `--sessions`. Token counts behind them are exact and cover
the whole session. The estimate runs a few percent under the billed figure; if
rates change, update the `PRICES` table at the top of `bin/sdd-cost`.

A cached total that has stopped moving means that session ended; the section
marks it `updated 2.0h ago` rather than presenting a frozen number as live.

---

# context and clear points

## measuring

`sdd-cost --context` reports how full the ORCHESTRATOR's window is — the only
one that accumulates across a run, since each subagent's window dies with it.
Occupancy only grows (every tool result appends; nothing is evicted), and a
transcript outlives `/clear`, so occupancy is measured within the current
lifetime, split at each reset.

It pins to `CLAUDE_CODE_SESSION_ID`, which Claude Code exports into every Bash
call, and reads that transcript wherever it was filed. Both fallbacks it
replaced were wrong in practice: newest-wins inside the project dir reports the
*other* terminal when two are open on one repo, and resolving the project dir
from the repo path fails outright for a cross-repo run (session in repo A,
worktree in repo B — a 44%-full window read as `no transcript data`). With no id
to pin to, the reading says `session guessed`. `--session <id>` pins explicitly;
`--json` is the machine form.

## clear points over compaction

The run's state is on disk, so at a stage boundary `/clear` then `/sdd:run`
resumes from `phase:` and loses nothing, where auto-compact replaces the
conversation with a lossy summary. Nothing in a plugin can trigger compaction
itself, so what sdd does instead is END THE TURN at a boundary and let the next
stage start in a fresh window.

Four settings under `config.context`:

| setting | default | effect at a stage boundary |
|---|---|---|
| `announce_clear_points` | `true` | say the run is safely resumable — you can't take a clear point you were never told about |
| `clear_point_at_pct` | 20 | past it, the announcement becomes a recommendation; the run keeps going |
| `hard_stop_at_pct` | 35 | >0 and past it, the run stops and hands back the resume instruction (0 disables) |
| `stop_at_every_stage` | `false` | when true, stop at every boundary regardless of occupancy — no stage pays for the previous one's returns, at one `/clear` + `/sdd:run` per stage (~6 a feature) |
| `stop_floor_pct` | 8 | below this the every-stage stop does not fire (an almost-empty window isn't worth re-establishing); `phase: done` never stops either |

The percentages are set for COST, not headroom: every request re-reads the whole
window at the cache-read rate, so 200k of occupancy on a 1m-context session is
already ~$0.10 a tool call — long before the window is near full.

**These are enforced by a hook, not by prose.** `hooks/context-guard.py --post`
fires on every `sdd-state` write that SETS `phase` — a stage boundary by
definition — measures occupancy and feeds the figure back with the verdict
applied. `--pre` then blocks `Task`/`Workflow` spawns while a stop stands, so the
next stage cannot start in a window that was supposed to be cleared; it lifts
itself once occupancy drops (a `/clear` keeps the session id, so the drop is the
only evidence available). This exists because the threshold used to live only in
run.md, and a measured run reached 44% with not one occupancy figure in its log.
Stops are cheap by construction: the new `phase:` is already written, so the run
resumes at exactly the stage that was about to start.

## why the orchestrator delegates so much

The biggest avoidable source of growth is re-reading, so the orchestrator does
not read the big artifacts at all: `sdd-subspec-writer` reads `spec.md` and
`tasks.md` at implement setup, writes the subspecs, and hands back one row per
task plus a ≤12-line `feature_card` — the feature intent later adjudication
needs. The same agent re-greps a dependent's `## interfaces` after each merge,
which inline would leave one permanent copy of the grep output per merge. What
stays with the orchestrator is what accumulated context makes BETTER, not worse:
scope-stop adjudication, ambiguity resolution, the diagnosis-first retry rung,
and both gates. See run.md's "### your own window".

---

# tests

```
cd tests && python3 -m unittest discover
for t in tests/*_workflow_test.mjs; do node "$t"; done
```

The `.mjs` files drive the workflow scripts against a stubbed Workflow runtime
(`agent`/`parallel`/`phase`/`log` replaced with recorders), so the control flow
the scripts own — retry ladders, conditional rounds, the digest and set-math
rules — is actually executed rather than read.
