# sdd — spec-driven development pipeline for Claude Code

A gated, multi-agent pipeline that takes a feature from description to
committed code: research → spec → plan → **gate 1** → implement → review →
**gate 2** → test → commit. The orchestrator (the main Claude session)
never writes code; specialized subagents do, and independent verifiers and
combative reviewers check them. All state lives on disk, so any point is
resumable and gates are safe `/clear` points.

## commands

| command | what it does |
|---|---|
| `/sdd:run <feature>` | full pipeline; empty args resume `specs/ACTIVE` |
| `/sdd:quick <change>` | fast path — mini-spec, one implementer/verifier, no worktree |
| `/sdd:status [slug]` | read-only progress report |
| `/sdd:cleanup [slug]` | after the PR merges: remove worktrees/branches, harvest learnings |

## where things live

```
~/.claude/
  commands/sdd/            run, quick, status, cleanup (orchestrator instructions)
  agents/sdd/              the 11 subagents — MODELS ARE PINNED HERE (frontmatter)
  sdd/
    pipeline.yaml          global default pipeline: stages, gates, routing, config
    templates/             state, spec, tasks, research, subspec, learning
    hooks/require-plan-approval.py   gate-1 enforcement (PreToolUse)
    statelib.py            shared tolerant parser for state.md (used by all tools)
    cost / watch / quality statusline.sh + statusline-segment.py   tooling
    tests/                 unittest suite for the scripts

<project>/
  .claude/sdd/pipeline.yaml   optional project override (preferred over global)
  specs/templates/*.md        optional project template overrides
  specs/<slug>/               spec.md, tasks.md, state.md, research.md, tasks/<id>.md
  specs/standards-digest.md   distilled coding standard (generated once)
  specs/learnings/            accumulated lessons + INDEX.md
  specs/ACTIVE                pointer: plain slug, or `worktree: <path>`
```

Two sources of truth, deliberately separate: **pipeline.yaml** owns process
(stages, gates, routing, config); **agent frontmatter** owns models and
tools. Style rules for generated code live in ONE artifact, the standards
digest (distilled from `config.coding_standard` + `config.comment_style`;
delete the digest to force regeneration after changing either).

## execution model

- **Feature worktree**: `/sdd:run` cuts `sdd/<slug>` from the confirmed
  upstream into `.claude/worktrees/sdd/<slug>` and works there; the main
  checkout gets a `worktree:` pointer in `specs/ACTIVE`.
- **Subspecs**: at implement setup the orchestrator distills spec.md +
  amendments into one standalone file per task
  (`specs/<slug>/tasks/<id>.md`) — feature context (summary, non-goals,
  constraints) plus that task's pre-merged requirements. Implementers and
  verifiers read only that — small context, no stale-spec drift, no
  cross-task bleed. A mechanical file-list miss comes back as a
  `needs_files` report the orchestrator adjudicates itself; only
  behavioral ambiguity stops for the user.
- **Task worktrees**: concurrent tasks each run in an isolated worktree
  (branch `sdd/<slug>-<id>`, dash not slash — git refs forbid nesting under
  an existing branch name). Isolation makes verifier scope checks exact and
  lets builds run concurrently. Verified work merges back into the feature
  branch as provisional `wip(sdd)` commits; the commit stage dissolves them
  (`git reset --soft` to the merge-base) and regroups into logical commits.
- **Gates**: gate 1 = approve / modify / abort; gate 2 = approve /
  spec-or-plan-wrong / fix-code / waive. Sized to fit one AskUserQuestion
  menu; free text can combine routes. Outcomes are written to state.md
  before continuing, so `/clear` + `/sdd:run` resumes losslessly.
- **Learnings**: mistakes, vetoes, and waivers become files in
  `specs/learnings/` with an INDEX.md the orchestrator greps at the start
  of every run — the pipeline is supposed to stop repeating itself.

## enforcement

`hooks/require-plan-approval.py` (PreToolUse on `Edit|Write|NotebookEdit|Bash`)
blocks in-project source mutations until state.md says `plan_approved: yes`;
only `specs/` and `.claude/` are writable before that. Bash coverage is a
heuristic (redirections, `tee`/`mv`/`rm`/`cp`, `sed -i`, `git apply`, ...)
that blocks a mutating command unless its targets are visibly safe — it
guards against process mistakes, not adversaries. Everything fails open
except recognizably mutating commands, so a broken state file can never
brick a session.

## tooling

```
.claude/sdd/watch --loop        live dashboard for a tmux side pane
.claude/sdd/cost [--agents|--sessions N|--brief]   spend, auto-calibrated
.claude/sdd/quality             pipeline health across features (metrics in state.md)
```

`cost` calibrates its estimates against as-billed totals the statusline
caches under `<claude-config>/projects/<munged-root>/cost-actuals.json` —
never inside the project. `quality` aggregates the `## metrics` counters
each state.md carries (retries, blocks, findings confirmed/rejected/waived,
gate reroutes) into rates that tell you whether the pipeline stages earn
their tokens.

## project setup

- Optional: `docs/coding_standard.md` (or point `config.coding_standard`
  elsewhere). Without it the digest falls back to `config.comment_style` +
  researched conventions.
- Optional: fw-skills installed as skills — stages use them when available,
  fall back inline when not.
- Recommended `.gitignore` entries for consuming repos:

  ```
  specs/ACTIVE
  .claude/worktrees/
  ```

  `specs/<slug>/` is deliberately committed with the feature.

## tests

```
cd ~/.claude/sdd/tests && python3 -m unittest discover
```

Covers the hook (file tools, Bash heuristics, worktree pointer, fail-open),
statelib's tolerance to LLM formatting drift, quality aggregation, and cost
calibration. Run after editing any script; the parsers and the guard are
load-bearing.
