---
description: show sdd progress — phase, gates, task statuses, tests run, and how to resume
argument-hint: "[feature-slug, defaults to specs/ACTIVE]"
---

Report SDD status. Feature: $ARGUMENTS (if empty, read `specs/ACTIVE`; if
that doesn't exist either, list the subdirectories of `specs/` with their
phases, then stop).

If `specs/ACTIVE` starts with `worktree:`, the feature lives in that
worktree — read its specs/ACTIVE and state.md from that path instead, and
name the worktree in the report.

Read `specs/<slug>/state.md` and report, compactly:

- feature slug, jira, upstream, current phase, hw testbed/bay if set
- gate flags: plan_approved (note if gate1_auto_approved is yes), review_approved
- adaptive stage-skips: the `stages_skipped` field, if it names any stage
- this run's policies: `autopilot`, `findings_policy`, `test_fail_policy`,
  `pr`, and `tier_offset` when it is not `standard`
- task table: done / in_progress / blocked / pending counts, then one line
  per non-pending task (include blocked reasons)
- amendments, waived findings, tests run — if any
- nonzero metrics counters (verify_retries, reroutes, ...) — one line
- the log tail — the last ~10 entries (they are timestamped and written per
  event now, so 3 lines no longer covers even one stage). Say how many entries
  there are in total, and point at `sdd-status --logs` for the whole thing.
- any subagent working right now, from `sdd-agents --live --no-tail` — one line
  each (type, task, elapsed, the call it is on). Skip the line entirely when
  none are. This is the only place the *current* fan-out shows up: the log
  records a dispatch and then its return, nothing in between.
- context occupancy, from `sdd-cost --context` — one line, and note whose
  window it is: the reading pins to the session asking, so run from THIS
  session it reports this one, not the run you are asking about (pass
  `--session <id>` to read the run's, or take the figure the dashboard shows —
  `sdd-status` reads the run's window, not the caller's). When it is at or past
  `config.context.clear_point_at_pct` (default 20% of the window), say a clear
  point is advised: `/clear` then `/sdd:run` resumes from the phase above,
  losing nothing. That threshold is about COST, not headroom — every request
  re-reads the whole window — so advise it well before the window looks full.
  Past `config.context.hard_stop_at_pct` (default 35), or at any boundary when
  `stop_at_every_stage` is on, the run does not merely advise: it stops and its
  next spawn is blocked until the window is cleared, so say that plainly.
- **next step:** `/sdd:run` resumes the pipeline from the current phase;
  name the gate or input it will stop at, if any. If phase is `done`,
  point to `/sdd:cleanup` instead.

Read-only: change nothing, spawn nothing.
