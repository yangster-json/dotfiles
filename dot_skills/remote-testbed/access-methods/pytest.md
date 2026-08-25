# Firmware copy, update, and hardware pytest

Read the platform access method first. A successful local package build is not a
firmware installation.

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

For example, `fw-zeus06` resolves to:

```bash
make cp UNIT_TEST=0 PY_CHECK=0 Q=1 \
  TESTBED=root@ir6 JUMP_HOST=fw-zeus00 HLOB=n CT0= CT1=
```

For a FlashArray, explicitly provide both controller endpoints:

```bash
make cp UNIT_TEST=0 PY_CHECK=0 Q=1 \
  JUMP_HOST=null HLOB=n CT0=<testbed>-ct0 CT1=<testbed>-ct1
```

For Endurance, use its HLOB-style target:

```bash
make cp UNIT_TEST=0 PY_CHECK=0 Q=1 \
  TESTBED=<testbed> JUMP_HOST=null HLOB=y
```

Before executing, dry-run the exact command with `make -n cp` using the same
variables and verify its SSH endpoints. Use `--delete` only after reviewing the
remote destination and only when the user intends it.

If a transfer must outlive the current tool call, create a local wrapper script
and launch it with `herdr pane run <pane-id> bash <script-path>`; do **not** pass
a multiline script through `bash -lc`.

## Update and test

Run the pytest using the RAS testbed name and correct slot/bay mapping. Add
`--update-fw` only when the user explicitly requested an update. Run it inside a
Herdr pane using the `fw-herdr-hw-test` workflow and record the pane ID and log.

A testlauncher package issue must be corrected locally before attempting the
remote update; copying firmware cannot fix local pytest discovery.
