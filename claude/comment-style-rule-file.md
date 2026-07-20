# Code Commenting Style

My personal conventions for comments I (or Claude on my behalf) write in source code.
Derived from my own commit history. Applies to all languages unless a project's own
CLAUDE.md/AGENTS.md says otherwise (the project rule wins).

**Keep comments short. One line, ~6 words, is the norm** — half are 5 words or fewer,
and a comment over ~12 words is rare. Write a terse note, not a sentence:
```cpp
// sum up nvme io stats
// only set led if state is different
// wait for stats to accumulate
```
```python
# back to idle
# start I/O and monitor LED transitions
# default health values
```

**Comment the *why*, not the *what*.** Restating code is noise. A comment earns its
place when the code cannot say it for itself: a non-obvious constraint, a quirk, or the
reason a workaround exists — still stated as briefly as the point allows.
```cpp
// don't want to write mtp if i2c fail or we already tried to prevent wear
// In UNIT_TEST builds util_get_serial_number_trimmed() always returns "PFM_UNITTEST"
```

**Point at the source of truth** when a value or algorithm mirrors something elsewhere.
Name the file, function, or ticket in a few words.
```cpp
// use FNV-1a algorithm to generate hash
```
```python
# mirrors EFC/src/monitor/monitor.h
# current thresholds are Topper * 70%
```

**Narrate tests as a sequence of short imperative steps**, and label phases. Each line
is a terse step; the test reads top-to-bottom as the scenario.
```cpp
// Write defaults then corrupt VSTRG1 register to create a mismatch
// Should stay in IDLE while waiting for MTP write
// Advance past the full timeout
```
```python
# Phase 1: baseline — jitter disabled
# check blink frequency
```

**Capitalization tracks weight.** Short inline notes are lowercase and unpunctuated
(`// sum up nvme io stats`, `# back to idle`); a fuller sentence is sentence-case with a
period. Only rarely — for genuinely subtle rationale a reader could not reconstruct —
expand to a multi-line block that states the problem *and* the fix. Reach for this
sparingly (well under 1% of comments), not by default:
```python
# The NVRAM (namespace-2) block device is periodically probed by the host
# kernel and device-discovery tooling, generating nvram_read I/O the activity
# LED counts. That re-arms the blink hold after the test's own I/O stops and
# makes the stop-latency check flaky. Hide the NVRAM namespace for the test so
# the drive sees no background reads; restore it in teardown.
```

**TODOs and refs carry an issue-tracker ticket** (e.g. `FW-xxxxx`) so they stay
traceable and can be swept later.
```python
# TODO: FW-25177 Update CD5519 thresholds once board characterization is done.
# ref: FW-21086
```

**Docstrings: one line, third-person verb, terminal period.** Describe the contract
(what it does / returns), not the mechanics. Expand to multiple lines only to state what
a test verifies.
```python
"""Create a queue entry for this process and return its path."""
"""Clean up any leftover queue directory from previous tests."""
```
