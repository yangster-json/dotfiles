---
name: triage-local-logs
description: WSSD firmware failure triage from test artifacts already on the local filesystem (build/wssd-testkit/artifacts) with NO Jira interaction — inventory artifacts, read pre-triage analysis, examine debug dumps, identify the primary failure, build a timeline, and report findings inline in chat. Use when asked to triage a local test failure, analyze a run's artifacts on disk, or investigate a failure without a ticket.
---

# WSSD Firmware Local Log Triage Rules

## Overview
This document provides a systematic approach to triaging WSSD firmware failures when
the test artifacts and logs are already available on the local filesystem. Unlike the
Jira-based triage flow, this rule does **not** interface with Jira — it neither fetches
tickets nor posts comments. The agent analyzes the failure directly from the artifacts
directory and reports findings inline in chat.

- **This Document Focus:** Software-level failure analysis from local artifacts
  - Analyzing firmware crashes, assertions, and errors
  - Understanding firmware log types and formats
  - Identifying root causes in firmware code
  - Reporting findings inline in chat (no Jira interaction)

## ⚠️ CRITICAL: Where to Find Logs

The logs for the failure being triaged are in the workspace at:

```
build/wssd-testkit/artifacts
```

This path is **relative to the current workspace root**. Always resolve it from the
workspace root the agent is operating in. If the directory does not exist or is empty,
stop and ask the user for the correct path instead of guessing.

### Typical layout inside `build/wssd-testkit/artifacts`
- Per-test-run subdirectories containing `fail/`, `pass/`, or similar folders
- `runner.stdout`, `runner.stderr`, `pytest_output.txt`
- `jenkins_logs/detail_*.log`
- `*_FAILED_debug_dump.log` / `*_debug_dump.log` — firmware event-log replays
- `pta_analysis_report`, `pta_logs/pta_report/*` — pre-triage analysis (if present)
- Per-drive firmware logs, telemetry dumps, backtraces

Use `ls`, `find`, and `grep` via the shell to enumerate and read these files. The
`view` tool works for in-workspace files; if it fails (for example because the
artifacts directory is a symlink or bind-mount to a non-workspace path), fall back
to shell tools (`cat`, `grep`, `zgrep`, `head`, `awk`).

**Shell note:** the examples below use `find` / `grep -r` rather than `**` globs,
because recursive `**` requires `shopt -s globstar` in bash and is not portable.
Prefer `find ... -exec` or `grep -r` when searching multiple levels of the
artifacts tree.

---

## ❌ Anti-Patterns (Do NOT Do These)

- ❌ Searching for Jira ticket IDs in the log tree — this rule has no Jira context
- ❌ Calling any Jira MCP tools (`jira_*`) — this flow is strictly local
- ❌ Posting or drafting Jira comments — output is inline chat only
- ❌ Guessing at alternate log locations when `build/wssd-testkit/artifacts` is present
- ❌ Spending more than 2–3 attempts trying to locate files; ask the user instead

---

## Core Triage Principles

### 1. Evidence-Based Analysis
- **Always** base conclusions on concrete evidence from logs, code, or data
- **Never** make assumptions without verification
- Quote specific log lines, error messages, or code snippets to support findings
- If evidence contradicts your hypothesis, stop and revise your analysis

### 2. Systematic Investigation
- Follow a structured approach from high-level to detailed analysis
- Document each step and what you found (or didn't find)
- Build a timeline of events when applicable
- Correlate findings across different data sources

### 3. Objective Reporting
- Focus on **identifying problems**, not proposing solutions (unless explicitly requested)
- Quantify confidence level in your analysis
- Clearly distinguish between facts, observations, and inferences
- Highlight any gaps or uncertainties in the analysis

---

## Step-by-Step Triage Process

### Step 1: Inventory the Artifacts Directory

Start by listing what is present under `build/wssd-testkit/artifacts`:

```bash
ls -la build/wssd-testkit/artifacts/
find build/wssd-testkit/artifacts/ -maxdepth 3 -type d
find build/wssd-testkit/artifacts/ -maxdepth 4 \
  \( -name "*.log" -o -name "*.out" -o -name "*.err" -o -name "*.txt" \) | head -40
```

Note any:
- Per-test-run directories and their `fail/` or `failure/` subfolders
- `*_FAILED_debug_dump.log` files (examined in Step 3 — **do not skip**)
- Pre-triage analysis outputs (`pta_analysis_report`, `pta_logs/pta_report/*`)
- Test harness outputs (`runner.stdout`, `runner.stderr`, `pytest_output.txt`)

If multiple test runs are present, ask the user which run to triage unless it is
obvious from directory naming (e.g., only one `fail/` directory exists).

### Step 2: Examine Pre-Triage Analysis (if available)

```bash
find build/wssd-testkit/artifacts -name pta_analysis_report -exec cat {} \;
find build/wssd-testkit/artifacts -path "*/pta_logs/pta_report/*" -type f -exec cat {} \;
```

What to look for:
- Automated failure classification
- Python stacktraces and error messages
- Identified patterns or known issues
- Suggested root causes

Pre-triage analysis is a starting point, not the final answer. Verify its claims
against the raw logs before adopting them.

### Step 3: Examine Debug Dump Logs (CRITICAL — DO NOT SKIP)

Debug dumps replay the firmware event log from boot and frequently reveal root
causes that are invisible in test-level logs.

```bash
# Find all debug dump logs in fail directories
find build/wssd-testkit/artifacts -path "*/fail/*debug_dump*.log"
find build/wssd-testkit/artifacts -path "*/fail/*FAILED_debug_dump*.log"

# Examine the debug dump (contains replayed firmware event log from boot)
cat <path-to-FAILED_debug_dump.log> | head -1000

# Boot-time warnings that indicate pre-existing drive issues
grep -E "\(warn\)|WARNING" <path-to-debug_dump.log> | head -100

# Metadata corruption warnings
grep -E "live.*!=.*scan|mismatch|corrupt" <path-to-debug_dump.log>
```

What debug dumps contain:
- `[REPLAY:...]` entries — firmware event log history replayed from boot
- Boot-time warnings about metadata mismatches or corruption
- Historical context showing what happened **before** the test ran
- Firmware state at time of failure

Why it matters: test-level failure logs often show **what** failed, not **why**. A
test may fail because of drive state corruption that pre-dates the test itself.

### Step 4: Identify the Primary Failure

For test-harness failures:

```bash
find build/wssd-testkit/artifacts -name runner.stdout     -exec cat {} \;
find build/wssd-testkit/artifacts -name runner.stderr     -exec cat {} \;
find build/wssd-testkit/artifacts -name pytest_output.txt -exec cat {} \;
find build/wssd-testkit/artifacts -path "*/jenkins_logs/detail_*.log" -exec cat {} \;

grep -rA 20 "Traceback (most recent call last)" build/wssd-testkit/artifacts --include="*.log"
grep -rA 10 -E "ERROR|FAILED|Exception"         build/wssd-testkit/artifacts --include="*.log"
```

For firmware failures:

```bash
# Watchdog / crash events
grep -riE "watchdog|FAULT ON CORE" build/wssd-testkit/artifacts --include="*.log"

# Assertion failures (fatal)
grep -r "\[ASSERT\]:" build/wssd-testkit/artifacts --include="*.log"

# Error-level messages
grep -r "(error)" build/wssd-testkit/artifacts --include="*.log"

# Media / flash errors
grep -riE "uncorrectable|high_ber|program_error|erase_error" \
  build/wssd-testkit/artifacts --include="*.log"
```

Extract: exact error message, timestamp, component/module, core/thread ID (for
firmware crashes), and the operation in progress at the time of failure.

### Step 5: Understand the Context

- For test failures, open the test file referenced by the stacktrace, read the test
  logic, and identify the expectations/assertions that were violated.
- For firmware failures, locate the source that generated the error (assertion line,
  log string, backtrace function names) and trace the code path leading to it.

### Step 6: Build a Timeline

Determine: when the operation started, when the failure occurred, what events
happened between those two points, and whether any warnings preceded the failure.
Correlate timestamps across multiple log files when the failure spans components.

Read the code to understand **which** log lines are meaningful — do not search for
strings you merely guess might be relevant.

### Step 7: Analyze Logs Systematically

Firmware log message prefixes:
- `(debug)` — LOGGER_DEBUG
- `(info)` — LOGGER_INFO
- `(warning)` — LOGGER_WARN
- `(error)` — LOGGER_ERROR (triggers watchdog)
- `(display)` — display messages
- `(bgs)` — background-service messages
- `(ltssm)` — PCIe link-state messages
- `[ASSERT]:` — assertion failures (fatal)
- `[TEST MARKER]:` — test markers
- `SBL:` / `MBL:` — secondary / main bootloader prefixes

Approach: start with `[ASSERT]` and `(error)`, search around the failure time, trace
the operation across components, look for anomalies and resource issues.

### Step 7a: Firmware-Specific Analysis

**Watchdog / crash:**
```bash
grep -iE "watchdog|FAULT ON CORE" <logs>
grep -B 50 "watchdog" <logs> | grep -E "\[ASSERT\]:|LOG_ERR"
grep -A 30 "Backtrace starting" <logs>
grep "CORE\[" <logs>
grep -B 100 "watchdog" <logs>
```
Focus on the **first** core to crash (usually lowest core ID). Recursive watchdogs
mean the handler itself crashed — investigate the first event, not subsequent ones.

**Media / flash errors:**
```bash
grep -iE "error_mask|uncorrectable|high_ber|program_error|erase_error" <logs>

# CRITICAL: extract complete flash location for EVERY failing drive
grep -iE "exception prog=.*block=.*die=" <logs>

# Block metadata context
grep -iE "injected_live_error|error_mask=|block_state=" <logs>
```
For each failing drive capture: CE/target, LUN/die, block, page, plane, address.
When multiple drives fail, document the full location for **all** of them — do not
stop after the first drive.

**Performance / hang:**
```bash
grep "core.*stuck" <logs>
```
Review WCT traces for incomplete operations and state-machine hangs; check for
resource exhaustion (allocation failures, queue-full, timeouts).

**Boot failures:**
```bash
grep -E "SBL:|MBL:" <logs>
grep -iE "init.*fail|startup.*error" <logs>
grep -iE "pcie|ddr|flash.*init" <logs>
```

### Step 8: Check for Known Patterns

Common firmware failure patterns:
1. **Assertion failure** — `[ASSERT]: file:line condition`; locate the assertion,
   understand the invariant that was violated.
2. **Watchdog timeout** — `FAULT ON CORE` + backtraces; firmware hung or overran;
   check the operation in progress and look for infinite loops.
3. **Recursive watchdog** — multiple watchdog events in sequence; investigate only
   the first.
4. **Multi-core crash** — backtraces from several cores; identify the first core to
   crash (usually lowest core ID).
5. **Media error cascade** — repeated uncorrectables in a short window; check
   whether errors localize to a specific block/die.
6. **Boot hang** — logs stop during init; examine last successful init step and any
   hardware errors.

General categories to consider: test environment / infrastructure, timing / race
conditions, resource exhaustion, configuration issues, code bugs.

### Step 9: Categorize the Failure

Choose one:
1. **Test Environment Issue** — testbed, infrastructure, or harness problem
2. **Firmware Bug** — firmware code defect
3. **Test Bug** — test code or logic defect
4. **Configuration Issue** — incorrect settings or tunables
5. **Known Issue** — previously identified (reference the prior finding if known)
6. **Cannot Determine** — insufficient information

Firmware-specific sub-categories: Watchdog/Crash, Media Error, PCIe Error,
Performance, Boot Failure, Background Service Issue.


---

## Output Format (Inline Chat Only)

When the analysis is complete, report findings **in chat** using the following
sections, in this order. Do **not** create a report file, and do **not** post to
Jira.

```
## Summary
One paragraph: what was investigated and the overall conclusion.

## Failure Details
- What Failed: <component, test, or operation>
- When: <timestamp or time range>
- Where: <environment, drive, controller, test run>
- Error Message: <exact error or failure reason>

## Evidence
Quoted log excerpts with file paths and (where possible) line numbers. Use fenced
code blocks. Include only the lines that directly support the conclusion.

## Timeline
- <timestamp> — <event>
- <timestamp> — <event>
- <timestamp> — failure occurred

## Root Cause
Explanation of why the failure occurred, supported by the evidence above. If the
root cause cannot be determined with confidence, state the leading hypotheses and
what evidence is missing.

## Category
<Test Environment / Firmware Bug / Test Bug / Configuration / Known Issue /
Cannot Determine>  —  plus firmware sub-category if applicable.

## Confidence
<High / Medium / Low> — brief justification.
```

Only include a **Recommendations** section if the user explicitly asked for one.

---

## Firmware Log Types Reference

### 1. Event Logs (evtlog)
Primary firmware logging; circular buffer in DDR. Types include STRING,
META_DATA, WATCHDOG, FCC_WATCHDOG, INDEX. Key fields: `clocks_lo`/`clocks_hi`,
`cpu_id`, `type`, `sequence_number`.

### 2. Watchdog Logs
Captured on firmware crash or hang. Contains ~45 s of event-log history plus
backtraces from all cores. Triggered by assertion failures, infinite loops, or
unhandled exceptions.

### 3. Serial / UART Logs
Real-time boot/operation output. Prefixes: `(info)`, `(warning)`, `(error)`,
`(debug)`, `(bgs)`, `SBL:`, `MBL:`.

### 4. Telemetry Logs
OCP (NVMe log pages 0x07/0x08) and WSSD vendor-specific event logs. Error
events, media errors, performance data, statistics.

### 5. FCC Logs (Flash Controller Core — Xtensa, not ARM)
Printf buffer and trace logs organized per-LUN context. Key fields:
`fcc_context`, `pc`, `tag`.

### 6. WCT Trace Logs (Work Context Tracker)
Detailed I/O operation traces. State transitions, timing, operation parameters,
callback results. Key fields: `start_time`, `end_time`, `type`, `state`,
`metadata_index`.

### 7. Backtraces
Format: `CORE[core_id/thread_id]: Backtrace starting at SP=...`
Contains SP, FP, LR, ELR, SPSR, and the call stack with function names/offsets.

---

## Special Considerations

**Firmware watchdog / crashes:** identify the crashing core (`CORE[XX/XX]`), find
the assertion or LOG_ERR that triggered it, analyze all core backtraces, focus on
the first core to crash, watch for recursive watchdogs, review the last ~100
lines before the watchdog event.

**Timeouts:** identify what timed out; check whether it completed after the
timeout; look for blocking operations or resource contention.

**Performance issues:** measure actual vs expected; look for bottlenecks;
correlate with system load.

**Intermittent failures:** check frequency and pattern; look for timing-dependent
behavior; consider race conditions.

**Boot failures:** identify where in the boot sequence the failure occurred;
check bootloader (`SBL:` / `MBL:`) logs; look for DDR / PCIe / Flash init
failures; check PLP status.

---

## Important Guidelines

### Do's
- ✅ Base all conclusions on concrete evidence
- ✅ Quote specific log lines and error messages
- ✅ Trace through code to know which log patterns to search for
- ✅ Build a timeline for complex failures
- ✅ Correlate findings across multiple sources
- ✅ State confidence level; highlight uncertainties
- ✅ Check backtraces from **all** cores (multi-core crashes are common)
- ✅ For media errors: extract full flash location (`exception prog=.*block=.*die=`)
  for **every** failing drive
- ✅ Always examine `*_FAILED_debug_dump.log` before concluding root cause
- ✅ Look for boot-time warnings (e.g., `live X != scan X`) indicating pre-existing
  issues

### Don'ts
- ❌ Do not call any Jira tools or post Jira comments — this rule is local-only
- ❌ Do not create report files unless the user explicitly asks
- ❌ Do not change any code (per project AGENTS.md) unless explicitly prompted
- ❌ Do not assume without verification
- ❌ Do not ignore contradictory evidence
- ❌ Do not propose solutions unless the user asked
- ❌ Do not stop after one failing drive when multiple drives failed
- ❌ Do not conclude root cause from test-level failure logs alone — check debug
  dumps
- ❌ Do not focus on the last watchdog in a recursive-watchdog scenario — the
  first one is the root cause
- ❌ Do not confuse FCC logs (Xtensa) with ARM core logs

---

## Next Steps After Triage

After delivering the inline analysis, stop. Do **not**:
- Open, modify, or comment on any Jira ticket
- Create, edit, or delete source code
- Write summary or report files

If the user follows up with a request (e.g., "file a bug", "suggest a fix",
"write a test to reproduce"), handle it at that point — but not preemptively.
