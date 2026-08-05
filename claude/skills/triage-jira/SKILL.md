---
name: triage-jira
description: WSSD firmware Jira ticket triage — the full systematic method for FAIL-xxxxx / FW-xxxxx failure tickets: deriving the /mnt/tlogs path from the ticket TITLE (not the ticket number), inventorying artifacts, examining *_FAILED_debug_dump.log, classifying watchdogs, assertions, media/flash errors, PCIe and boot failures, and writing the Jira triage comment in the required format. Use whenever asked to triage, investigate, or root-cause a firmware Jira ticket, or when a FAIL-/FW- ticket id appears in the request.
---

# WSSD Firmware Jira Ticket Triage Rules

## Overview
This document provides a systematic approach to triaging WSSD firmware-related Jira tickets. It focuses on software-level failure analysis including firmware crashes, assertions, media errors, and performance issues.

- **This Document Focus:** Software-level failure analysis
  - Analyzing firmware crashes, assertions, and errors
  - Understanding firmware log types and formats
  - Identifying root causes in firmware code

## ⚠️ CRITICAL: How to Find Logs (Read This First!)

**Log paths do NOT contain JIRA ticket numbers!**

The log location is derived from the JIRA ticket TITLE, not the ticket number. You MUST access the JIRA ticket first to get the log path information.

### Log Path Construction

| Ticket Title Component | Example | Maps To |
|------------------------|---------|---------|
| Jenkins host | `fwjenkins2` | `/mnt/tlogs/fwjenkins2/...` |
| Job name | `master_jenkins2-wssd.io.puffin-wssd.e2e_dp_hydrogen` | `.../jobs/<job-name>/...` |
| Build number | `87` | `.../<build-number>/` |

**Full example:**
- Ticket: FAIL-1013803
- Title: `fwjenkins2 master_jenkins2-wssd.io.puffin-wssd.e2e_dp_hydrogen - 87 lp-hw-hgp2b-06-node1`
- Log path: `/mnt/tlogs/fwjenkins2/jobs/master_jenkins2-wssd.io.puffin-wssd.e2e_dp_hydrogen/87/`

### Log File System Notes

- Logs are typically mounted via NFS at `/mnt/tlogs`
- A symlink `/tlogs -> /mnt/tlogs` may or may not exist
- Always check both paths if one doesn't work
- Verify mount with: `mount | grep tlogs` or `ls /mnt/tlogs`

---

## ❌ Anti-Patterns (Do NOT Do These)

- ❌ `grep -r "FAIL-XXXXXXX" /tlogs/` - Ticket IDs are NOT in log paths
- ❌ `find /tlogs -name "*XXXXXXX*"` - Will never find anything
- ❌ Searching random directories hoping to find logs
- ❌ Spending more than 2-3 attempts trying to guess log locations

**If you don't know the log path after 2 attempts, STOP and ask the user for the JIRA ticket title.**

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

### Step 0: Access the JIRA Ticket First (CRITICAL)

**Before searching for logs, you MUST access the JIRA ticket to get log location information.**

1. **Open the JIRA ticket in browser:**
   - URL pattern: `https://jira.purestorage.com/browse/FAIL-XXXXXXX`
   - Use the `open-browser` tool or ask user to provide ticket details

2. **From the JIRA ticket title, extract:**
   - Jenkins host (e.g., `fwjenkins2`)
   - Job name (e.g., `master_jenkins2-wssd.io.puffin-wssd.e2e_dp_hydrogen`)
   - Build number (e.g., `87`)

3. **Construct log path:**
   - Pattern: `/mnt/tlogs/<jenkins-host>/jobs/<job-name>/<build-number>`
   - Example: `/mnt/tlogs/fwjenkins2/jobs/master_jenkins2-wssd.io.puffin-wssd.e2e_dp_hydrogen/87`

**DO NOT search for ticket IDs in log directories - they are not stored that way!**

### If JIRA Access is Unavailable

If you cannot access JIRA directly (API returns 401/403, or browser not available):

1. **Ask the user** to provide:
   - The JIRA ticket title (contains jenkins host, job name, build number)
   - OR the JIRA ticket description
   - OR the Jenkins job URL directly

2. **Example prompt to user:**
   > "I cannot access JIRA directly. Could you please provide the ticket title or
   > description for FAIL-XXXXXXX? I need to extract the Jenkins job name and
   > build number to locate the logs."

---

### Step 1: Gather Initial Context

**Examine the Jira ticket:**
- Read the ticket description, summary, and any comments
- Identify the failure type, environment, and affected components
- Note any labels, priority, or severity indicators
- Check for related tickets or duplicates

**Key questions to answer:**
- What is the reported problem?
- When did it occur? (timestamp, build number, version)
- Where did it occur? (environment, testbed, array, controller)
- What was the expected vs actual behavior?
- Is this a new issue or a regression?

### Step 2: Locate and Inventory Available Data

**Identify data sources:**
- Log files (test logs, system logs, application logs)
- Core dumps or crash reports
- Test output files (stdout, stderr, pytest output)
- Configuration files or tunables
- Pre-triage analysis reports (PTA, automated analysis)
- Code repositories (test code, product code)

**Create an inventory:**
```bash
# List available log directories and files
ls -la /path/to/logs/
find /path/to/logs/ -name "*.log" -o -name "*.out" -o -name "*.err" | head -20

# Check for pre-triage analysis
cat /path/to/pta_analysis_report
cat /path/to/pta_logs/pta_report/*
```

### Step 2.5: Examine Debug Dump Logs (CRITICAL - DO NOT SKIP)

**Debug dump logs may contain firmware event history that often reveals root causes missed in test logs.**

For test failures, ALWAYS check for debug dump logs and test failure logs:
```bash
# Find all debug dump logs in the fail directory
ls -la /path/to/artifacts/*/fail/*debug_dump*.log
ls -la /path/to/artifacts/*/fail/*FAILED_debug_dump*.log

# Examine the debug dump - it contains replayed firmware event logs from boot
cat /path/to/fail/<DRIVE>_FAILED_debug_dump.log | head -1000

# Check for boot-time warnings that indicate pre-existing drive issues
grep "(warn)\|WARNING" /path/to/fail/*debug_dump*.log | head -100

# Check for metadata corruption warnings
grep "live.*!=.*scan\|mismatch\|corrupt" /path/to/fail/*debug_dump*.log
```

**What debug dumps contain:**
- `[REPLAY:...]` entries - Firmware event log history replayed from boot
- Boot-time warnings about metadata mismatches or corruption
- Historical context showing what happened BEFORE the test ran
- Firmware state at time of failure

**Why this matters:**
- Test failure logs may only show WHAT failed, not WHY
- Debug dumps show firmware state and history that often reveals pre-existing issues
- Metadata corruption, boot failures, and initialization bugs are visible here
- A test may fail because of drive state corruption that occurred before the test started

### Step 3: Examine Pre-Triage Analysis (if available)

**Review automated analysis:**
```bash
cat /path/to/pta_analysis_report
cat /path/to/pta_logs/pta_report/pta_analysis_jira_report
```

**What to look for:**
- Automated failure classification
- Python stacktraces and error messages
- Identified patterns or known issues
- Suggested root causes

**Note:** Pre-triage analysis is helpful but not always complete or accurate. Use it as a starting point, not the final answer.

### Step 4: Identify the Primary Failure

**For test failures:**
```bash
# Check test output files
cat /path/to/runner.stdout
cat /path/to/runner.stderr
cat /path/to/pytest_output.txt
cat /path/to/jenkins_logs/detail_*.log

# Look for Python stacktraces
grep -A 20 "Traceback (most recent call last)" /path/to/logs/*.log
grep -A 10 "ERROR\|FAILED\|Exception" /path/to/logs/*.log
```

**For firmware failures:**
```bash
# Check for watchdog/crash events (firmware crash)
grep -i "watchdog\|FAULT ON CORE" /path/to/logs/*.log

# Check for assertion failures (fatal errors)
grep "\[ASSERT\]:" /path/to/logs/*.log

# Check for error messages
grep "(error)" /path/to/logs/*.log

# Check for media/flash errors
grep -i "uncorrectable\|high_ber\|program_error\|erase_error" /path/to/logs/*.log
```

**Key information to extract:**
- Exact error message or failure reason
- Timestamp of failure
- Component or module that failed
- Core/thread ID (for firmware crashes)
- Failure context (what was happening when it failed)

### Step 5: Understand the Context

**For test failures, examine the test code:**
- Locate the test file and function from the stacktrace
- Read the test logic to understand what it's testing
- Identify the test expectations and assertions
- Determine what operation was being performed when it failed

**For firmware failures, examine the relevant code:**
- Identify the component or module from error messages
- Locate the source code that generated the error
- Understand the code flow leading to the failure
- Check for recent changes or related commits

### Step 6: Build a Timeline

**Determine key timestamps:**
1. When did the test/operation start?
2. When did the failure occur?
3. What events happened between start and failure?
4. Were there any warnings or errors before the failure?

**Correlate across log sources:**
```bash
# Search for events around the failure time
grep "HH:MM:SS" /path/to/logs/*.log

# Build a chronological view
grep -h "timestamp_pattern" /path/to/logs/*.log | sort
```

**Important:** Read and trace through the code to understand what log lines to search for. Don't just search for strings you think might be relevant.

### Step 7: Analyze Logs Systematically


**Firmware log message prefixes:**
- `(debug)` - Debug messages (LOGGER_DEBUG)
- `(info)` - Informational messages (LOGGER_INFO)
- `(warning)` - Warning messages (LOGGER_WARN)
- `(error)` - Error messages that trigger watchdog (LOGGER_ERROR)
- `(display)` - Display messages
- `(bgs)` - Background service messages
- `(ltssm)` - PCIe link state messages
- `[ASSERT]:` - Assertion failures (fatal)
- `[TEST MARKER]:` - Test markers
- `SBL:` - Secondary bootloader prefix
- `MBL:` - Main bootloader prefix

**Analysis approach:**
1. Start with high-severity logs (`[ASSERT]`, `(error)`)
2. Search for error patterns around the failure time
3. Trace the operation flow through different components
4. Look for anomalies or unexpected behavior
5. Check for resource issues (memory, disk, network)

### Step 7b: Firmware-Specific Log Analysis

**For Watchdog/Crash Failures:**

1. **Identify the watchdog trigger:**
```bash
# Find watchdog event
grep -i "watchdog\|FAULT ON CORE" /path/to/logs/*.log

# Find the assertion or error that triggered it
grep -B 50 "watchdog" /path/to/logs/*.log | grep -E "\[ASSERT\]:|LOG_ERR"
```

2. **Analyze the backtrace:**
```bash
# Find backtrace output
grep -A 30 "Backtrace starting" /path/to/logs/*.log

# Look for function names and offsets
# Example: "caller=0x12345678 <function_name+0x123>"
```

3. **Check which core/thread crashed:**
```bash
# Format: CORE[core_id/thread_id]
grep "CORE\[" /path/to/logs/*.log
```

4. **Review events leading to crash:**
```bash
# Get last 100 lines before watchdog
grep -B 100 "watchdog" /path/to/logs/*.log
```

**For Media/Flash Errors:**

1. **Check WSSD event logs:**
```bash
# Look for error events
grep -i "error_mask\|uncorrectable\|high_ber\|program_error\|erase_error" /path/to/logs/*.log
```

2. **Extract complete flash location for ALL failing drives:**
```bash
# CRITICAL: Always search for the detailed exception line which contains complete flash location
# Pattern: "exception prog=X erase=X on addr=0x... size=...kiB block=XXX die=XXX page=XXX"
grep -i "exception prog=.*block=.*die=" /path/to/logs/*.log

# This pattern extracts: address, size, block number, die number, and page number for each error
# Example output:
# 0000:8b:00.0@CH0.BAY00: exception prog=1 erase=1 on addr=0x31d090000000 size=52kiB block=398 die=530 page=0, end
```

3. **Extract block metadata for error context:**
```bash
# Search for metadata dumps that show injected_live_error, error_mask, block_state, etc.
grep -i "injected_live_error\|error_mask=\|block_state=" /path/to/logs/*.log
```

4. **Identify affected flash location (extract for EACH failing drive):**
- CE (Chip Enable / Target)
- LUN (Logical Unit Number / Die)
- Block number
- Page number
- Plane information (if available)
- Address (hex)

5. **Check error frequency:**
- Single error vs. repeated errors
- Specific location vs. widespread
- Same block/die across multiple drives vs. isolated

**IMPORTANT:** When multiple drives fail, extract and document the complete flash location (address, die, block, page) for EACH failing drive. Do not stop after analyzing only one drive.

**For Performance/Hang Issues:**

1. **Check for core stuck detection:**
```bash
grep "core.*stuck" /path/to/logs/*.log
```

2. **Review WCT traces if available:**
- Look for operations that didn't complete
- Check for state machine hangs

3. **Check for resource exhaustion:**
- Memory allocation failures
- Queue full conditions
- Timeout messages

**For Boot Failures:**

1. **Check bootloader logs:**
```bash
# SBL (Secondary Bootloader) or MBL (Main Bootloader)
grep "SBL:\|MBL:" /path/to/logs/*.log
```

2. **Look for initialization failures:**
```bash
grep -i "init.*fail\|startup.*error" /path/to/logs/*.log
```

3. **Check for hardware detection issues:**
```bash
grep -i "pcie\|ddr\|flash.*init" /path/to/logs/*.log
```

### Step 8: Check for Known Patterns

**Common firmware failure patterns:**

1. **Assertion Failures:**
   - Pattern: `[ASSERT]: filename:line condition`
   - Cause: Code violated an invariant/assumption
   - Action: Find the assertion in code, understand the condition

2. **Watchdog Timeout:**
   - Pattern: `FAULT ON CORE` followed by backtraces
   - Cause: Firmware hung or took too long
   - Action: Check what operation was in progress, look for infinite loops

3. **Recursive Watchdog:**
   - Pattern: Multiple watchdog events in sequence
   - Cause: Watchdog handler itself crashed
   - Action: Focus on the first watchdog, not subsequent ones

4. **Multi-Core Crash:**
   - Pattern: Backtraces from multiple cores
   - Cause: One core crashed, others were interrupted
   - Action: Identify the first core to crash (lowest core ID usually)

5. **Media Error Cascade:**
   - Pattern: Multiple uncorrectable errors in short time
   - Cause: Flash block failure or read disturb
   - Action: Check if errors are localized to specific block/die

6. **Boot Hang:**
   - Pattern: Logs stop during initialization
   - Cause: Hardware not responding, infinite loop in init
   - Action: Check last successful init step, look for hardware errors

**Common general failure patterns:**
- Test environment artifacts (benign cores, setup issues)
- Infrastructure problems (network, hardware, testbed)
- Timing issues (timeouts, race conditions)
- Resource exhaustion (memory, disk space, file descriptors)
- Configuration issues (tunables, settings)
- Code bugs (logic errors, null pointers, assertions)

**Search for similar issues:**
```bash
# Search Jira for similar failures
# Use Jira search with relevant keywords from the error message
```

### Step 9: Categorize the Failure

**Determine the failure category:**
1. **Test Environment Issue:** Testbed, infrastructure, or test framework problem
2. **Firmware Bug:** Firmware code related problem
3. **Test Bug:** Issue with the test code or test logic
4. **Configuration Issue:** Incorrect settings or tunables
5. **Known Issue:** Previously identified problem
6. **Cannot Determine:** Insufficient information or unclear root cause

**Firmware-Specific Failure Categories:**

1. **Watchdog/Crash:** Firmware assertion or crash
   - Assertion failure (LOG_ERR, DEBUG_ASSERT)
   - Null pointer dereference
   - Stack corruption
   - Infinite loop/hang

2. **Media Error:** Flash/NAND related errors
   - Uncorrectable ECC errors
   - Program/Erase failures
   - High bit error rate
   - Bad block issues

3. **PCIe Error:** Host interface issues
   - Link training failures
   - Transaction errors
   - Timeout on host commands

4. **Performance Issue:** Latency or throughput problems
   - I/O timeouts
   - Slow operations
   - Resource contention

5. **Boot Failure:** Firmware failed to boot
   - Bootloader failure
   - Initialization failure
   - Hardware detection failure

6. **Background Service Issue:** Non-critical background task failure
   - Garbage collection issues
   - Wear leveling problems
   - Background scrub failures

**Assess impact:**
- Is this a customer-facing issue?
- Does it affect functionality or just testing?
- What is the severity and priority?
- Is it reproducible?

### Step 10: Document Findings

**Prepare your analysis:**
1. Summarize the problem clearly and concisely
2. Provide evidence for all claims (log snippets, code references)
3. Build a timeline if relevant
4. Identify the root cause (if confident) or list possibilities
5. Note any gaps or uncertainties
6. Quantify your confidence level

**Use proper formatting:**
- Use `{code:title=filename}` for code snippets
- Use `{noformat:title=/path/to/logfile}` for log excerpts
- Include timestamps and line numbers
- Provide full context for quoted material

---

## Jira Comment Structure

**Standard format for triage analysis:**

```
h3. Augment Auto-Triage Summary
[One paragraph explaining what was investigated and the conclusion]

h3. Failure Details
*What Failed:* [Specific component, test, or operation]
*When:* [Timestamp or time range]
*Where:* [Environment, testbed, controller]
*Error Message:* [Exact error or failure reason]

h3. Evidence
{noformat:title=/path/to/logfile}
[Relevant log lines with timestamps]
{noformat}

{code:title=filename.py}
// Relevant code snippets
{code}

h3. Timeline of Events
# [Timestamp] - [Event description]
# [Timestamp] - [Event description]
# [Timestamp] - [Failure occurred]

h3. Root Cause Analysis
[Detailed explanation of why the failure occurred, supported by evidence]

h3. Category
[Test Environment / Product Bug / Test Bug / Configuration / Known Issue / Cannot Determine]

h3. Confidence Level
[High / Medium / Low] - [Brief explanation of confidence level]

h3. Recommendations
[Next steps, if any - only if explicitly requested]
```

---

## Important Guidelines

### Do's:
- ✅ Base all conclusions on concrete evidence
- ✅ Quote specific log lines and error messages
- ✅ Trace through code to understand behavior
- ✅ Build timelines for complex failures
- ✅ Correlate findings across multiple sources
- ✅ State your confidence level
- ✅ Highlight uncertainties or gaps
- ✅ Use proper Jira formatting
- ✅ You can't read any files under /tlogs directly via the "read file" tool, but you can use the shell to grep/cat them to see their contents
- ✅ Logs in /tlogs can be read via zgrep/grep/cat, but cannot be directly opened interactively; capture only the needed lines.
- ✅ Limit grep output size by piping into awk or head.
- ✅ Check backtraces from all cores (multi-core crashes are common in firmware)
- ✅ Read and understand the code to know what log patterns to search for
- ✅ Pay attention to bootloader prefixes (SBL/MBL) for boot issues
- ✅ For media/flash errors: Always search for `exception prog=.*block=.*die=` pattern to extract complete flash location (address, block, die, page) for ALL failing drives
- ✅ For error injection tests: Check `injected_live_error` metadata to distinguish test-injected vs genuine errors
- ✅ ALWAYS examine `*_FAILED_debug_dump.log` files BEFORE concluding root cause
- ✅ Check for boot-time warnings in debug dumps that indicate pre-existing issues
- ✅ Look for patterns like "live X != scan X" which indicate metadata mismatches
- ✅ Count warnings to assess if issue is isolated or widespread

### Don'ts:
- ❌ Make assumptions without verification
- ❌ Search for random strings hoping to find something
- ❌ Ignore contradictory evidence
- ❌ Propose solutions without understanding the problem
- ❌ Over-generalize from limited data
- ❌ Skip steps in the investigation
- ❌ Provide analysis when confidence is low
- ❌ Assume a single log line tells the whole story (firmware crashes often have cascading effects)
- ❌ Ignore backtraces from other cores (multi-core crashes are common)
- ❌ Confuse FCC logs with ARM core logs (different processors)
- ❌ Ignore the bootloader prefix (SBL/MBL) when analyzing boot issues
- ❌ Focus only on the last watchdog in a recursive watchdog scenario (first one is the root cause)
- ❌ Overlook the difference between UNIT_TEST and hardware builds
- ❌ Stop after analyzing only one failing drive when multiple drives failed - extract complete info for ALL
- ❌ Never conclude root cause based solely on test failure logs without checking debug dumps
- ❌ Assume the test caused the problem - check if drive state was corrupted before test ran
- ❌ Skip debug dump examination even if test failure seems obvious

---

## Firmware Log Types and Sources

Understanding the different types of firmware logs is crucial for effective triage.

### 1. Event Logs (evtlog)
- **Description:** Primary firmware logging system
- **Storage:** Circular buffer in DDR memory
- **Retrieval:** Via `puressd` tools or serial port streaming
- **Contents:** Timestamped events from all cores
- **Log types:** STRING, META_DATA, WATCHDOG, FCC_WATCHDOG, INDEX
- **Key fields:**
  - `clocks_lo` and `clocks_hi` - 64-bit timestamp in clock cycles
  - `cpu_id` - Core that generated the log
  - `type` - Log entry type
  - `sequence_number` - Per-core sequence number

### 2. Watchdog Logs
- **Description:** Captured when firmware crashes or hangs
- **Storage:** Saved to `nv_debug_log` table in DDR, optionally to SPI flash
- **Contents:** Last 45 seconds of event log plus backtraces from all cores
- **Trigger:** Assertion failures, infinite loops, unhandled exceptions
- **Key information:**
  - Backtrace from crashing core
  - Backtraces from other cores (interrupted state)
  - Recent log history before crash
  - Watchdog cause and count

### 3. Serial/UART Logs
- **Description:** Real-time output during boot and operation
- **Use cases:** Early boot failures, real-time debugging
- **Access:** Serial console connection or log capture
- **Features:** Can stream evtlog in real-time
- **Prefixes:** `(info)`, `(warning)`, `(error)`, `(debug)`, `(bgs)`, `SBL:`, `MBL:`

### 4. Telemetry Logs
- **Description:** Structured logs for monitoring and diagnostics
- **Types:**
  - OCP telemetry (NVMe standard, log page 0x07, 0x08)
  - WSSD event logs (vendor-specific)
- **Contents:** Error events, media errors, performance data, statistics
- **Retrieval:** NVMe admin commands (`nvme get-log`)

### 5. FCC Logs (Flash Controller Core)
- **Description:** Logs from the flash controller processor (Xtensa core)
- **Separate from:** ARM core logs (different processor)
- **Types:**
  - Printf buffer - Text messages from FCC
  - Trace logs - PC (program counter) and tag pairs
- **Organization:** Context-based per LUN/die
- **Key fields:**
  - `fcc_context` - Which LUN context generated the log
  - `pc` - Program counter
  - `tag` - Trace tag identifier

### 6. WCT Trace Logs (Work Context Tracker)
- **Description:** Detailed traces of I/O operations through the firmware stack
- **Use cases:** Performance analysis, hang debugging, operation flow tracing
- **Contents:**
  - State transitions (data manager, FIO manager states)
  - Timing information (start/end timestamps)
  - Operation parameters (LBA, length, namespace)
  - Callback results and status codes
- **Key fields:**
  - `start_time`, `end_time` - Operation timing
  - `type` - Trace entry type (WCT, DM, FIO_REQ, FIO_CB, etc.)
  - `state` - Current state of the operation
  - `metadata_index` - Flash metadata index

### 7. Backtraces
- **Description:** Stack traces captured at crash or on-demand
- **Format:** `CORE[core_id/thread_id]: Backtrace starting at SP=...`
- **Contents:**
  - Stack pointer (SP), frame pointer (FP), link register (LR)
  - Exception link register (ELR), saved program status (SPSR)
  - Call stack with function names and offsets
  - Thread-local storage pointers
- **Analysis:** Shows function call chain leading to crash
- **Example:**
  ```
  CORE[02/00]: Backtrace starting at SP=0x12345678
  CORE[02/00]: #0  0x87654321 <function_name+0x123>
  CORE[02/00]: #1  0x87654400 <caller_function+0x45>
  ```

---

## Special Considerations

### For Firmware Watchdog/Crashes:
- Identify which core/thread crashed (CORE[XX/XX] format)
- Check for assertion message or LOG_ERR that triggered watchdog
- Analyze all backtraces (multiple cores will have traces)
- Focus on the first core to crash (usually lowest core ID)
- Check for recursive watchdog (watchdog handler crashed)
- Review last 100 log lines before watchdog event

### For Timeouts:
- Identify what operation timed out
- Check if the operation completed after the timeout
- Look for resource contention or blocking operations
- Verify timeout thresholds are appropriate

### For Performance Issues:
- Measure actual vs expected performance
- Check for resource bottlenecks
- Look for inefficient operations or queries
- Correlate with system load or activity

### For Intermittent Failures:
- Check failure frequency and pattern
- Look for timing-dependent behavior
- Identify environmental factors
- Consider race conditions or resource contention
- For firmware: Check if failure correlates with specific operations or load patterns

### For Boot Failures:
- Identify where in boot sequence the failure occurred
- Check bootloader logs (SBL/MBL prefixes)
- Look for hardware initialization failures (DDR, PCIe, Flash)
- Check if firmware image is corrupted or incompatible
- Review power-on sequence and PLP (power loss protection) status
- For firmware: Check if failure correlates with specific operations or load patterns

---

## Next Steps After Triage

**Based on the category:**
1. **Test Environment:** Create FW jira ticket with complete information
2. **Product Bug:** Create FW jira ticket with complete information
3. **Test Bug:** Create FW jira ticket with complete information
4. **Configuration:** Document correct configuration
5. **Known Issue:** Provide link to existing ticket
6. **Cannot Determine:** Create FW jira ticket with complete information
   
**Always include:**
- Link to logs or artifacts
- Reproducibility information
- Impact assessment
- Suggested priority/severity
- For firmware crashes: backtrace, assertion message, core/thread ID
- For media errors: flash location (CE, LUN, block, page), error type, frequency