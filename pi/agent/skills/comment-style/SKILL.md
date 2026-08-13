---
name: comment-style
description: Jason's personal source-comment conventions — terse ~6-word lowercase notes, why-not-what, tickets on TODOs, imperative step comments in tests, one-line docstrings. Load before writing or editing comments or docstrings in a source file, in any language, unless the project's own CLAUDE.md/AGENTS.md overrides it.
---

# Comment style

Derived from my own commit history. Applies to all languages unless a project's
CLAUDE.md/AGENTS.md says otherwise — the project rule wins.

- **~6 words, one line.** Over ~12 words is rare. A terse note, not a sentence.
  `// sum up nvme io stats` · `# back to idle`

- **Why, not what.** Restating code is noise. A comment earns its place for a
  non-obvious constraint, a quirk, or the reason a workaround exists.
  `// don't want to write mtp if i2c fail or we already tried to prevent wear`

- **Point at the source of truth** when a value or algorithm mirrors something
  elsewhere — name the file, function, or ticket in a few words.
  `# mirrors EFC/src/monitor/monitor.h` · `# current thresholds are Topper * 70%`

- **Tests narrate as imperative steps**, labelled by phase, so the test reads
  top-to-bottom as the scenario.
  `// Advance past the full timeout` · `# Phase 1: baseline — jitter disabled`

- **Capitalization tracks weight.** Short inline notes are lowercase and
  unpunctuated; a fuller sentence is sentence-case with a period.

- **Multi-line blocks well under 1% of the time** — only for subtle rationale a
  reader could not reconstruct, and then state the problem *and* the fix.

- **TODOs and refs carry an issue-tracker ticket** so they stay traceable and
  can be swept later.
  `# TODO: FW-25177 Update CD5519 thresholds once board characterization is done.`

- **Docstrings: one line, third-person verb, terminal period.** Describe the
  contract, not the mechanics. Expand only to state what a test verifies.
  `"""Create a queue entry for this process and return its path."""`
