---
name: remote-testbed
description: RAS-first router for remote WSSD testbeds (name, bay/slot, firmware copy/update, hw pytest, controller/blade access, remote logs). Resolves platform and route before any SSH or mutation.
---

# Remote Testbed

Single entry point. Read only the references matching the classified platform and requested task (usually one type + one task file); never preload the rest.

## First: resolve + check reservations

Before SSH, `make cp`, `drun`/testlauncher, fw update, or log search:

1. `python3 scripts/resolve-testbed.py <name> [--json]` — tries `<name>`, `lp-<name>`, `lp-<name>-node<N>`. Exits `RAS target not found` / `RAS unreachable` → say so, use [fallbacks.md](fallbacks.md), confirm topology with user, pass `--server <host>`. Never guess a `fw-*` nickname is an SSH host.
2. Record canonical RAS name, physical hosts, labels, env, notes. `-node<N>` = slot partition of one host: SSH/`make cp` → host in `hm_computenode`/`controllers`; `--testbed` → node whose `PARTITIONED_SLOTS` has the slot. Each node has own claim; BMC/power hits all nodes.
3. `shared_testbed` in output (labels `shared_testbed`/`wssd_shared_testbed`, or claimant `shared_testbed`): RAS claim isn't yours → testlauncher needs `--user $USER --slot <slot>` (else `testbed <name> claimed to <claimant>`); follow RAS notes for per-drive claiming.
4. Drive reservations: https://drives.app.purestorage.com/ is authoritative for per-drive **claim**/**deny** (not RAS claims/jobs, not the old Google-sheet deny list; look up by serial+bay). Model number → `/decode`. Report any claim/deny before mutating: deny = don't use; claim = no overlap without claimant's OK.
5. Classify (below), read the reference.

Credentials (BMC/console) are in RAS `notes`/env `BMC_IPMI_*`; resolver masks them. Use `--json` only for a requested BMC/console action; never paste into reports/Jira/memory. Don't infer HLOB, FlashArray, or SSH user from the name.

## Classify by RAS signals (never by name)

| RAS signal | Platform | Read |
|---|---|---|
| 2 `controllers`, `PS_HA_CONTROLLER0/1` env | FlashArray dual-ct | [testbed-types/flasharray.md](testbed-types/flasharray.md) |
| label `flashblade` + `env.JUMP_HOST` (Legend: `wssd_legend`; Zeus: jump `fw-zeus00`) | FlashBlade blade | [testbed-types/flashblade.md](testbed-types/flashblade.md) |
| `hm_computenode`, labels `hyper:*`/`hyperscale:hydrogen` | Endurance/Hyperscaler, one CentOS host, often `split_node` | [testbed-types/endurance.md](testbed-types/endurance.md) |

Task refs (plus type ref): copy/update fw or hw pytest → [access-methods/pytest.md](access-methods/pytest.md); remote fw logs → [access-methods/logs.md](access-methods/logs.md).

## Hand off

Pass resolved topology (RAS name, hosts, jump host, slot, shared/claim state) to the fw-skill (installed by name, or `pure-experimental/fw-skills/skills/<group>/<name>/SKILL.md`):

| Task | Skill |
|---|---|
| hw pytest / `--update-fw` | `fw-hw-test` |
| one build → many testbeds | `fw-multi-testbed-cp` |
| drive state, overrides, deny, endurance host down | `fw-fix-drives` |
| SBL / bootrom / MISSING DEVICE | `fw-recover-missing-drives` |
| orphan bad_plane_map, "Not a block device" | `fw-cleanup-drive` |
| UECC / bad block | `fw-bad-block-triage` |
| PLP power plot | `fw-plot-power-test` |
| Jira/Jenkins failure here | `fw-debug-triage`, `fw-pcie-triage` |

## Safety

- Read-only first. No claim changes, resets, bay power-cycles, fw copy, or test start unless asked.
- No generic `make cp`: translate RAS topology into a reviewed target-specific command; `config.mk` HLOB defaults don't fit every testbed.
- Report resolved platform, route, bay/slot, and command log path.
