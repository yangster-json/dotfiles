---
name: fw-herdr-hw-test
description: Run and monitor long WSSD hardware tests safely in a dedicated Herdr tab. Use when asked to run a firmware pytest, drun/testlauncher test, or hardware test on a testbed/bay, especially when the test may outlive the current agent request.
compatibility: Requires Herdr, HERDR_ENV=1, drun, and a firmware checkout.
---

# Firmware Herdr Hardware Test

Run long hardware tests in a dedicated Herdr tab so cancelling the initiating
Pi tool call does not terminate the test.

## Preconditions

Verify this Pi instance is inside Herdr before controlling it:

```bash
test "${HERDR_ENV:-}" = 1
```

If this fails, tell the user that no Herdr-managed pane is available. Do not
attempt to create or control Herdr tabs.

Before starting a test:

1. Confirm the requested testbed, bay, and test name.
2. Use the firmware hardware-test workflow to determine the correct slot.
   Flash Array bays use `slot = bay + 400`; bay 4 is slot 404.
3. Check whether the user wants the current firmware upgraded. Build/copy the
   test artifacts before creating the test tab when an updated tools package is
   required.
4. Do not start another test if the target bay already has a live testlauncher
   run. Inspect its process or its existing Herdr pane first.

## Create a Background Test Tab

Keep the user's current tab focused. Create a tab in the current workspace and
capture the JSON response:

```bash
herdr tab create \
  --workspace "$HERDR_WORKSPACE_ID" \
  --cwd "$PWD" \
  --label "<test-name>-<testbed>-bay<bay>" \
  --no-focus
```

Parse the returned tab and root-pane IDs from the JSON response. Treat IDs as
opaque; do not derive them from tab order or labels.

## Launch the Test

Use `herdr pane run` on the newly created root pane. Always persist output to a
unique local log and preserve the testlauncher's exit code through `pipefail`:

```bash
herdr pane run <pane-id> \
  "set -o pipefail; \
   drun build/wssd-testkit/testlauncher \
     --testbed <testbed> --slot <slot> --user \"$USER\" --repeat 1 \
     wssd.<test-name> 2>&1 | tee /tmp/<test-name>-<testbed>-bay<bay>.log; \
   test_status=\${PIPESTATUS[0]}; \
   printf '\\nTESTLAUNCHER_EXIT=%s\\n' \"\$test_status\"; \
   exit \"\$test_status\""
```

Only add `--update-fw` when the user requested an upgrade and artifacts were
built with `FW_TEST_9999=debug`.

Report immediately:

- Herdr tab and pane IDs
- testbed, bay, and slot
- exact log path
- that closing the test tab or sending Ctrl-C to its pane will stop the test

Cancelling this agent's monitoring command or the initiating Pi request does
not stop the test, because it runs in the independent Herdr pane.

## Monitor Safely

Read the test pane without changing UI focus:

```bash
herdr pane read <pane-id> --source recent-unwrapped --lines 160
```

To wait for completion, wait for the marker emitted by the launch wrapper:

```bash
herdr pane wait-output <pane-id> \
  --match "TESTLAUNCHER_EXIT=" \
  --source recent-unwrapped \
  --timeout <milliseconds>
```

Then read the final test report and the saved log:

```bash
herdr pane read <pane-id> --source recent-unwrapped --lines 240
```

Use the test report's `RESULT: PASS` or `RESULT: FAIL` and
`TESTLAUNCHER_EXIT=` as the authoritative completion evidence. For a failure,
quote the failed case and exact error. Inspect downloaded artifacts or debug
dumps when needed.

## Cancellation and Cleanup

- Do not close the created tab after a completed test unless the user asks.
- Do not send `ctrl+c` or `herdr pane close` to its pane unless the user
  explicitly requests cancellation.
- If the user asks to stop the test, target only the created pane:

  ```bash
  herdr pane send-keys <pane-id> ctrl+c
  ```

  Confirm process exit with `herdr pane read`; do not infer cancellation from
  the input delivery alone.
- Do not stop the Herdr server or close unrelated panes, tabs, workspaces, or
  sessions.
