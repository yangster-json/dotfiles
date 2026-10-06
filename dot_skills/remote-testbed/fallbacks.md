# Fallbacks (RAS unreachable / target not found)

Snapshot verified vs RAS 2026-10-01, not truth: tell user, confirm route with a read-only probe, recheck RAS later.

## FlashBlade jump hosts

| Site | Jump host | Blades | RAS names |
|---|---|---|---|
| Legend tape room | `legend-wssd-fw-tape-r8` | `ir1`..`ir10` | `lp-fw-legendNN` (`lp-fw-legend02`→`ir2`) |
| Legend C14 | `irp301-c02` | `ir1`..`ir7` | `lp-irp301-c02-fbN` (`-fb3`→`ir3`) |
| Zeus/Thor | `fw-zeus00` | `ir6` etc. | `lp-fw-zeusNN` (`lp-fw-zeus06`→`ir6`) |

`ssh -o BatchMode=yes -o ConnectTimeout=15 -J <jump-host> root@<blade>`. All use `TESTLAUNCHER_PROFILE=iros_thor`; with `--server`, pass `--jump-host <jump> --profile iros_thor` yourself.

## Name → RAS entry

| Name | RAS entry | Physical host(s) |
|---|---|---|
| `fw-<name>` (FA) | `lp-fw-<name>` | `fw-<name>-ct0`, `-ct1` |
| `hyper-<id>` (split) | `lp-hyper-<id>-node<N>` only (bare/`lp-` 404) | `hyper-<id>` |
| Legend/Zeus blade | table above | `ir<N>` behind jump |

Example split: `hyper-cb653a-16` → node0 slots 30–37, node1 38–45, node2 46–53 (bays 16–23).

## `--server`

Unregistered `--testbed` fails: `AttributeError: 'NoneType' object has no attribute 'json'`.

```bash
drun build/wssd-testkit/testlauncher --server <host> --slot <slot> --user $USER \
  [--jump-host <jump> --profile iros_thor] <tests>
```

`--server` skips RAS: no claim check, `JUMP_HOST`, or `PARTITIONED_SLOTS` → on a split node power-cycle may hit **every** bay. Prefer `--testbed lp-<name>-node<N>` when RAS is up; `--server` there only if user accepts risk.

## SSH config

Wildcards: `*-ct0`, `*-ct1`, `fw*`, `hw*`, `lp*` → `root` + `id_rsa_pureroot`; `legend*`, `ir*`, `*zeus*` → `ir` + `id_rsa_iros_root`. Verify `ssh -G <host> | grep -E '^(user|identityfile|proxyjump) '`; else pass `-l root -i <key>`.
