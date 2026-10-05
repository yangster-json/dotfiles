# Firmware copy, update, and hardware pytest

Read the platform access method first. A successful local package build is not a
firmware installation, and `make cp` only stages files: it never flashes. Every
copy of new firmware needs an upgrade (`--update-fw` or `wssdtool upgrade`)
before the test exercises it.

Run `make cp` and testlauncher from your dev VM / workstation checkout, never
from the controller or blade. testlauncher reaches the target over SSH (through
`JUMP_HOST` for FlashBlade) and stages its own package there.

## Copy

Copy the built package through `make cp` and provide all topology values on the
command line. Do not modify `config.mk`, `top.mk`, or another repository file to
configure a testbed. A one-off transfer does not need Herdr; run it directly so
the shell owns and reports its exit status.

For a FlashBlade blade, override the normal jump-host copy target with the actual
SSH destination from RAS:

```bash
make cp UNIT_TEST=0 PY_CHECK=0 Q=1 \
  TESTBED=root@<blade> JUMP_HOST=<jump-host> HLOB=n CT0= CT1=
```

For a FlashArray, explicitly provide both controller endpoints:

```bash
make cp UNIT_TEST=0 PY_CHECK=0 Q=1 \
  JUMP_HOST=null HLOB=n CT0=<testbed>-ct0 CT1=<testbed>-ct1
```

For a single-host target with no `-ct0`/`-ct1` split (Endurance, HLOB), copy to
the one host:

```bash
make cp UNIT_TEST=0 PY_CHECK=0 Q=1 \
  TESTBED=<host> JUMP_HOST=null HLOB=y
```

`HLOB` only selects the copy route in `top.mk`: a non-`null` `JUMP_HOST` wins
(`cp_jmp`, `HLOB` ignored), then `HLOB=y` copies to `TESTBED`, else to `CT0` and
`CT1`. It does not change the firmware build or slot numbering. Use the same
variables with `cp_only` to copy without rebuilding.

Before executing, dry-run the exact command with `make -n cp` using the same
variables and verify its SSH endpoints. Use `--delete` only after reviewing the
remote destination and only when the user intends it.

If a transfer must outlive the current tool call, create a local wrapper script
and launch it with `herdr pane run <pane-id> bash <script-path>`; do **not** pass
a multiline script through `bash -lc`.

## Slot

Take the slot from RAS `env.PARTITIONED_SLOTS` or the controller's device
enumeration, not from a formula alone. Conventions to check against:

| Platform | Slot |
|---|---|
| FlashArray dual controller | `400 + bay` |
| FlashBlade (bays start at 1) | `400 + (bay - 1)` |
| Single-host HLOB | `30 + bay` |

A wrong slot fails with `MissingDeviceException: Unable to find any wssd devices`.
Example: FlashBlade bay 2 is slot 401 (FB bays start at 1); using `400 + bay`
gives 402, which matches no enumerated `phy_slot`. Source:
https://wiki.purestorage.com/spaces/PBU/pages/207848432/How+to+use+Firmware+Legend+Chassis
When unsure, list the controller's enumeration (`wssdtool ls`) and match its
slot column.

## Update and test

Run the pytest with `--testbed <RAS node>`, or `--server <host>` when the target
is not in RAS, and the verified slot. Add `--update-fw` only when the user
explicitly requested an update. Run it with `fw-hw-test`; record the label and
log.

To upgrade by hand instead, run on the resolved controller or blade:

```bash
cd ~/$USER/testlauncher/wssd-tools-test-<sha> && bin/wssdtool -b<bay> upgrade
```

A testlauncher package issue must be corrected locally before attempting the
remote update; copying firmware cannot fix local pytest discovery.
