---
description: run the sdd pipeline — research through commit, gated only after plan and after review
argument-hint: <feature description> [jira=FW-XXXXX] [upstream=<branch>] [testbed=<name> bay=<n>] — or empty to resume specs/ACTIVE
---

Run the SDD pipeline for: $ARGUMENTS

You are the orchestrator. Read the pipeline file FIRST — the project's
`.claude/sdd/pipeline.yaml` if it exists, else `~/.claude/sdd/pipeline.yaml`
(the global default). It defines the stages, agent/model assignments, the
two gates, and their routing. This command only tells you how to interpret
it; the pipeline file is authoritative and the user edits it, so never
assume it still says what it said last run.

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
     menu entirely unless every question is pre-answered.
  3. Resolve each "you decide" per the pipeline file's intake notes, record
     everything in state.md once it exists, and restate every auto-decision
     at gate 1 for veto. If depth resolves to quick, hand off to /sdd:quick
     and say so.
  4. `git fetch origin <upstream>` so the base is current (skip the fetch
     only for a local-HEAD base).
- Worktree spin-off — when config.worktree.enabled, this is a git repo, and
  the session is not already inside an sdd worktree: remember the current
  root as <main>, cut the worktree from the confirmed upstream:
  `git worktree add <main>/.claude/worktrees/sdd/<slug> -b sdd/<slug> <upstream>`,
  then call EnterWorktree with `path` set to that directory (this moves the
  session into it). Write the resume pointer
  `worktree: .claude/worktrees/sdd/<slug>` to `<main>/specs/ACTIVE`. If
  EnterWorktree is unavailable or this is not a git repo, continue in place
  and say so once — and warn if the current HEAD is not on the confirmed
  upstream's tip.
- Then create `specs/<slug>/state.md` from the state template (the project's
  `specs/templates/state.md` if present, else `~/.claude/sdd/templates/state.md`)
  and write the plain slug to `specs/ACTIVE` in the current root. Record the
  confirmed base as `upstream:` in state.md, and parse optional `jira=`,
  `testbed=`, `bay=` tokens (they override config.hw_test).
- Resume ($ARGUMENTS empty): read `specs/ACTIVE`. If it starts with
  `worktree:`, the feature lives in that worktree — call EnterWorktree with
  `path` set to it, then read specs/ACTIVE there. Resume from the `phase:`
  in state.md; never redo completed stages. `upstream:` is already recorded
  — do not re-ask it on resume.

## how to execute stages

- Run the pipeline stages in order, updating `phase:` and appending a Log
  line in state.md as each stage completes. Include the session figure from
  `~/.claude/sdd/cost --brief` in that log line (e.g. "implement complete ·
  session $9.80") — successive stage lines give per-stage cost deltas.
- Between stages, keep going — the ONLY places you stop for the user are
  GATE 1 (after plan), GATE 2 (after review-judge), and an implementer
  ambiguity report. Everything else runs straight through.
- Run gates with AskUserQuestion; the routes listed in the pipeline file are
  the options. Free-text answers may combine routes ("fix F1/F2, waive F3,
  testbed fw-comet02 bay 19") — honor all parts.
- When presenting a gate, run `~/.claude/sdd/cost --brief` and include its
  one line — the user decides routing with the spend in front of them.
- After a gate routes backward (spec-writer / planner / implementer), re-run
  only the affected downstream work (delta), not the whole pipeline.

## context discipline (applies to every spawn)

- Pass each agent ONLY what its agent-file "inputs" contract lists: compact
  json for structured data, file paths for artifacts it should read itself.
  Never paste whole artifacts, other agents' full returns, or conversation
  history into a prompt.
- Exception where excerpts beat reads: build implementer/verifier task json
  with the full TEXT of the task's requirements and the amendments touching
  its files (read spec.md once yourself and extract) — those agents never
  read spec.md or state.md.
- Agents return hybrid markdown + a fenced ```json block; the json is the
  machine-readable payload you act on. If an agent returns malformed json,
  re-spawn it once with the parse error.
- You never write code yourself. All source changes go through implementer
  agents; all verdicts come from verifier/judge agents.

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

## hardware tests

The test stage needs `hw_testbed`/`hw_bay` from state.md (seeded from
config.hw_test or gate-2 input). If none was provided, run unit tests only
and state plainly that hardware tests were skipped — never fake or infer a
hardware pass.

## report at the end (or at a stop)

Phase reached, tasks done/blocked, confirmed + waived findings, tests run
with results, commits made, and — if stopped — exactly what input is needed
to resume with `/sdd:run`.
