# sdd state: <feature-slug>

created: <YYYY-MM-DD>
jira: none
upstream: none       <!-- confirmed base branch (e.g. origin/master) — set at start, worktree base + pr target -->
phase: research  <!-- research | spec | plan | implement | review | test | commit | done -->
plan_approved: no    <!-- gate 1 — unlocks source edits (enforced by hook) -->
gate1_auto_approved: no  <!-- yes if config.gate1_skip_if_simple approved this without asking; restated at gate 2 -->
review_approved: no  <!-- gate 2 -->
gate2_auto_approved: no  <!-- yes if config.autopilot.gate2=skip approved this without asking; findings surfaced in the final report -->
autopilot: gate1=ask,gate2=ask  <!-- resolved at intake (the `gates` question), overrides config.autopilot for this run; the gate stages read THIS. default ask,ask = normal two-gate flow -->
findings_policy: fix   <!-- intake on_findings: fix|waive|stop — disposition for confirmed review findings; used verbatim when gate2 skipped, pre-selects the route when gate2 asks -->
test_fail_policy: halt <!-- intake on_test_fail: halt|proceed — what to do when tests stay red after config.recovery.test_fix_rounds; proceed commits anyway with red tests led in the report, never faked -->
pr: none               <!-- intake pr: none|open — open a PR after commit (skill fw-pr) -->
stages_skipped: none <!-- adaptive (config.adaptive): optional stages skipped for this feature, each with a one-line reason; restated at gate 1. `none` = full graph -->
tier_offset: standard <!-- auto-route (config.auto_route): feature difficulty read taken at intake — light|standard|heavy + one-line reason — shifts config.models up/down one rung for every spawn; restated at gate 1. `standard` = baseline map unchanged (also the value when auto_route is disabled) -->
base_ref:            <!-- feature-branch HEAD after the specs snapshot; review/test diff against this -->
hw_testbed: none     <!-- e.g. fw-comet02 — from pipeline config or gate 2 -->
hw_bay: none         <!-- e.g. 19 -->

## tasks
<!-- mirrored from tasks.md by the plan stage; statuses live here. gate-2
     fix tasks (F1..) and quick tasks (Q1) are appended here and get
     subspecs (specs/<slug>/tasks/<id>.md) like any other task. -->
| id | title | complexity | status | depends_on | parallel_ok |
|----|-------|------------|--------|------------|-------------|

## metrics
<!-- counters the orchestrator updates as events happen; sdd-quality
     aggregates them across features. keep the `key: n` shape. -->
verify_retries: 0
tasks_blocked: 0
ambiguities: 0
file_list_fixes: 0
findings_confirmed: 0
findings_rejected: 0
findings_waived: 0
gate1_reroutes: 0
gate2_reroutes: 0
test_failures: 0
merge_conflicts: 0

## amendments
<!-- spec decisions made after gate 1; amendments override spec.md where they conflict -->
<!-- A1 (<date>): <question> -> <decision> -->

## waived findings
<!-- confirmed review findings the user chose to ship anyway (gate 2) -->

## tests run
<!-- filled by the test stage: test, where (x86 / testbed+bay), result -->

## log
- <YYYY-MM-DD> feature initialized
