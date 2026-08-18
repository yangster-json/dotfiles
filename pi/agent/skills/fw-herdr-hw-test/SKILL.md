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

Create an unfocused tab and record the returned `root_pane.pane_id`:

```bash
herdr tab create --workspace "$HERDR_WORKSPACE_ID" --cwd "$PWD" \
  --label "<test-name>-<node>-bay<bay>" --no-focus
```

Run through Bash, not the pane's unspecified default shell. Record both the
shell status and test report: testlauncher can return zero even when its report
is `RESULT: FAIL`.

```bash
herdr pane run <pane-id> bash -lc '
set -o pipefail
log_path=/tmp/<test-name>-<node>-bay<bay>.log
drun build/wssd-testkit/testlauncher \
  --testbed <node> --slot <slot> --user "$USER" --repeat 1 \
  wssd.<test-name> 2>&1 | tee "$log_path"
shell_status=$?
test_result=$(grep -E "RESULT: (PASS|FAIL)" "$log_path" | tail -1 || true)
printf "\nTESTLAUNCHER_EXIT=%s\n%s\n" "$shell_status" "$test_result" | tee -a "$log_path"
'
```

`RESULT: FAIL`, missing `RESULT`, or a nonzero shell status is failure. Add
`--update-fw` only when explicitly requested. Run several hardware tests
sequentially; do not run conflicting tests concurrently.

## Monitor

Default: wait and report final PASS/FAIL in this turn. Herdr's timeout is in
milliseconds and is capped near 2,147,483,647; use 1,800,000 (30 minutes) per
wait, then repeat if the test is still active:

```bash
herdr pane wait-output <pane-id> --match TESTLAUNCHER_EXIT= \
  --source recent-unwrapped --timeout 1800000
```

Herdr may reap a tab/pane as soon as its command exits. Therefore the saved log
is authoritative when `pane read`, `wait-output`, or `process-info --pane
<pane-id>` reports `pane_not_found`:

```bash
rg -n 'RESULT:|TESTLAUNCHER_EXIT=|Test Passed|Test Failed|Traceback' \
  /tmp/<test-name>-<node>-bay<bay>.log | tail -80
```

If no exit marker exists, report that the test is still unconfirmed and include
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
