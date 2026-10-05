# Endurance / Hyperscaler access

RAS signals: `hm_computenode` set, labels `hyper:*`, `hyperscale:hydrogen`,
often `hyper:chassis:endurance` and `split_node`. One CentOS host, no
`-ct0`/`-ct1`; SSH as `root@<hm_computenode>`.

- Split node: the host is shared by several `lp-<host>-node<N>` RAS entries.
  Use the node that owns the slot for `--testbed`; copy and SSH to the host.
- Slots come from `PARTITIONED_SLOTS` (30 + bay convention).
- BMC: `env.BMC_IPMI_ADDR` (`https://<host>-bmc.dev.purestorage.com/`);
  credentials in RAS notes/env. A BMC power action hits **all** nodes, so
  every node must be claimed first.
- Logs live under `/var/log/pure`; determine exact filenames before searching
  (see access-methods/logs.md).

Confirm the host with a shallow read-only probe before mutation.

## Known failures

Fixes are in `fw-fix-drives`:

| Symptom | Section |
|---|---|
| SSH rc 255, host not pingable (thermal shutdown / panic) | §4.20 Endurance testbed unreachable — BMC power-cycle, user-driven |
| Boots into lifeguard (extra `vmlinuz`) | §4.21 Endurance testbed stuck in lifeguard |
| VFIO loopback failure | §4.18 VFIO on — `TUNE_NVME_DISABLE_VFIO = 1` in RAS env |
