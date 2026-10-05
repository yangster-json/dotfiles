---
name: fw-hw-test
description: Run WSSD hardware pytests by default through detached `hwtest`, optionally watched from a Herdr observer pane, with completion reported through bg-cmd-runner so the agent stays usable. Use for drun/testlauncher hardware tests and to list, watch, or kill such runs.
compatibility: Requires `~/.pi/agent/bin/hwtest`, drun, a built firmware checkout, and pi-subagents with the bg-cmd-runner agent. Herdr is optional (observer pane only).
---

# Background hardware test

Start with the `remote-testbed` skill. It resolves the testlauncher target,
controller or blade route, copy command, slot, and drive claim/deny state; do
not infer them from a testbed name. The test runs detached (`setsid`, no
terminal), so closing a pane, the Pi session, or the watcher never stops it.
Only `hwtest kill` does.

## Layout

| Role | What |
|---|---|
| Runner | `hwtest start` → detached wrapper → `drun --env-file` → testlauncher, output to log |
| Tag | `HWTEST_ID=<label>` passed into the container; `kill` finds processes by it |
| Observer | Herdr pane running `tail -F <log>` (`--view` / `hwtest view`); safe to close |
| Completion | bg-cmd-runner runs `hwtest wait <label>`; Pi notifies on finish |
| State | `~/.local/state/hwtest/<label>/` (`meta.json`, `test.log`, `exit`, `run.sh`) |

## Launch

Run from the firmware checkout:

```bash
hwtest start --testbed <node> --slot <slot> --test <test-name> --view [--update-fw] [-- <extra testlauncher args>]
```

- `--test` accepts `wssd.<name>` or `<name>`.
- `--update-fw` only when the user explicitly requested it.
- `start` refuses if the testbed/slot already has a testlauncher (`--force`
  overrides only with user approval). Run tests sequentially per slot.
- Label defaults to `<test>-<node>-s<slot>-<MMDD-HHMMSS>`; record it with the log path.

## Monitor (default: non-blocking)

Immediately launch the watcher and return control to the user:

```
subagent({
  agent: "bg-cmd-runner",
  async: true,
  timeoutMs: 86400000,
  task: '<BACKGROUND_TEST_RUNNER_JSON>{"cwd":"<repo>","command":["<abs path to ~/.pi/agent/bin/hwtest>","wait","<label>"],"iterations":1,"label":"<label>-watch","stop_on_failure":true}</BACKGROUND_TEST_RUNNER_JSON>'
})
```

- Use the absolute `hwtest` path (`$HOME/.pi/agent/bin/hwtest`, expanded) in `command`.

- Always pass `timeoutMs` (default subagent deadline is 30 min). `hwtest wait`
  gives up after `--max-hours` (24) with exit 124 and leaves the test running.
- Do not sleep/poll; the completion notification arrives in chat. Then read the
  `HWTEST <label>: ...` line and key lines from the iteration log it names.
- Only block (`hwtest wait <label>` directly) if the user asks to wait.

`hwtest wait` exit codes: `0` PASS, testlauncher code on FAIL, `130` killed,
`125` unconfirmed (missing exit marker or verdict), `124` wait window elapsed.

## Inspect

```bash
hwtest ls [--running]      # label, status, testbed/slot, elapsed, log
hwtest status <label>      # summary + tagged in-container processes
hwtest view <label>        # reopen the Herdr observer pane (or prints tail -F cmd)
rg -n 'RESULT:|TESTLAUNCHER_EXIT=|Test Passed|Test Failed|FAILED|FAILURES|Traceback' <log> | tail -100
```

## Kill

Only on user request:

```bash
hwtest kill <label>
```

- Sends SIGINT to the tagged in-container processes, waits 60s.
- If they exit, reports the result; then confirm the slot is released.
- If still alive, it prints manual SIGTERM → SIGKILL steps with the exact PIDs.
  Relay those to the user; do not escalate without approval.
- Never kill the `docker exec` client or the wrapper: docker does not forward
  signals, and killing the client orphans testlauncher inside the container.

## Result rules

- Pass requires `TESTLAUNCHER_EXIT=0` plus `RESULT: PASS` or testlauncher's
  final `---------------- Test Passed ----------------` banner. This branch of
  testlauncher may emit only the banner, not a `RESULT:` line.
- `RESULT: FAIL`, final `Test Failed` banner, or nonzero exit is failure even
  when other subtests passed or artifact collection also fails. Do not treat
  expected in-test `FAILED` diagnostics as the final verdict.
- `UNCONFIRMED` (missing exit marker or exit 0 without a final verdict):
  report with label and log; do not claim pass or fail.
- Report node, slot/bay, label, log path, final banner/`RESULT` and
  `TESTLAUNCHER_EXIT`.
- Never close unrelated Herdr tabs/panes or stop Herdr.
