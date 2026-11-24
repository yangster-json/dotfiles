---
name: fw-pr-status
description: >-
  Show the status of the user's open GitHub PRs (default PURE-Firmware/wssd-firmware)
  as one table - review, CI, Orchestrator merge-queue state, JIRA status and the
  next step - with every blocker already classified by a script (stale build,
  JIRA Needed/In Progress, rebase, cancelled Jenkins, unanswered review,
  ready for merge-me). Use when the user asks "status of my PRs", "what's
  blocking my PRs", "is my PR in orchestrator", "did my PR merge", or wants a
  PR dashboard for themselves or a teammate.
compatibility: >-
  Requires `gh` logged in to a Pure GitHub account (repo scope) and python3.
  JIRA columns use ~/.jira_config (JIRA_URL, JIRA_PERSONAL_TOKEN) and are skipped
  without it. The `orchestrator` CLI is optional.
---

# PR status

`scripts/fw-pr-status` (relative to this skill's directory) does all
deterministic work: fetch, classify, and produce the exact command for each
fixable blocker. The agent only handles items the script marks `triage`,
`decide` and `review`, and asks before any action.

## Steps

1. Run `python3 <skill-dir>/scripts/fw-pr-status` with the user's filters:

   ```
   fw-pr-status                       # your open, non-draft PRs
   fw-pr-status 9226 9231             # just these PRs
   fw-pr-status --drafts              # include drafts
   fw-pr-status --state closed --days 3   # recently merged/closed
   fw-pr-status --repo all            # every repo
   fw-pr-status --author <login>      # a teammate's PRs
   fw-pr-status -v                    # also show wait items
   fw-pr-status --json                # rows + items + JIRA fields
   ```

2. Show the table and the item list to the user verbatim. Don't restate it.
3. Handle only these item kinds:
   - `triage`: the script couldn't classify it. Read the snippet and URL, and say
     in 1–2 lines what failed and whether the PR's diff caused it. Follow `hint:`
     when present (e.g. `fw-tpe-fetch-logs PR-N` for precommit, `fw-tpe-investigate`
     for a failed Orchestrator testplan). For a precommit FAIL, compare the failing
     suite with the PR diff (`gh pr diff N`) before calling it a flake.
   - `decide`: needs a human judgment, usually JIRA Needed/Not needed versions.
     Suggest values from the PR's base branch and the ticket. Don't edit JIRA.
   - `review`: summarize what the reviewer asked for. Don't reply on the PR.
4. Offer the runnable items by id. On approval, execute them through the script:
   `fw-pr-status --run 9226.1,9231.1` (it reruns the same analysis and runs only
   those commands). Never post `merge-me`, add labels, or rerun workflows
   without explicit approval, and never on someone else's PR.

## Table columns

| Column | Source |
|---|---|
| CI | GitHub checks only (Actions workflows): `pass`, `FAIL n, m running`, `running n` |
| Jenkins | latest `firmware-build-pipeline` build only: `#N running: <stages>`, `#N FAIL: <stages>`, `#N pass`; results from older builds are ignored |
| Orchestrator | `queued (job N)`, `testing (plan N)`, `passed, merging`, `FAILED: …`, `merged`, `-` = never submitted |
| Next | top-priority item for the PR |

## Item kinds (set by the script)

| Kind | Meaning | Agent |
|---|---|---|
| `stale` | failure already fixed (JIRA updated, newer build) — rerun if `$` shown | offer `--run` |
| `run` | ready: add `is_merge_ready`, or `merge-me` | offer `--run` |
| `manual` | known fix outside GitHub: rebase, JIRA status, Jenkins rebuild, purged logs | tell user |
| `decide` | human choice (JIRA Needed/Not needed) | suggest |
| `review` | changes requested, unresolved threads, unanswered comments | summarize |
| `triage` | unrecognized or real test failure; snippet + URL attached | investigate |
| `wait` | checks running / reviewers pending (shown with `-v`) | — |

## GitHub account

If several `gh` accounts are logged in and the active one isn't a Pure (`*_pure`)
login, the script pins its calls to the first logged-in `*_pure` account via
`GH_TOKEN`, without running `gh auth switch`. Override with `--gh-user <login>`
or `FW_PR_STATUS_GH_USER`. `JIRA_CONFIG` overrides the `~/.jira_config` path.

## What the script already knows

- Orchestrator state is read from the `Orchestrator Merge Status` commit status and
  the `ci-orchestrator[bot]` merge comment (the web UI needs SSO).
- GitHub Actions logs: "Story tickets … need to be 'In Progress'", "Bug tickets …
  need to have 'Needed'", Needed/Not Needed coverage (checked against live JIRA),
  check-cbt-mapping missing files (= stale branch, reports commits behind),
  check-unique duplicates.
- Jenkins: superseded builds, "was cancelled", "is_merge_ready label not set",
  purged logs (404), precommit `TEST REPORT` FAIL rows from the downstream
  `wssd-test-precommit` build.

When a `triage` item turns out to be a new recurring, deterministic pattern,
add a classifier for it in `classify_actions` / `classify_jenkins` in
`scripts/fw-pr-status` instead of re-diagnosing it each time.
