---
name: fw-herdr-hw-test
description: Safely run and monitor a long WSSD hardware pytest in an independent Herdr pane. Use with drun/testlauncher hardware tests that may outlive the current Pi tool call.
compatibility: Requires HERDR_ENV=1, Herdr CLI, drun, and a firmware checkout.
---

# Herdr Hardware Test

Use this after the `fw-hw-pytest` target preflight passes. Herdr protects the
test from cancellation of Pi's initiating tool call; it does not protect it from
closing its own tab/pane or sending that pane Ctrl-C.

## Launch

Require Herdr and no existing test on the target:

```bash
test "${HERDR_ENV:-}" = 1
pgrep -af 'testlauncher.*<test-name>'
```

Create an unfocused sibling pane within the current tab, and record the
returned `pane_id`. Do not open a new tab. Name the pane so it is
identifiable in the pane list:

```bash
current_pane=$(herdr pane current --current)
herdr pane split <current-pane-id> --direction right --cwd "$PWD" --no-focus
herdr pane rename <pane-id> "<test-name>-<node>-bay<bay>"
```

Run a saved Bash wrapper, not the pane's unspecified default shell and not
an inline `bash -lc` script. Some Herdr versions do not preserve a multiline
`-c` argument reliably; that can run the body but lose the final exit marker,
leaving `wait-output` blocked. Record both the shell status and test report:
testlauncher can return zero even when its report is `RESULT: FAIL`.

Create the wrapper locally, then pass its path as a normal positional argument:

```bash
script_path=/tmp/run-<test-name>-<node>-bay<bay>.sh
cat >"$script_path" <<'EOF'
#!/usr/bin/env bash
set -o pipefail
log_path=/tmp/<test-name>-<node>-bay<bay>.log
drun build/wssd-testkit/testlauncher \
  --testbed <node> --slot <slot> --user "$USER" --repeat 1 \
  wssd.<test-name> 2>&1 | tee "$log_path"
shell_status=${PIPESTATUS[0]}
test_result=$(grep -E "RESULT: (PASS|FAIL)" "$log_path" | tail -1 || true)
printf "\nTESTLAUNCHER_EXIT=%s\n%s\n" "$shell_status" "$test_result" | tee -a "$log_path"
EOF
chmod 700 "$script_path"
herdr pane run <pane-id> bash "$script_path"
```

The marker must contain a numeric status. If it is blank or absent, do not wait
indefinitely: inspect the saved log and check whether the underlying process is
still active.

`RESULT: FAIL`, missing `RESULT`, or a nonzero shell status is failure. Add
`--update-fw` only when explicitly requested. Run several hardware tests
sequentially; do not run conflicting tests concurrently.

## Monitor

Default: wait and report final PASS/FAIL in this turn. Herdr's timeout is in
milliseconds and is capped near 2,147,483,647; use 1,800,000 (30 minutes) per
wait:

```bash
herdr pane wait-output <pane-id> --match TESTLAUNCHER_EXIT= \
  --source recent-unwrapped --timeout 1800000
```

A `wait-output` timeout is **not** a test result. Immediately inspect both the
saved log and process state. If the wrapper/testlauncher remains active, repeat
the 30-minute wait and continue this loop until its numeric exit marker appears.
Do not give an intermediate test step, expected injected fault, or a running
status as the final result.

```bash
herdr pane process-info --pane <pane-id>
rg -n 'RESULT:|TESTLAUNCHER_EXIT=|Test Passed|Test Failed|FAILED|FAILURES|Traceback' \
  /tmp/<test-name>-<node>-bay<bay>.log | tail -100
```

Herdr may reap a tab/pane as soon as its command exits. Therefore the saved log
is authoritative when `pane read`, `wait-output`, or `process-info --pane
<pane-id>` reports `pane_not_found`:

```bash
rg -n 'RESULT:|TESTLAUNCHER_EXIT=|Test Passed|Test Failed|FAILED|FAILURES|Traceback' \
  /tmp/<test-name>-<node>-bay<bay>.log | tail -100
```

A nonzero `TESTLAUNCHER_EXIT`, `RESULT: FAIL`, `Test Failed`, `FAILED`, or
`FAILURES` is a failure even when diagnostics/artifact collection also fails.
Always report that failure promptly with its log path; artifact-collection errors
must not mask the primary test failure. If no exit marker exists after checking
both log and process state, report that the test is still unconfirmed and include
the tab/pane ID plus log path. Do not claim completion solely because a pane
disappeared.

Return immediately only when the user explicitly asks for background/no-wait
execution. Always report node, controller, bay, slot, pane ID, log path, and final
`RESULT` plus `TESTLAUNCHER_EXIT`; `RESULT` is the pass/fail authority.

## Stop

Only on explicit request:

```bash
herdr pane send-keys <pane-id> ctrl+c
```

Then confirm termination in the log or with:

```bash
herdr pane process-info --pane <pane-id>
```

Never close unrelated tabs/panes or stop Herdr.
