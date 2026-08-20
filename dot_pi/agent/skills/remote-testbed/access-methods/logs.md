# Remote firmware logs

This workflow is read-only. Use it only after `remote-testbed` has classified the
testbed in RAS and supplied the platform, endpoint, controller/blade mapping, and
connection route. Preserve that RAS-derived route throughout the investigation.


# Remote Testbed Log Search

Use this skill for **read-only** searches of logs still resident on a testbed. It is
not Jira/tlog artifact triage: Jenkins artifacts such as `/logs/jobs/...` and
`/mnt/tlogs/...` are separate sources.

## Safety and scope

- Begin read-only. Do not restart services, run `wssdtool` actions that mutate state,
  change claims, or power-cycle a bay.
- Use `ssh -o BatchMode=yes -o ConnectTimeout=15`.
- Inspect archive names and retention with `ls` before searching file contents.
  Never recursively search an entire remote filesystem.
- Bound content searches to an identified log family and time window. Use `grep` for
  current/plain logs and `zgrep` (or Python `gzip`) for rotated `.gz` files.
- Do not assume a serial is present continuously. A binary search is valid only after
  a sparse source establishes a monotonic installation/removal interval; otherwise
  use coarse, evenly spaced probes followed by a bounded search of the resulting
  interval.
- Report the searched retention range, sources checked, exact matching lines, and
  uncertainty. Absence in a sampled archive is not proof of absence from all time.

## Classify the target first

**Look up the testbed in RAS before SSH.** Use RAS metadata to establish the platform,
testbed host or management endpoint, controller/blade mapping, and any connection
requirements. Treat this as the authoritative classification source; use SSH only
afterward to confirm that the expected host and log roots are reachable.

Use the configured RAS client, URL, or internal workflow available to the current
environment. Do not invent a RAS endpoint. If RAS is unavailable or returns
ambiguous metadata, say so, perform at most two or three shallow read-only SSH
probes to identify the platform, and report the uncertainty. Do not infer one
platform's paths or rotation convention from another.

| Platform | Connection | Controller/device log root | Primary log family |
|---|---|---|---|
| FlashArray | SSH to a hostname ending `-ct0` or `-ct1` | `/var/log/purity` | `wssd.log*`, `wssd-structured.log*` |
| FlashBlade | SSH to the FM, then `ssh root@ir<N>` | `/logs` on the blade | inspect the blade's log family first |
| Endurance | SSH to its testbed host | `/var/log/pure` | `dfm.log*` and its structured counterpart if present |

If classification remains unclear after the RAS lookup and shallow probes, stop and
ask the user for the platform or exact host path. Do not claim, reconfigure, or
otherwise change a testbed just to inspect it.

### FlashArray controller visibility

Search the named controller first, then check its peer when the evidence matters.
A drive can be visible on only one controller, and `wssdlog` may be disabled on one
controller during PCIe/NVMe testing. Treat controller and drive timestamps as
approximately correlated, not perfectly synchronized.

```bash
ssh <testbed>-ct0 'wssdtool --bay <bay> ls'
ssh <testbed>-ct1 'wssdtool --bay <bay> ls'
```

`wssdtool ls` is a current-inventory observation only; it does not establish a past
bay-to-serial mapping.

## FlashArray workflow

### 1. Inventory rather than scan

```bash
host=<testbed>-ct0
ssh "$host" '
  ls -1 /var/log/purity/wssd.log* | wc -l
  ls -1tr /var/log/purity/wssd.log* | head -3
  ls -1t  /var/log/purity/wssd.log* | head -3
  ls -1t /var/log/purity/wssd-device-dump* /var/log/purity/inventory_tool.log* 2>/dev/null | head -40
'
```

The in-repo FlashArray logger definition is
`scripts/purity.wssdlog.upstart`. It writes:

- `/var/log/purity/wssd.log`
- `/var/log/purity/wssd-structured.log`
- `/var/log/purity/wssd-err.log`
- `/var/log/purity/wssd-auto-triage.log`

It invokes `wssdtool --all dump debugtail`, so these logs aggregate all bays. Use the
bay token (normally `CH<n>.BAY<nn>`) to correlate a matching serial to a slot.

### 2. Use sparse historical sources first

Before opening hundreds or thousands of hourly logs, inspect these only if present:

- `wssd-device-dumps.tar*` — periodic device-dump archives created by
  `wssdtool ... dump device`; inspect archive member names/content before relying on
  them as inventory history.
- `wssd-device-dump-all.log*` — recent device-dump snapshots.
- `inventory_tool.log*` — sparse inventory-tool observations.
- `syslog*` — host-side insertion, PCIe, reset, and service events.

Probe the oldest, newest, and several evenly spaced sparse snapshots for the serial
and bay. Once a snapshot establishes a continuous presence/absence boundary, binary
search that *specific* ordered series. If the snapshots do not contain the serial,
use them only to bound recent retention; do not pretend they prove an earlier removal.

### 3. Narrow hourly logs

FlashArray hourly archive names normally use the label:

```text
wssd.log-YYYYMMDDHH.gz
wssd-structured.log-YYYYMMDDHH.gz
```

The active/current interval can be plain (uncompressed). The naming convention is
also used by `scripts/histogram_plot_generator.py`. First construct a narrow date
range from sparse evidence, syslog events, or a user-provided time range, then search
only that interval.

```bash
# Exact serial in a known hourly archive
ssh "$host" 'zgrep -H -i -- "<serial>" /var/log/purity/wssd.log-YYYYMMDDHH.gz'

# Exact serial in current plain log
ssh "$host" 'grep -H -i -- "<serial>" /var/log/purity/wssd.log'

# Correlate a matching serial with the requested bay in a small interval
ssh "$host" 'zgrep -H -i -C 4 -- "<serial>\|CH0.BAY04" \
  /var/log/purity/wssd.log-YYYYMMDD{08,09,10}*.gz'
```

Do not use an unbounded glob spanning every historical archive. A short explicit list
or a generated list confined to an established interval is acceptable.

### 4. Search the right representation

Search both text and structured families when the question is about firmware events
rather than just host-side text. Structured records may be JSON-like; legacy records
can include msgpack test markers. The in-repo reader at
`test/common/wct_trace_plot.py` handles both plain and gzip input.

Correlate relevant results with:

- `wssd-err.log*` and `wssd-auto-triage.log*` for high-level error context;
- `syslog*` for host, PCIe, and service events;
- `wssdtool --bay <bay> ls` for the current mapping only.

## FlashBlade workflow

1. SSH to the FlashBlade FM, then the relevant blade as `root@ir<N>`.
2. Inventory one level of `/logs`; identify the relevant blade log family before
   searching contents.
3. The hourly log rotation boundary is approximately **17 minutes after the hour**.
   Do not map a wall-clock event to a `HH:00` archive as on FlashArray. For an event
   near a boundary, inspect the preceding and following rotated intervals.
4. Confirm the actual filename timestamp convention on the blade; it may encode the
   interval close/open rather than the event hour.
5. Keep searches bounded to the identified log family and a time window.

The 17-minute convention is documented in the internal wiki page *The FlashBlade Log
Downloader Script* (page 329775008). It is platform-specific and must not be applied
to FlashArray or Endurance.

## Endurance workflow

1. Inventory `/var/log/pure` shallowly.
2. Locate `dfm.log*` first, then inspect for a structured companion and error/system
   logs with the actual names found on that host.
3. Establish archive naming and rotation from the files present before building a time
   range. Do not assume FlashArray's `wssd.log-YYYYMMDDHH.gz` syntax.
4. Use sparse inventory/device-dump sources when available, then search only the
   narrowed `dfm.log*` window.

## Serial/bay historical lookup strategy

For “when was serial X last in bay Y?” use this evidence order:

1. Current `wssdtool`/platform inventory: establishes only the current occupant.
2. Historical inventory and device-dump snapshots: locate a coarse installation or
   replacement window.
3. System logs: identify insertion/removal/reset events in that coarse window.
4. Primary firmware log and structured log: find the last serial/bay evidence and
   surrounding context.
5. Peer controller: confirm or explain controller-specific visibility.

Report a bounded interval when exact last presence cannot be proven, for example:

```text
Last evidence of <serial> in CH0.BAY04: <timestamp/file/line>
First subsequent evidence of a different occupant: <timestamp/file/line>
Therefore the replacement occurred between: <start> and <end>
Sources searched: <families and retention range>
```

## Repository reference points

- `scripts/purity.wssdlog.upstart` — FlashArray WSSD logger paths and producer.
- `scripts/histogram_plot_generator.py` — hourly `wssd-structured.log-%Y%m%d%H.gz`
  selection; current interval is uncompressed.
- `test/common/wct_trace_plot.py` — structured JSON-like and legacy msgpack marker
  parsing, with gzip support.
- `scripts/determine_log_spam.py` — `/var/log/purity` and `wssd.log` defaults.
- `scripts/vttune_processor.py` and
  `utils/manufacturing_tools/puressd/src/py/wssdtool/wssdtool_dump.py` —
  `wssd-device-dumps.tar*` provenance.
- `utils/triage/jenkins_triage.py` — `/logs/jobs/...` is Jenkins artifact storage,
  not a remote controller's firmware-log root.

## Do not do

- Do not recursively search `/var/log`, `/logs`, or a filesystem root.
- Do not scan every rotated hourly log before checking sparse sources and retention.
- Do not call an arbitrary membership search a binary search.
- Do not conflate a log archive's filename hour with FlashBlade's event interval.
- Do not confuse remote controller logs with Jenkins test artifacts.
- Do not claim a drive was never installed simply because the current inventory or a
  recent snapshot does not show it.
