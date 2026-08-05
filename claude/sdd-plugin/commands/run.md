---
description: run the sdd pipeline — research through commit, gated only after plan and after review
argument-hint: <feature description> [jira=FW-XXXXX] [upstream=<branch>] [testbed=<name> bay=<n>] — or empty to resume specs/ACTIVE
---

Run the SDD pipeline for: $ARGUMENTS

You are the orchestrator. Get the pipeline FIRST by running
`sdd-pipeline --section config` — never by Reading pipeline.yaml. The resolver
picks the project's `.claude/sdd/pipeline.yaml` over the plugin's bundled copy,
merges the whole `extends:` chain, and strips the comments, so you read data
instead of the ~54KB of documentation written for whoever edits the file. Then
pull each stage's own block with `sdd-pipeline --stage <name>` as you reach it,
rather than carrying all seven for the whole run. `--json` if you want it
parsed; `--chain` to show which files a resolution came from.

The pipeline defines the stages, agent assignments, the two gates, and their
routing. Agents are invocable as `sdd:sdd-<name>`. EFFORT is pinned in each
agent's frontmatter; MODEL TIER comes from `config.models` when present (it
overrides frontmatter — see "## model routing" below), otherwise from
frontmatter. This command only tells you how to interpret the pipeline; the
pipeline is authoritative and the user edits it, so re-run the resolver each
run and never assume it still says what it said last time.

## extends (personal / team profile layering)

A pipeline file with a top-level `extends:` key carries only a delta and
inherits the rest from a base — `extends: plugin` for the bundled default (a
sentinel, so it survives `/plugin update` moving that file into a versioned
cache), or a filesystem path for a team-shared base. Chaining is allowed, so
`<project> extends <profile> extends plugin` resolves plugin → profile →
project, outermost applied last. `config:` merges by top-level key and
`pipeline:` by `stage:` name: an entry present in the outer file replaces the
base's value entirely, one that is absent inherits unchanged with the base's
stage order preserved, and an unrecognized `stage:` name appends at the end.

`sdd-pipeline` implements all of that — you do not walk the chain or merge
layers yourself, and a cycle comes back as an error rather than a loop. The
rules are documented here because the user hand-writes these files (e.g.
`sdd-profiles/datastore-fw/pipeline.yaml`, kept outside the plugin so
`/plugin update` never touches it), not because you execute them.

## start or resume

- New feature ($ARGUMENTS describes one): derive a kebab-case slug, then run
  **intake BEFORE anything else** — no worktree, no files, no agents until
  it is answered:
  1. Gather branch candidates: the repo default
     (`git symbolic-ref refs/remotes/origin/HEAD`), the current branch
     (`git rev-parse --abbrev-ref HEAD`), and its configured upstream
     (`git rev-parse --abbrev-ref @{upstream}`, which may not exist).
  2. Ask the intake questions covering config.intake.questions — upstream base
     (the candidates above as options), jira ticket, hardware-test intent,
     pipeline depth, gates, tier, stages, on_findings, on_test_fail, pr.
     AskUserQuestion caps at 4 questions per call, so batch them across
     back-to-back menus (all before anything starts), most decision-shaping
     first. PRINCIPLE: every decision that would otherwise surface LATER — a
     gate, an auto-decision restated for veto, a halt — is pre-answerable here,
     so a fully-specified launch never needs a second look; if you ever add a
     later pause point, add its intake question too. Every question carries a
     "you decide" option that reproduces today's behavior, so a user who
     ignores the extras loses nothing. Tokens in $ARGUMENTS (upstream=, jira=,
     testbed=/bay=, gates=, tier=, stages=, on_findings=, on_test_fail=, pr=)
     pre-answer their question — skip those; when ALL are pre-answered, skip the
     menus entirely (e.g. `gates=unattended on_findings=fix pr=open` +
     upstream/jira launches with no prompt at all). Before building the hw_test
     question's options, apply config.hw_test_heuristic if set (see ## hw-test
     heuristic below).
  3. Resolve each "you decide" per the pipeline file's intake notes, record
     everything in state.md once it exists, and restate every auto-decision
     at gate 1 for veto. If depth resolves to quick, hand off to /sdd:quick
     and say so. Otherwise, when config.adaptive.enabled, resolve depth into a
     TAILORED graph — decide which optional stages to skip per
     "## adaptive stage selection" and record the skip-list in state.md's
     `stages_skipped:` — rather than assuming the full graph. When
     config.auto_route.enabled, also take the feature-level difficulty read here
     and record it in state.md's `tier_offset:` per "## model tier auto-routing"
     — it sets the tier for every spawn from the first scout on.
  4. The fetch happens inside `feature-start` (below). Only without
     worktrees (config disabled / not a git repo) run
     `git fetch origin <upstream>` yourself so the base is current —
     skipped for a local-HEAD base.
- Worktree spin-off — when config.worktree.enabled, this is a git repo, and
  the session is not already inside an sdd worktree: run
  `sdd-git feature-start <slug> <upstream>` (it fetches,
  validates, cuts `.claude/worktrees/sdd/<slug>` on branch `sdd/<slug>`,
  and prints the path), then call EnterWorktree with `path` set to that
  directory (this moves the session into it). Write the resume pointer
  `worktree: .claude/worktrees/sdd/<slug>` to `<main>/specs/ACTIVE`. If
  EnterWorktree is unavailable or this is not a git repo, continue in place
  and say so once — and warn if the current HEAD is not on the confirmed
  upstream's tip.
- Then create `specs/<slug>/state.md` from the state template (the project's
  `specs/templates/state.md` if present, else `$(sdd-path templates/state.md)`)
  and write the plain slug to `specs/ACTIVE` in the current root. **Fill the
  `## feature` section with the description verbatim, before the first stage** —
  research.md and spec.md do not exist yet, so until they do this is the only
  copy, and a stop or resume at `phase: research` would otherwise come back
  knowing the slug and nothing else. Record the
  confirmed base as `upstream:` in state.md, and parse optional `jira=`,
  `testbed=`, `bay=` tokens (they override config.hw_test). Resolve the `gates`
  answer to state.md's `autopilot:` field (`gate1=<ask|skip>,gate2=<ask|skip>`):
  "both gates" -> ask,ask; "skip plan gate" -> skip,ask; "unattended" ->
  skip,skip; "you decide" or absent -> the config.autopilot defaults. The
  `gates=` token maps the same (both|skip-plan|unattended). This is the run's
  authority for both gates; the gate stages read it, not config directly.
  Resolve the remaining intake answers to their state.md fields the same way
  (answer or matching token; "you decide"/absent -> the field's default):
  `tier` -> tier_offset (standard|heavy|light; you-decide -> the auto_route read
  per "## model tier auto-routing", which then owns it); `stages` -> full sets
  stages_skipped: none and suppresses adaptive for the run, tailor/you-decide ->
  normal adaptive per "## adaptive stage selection"; `on_findings` ->
  findings_policy (fix|waive|stop); `on_test_fail` -> test_fail_policy
  (halt|proceed); `pr` -> pr (none|open). All are recorded before the first
  stage and read by the stage that owns each (gate 2, test, commit); on resume
  they are already set — do not re-ask.
- Resume ($ARGUMENTS empty): read `specs/ACTIVE`. If it starts with
  `worktree:`, the feature lives in that worktree — call EnterWorktree with
  `path` set to it, then read specs/ACTIVE there. Resume from the `phase:`
  in state.md; never redo completed stages. `upstream:` is already recorded
  — do not re-ask it on resume.

## how to execute stages

- Run the pipeline stages in order. Do state.md bookkeeping through
  `sdd-state`, not hand edits: `state set phase <stage>`,
  `state log "<line>"` at every event config.logging names (see
  "## logging" below), `state set plan_approved yes` /
  `review_approved yes` at the gates, `state task <id> <status>` as tasks
  move. Hand-edit only what the CLI doesn't cover: the initial tasks
  table, amendments, waived findings, tests run, `stages_skipped:`
  (the adaptive skip-list), and `tier_offset:` (the auto-route read).
- **One event, one call — use `state event`.** Most moments in a run produce
  several of those edits at once (a task passes: status flips, a counter
  bumps, a line is logged). Do them in a SINGLE
  `sdd-state event --task T3=done --bump verify_retries --log "…"`, not three
  consecutive `state` calls. This is not cosmetic: every tool call re-sends
  your whole context window, so at a normal mid-run occupancy three calls to
  write three lines cost three windows — bookkeeping was ~20% of the
  orchestrator's spend on measured runs. `event` takes repeated
  `--set k=v` / `--task id=status` / `--bump counter[=n]` / `--log message`,
  applies them set → task → bump → log whatever order you pass, and writes
  once. It does NOT weaken "log as you go" (see "## logging"): batch the
  edits that belong to the same event, never events that happened at
  different times.
- Batch the read-only probes the same way: the two `sdd-cost` calls at a
  stage end are one `sdd-cost --brief; sdd-cost --context` invocation.
- Keep the `## metrics` counters current with
  `sdd-state bump <counter>` — or the `--bump` leg of an `event` — at the
  events the pipeline file names (verify_retries, tasks_blocked, ambiguities,
  file_list_fixes, findings_confirmed/rejected/waived, gate1_reroutes,
  gate2_reroutes, test_failures, merge_conflicts) — they feed `sdd-quality`.
- Run the git choreography through `sdd-git` (feature-start,
  task-start, wip, task-merge, snapshot, dissolve — the pipeline file's
  stages say when). Each command validates its preconditions and refuses
  loudly (exit 1; exit 2 = merge conflict, already aborted); treat a
  refusal as a stop signal to diagnose, never something to work around
  with raw git.
- The ONLY times you take user input are: the intake menu at the very
  start, GATE 1 (after plan), and GATE 2 (after review) — and either gate is
  dropped when config.autopilot skips it (its decision then moves to the
  final report per the commit stage's close; with both skipped, intake is the
  sole touchpoint). Nothing between those points pauses for the user — not a behavioral ambiguity, not a
  file-list miss, not a blocked task. When a mid-pipeline decision you might
  once have asked about comes up, RESOLVE IT YOURSELF with best judgment
  (the spec's summary / non-goals / constraints and the surrounding code are
  the tiebreakers), record it as an amendment in state.md flagged
  `(assumption)`, and surface it at the NEXT gate for veto — the same way
  intake "you decide" choices and a gate-1 auto-approval are restated at
  their gate. Past gate 2 (a fix or test-fix task) there is no later gate,
  so such assumptions go in the final report instead. This is a hard rule:
  do NOT invent confirmation prompts, "just checking" questions, or approval
  steps the gates below don't define. A needs_files report is yours to
  adjudicate per the implement stage's scope_stop rule; a behavioral
  ambiguity per its ambiguity rule (assume + amend + surface, never ask).
  Dead ends are minimized, not eliminated: a failing task or test first
  climbs the bounded rescue ladder in config.recovery (escalating retries,
  merge-conflict serial re-run, diagnosis-first test rounds) before it gives
  up. Only when that ladder is exhausted does the pipeline STOP and report
  (still-red tests after the last fix round, a task that failed every
  attempt, a missing external dependency) — and that is an error
  termination, not a request for input. config.gate1_skip_if_simple can even
  resolve GATE 1 itself (see "## gate 1 auto-approve" below).
- Run gates with AskUserQuestion; the routes listed in the pipeline file are
  the options (they are sized to fit one menu). Free-text answers may
  combine routes ("fix F1/F2, waive F3, testbed fw-comet02 bay 19") —
  honor all parts. Where a route says YOU decide the sub-route (gate 1
  "modify", gate 2 "spec or plan wrong"), infer it from the user's words
  and say which you picked.
- When presenting a gate, run `sdd-cost --brief` and include its
  one line — the user decides routing with the spend in front of them.
- After a gate routes backward (spec-writer / planner / implementer), re-run
  only the affected downstream work (delta), not the whole pipeline.

## model routing (config.models)

Model tier is centralized in `config.models` (role -> tier), so a rebalance is
one edit there instead of a sweep across `agents/*.md`, and it layers through
`extends:`. Apply it at EVERY spawn:

- Agent-tool spawns (any `sdd:sdd-<name>` you launch directly — the scouts on
  the research fallback path, an inline judge re-run, a spec-writer/planner
  revision, etc.): the `config.models` KEY is the agent's file basename, i.e.
  the whole `sdd-<name>` (agent `sdd:sdd-planner` keys on `sdd-planner`, NOT
  `planner`). If `config.models` has that key, pass its value as the spawn's
  `model`. No entry (or no `config.models` block at all) -> pass no model and
  let the agent's frontmatter default stand. EFFORT always comes from
  frontmatter — never override it here.
- Workflow spawns (research, review, implement): the scripts spawn via `agentType` and
  cannot read the pipeline file, so THREAD the map in. Add `models:
  config.models` (the whole map, as real json) to the `args` you pass the
  Workflow tool. Each script applies `models[<agent-name>]` as that agent's
  model override and falls back to frontmatter when the map lacks the key —
  so passing nothing preserves today's behavior.

This is override-with-fallback: `config.models` wins where it speaks,
frontmatter fills every gap. Deleting the block restores pre-config behavior
exactly. When config.auto_route is on, the map you apply here is the
OFFSET-SHIFTED effective map, not config.models verbatim — see "## model tier
auto-routing".

## context discipline (applies to every spawn)

- Pass each agent ONLY what its agent-file "inputs" contract lists: compact
  json for structured data, file paths for artifacts it should read itself.
  Never paste whole artifacts, other agents' full returns, or conversation
  history into a prompt.
- Implementers and verifiers get a SUBSPEC, not spec excerpts in the
  prompt: at implement setup `sdd:sdd-subspec-writer` reads spec.md and
  tasks.md and writes `specs/<slug>/tasks/<id>.md` per task, and you pass
  `{workdir, subspec}`. Those agents read only their subspec, never spec.md or
  state.md; when an amendment lands, update the affected subspecs — a
  one-section edit is yours, a re-grep after a merge goes back to the same
  agent in `mode: regen`.
- Most agents return hybrid markdown + a fenced ```json block; the json is
  the machine-readable payload you act on. If an agent returns malformed
  json, re-spawn it once with the parse error. The exception is the research
  scouts (sdd:sdd-researcher / -deep): they return a pure-markdown report the
  research stage synthesizes — no json block.
- You never write code yourself. All source changes go through implementer
  agents; all verdicts come from verifier/judge agents.

### your own window (re-reading is the main leak)

Your context is the only one that accumulates across the whole run — a
subagent's dies with it. It only grows, so every avoidable re-read is
permanent. The rule: **an artifact you have already read this session is
already in your context — do not read it again.** Concretely:

- **`spec.md` and `tasks.md` are never yours to read in full.** The plan stage
  hands you a table, not tasks.md; `sdd:sdd-subspec-writer` reads both at
  implement setup so you don't have to, and hands back counts plus a
  `feature_card`. That card — summary, non-goals, constraints — is the feature
  intent you adjudicate against for the rest of the run; it is deliberately the
  one thing that comes back in full. The exception is a spec AMENDMENT: read
  only the section you are amending.
- **Everything a task needs is in its subspec, and every status is in
  state.md.** Do NOT read a subspec, or a slice of tasks.md, before each
  implementer spawn — the implementer reads its own subspec, and re-reading
  one turns a per-task cost into a permanent one. If you need a task's row
  mid-implement, it is in the state.md you are already updating.
- **`pipeline.yaml` is read once, at the very start.** It does not change
  mid-run; re-reading it to re-check a config value costs more than
  remembering the value.
- Reach for `offset`/`limit` when you need part of a file you have NOT read,
  not to re-fetch part of one you have.

## clear points (context, not compaction)

Your window fills as the run proceeds and nothing evicts it until `/clear` or
auto-compact. sdd prefers a **clear point**: the run's state is already on disk
(state.md, spec.md, tasks.md, subspecs), so `/sdd:run` with no arguments
resumes from `phase:` and loses nothing. Auto-compact, by contrast, replaces
the conversation with a lossy summary. A clear point is strictly better —
but only the user can take one, so your job is to make it visible.

- **You cannot compact or clear yourself.** No tool does it: `/clear` and
  `/compact` are user-typed commands, and no hook can trigger them (a
  PreCompact hook only observes one that already started). Never claim to have
  compacted, and never spend a turn trying. What sdd does instead is end the
  turn at a stage boundary so the NEXT stage starts in a fresh window — better
  than compaction, because nothing is summarized and nothing is lost.
- **Measure at every `stage_end`**, with `sdd-cost --context` (one line:
  occupancy, window, peak, requests). Include its figure in the stage_end log
  line next to the cost delta, so consecutive lines show context growth per
  stage the same way they show spend. The figure is your own window's: the
  reading pins to `CLAUDE_CODE_SESSION_ID`, so it is right even when the
  feature lives in another repo than the session (a cross-repo run used to
  read "no transcript data" while its window was 44% full).
- **The measurement is also enforced, not just asked for.**
  `hooks/context-guard.py` fires on every `sdd-state` write that SETS `phase`
  — a stage boundary by definition — and feeds the occupancy figure back to
  you with the verdict already applied (note / recommend / stop). It exists
  because this was prose-only and a measured run reached 44% having never
  logged a single figure. Treat its line as the measurement: log it, act on
  it, and do not re-run `sdd-cost --context` to double-check the same
  boundary.
- **Announce the boundary** when `config.context.announce_clear_points`: on
  leaving a stage, state in one line that the run is safely resumable — the
  phase it would resume from, and that `/clear` then `/sdd:run` continues it.
  Below `clear_point_at_pct` that is a note, not a suggestion; keep it to one
  line and move on.
- **Recommend it** once occupancy is at or past `config.context.clear_point_at_pct`
  (default 20 — a percentage of the WINDOW, so 20% of a 1m-context session is
  200k tokens): say plainly that a clear point is advised here, give the
  occupancy figure, and continue working. Do not stop, do not ask — a gate is
  the only place you take input, and context pressure is not a gate.
- **Stop at EVERY stage boundary when `config.context.stop_at_every_stage`**
  (default true). This is the "compact between stages" rule, done the lossless
  way: on entering a stage — with the new `phase:` already written, which is
  what makes resume exact — log a `stop` event naming that phase and end the
  turn with the resume instruction. No stage then pays for the previous one's
  agent returns. It costs one `/clear` + `/sdd:run` per stage; set the key
  false for threshold-only stops (the right choice for an unattended run,
  unless something outside the session re-launches it). Two boundaries are
  exempt: occupancy below `config.context.stop_floor_pct` (default 8 — an
  almost-empty window costs more to re-establish than it saves, which is the
  first boundary of a run and all of `/sdd:quick`), and `phase: done`, which
  has no next stage.
- **Stop if `config.context.hard_stop_at_pct` is >0 and occupancy is past it**
  (default 35). Same shape, threshold-triggered: finish the current stage, log
  a `stop` event naming the resume phase, and end the turn with the resume
  instruction. This is the backstop for unattended runs, where nobody acts on
  the recommendation — but it is not conditional on autopilot, so an attended
  run stops too. That is deliberate: past this figure every further request
  re-reads a window that large, and `/clear` + `/sdd:run` resumes losslessly
  from `phase:`. Present it as the cheap next step it is, not as a failure.
- **While a stop is in force, new spawns are BLOCKED.** The same guard hook
  denies `Task` and `Workflow` calls until the window is actually cleared, so
  "finish the stage anyway" is not available to you at a boundary stop. If you
  see that denial, do not work around it (no inline substitute for the agent,
  no second attempt): end the turn with the resume instruction. Nothing is
  stranded — an interrupted stage re-runs its workflow from the top (see
  "## workflow stages"), and the guard lifts itself once occupancy drops.
- A stage boundary is the ONLY safe clear point: mid-stage, unmerged task
  worktrees and un-recorded verdicts live only in your context. Never suggest
  one between an implementer spawn and its merge.

## learnings (don't repeat past mistakes)

Two scopes, same file shape (template: project `specs/templates/learning.md`
if present, else `$(sdd-path templates/learning.md)`):

- **project** (config.learnings.project) — this codebase's quirks (naming,
  testbed, conventions, file layout). Run `sdd-git learnings-dir`
  to get its directory — it prints (and creates)
  `<claude-config>/sdd-learnings/<munged-repo>`, keyed by the main
  checkout's absolute path (same convention `sdd-cost` uses for its
  per-project transcripts), so a feature or task worktree all resolve the same
  directory. Its index is `<that-dir>/INDEX.md`. NEVER written into the
  project's own tree — nothing to gitignore there, and it persists across
  every worktree and every feature regardless of the project's own git
  history.
- **global** (config.learnings.global) — pipeline/agent-behavior lessons
  that would recur on ANY codebase (a stage misjudging scope, a reviewer
  stance over-triggering, a gate route that surprised the user). Run
  `sdd-git learnings-dir --global` for its directory
  (`<claude-config>/sdd-learnings/_global`); its index is
  `<that-dir>/INDEX.md`. Lives outside the plugin cache, so it survives
  `/plugin update` and is shared across every project.

- **Reading (stays cheap on context):** at pipeline start, read both
  INDEX.md files if they exist — each is one short line per entry, so both
  together cost a handful of lines even with a long history. Skip a scope
  whose directory doesn't exist yet. Grep the two indexes for entries
  matching THIS feature's subsystem, files, or stage, merge the hits, and
  pass only the matched entry files (not the full indexes, not unrelated
  entries) as inputs to the agents the pipeline file marks (scouts,
  spec-writer, planner) — fold implementation-stage matches into the
  relevant subspec notes instead. An agent whose stage has no matching
  entry in either index gets nothing extra: the index is what keeps this
  from turning into "paste every past lesson into every prompt."
- **Writing:** when a gate reroutes, a task double-fails or a merge
  conflicts, the user vetoes an auto-decision, or a finding is waived,
  write one learning file and add its INDEX.md line
  (`- [slug](slug.md) — stage:<stage> tags:<t1,t2> — <hook>`) — in whichever
  scope the lesson fits:
    - names this codebase's specific files, APIs, tests, or testbeds ->
      project
    - about the pipeline's or an agent's behavior/tendencies, independent
      of which codebase it ran on -> global
  When unsure, default to project: a global entry gets committed and
  pushed in the sdd install, so scrub any codebase-specific detail (ticket
  IDs, internal paths, proprietary logic) before writing one there — never
  let project specifics leak into a "general" lesson. Phrase "how to
  avoid" as a check the next run can actually apply.

## logging (config.logging)

state.md's `## log` is the run's flight recorder: after a `/clear`, after a
crash, and for the human reading a finished feature, it is the only record of
what actually happened. `sdd-state log` stamps `- YYYY-MM-DD HH:MM`, so many
entries per stage stay ordered and timeable.

- **Log as you go, not at the end.** Write the line at the moment the event
  happens — never batch a stage's events into one summary afterwards, and
  never reconstruct them later from memory. An interrupted run must leave a
  log that explains where it got to. (Batching a single event's edits into one
  `state event` call is not batching events — it is the same instant, one tool
  call instead of three. Multiple `--log` legs in one call are fine only when
  the lines describe that same moment.)
- **What to log:** every event in `config.logging.events` when
  `config.logging.level` is `verbose` (the default); only the stage
  transitions, gates, task outcomes, findings, tests, and commits when it is
  `normal`. On a fully unattended run (both gates skipped) the log IS the
  user's only window into the middle of the pipeline — treat verbose as
  mandatory there.
- **Do not narrate a running subagent.** Log the dispatch and the return, not
  what an agent is doing between them: the user already has that live, from the
  agents' own transcripts (`sdd-agents`, or `a` in `sdd-status --loop`). Your
  job is the events only you know about.
- **Shape:** one line, `<stage>: <what happened>`, carrying the numbers that
  make it reviewable — ids, counts, verdicts, effort/tier when it changed, and
  on stage_end both the `sdd-cost --brief` figure and the `sdd-cost --context`
  occupancy, so consecutive lines give per-stage cost AND context deltas. State
  what HAPPENED; the artifacts already hold what was DECIDED, so never paste
  spec or task text into the log.
- **Always log the why, not just the what,** for anything that went sideways:
  a retry line says what failed, a blocked task says what was still wrong on
  the last attempt, a reroute says which route and why, a waived finding says
  on whose call. These are exactly the lines someone reads back later.
- **Examples** (verbose, one stage):

      research: 3 scouts dispatched — 2 enum (haiku), 1 deep (sonnet)
      research: scout 2/3 returned — 4 findings, 1 open question
      research: research.md written — 61 lines, 3 conventions, 2 risks
      research: complete · 1m40s · session $0.42 · ctx 118k/1.0M (12%)
      implement: T3 start — subspec 41 lines, worktree sdd/led-blink-T3
      implement: T3 verify FAIL — new test never ran red; retry 1/3 at effort high
      implement: T3 verify PASS — 2 requirements, scope clean
      implement: T3 merged --no-ff into sdd/led-blink

- **Do not** log secrets, full file contents, agent prompts, or whole agent
  returns. A line that would not fit on one terminal row is too long.
- The counters in `## metrics` are not a substitute: bump them AND log the
  event. `sdd-quality` aggregates the counters; the log is what explains them.

## gates are context-reset points

Record every gate outcome (and each stage completion) in state.md BEFORE
continuing — never hold pipeline state only in conversation. That makes
gates safe reset points: after resolving a gate on a large feature, tell the
user they can `/clear` and re-run `/sdd:run` to continue with a fresh
context — resume is lossless from state.md and sheds every accumulated agent
return.

## fw-skills

Where a stage names a skill (see config.fw_skills), check whether it is
available in this session. Available → invoke the skill and let it own that
process. Not available → use the stage's fallback, and mention once in the
final report that fw-skills was not installed.

## internal docs (optional config.internal_docs)

If config.internal_docs is set, run its listed lookups yourself at the
start of the research stage, in parallel with invoking the research
workflow — these are session MCP tools and one-off agent spawns (Glean,
Google Drive, Confluence, jira-analyst, jenkins-analyst), not part of
research.js's scout roster, so they never go through the workflow script.
Fold any hits into research.md's context section alongside the scout
reports. Not set → the research stage runs exactly as described below, no
extra step.

## workflow stages (deterministic fan-outs)

Where a stage carries `run_via: workflow <name>`, its agent fan-out is
executed by a Workflow script, not by you spawning agents:

- Resolve the script like the pipeline file itself: the project's
  `.claude/sdd/<config.workflows.name>` if it exists, else the bundled copy
  via `sdd-path <config.workflows.name>` — and pass that ABSOLUTE path as
  `scriptPath`.
- Build `args` exactly as the stage's `orchestrator` note describes, as
  real json (objects and arrays, never a json-encoded string), PLUS
  `models: config.models` so the script can route each agent's tier (see
  "## model routing"). Everything around the call stays yours: angle
  selection, round 0, gates, state.md, metrics, learnings.
- Workflow-spawned agents return schema-validated json — the result object
  is the machine payload, no parsing (the research scouts are the one
  exception: they return markdown reports the orchestrator synthesizes). A
  `null` or missing entry means an agent was skipped or died: treat it as a
  gap to re-run inline (the stage's `orchestrator` note says how), never as
  an empty success.
- If the Workflow tool is unavailable, or the run errors or returns
  nothing, fall back to spawning the stage's agents yourself per its
  round/agent descriptions, and mention it once in the final report.
- Workflow resume (`resumeFromRunId`) is same-session only — it is NOT the
  pipeline's resume mechanism. Cross-session resume stays state.md-based:
  a stage interrupted mid-workflow just re-runs its workflow from the top.

## hw-test heuristic (optional config.hw_test_heuristic)

If config.hw_test_heuristic is set (a list of keywords), scan the feature
description for a case-insensitive match before building the intake menu
(start-or-resume step 2). A match drops the hw_test question's "decide at
gate 2" option — down to testbed+bay now / no hw tests — and the gate-1
auto-decision restatement notes which keyword(s) matched. Not set → the
hw_test question keeps all three options, unchanged from today.

## gate 1 auto-approve (config.gate1_skip_if_simple, default true)

The plan stage's `gate:` block spells out the check; the summary here is
for orientation. When config.gate1_skip_if_simple is true (the default)
and the plan that just came back is trivial — every task row in tasks.md
tagged `complexity: simple`, zero unplannable requirements, no unresolved
spec-critic blocker — resolve gate 1 yourself instead of stopping:
`state set plan_approved yes`, `state set gate1_auto_approved yes`, and a
`state log` line naming the tasks. Continue straight into implement. Any
task tagged `standard`, or any unplannable requirement, or any unresolved
blocker, forces the normal human gate regardless of the flag — this is a
narrow bypass for genuinely small plans, not a way to wave through
anything the planner produces.

Because the user never saw the plan, GATE 2 restates the auto-approval
(task count/titles) in its summary — their first look at the plan is that
gate, and an objection there routes exactly like any other "spec or plan
wrong" gate-2 finding. A project or profile can set this false in its
pipeline.yaml to restore the always-ask gate 1.

## adaptive stage selection (config.adaptive)

Between "full `/sdd:run`" and "hand off to `/sdd:quick`" there is a middle
ground: run `/sdd:run` but SKIP the optional stages this feature does not need.
When `config.adaptive.enabled` (default true), you own that judgment — never
silently. The rules:

- **What is skippable.** Only a stage (or substep) that carries `optional:
  true` / `critics_optional: true` in the pipeline file. Today that is the
  `research` stage and the `spec` stage's two critics. Everything else — spec
  writer, plan, implement, review, test, commit — always runs. Never invent a
  skip the pipeline file does not mark optional.
- **When you decide.** At the very start, as part of resolving the intake
  `depth` question (see "start or resume" step 3). For each optional stage read
  its `skip_when:` heuristic against this feature and decide run/skip with a
  one-line reason. `research` must be decided here because it runs first; the
  critics decision can be made now or refreshed once the spec exists.
- **Record it.** Write the skip-list to `state.md`'s `stages_skipped:` field
  (stage name + one-line reason each; `none` if nothing skipped) before the
  stage would have run, and `state log` it. A skipped stage's `when_skipped:`
  note in the pipeline file says how to keep downstream inputs intact (e.g.
  research writes a stub research.md) — follow it; never leave the next stage
  without its contract.
- **Surface for veto.** The skip-list is an auto-decision: restate it at GATE 1
  in the plan summary (and at GATE 2 when gate 1 auto-approved), exactly like an
  intake "you decide" choice. If the user objects, un-skip the named stage and
  run it as a delta before continuing — route it like a gate "modify".
- **Off switch.** `config.adaptive.enabled: false` forces the full graph: run
  every stage, propose no skips, and set `stages_skipped: none`. The `stages`
  intake answer does the same per-run: `full` forces the full graph regardless
  of config; `tailor`/`you decide` runs the normal proposal above.

This is discretion with a receipt: the model tailors the graph, the human keeps
the veto, and nothing is dropped without a recorded reason.

## model tier auto-routing (config.auto_route)

`config.models` is the BASELINE role -> tier map. When
`config.auto_route.enabled` (default false — off leaves that map untouched and
this whole section inert), you take ONE difficulty read for the feature at intake
and shift the whole map up or down a rung for this run. Like the adaptive
skip-list, this is your judgment, never silent.

- **The ladder and the offset.** Tiers rank `haiku < sonnet < opus`. The read
  yields an offset applied to EVERY role in config.models and clamped at the ends:
    - **heavy (+1)** — unfamiliar subsystem, cross-cutting change, subtle
      invariants / concurrency / data-flow: bump each role up (haiku->sonnet,
      sonnet->opus, opus stays).
    - **standard (0)** — the common case: config.models unchanged.
    - **light (-1)** — trivial, isolated, mechanical, well-understood: bump each
      role down (opus->sonnet, sonnet->haiku, haiku stays).
- **When you decide.** At the very start, alongside the intake depth /
  adaptive-skip resolution (see "start or resume" step 3), from the feature
  description and any base-spec context — before any agent spawns, so the first
  scouts already run at the chosen tier. An explicit `tier` intake answer
  (standard|heavy|light) OVERRIDES this read; you only take the read when that
  answer is "you decide".
- **How to apply it.** Do NOT teach the spawn sites about offsets. Resolve the
  EFFECTIVE map once — apply the offset to config.models with ladder clamping —
  and use that effective map everywhere config.models is used per "## model
  routing": as each Agent-tool spawn's `model`, and as the `models:` arg threaded
  to the research / review / implement workflows. The scripts stay unchanged; they
  receive an already-shifted plain map. Offset 0 => the effective map IS
  config.models.
- **Composition with complexity.** Orthogonal: the per-task `complexity` tag
  picks WHICH agent (implementer-lite vs implementer), this offset then shifts
  that agent's tier. A heavy feature runs a simple task's lite implementer at
  sonnet and a standard task's implementer at opus.
- **Record it.** Write the read + one-line reason to state.md's `tier_offset:`
  (`standard` when offset 0) before the first spawn, and `state log` it.
- **Surface for veto.** Restate it at GATE 1 in the plan summary (and at GATE 2
  when gate 1 auto-approved), exactly like the adaptive skip-list and intake
  auto-decisions. If the user objects, re-resolve the offset per their note and
  rebuild the effective map for the remaining stages — no completed stage reruns.
- **Bias.** Lean toward `standard`; reserve `light` for genuinely trivial
  features, because a light read can route a standard-complexity task to haiku,
  and a down-route is costlier to get wrong than an up-route. When torn between
  two reads, pick the higher one.
- **Off switch.** `config.auto_route.enabled: false` (default) => no read,
  `tier_offset: standard`, config.models used verbatim.

## hardware tests

The test stage needs `hw_testbed`/`hw_bay` from state.md (seeded from
config.hw_test, config.hw_test_heuristic at intake, or gate-2 input). If
none was provided, run unit tests only and state plainly that hardware
tests were skipped — never fake or infer a hardware pass.

## report at the end (or at a stop)

Phase reached, tasks done/blocked, confirmed + waived findings, tests run
with results, commits made, and — if stopped — exactly what input is needed
to resume with `/sdd:run`.
