# Endurance / Hyperscaler

RAS: `hm_computenode`, labels `hyper:*`, `hyperscale:hydrogen`, often `hyper:chassis:endurance`, `split_node`. One CentOS host, no `-ct0/-ct1`; SSH `root@<hm_computenode>` via `-J root@<ras_name>`. Confirm host read-only before mutation.

- Slots from `PARTITIONED_SLOTS` (30 + bay).
- BMC: `env.BMC_IPMI_ADDR` (`https://<host>-bmc.dev.purestorage.com/`), creds in RAS.
- Logs: `/var/log/pure`; read ../access-methods/logs.md only for a log task.

Known failures (fix sections in `fw-fix-drives`):
- SSH rc 255, not pingable (thermal/panic) → §4.20 BMC power-cycle, user-driven
- Boots into lifeguard (extra `vmlinuz`) → §4.21
- VFIO loopback failure → §4.18 `TUNE_NVME_DISABLE_VFIO = 1` in RAS env
