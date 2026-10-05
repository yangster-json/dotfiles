---
name: remote-testbed
description: RAS-first router for remote WSSD testbed work. Use for a remote testbed name, bay or slot, firmware package copy/update, hardware pytest execution, controller or blade access, or firmware-log investigation. Resolves the actual platform and access path before any SSH or mutating action.
---

# Remote Testbed

This is the single entry point for remote firmware testbeds. Detailed platform
workflows are ordinary references, not nested skills, so they remain hidden until
the target and task are known.

## Required first step: classify and check drive reservations

Before SSH, `make cp`, `drun`, testlauncher, firmware update, or log searches:

1. Run `scripts/resolve-testbed.py <name>`. It tries `<name>`, `lp-<name>`,
   then `lp-<name>-node<N>`. Do not guess that a `fw-*` nickname is an SSH host.
2. Record the canonical RAS name, physical hosts, labels, environment, and notes.
   A `-node<N>` entry is a slot partition of one physical host, not a separate
   testbed: SSH and `make cp` go to the host in `hm_computenode`/`controllers`,
   while `--testbed` takes the node whose `PARTITIONED_SLOTS` contains the slot.
   Each node has its own claim; BMC or power actions affect every node.
3. Check `shared_testbed` in the resolver output (RAS labels `shared_testbed` /
   `wssd_shared_testbed`, or claimant `shared_testbed`). On a shared testbed the
   RAS claim is not yours: pass `--user $USER --slot <slot>` to testlauncher
   (otherwise it raises `testbed <name> claimed to <claimant>`), and follow the
   RAS notes for per-drive claiming.
4. RAS down or no form resolves: say so and use [fallbacks.md](fallbacks.md).
   Get or confirm the topology with the user and pass `--server <host>`.
5. Query the authoritative drive inventory at
   `https://drives.app.purestorage.com/` for the target bay/slot. Its active
   **claim** or **deny** reservation controls whether a drive may be used;
   do not use RAS claims or active jobs as a proxy for a per-drive reservation.
6. If the user supplied a model number, use
   `https://drives.app.purestorage.com/decode` to decode it. For a questionable
   drive, use its serial number and bay in the drive inventory instead of relying
   on the old Google-sheet deny list.
7. Classify the platform by the RAS signals below, then read the appropriate reference below.
8. Report an active drive claim or deny before mutating that bay. A deny means do
   not use the bay. A claim means do not overlap work without the claimant's
   authorization. RAS activity can be relevant context, but is not the
   authoritative drive claim state.

Use the standard-library RAS topology resolver (summary by default; `--json`
for raw records):

```bash
python3 scripts/resolve-testbed.py <testbed>
```

RAS is authoritative for connection topology when the target is registered; it
exits with `RAS target not found` or `RAS unreachable` otherwise.

Credentials (BMC user/password, console access) are in the RAS testbed `notes`
and `env` (`BMC_IPMI_*`). The resolver masks them; read them with `--json` only
when the user asked for a BMC/console action, and never paste them into reports,
Jira, or memory. The Drives app is authoritative for
per-drive claims, denies, and model decoding. Do not infer HLOB, FlashArray, or
SSH user from the target's name.

## Classify by RAS signals

| Signal in RAS | Platform | Reference |
|---|---|---|
| 2 `controllers`, `PS_HA_CONTROLLER0/1` env | FlashArray, dual controller | flasharray.md |
| label `flashblade` + `env.JUMP_HOST` | FlashBlade blade (Legend: label `wssd_legend`; Zeus: jump `fw-zeus00`) | flashblade.md |
| `hm_computenode` set, labels `hyper:*` / `hyperscale:hydrogen` | Hyperscaler / Endurance chassis, one CentOS host, often `split_node` | endurance.md |

Never classify from the name alone; names are only a fallback hint.

## Route by requested action

| Task | Read after RAS classification |
|---|---|
| Classify a FlashArray testbed | [testbed-types/flasharray.md](testbed-types/flasharray.md) |
| Classify a FlashBlade testbed | [testbed-types/flashblade.md](testbed-types/flashblade.md) |
| Classify an Endurance testbed | [testbed-types/endurance.md](testbed-types/endurance.md) |
| Copy or update firmware; run a WSSD hardware pytest | [access-methods/pytest.md](access-methods/pytest.md), plus the testbed-type reference |
| Find remote controller/blade firmware logs | [access-methods/logs.md](access-methods/logs.md), plus the testbed-type reference |
| RAS down or target unregistered | [fallbacks.md](fallbacks.md) |

## Hand off to fw-skills

After classification, hand the resolved topology (RAS name, physical hosts,
jump host, slot, shared/claim state) to the matching fw-skills workflow. They
live in `pure-experimental/fw-skills` (`skills/<group>/<name>/SKILL.md`); load
the installed skill by name, or read it from a local clone if not installed.

| Task | fw-skill |
|---|---|
| Run a hardware pytest / `--update-fw` | `fw-hw-test` |
| Copy one build to several testbeds | `fw-multi-testbed-cp` |
| Fix drive state, overrides, deny, endurance host down | `fw-fix-drives` |
| SBL / bootrom / MISSING DEVICE | `fw-recover-missing-drives` |
| Orphan bad_plane_map, "Not a block device" | `fw-cleanup-drive` |
| UECC / bad block on a bay | `fw-bad-block-triage` |
| PLP power plot | `fw-plot-power-test` |
| Jira/Jenkins failure on this testbed | `fw-debug-triage`, `fw-pcie-triage` |

## Safety boundary

- Read-only discovery first. Never change claims, reset a target, power-cycle a
  bay, copy firmware, or start a test unless the user asked for that action.
- Do not run generic `make cp` until the RAS topology has been translated into a
  reviewed target-specific copy command. Generic `config.mk` HLOB settings do not
  describe every testbed.
- For a hardware test, use `fw-hw-test` after this routing step.
- Preserve the resolved platform, connection route, target bay/slot, and command
  log path in the final report.
