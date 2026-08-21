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

1. Query RAS for the supplied target. If its unprefixed name returns 404, try the
   canonical `lp-<name>` form. Do not guess that a `fw-*` nickname is an SSH host.
2. Record the canonical RAS name, labels, environment, controllers, and notes.
3. Query the authoritative drive inventory at
   `https://drives.app.purestorage.com/` for the target bay/slot. Its active
   **claim** or **deny** reservation controls whether a drive may be used;
   do not use RAS claims or active jobs as a proxy for a per-drive reservation.
4. If the user supplied a model number, use
   `https://drives.app.purestorage.com/decode` to decode it. For a questionable
   drive, use its serial number and bay in the drive inventory instead of relying
   on the old Google-sheet deny list.
5. Classify the platform and then read the appropriate reference below.
6. Report an active drive claim or deny before mutating that bay. A deny means do
   not use the bay. A claim means do not overlap work without the claimant's
   authorization. RAS activity can be relevant context, but is not the
   authoritative drive claim state.

Use the standard-library RAS topology resolver:

```bash
python3 scripts/resolve-testbed.py <testbed>
```

RAS is authoritative for connection topology. The Drives app is authoritative for
per-drive claims, denies, and model decoding. Do not infer HLOB, FlashArray, or
SSH user from the target's name.

## Route by requested action

| Task | Read after RAS classification |
|---|---|
| Classify a FlashArray testbed | [testbed-types/flasharray.md](testbed-types/flasharray.md) |
| Classify a FlashBlade testbed | [testbed-types/flashblade.md](testbed-types/flashblade.md) |
| Classify an Endurance testbed | [testbed-types/endurance.md](testbed-types/endurance.md) |
| Copy or update firmware; run a WSSD hardware pytest | [access-methods/pytest.md](access-methods/pytest.md), plus the testbed-type reference |
| Find remote controller/blade firmware logs | [access-methods/logs.md](access-methods/logs.md), plus the testbed-type reference |

## Safety boundary

- Read-only discovery first. Never change claims, reset a target, power-cycle a
  bay, copy firmware, or start a test unless the user asked for that action.
- Do not run generic `make cp` until the RAS topology has been translated into a
  reviewed target-specific copy command. Generic `config.mk` HLOB settings do not
  describe every testbed.
- For a hardware test, use the `fw-herdr-hw-test` skill after this routing step.
- Preserve the resolved platform, connection route, target bay/slot, and command
  log path in the final report.
