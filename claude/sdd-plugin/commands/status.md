---
description: show sdd progress — phase, gates, task statuses, tests run, and how to resume
argument-hint: [feature-slug, defaults to specs/ACTIVE]
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
- task table: done / in_progress / blocked / pending counts, then one line
  per non-pending task (include blocked reasons)
- amendments, waived findings, tests run — if any
- nonzero metrics counters (verify_retries, reroutes, ...) — one line
- last 3 log lines
- **next step:** `/sdd:run` resumes the pipeline from the current phase;
  name the gate or input it will stop at, if any. If phase is `done`,
  point to `/sdd:cleanup` instead.

Read-only: change nothing, spawn nothing.
