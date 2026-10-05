# Fallbacks when RAS is down or the target is unregistered

Use only when `scripts/resolve-testbed.py` reports `RAS unreachable` or
`RAS target not found`. This is a snapshot (verified against RAS 2026-10-01),
not a source of truth: tell the user you are using a fallback, confirm the
route with a read-only probe, and re-check RAS once it is back.

## Jump hosts (FlashBlade)

| Site | Jump host | Blades | RAS names |
|---|---|---|---|
| Legend, tape room | `legend-wssd-fw-tape-r8` | `ir1`..`ir10` | `lp-fw-legendNN` (e.g. `lp-fw-legend02` → `ir2`) |
| Legend, C14 | `irp301-c02` | `ir1`..`ir7` | `lp-irp301-c02-fbN` (e.g. `lp-irp301-c02-fb3` → `ir3`) |
| Zeus/Thor | `fw-zeus00` | `ir6` etc. | `lp-fw-zeusNN` (e.g. `lp-fw-zeus06` → `ir6`) |

```bash
ssh -o BatchMode=yes -o ConnectTimeout=15 -J <jump-host> root@<blade>
```

All three report `TESTLAUNCHER_PROFILE=iros_thor` in RAS. With `--server`,
testlauncher does not read `JUMP_HOST` from RAS; pass `--jump-host <jump-host>`
and `--profile iros_thor` yourself.

## Name → RAS entry

| Name shape | RAS entry | Physical host(s) |
|---|---|---|
| `fw-<name>` (FA) | `lp-fw-<name>` | `fw-<name>-ct0`, `fw-<name>-ct1` |
| `hyper-<id>` (split node) | `lp-hyper-<id>-node<N>` only; bare and `lp-` forms 404 | `hyper-<id>` (one host) |
| Legend/Zeus blade | see table above | `ir<N>` behind the jump host |

A `-node<N>` entry is a slot partition of one physical host, not a separate
testbed. Each node has its own claim and `PARTITIONED_SLOTS`. Known example:
`hyper-cb653a-16` → node0 slots 30–37, node1 38–45, node2 46–53 (bays 16–23).

## Unregistered or unreachable: `--server`

Symptom of an unregistered `--testbed`: testlauncher's RAS lookup fails with
`AttributeError: 'NoneType' object has no attribute 'json'`.

```bash
drun build/wssd-testkit/testlauncher --server <host> --slot <slot> --user $USER \
  [--jump-host <jump-host> --profile iros_thor] <tests>
```

`--server` skips RAS: no claim check, no `JUMP_HOST`, and no
`PARTITIONED_SLOTS`. On a split node that means testlauncher does not know the
partition and power-cycle steps may hit **every** bay on the host. Prefer
`--testbed lp-<name>-node<N>` whenever RAS is up; use `--server` there only if
the user accepts that risk.

## SSH

The usual `~/.ssh/config` wildcards route these without per-host entries:
`*-ct0`, `*-ct1`, `fw*`, `hw*`, `lp*` → `root` with `id_rsa_pureroot`;
`legend*`, `ir*`, `*zeus*` → user `ir` with `id_rsa_iros_root`. Check
`ssh -G <host> | grep -E '^(user|identityfile|proxyjump) '` before relying on it;
if your config lacks them, pass `-l root -i <key>` explicitly.
