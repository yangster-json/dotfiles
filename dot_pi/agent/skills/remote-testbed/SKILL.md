---
name: remote-testbed
description: RAS-first router for remote WSSD testbed work. Use for a remote testbed name, bay or slot, firmware package copy/update, hardware pytest execution, controller or blade access, or firmware-log investigation. Resolves the actual platform and access path before any SSH or mutating action.
---

# Remote Testbed

This is the single entry point for remote firmware testbeds. Detailed platform
workflows are ordinary references, not nested skills, so they remain hidden until
the target and task are known.

## Required first step: classify in RAS

Before SSH, `make cp`, `drun`, testlauncher, firmware update, or log searches:

1. Query RAS for the supplied target. If its unprefixed name returns 404, try the
   canonical `lp-<name>` form. Do not guess that a `fw-*` nickname is an SSH host.
2. Record the canonical RAS name, labels, environment, controllers, notes, claim,
   and active jobs.
3. Classify the platform and then read the appropriate reference below.
4. If the target is claimed or has active work, report that before mutating it.

Use the standard-library resolver:

```bash
python3 scripts/resolve-testbed.py <testbed>
```

RAS is authoritative for the connection topology. Do not infer HLOB, FlashArray,
or SSH user from the target's name.

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
