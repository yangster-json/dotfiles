# FlashBlade

Route = RAS `env.JUMP_HOST` + blade from `controllers` (else `notes`); never construct names. All variants `TESTLAUNCHER_PROFILE=iros_thor`.

| Variant | RAS signal | Jump host (fallback only, if RAS is down) |
|---|---|---|
| Legend tape room | label `wssd_legend`, `flashblade.thor` | `legend-wssd-fw-tape-r8` |
| Legend C14 | `lp-irp301-c02-fbN` | `irp301-c02` |
| Zeus/Thor | `lp-fw-zeusNN` | `fw-zeus00` |

```bash
ssh -o BatchMode=yes -o ConnectTimeout=15 -J <jump-host> root@<blade>
```

- Confirm blade identity read-only before transfers/tests.
- Blade's default `wssdtool` is often old: `source /ssd/testlauncher-env/bin/activate` then use the copied one.
- testlauncher: `--testbed <RAS name>` (RAS supplies jump host + profile); `--server <blade>` only if unregistered.
- Copy: `TESTBED=root@<blade> JUMP_HOST=<jump-host>`. Not `ir@<ras-name>`, not `config.mk` defaults.
- Ref: https://wiki.purestorage.com/spaces/PBU/pages/207848432/How+to+use+Firmware+Legend+Chassis
