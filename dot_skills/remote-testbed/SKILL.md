---
name: remote-testbed
description: RAS-first router for remote WSSD testbeds (name, bay/slot, firmware copy/update, hw pytest, controller/blade access, remote logs). Resolves platform and route before any SSH or mutation.
---

# Remote Testbed

Read only the references for the classified platform and task (usually one type + one task file); never preload the rest.

## First: resolve + check reservations

Before SSH, `make cp`, testlauncher, fw update, or log search:

1. `python3 <this skill's dir>/scripts/resolve-testbed.py <name>` (no `--json`; output already has platform, hosts, ready `ssh` route, jump host, slots, claim, notes): path is next to this SKILL.md, not in the cwd; don't search for it. Tries `<name>`, `lp-<name>`, `lp-hw-`/`lp-fw-<name>`, `lp-<name>-node<N>`. `RAS unreachable` → [fallbacks.md](fallbacks.md). `RAS target not found` → stop: tell user, ask for platform + hosts (don't offer example host names); give no command with guessed hosts (`<name>-ct0`, `lp-<name>`, jump host), not even as an example; testlauncher then needs `--server <host>`. Never treat a `fw-*` nickname as an SSH host.
2. `lp-<host>-node<N>` = slot partition of one host (any platform): SSH/`make cp`/logs → the host; `--testbed` → node whose `partitioned_slots` has the slot; BMC/power hits all partitions → claim every node (resolver lists siblings).
3. `shared_testbed` in output → RAS claim isn't yours: testlauncher needs `--user $USER --slot <slot>` (else `testbed <name> claimed to <claimant>`); follow RAS notes for per-drive claims.
4. https://drives.app.purestorage.com/ is authoritative for per-drive claim/deny (by serial+bay; model → `/decode`). Deny = don't use; claim = no overlap without claimant's OK. Report before mutating.

## Route

Default: the resolver's `ssh` line = through the RAS launchpad, `ssh -J root@<ras_name> root@<host>` (every RAS record, partition nodes included, is a launchpad; never bare `ssh <host>`). Use the same `-J` for `scp`/`rsync`/`make cp`. Hosts take `root` + `~/.ssh/id_rsa_pureroot` (on every engineer VM). FlashBlade: resolver `jump_host` instead. Launchpad down → direct SSH from the dev VM ([fallbacks.md](fallbacks.md)). testlauncher connects directly (its `--jump-host` assumes `ir@`, FlashBlade only).

BMC/console creds live in RAS `notes`/`BMC_IPMI_*`: resolver masks them (best-effort for free-text notes); `--json` only for a requested BMC/console action; never paste them anywhere. Never infer platform, HLOB, or SSH user from the name.

## testlauncher command

`drun build/wssd-testkit/testlauncher --testbed <ras_name> --slot <slot> --user "$USER" --repeat 1 wssd.<test>` (Endurance: the partition node; `--server <host>` only if not in RAS; add `--update-fw` only when asked). Executing it, dry run, upgrade → `fw-hw-test`.

Slot: FlashArray `400 + bay`; FlashBlade `400 + (bay - 1)` (bays from 1); Endurance/single host = the bay's entry in `partitioned_slots` (`30 + bay`). Wrong slot → `MissingDeviceException: Unable to find any wssd devices`.

## Platform refs (resolver `platform`)

FlashArray → [testbed-types/flasharray.md](testbed-types/flasharray.md); FlashBlade → [testbed-types/flashblade.md](testbed-types/flashblade.md); Endurance → [testbed-types/endurance.md](testbed-types/endurance.md). Copy/update fw → [access-methods/pytest.md](access-methods/pytest.md); remote logs → [access-methods/logs.md](access-methods/logs.md). Slot-only or route-only questions need no ref.

## Hand off (pass resolved topology)

- hw pytest / `--update-fw` → `fw-hw-test`; one build → many testbeds → `fw-multi-testbed-cp`
- drive state, overrides, deny, endurance host down → `fw-fix-drives`; SBL/bootrom/MISSING DEVICE → `fw-recover-missing-drives`; bad_plane_map, "Not a block device" → `fw-cleanup-drive`
- UECC → `fw-bad-block-triage`; PLP plot → `fw-plot-power-test`; Jira/Jenkins failure → `fw-debug-triage`, `fw-pcie-triage`

## Safety

- Read-only first: no claim changes, resets, power-cycles, copies, or tests unless asked.
- No generic `make cp`: build a target-specific command from RAS (`config.mk` defaults don't fit every testbed).
- Report platform, route, bay/slot, log path.
