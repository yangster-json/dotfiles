---
description: run the sdd pipeline — research through commit, gated only after plan and after review
argument-hint: <feature description> [jira=FW-XXXXX] [upstream=<branch>] [testbed=<name> bay=<n>] — or empty to resume specs/ACTIVE
---

Run the SDD pipeline for: $ARGUMENTS

You are the orchestrator. Read the pipeline file FIRST — the project's
`.claude/sdd/pipeline.yaml` if it exists, else the plugin's bundled copy
(run `sdd-path pipeline.yaml` to get its absolute path). It defines the
stages, agent assignments, the two gates, and their routing (models/effort
are NOT set there — they are pinned in each agent's frontmatter, invocable as
`sdd:sdd-<name>`). This command only tells you how to interpret it; the
pipeline file is authoritative and the user edits it, so never assume it
still says what it said last run.

## extends (personal / team profile layering)

If the resolved pipeline.yaml has a top-level `extends:` key, it carries only
a delta and inherits the rest from a base. Resolve the base value:
- `extends: plugin` — a sentinel for the plugin's bundled default; resolve it
  to `$(sdd-path pipeline.yaml)`. Use this from a profile so it survives
  `/plugin update` (the bundled default moves to a versioned cache; a
  hardcoded path would not).
- `extends: <path>` — a filesystem path (expand `~`), for a base that is not
  the plugin default (e.g. a team-shared project pipeline.yaml).

Chaining is allowed: the base may itself carry `extends`. Walk the chain to
its terminal base — the file with no `extends`, which must be a complete
pipeline (the plugin default is the usual terminus) — then merge each layer
back over it, outermost applied last. So `<project pointer> extends
<profile> extends plugin` resolves plugin → profile → project. A cycle
(a file reached twice) is an error: stop and report it, do not loop.

At each merge step: `config:` merges by top-level key name — a key present in
the outer file replaces that key's entire value from the base; a key absent
inherits unchanged. `pipeline:` entries merge the same way, matched by
`stage:` name — a stage present in the outer file fully replaces that named
stage; a stage absent inherits unchanged, original order preserved; an
unrecognized `stage:` name appends at the end. `extends:` itself is consumed
during resolution, never a merged key.

This lets a personal or team profile (e.g. `sdd-profiles/datastore-fw/pipeline.yaml`,
outside the plugin so `/plugin update` never touches it) carry only its delta
instead of duplicating the whole file.

## start or resume

- New feature ($ARGUMENTS describes one): derive a kebab-case slug, then run
  **intake BEFORE anything else** — no worktree, no files, no agents until
  it is answered:
  1. Gather branch candidates: the repo default
     (`git symbolic-ref refs/remotes/origin/HEAD`), the current branch
     (`git rev-parse --abbrev-ref HEAD`), and its configured upstream
     (`git rev-parse --abbrev-ref @{upstream}`, which may not exist).
  2. Ask ONE AskUserQuestion menu covering config.intake.questions —
     upstream base (the candidates above as options), jira ticket,
     hardware-test intent, pipeline depth. Every question carries a
     "you decide" option. Tokens in $ARGUMENTS (upstream=, jira=,
     testbed=/bay=) pre-answer their question — skip those. Never skip the
     menu entirely unless every question is pre-answered. Before building
     the hw_test question's options, apply config.hw_test_heuristic if set
     (see ## hw-test heuristic below).
  3. Resolve each "you decide" per the pipeline file's intake notes, record
     everything in state.md once it exists, and restate every auto-decision
     at gate 1 for veto. If depth resolves to quick, hand off to /sdd:quick
     and say so.
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
  and write the plain slug to `specs/ACTIVE` in the current root. Record the
  confirmed base as `upstream:` in state.md, and parse optional `jira=`,
  `testbed=`, `bay=` tokens (they override config.hw_test).
- Resume ($ARGUMENTS empty): read `specs/ACTIVE`. If it starts with
  `worktree:`, the feature lives in that worktree — call EnterWorktree with
  `path` set to it, then read specs/ACTIVE there. Resume from the `phase:`
  in state.md; never redo completed stages. `upstream:` is already recorded
  — do not re-ask it on resume.

## how to execute stages

- Run the pipeline stages in order. Do state.md bookkeeping through
  `sdd-state`, not hand edits: `state set phase <stage>` plus
  `state log "<stage> complete · session $X"` as each stage completes
  (the figure from `sdd-cost --brief` — successive stage lines
  give per-stage cost deltas), `state set plan_approved yes` /
  `review_approved yes` at the gates, `state task <id> <status>` as tasks
  move. Hand-edit only what the CLI doesn't cover: the initial tasks
  table, amendments, waived findings, tests run.
- Keep the `## metrics` counters current with
  `sdd-state bump <counter>` at the events the pipeline file
  names (verify_retries, tasks_blocked, ambiguities, file_list_fixes,
  findings_confirmed/rejected/waived, gate1_reroutes, gate2_reroutes,
  test_failures, merge_conflicts) — they feed `sdd-quality`.
- Run the git choreography through `sdd-git` (feature-start,
  task-start, wip, task-merge, snapshot, dissolve — the pipeline file's
  stages say when). Each command validates its preconditions and refuses
  loudly (exit 1; exit 2 = merge conflict, already aborted); treat a
  refusal as a stop signal to diagnose, never something to work around
  with raw git.
- The ONLY times you take user input are: the intake menu at the very
  start, GATE 1 (after plan), and GATE 2 (after review). Nothing between
  those points pauses for the user — not a behavioral ambiguity, not a
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

## context discipline (applies to every spawn)

- Pass each agent ONLY what its agent-file "inputs" contract lists: compact
  json for structured data, file paths for artifacts it should read itself.
  Never paste whole artifacts, other agents' full returns, or conversation
  history into a prompt.
- Implementers and verifiers get a SUBSPEC, not spec excerpts in the
  prompt: at implement setup you read spec.md once and write
  `specs/<slug>/tasks/<id>.md` per task (subspec template — feature
  context, full requirement + amendment text, file list, verify command,
  grepped interfaces, notes), then pass `{workdir, subspec}`. Those agents read only their
  subspec, never spec.md or state.md; when an amendment lands, update the
  affected subspecs.
- Most agents return hybrid markdown + a fenced ```json block; the json is
  the machine-readable payload you act on. If an agent returns malformed
  json, re-spawn it once with the parse error. The exception is the research
  scouts (sdd:sdd-researcher / -deep): they return a pure-markdown report the
  research stage synthesizes — no json block.
- You never write code yourself. All source changes go through implementer
  agents; all verdicts come from verifier/judge agents.

## learnings (don't repeat past mistakes)

Two scopes, same file shape (template: project `specs/templates/learning.md`
if present, else `$(sdd-path templates/learning.md)`):

- **project** (config.learnings.project) — this codebase's quirks (naming,
  testbed, conventions, file layout). Run `sdd-git learnings-dir`
  to get its directory — it prints (and creates)
  `<claude-config>/sdd-learnings/<munged-repo>`, keyed by the main
  checkout's absolute path (same convention `cost` uses for
  `cost-actuals.json`), so a feature or task worktree all resolve the same
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
  real json (objects and arrays, never a json-encoded string). Everything
  around the call stays yours: angle selection, round 0, gates, state.md,
  metrics, learnings.
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

## hardware tests

The test stage needs `hw_testbed`/`hw_bay` from state.md (seeded from
config.hw_test, config.hw_test_heuristic at intake, or gate-2 input). If
none was provided, run unit tests only and state plainly that hardware
tests were skipped — never fake or infer a hardware pass.

## report at the end (or at a stop)

Phase reached, tasks done/blocked, confirmed + waived findings, tests run
with results, commits made, and — if stopped — exactly what input is needed
to resume with `/sdd:run`.
