# sdd state: <feature-slug>

created: <YYYY-MM-DD>
jira: none
upstream: none       <!-- confirmed base branch (e.g. origin/master) — set at start, worktree base + pr target -->
phase: research  <!-- research | spec | plan | implement | review | test | commit | done -->
plan_approved: no    <!-- gate 1 — unlocks source edits (enforced by hook) -->
review_approved: no  <!-- gate 2 -->
base_ref:            <!-- set when implement starts; review/test diff against this -->
hw_testbed: none     <!-- e.g. fw-comet02 — from pipeline config or gate 2 -->
hw_bay: none         <!-- e.g. 19 -->

## tasks
<!-- mirrored from tasks.md by the plan stage; statuses live here, tasks.md is immutable -->
| id | title | complexity | status | depends_on | parallel_ok |
|----|-------|------------|--------|------------|-------------|

## amendments
<!-- spec decisions made after gate 1; amendments override spec.md where they conflict -->
<!-- A1 (<date>): <question> -> <decision> -->

## waived findings
<!-- confirmed review findings the user chose to ship anyway (gate 2) -->

## tests run
<!-- filled by the test stage: test, where (x86 / testbed+bay), result -->

## log
- <YYYY-MM-DD> feature initialized
