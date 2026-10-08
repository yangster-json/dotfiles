# Remote firmware logs (read-only)

Logs still on a testbed. Use after RAS classification; keep the RAS route. Not Jenkins artifacts (`/logs/jobs/...`, `/mnt/tlogs/...`).

## Rules

- Read-only: no service restarts, mutating `wssdtool`, claim changes, power-cycles.
- Define `rssh` first: `rssh() { ssh -o BatchMode=yes -o ConnectTimeout=15 -J root@<ras_name> "$@"; }` (FlashBlade: `-J <jump-host>`; launchpad down: drop `-J`).
- `ls` archive names/retention before content search. Never recurse `/var/log`, `/logs`, or `/`.
- Bound searches to one log family + time window; `grep` plain, `zgrep` (or Python `gzip`) for `.gz`.
- Binary search only on a sparse ordered series with an established monotonic presence boundary; else coarse evenly spaced probes, then bounded search.
- No RAS / ambiguous: ≤2–3 shallow SSH probes, report uncertainty; still unclear → ask user. Don't carry one platform's paths/rotation to another.
- Report retention range searched, sources, exact lines, uncertainty. Absence in a sample ≠ never present; current inventory ≠ history.

| Platform | Connection | Root | Primary family |
|---|---|---|---|
| FlashArray | launchpad → `-ct0`/`-ct1` | `/var/log/purity` | `wssd.log*`, `wssd-structured.log*` |
| FlashBlade | jump → `root@ir<N>` | `/logs` | inspect first |
| Endurance | launchpad → host | `/var/log/pure` | `dfm.log*` (+ structured if present) |

## FlashArray

Search named controller, then peer if it matters: drive may be visible on one ct only, `wssdlog` may be disabled on one during PCIe/NVMe tests. Ct/drive timestamps only roughly synced. `wssdtool --bay <bay> ls` = current occupant only.

1. Inventory:
   ```bash
   rssh "$host" 'ls -1 /var/log/purity/wssd.log* | wc -l; ls -1tr /var/log/purity/wssd.log* | head -3; ls -1t /var/log/purity/wssd.log* | head -3; ls -1t /var/log/purity/wssd-device-dump* /var/log/purity/inventory_tool.log* 2>/dev/null | head -40'
   ```
   `scripts/purity.wssdlog.upstart` writes `wssd.log`, `wssd-structured.log`, `wssd-err.log`, `wssd-auto-triage.log` via `wssdtool --all dump debugtail` — all bays; correlate by `CH<n>.BAY<nn>`.
2. Sparse sources first (if present): `wssd-device-dumps.tar*` (periodic `dump device`; check members), `wssd-device-dump-all.log*`, `inventory_tool.log*`, `syslog*` (insert/PCIe/reset/service). Probe oldest/newest/evenly spaced; if serial absent, they only bound recent retention.
3. Hourly: `wssd.log-YYYYMMDDHH.gz`, `wssd-structured.log-YYYYMMDDHH.gz`; current interval plain. Narrow window first, then e.g.:
   ```bash
   rssh "$host" 'zgrep -H -i -C 4 -- "<serial>\|CH0.BAY04" /var/log/purity/wssd.log-YYYYMMDD{08,09,10}*.gz'
   rssh "$host" 'grep -H -i -- "<serial>" /var/log/purity/wssd.log'
   ```
   No unbounded all-archive globs.
4. For fw events search text + structured (JSON-like or legacy msgpack; `test/common/wct_trace_plot.py` reads both, gzip ok). Correlate `wssd-err.log*`, `wssd-auto-triage.log*`, `syslog*`.

## FlashBlade

Inventory one level of `/logs`, pick family. Hourly rotation ≈ **:17 past the hour** (wiki *The FlashBlade Log Downloader Script*, page 329775008) — FB only; near a boundary check both intervals. Verify filename timestamp convention (may be close/open time).

## Endurance

Shallow inventory `/var/log/pure`; `dfm.log*` first, then actual structured/error/system names. Derive naming/rotation from files present (not FA syntax). Sparse sources, then narrowed `dfm.log*` window.

## Serial/bay history ("when was X last in bay Y?")

Evidence order: current inventory → inventory/device-dump snapshots (coarse window) → syslog events → fw + structured logs → peer controller. If not provable, report:

```text
Last evidence of <serial> in CH0.BAY04: <ts/file/line>
First evidence of different occupant: <ts/file/line>
Replacement between: <start> and <end>
Sources searched: <families, retention range>
```

## Repo refs

`scripts/purity.wssdlog.upstart` (FA paths), `scripts/histogram_plot_generator.py` (hourly selection), `test/common/wct_trace_plot.py` (parsing), `scripts/determine_log_spam.py`, `scripts/vttune_processor.py` + `utils/manufacturing_tools/puressd/src/py/wssdtool/wssdtool_dump.py` (device-dumps tar), `utils/triage/jenkins_triage.py` (`/logs/jobs` = Jenkins, not controller).
