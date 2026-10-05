# FlashBlade access

RAS labels such as `flashblade` and notes/environment fields define the actual
route. Read `JUMP_HOST`, controller/blade fields, and `notes` rather than
constructing a host name.

Variants (all report `TESTLAUNCHER_PROFILE=iros_thor`):

| Variant | RAS signal | Jump host |
|---|---|---|
| Legend, tape room | label `wssd_legend`, `flashblade.thor` | `legend-wssd-fw-tape-r8` |
| Legend, C14 | name `lp-irp301-c02-fbN` | `irp301-c02` |
| Zeus/Thor | name `lp-fw-zeusNN` | `fw-zeus00` |

The jump host list is a fallback only; use RAS `env.JUMP_HOST` when available
(see ../fallbacks.md). Reference:
https://wiki.purestorage.com/spaces/PBU/pages/207848432/How+to+use+Firmware+Legend+Chassis

Typical Thor topology:

```text
FM / jump host -> blade
ssh -J <jump-host> root@<blade>
```

Take `<jump-host>` from RAS `env.JUMP_HOST` and `<blade>` from `controllers`
(or `notes`), then use exactly:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=15 -J <jump-host> root@<blade>
```

The blade's default `wssdtool` is often too old; activate
`/ssd/testlauncher-env/bin/activate` before running the copied `wssdtool`.

Confirm the blade identity with a shallow read-only command before transferring
files or running a test.

Copy with `TESTBED=root@<blade> JUMP_HOST=<jump-host>`; with a jump host,
`top.mk` ignores `HLOB`. Do not use `ir@<ras-name>` or a `make cp` that relies on
`config.mk` defaults.
