# Firmware copy, update, hw pytest

Read the platform ref first. A local build isn't an install; `make cp` only stages, never flashes — every new copy needs `--update-fw` or `wssdtool upgrade` before testing. Run `make cp` and testlauncher from the dev VM checkout, never on the controller/blade.

## Copy

All topology on the command line; never edit `config.mk`/`top.mk`/repo files. One-off copy runs directly (no Herdr).

```bash
# FlashBlade
make cp UNIT_TEST=0 PY_CHECK=0 Q=1 TESTBED=root@<blade> JUMP_HOST=<jump-host> HLOB=n CT0= CT1=
# FlashArray
make cp UNIT_TEST=0 PY_CHECK=0 Q=1 JUMP_HOST=null HLOB=n CT0=<testbed>-ct0 CT1=<testbed>-ct1
# Single host (Endurance, HLOB)
make cp UNIT_TEST=0 PY_CHECK=0 Q=1 TESTBED=<host> JUMP_HOST=null HLOB=y
```

`top.mk` route: non-`null` `JUMP_HOST` wins (`cp_jmp`, HLOB ignored) → `HLOB=y` copies to `TESTBED` → else `CT0`+`CT1`. HLOB doesn't affect build or slots. Same vars work with `cp_only` (no rebuild).

- Dry-run `make -n cp` with same vars; verify SSH endpoints.
- `--delete` only after reviewing remote dest and if user intends it.
- Copy must outlive the tool call → write a local script, `herdr pane run <pane-id> bash <script>`; no multiline `bash -lc`.

## Slot

From RAS `env.PARTITIONED_SLOTS` or controller enumeration (`wssdtool ls` slot column), not formula alone:

| Platform | Slot |
|---|---|
| FlashArray | `400 + bay` |
| FlashBlade (bays from 1) | `400 + (bay - 1)` (bay 2 → 401) |
| Single-host HLOB | `30 + bay` |

Wrong slot → `MissingDeviceException: Unable to find any wssd devices`.

## Update + test

Run via `fw-hw-test` with `--testbed <RAS node>` (or `--server <host>` if unregistered) and verified slot; record label + log. `--update-fw` only if user asked. Manual upgrade on controller/blade:

```bash
cd ~/$USER/testlauncher/wssd-tools-test-<sha> && bin/wssdtool -b<bay> upgrade
```

Fix testlauncher package/pytest-discovery issues locally first; copying fw can't fix them.
