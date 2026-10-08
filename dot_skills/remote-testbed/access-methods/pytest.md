# Firmware copy, update, hw pytest

Read the platform ref first. A local build isn't an install; `make cp` only stages, never flashes. Upgrade (`--update-fw` or `wssdtool upgrade`) only when the user asks; build with `FW_TEST_9999=debug` first (dev version `test` fails testlauncher's version check). Run `make cp` and testlauncher from the dev VM checkout, never on the controller/blade.

## Copy

All topology on the command line; never edit `config.mk`/`top.mk`/repo files. One-off copy runs directly (no Herdr).

```bash
# FlashBlade
make cp UNIT_TEST=0 PY_CHECK=0 Q=1 TESTBED=root@<blade> JUMP_HOST=<jump-host> CT0= CT1=
# FlashArray (launchpad; one RAS controller endpoint per run)
make cp UNIT_TEST=0 PY_CHECK=0 Q=1 JUMP_HOST=root@<ras_name> TESTBED=<controller0>
make cp_only UNIT_TEST=0 PY_CHECK=0 Q=1 JUMP_HOST=root@<ras_name> TESTBED=<controller1>
# Single host (Endurance; launchpad)
make cp UNIT_TEST=0 PY_CHECK=0 Q=1 JUMP_HOST=root@<ras_name> TESTBED=<host>
# Launchpad down (direct)
make cp UNIT_TEST=0 PY_CHECK=0 Q=1 JUMP_HOST=null HLOB=n CT0=<controller0> CT1=<controller1>   # FA
make cp UNIT_TEST=0 PY_CHECK=0 Q=1 JUMP_HOST=null HLOB=y TESTBED=<host>                        # single host
```

`top.mk` route: non-`null` `JUMP_HOST` wins (`cp_jmp.$(TESTBED)`, one target; `HLOB`/`CT0`/`CT1` ignored) → `HLOB=y` copies to `TESTBED` → else `CT0`+`CT1`. HLOB doesn't affect build or slots. Same vars work with `cp_only` (no rebuild).

- Dry-run `make -n cp` with same vars; verify SSH endpoints.
- Every `cp`/`cp_only` rsyncs with `--delete` (no opt-out): inspect `/root/<local-user>/testlauncher` on the target first.
- Copy must outlive the tool call → write a local script, `herdr pane run <pane-id> bash <script>`; no multiline `bash -lc`.

## Slot

Use the slot rule in SKILL.md; confirm with RAS `PARTITIONED_SLOTS` or the `wssdtool ls` slot column.

## Update + test

Run via `fw-hw-test` with `--testbed <RAS node>` (or `--server <host>` if unregistered) and verified slot; record label + log. `--update-fw` only if user asked. Manual upgrade on controller/blade (`<local-user>` = dev-VM `$USER`, not the remote one):

```bash
cd /root/<local-user>/testlauncher/wssd-tools-test-<sha> && bin/wssdtool -b<bay> upgrade
```

Fix testlauncher package/pytest-discovery issues locally first; copying fw can't fix them.
