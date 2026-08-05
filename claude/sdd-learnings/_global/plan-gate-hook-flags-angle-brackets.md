# learning: plan-gate-hook-flags-angle-brackets

date: 2026-07-31
feature: harden-vpd-record-updates
stage: research
tags: pipeline, hooks, sdd-state, gate1, tooling-friction

## what happened
`sdd-state log "<message>"` was rejected by the pre-gate-1 source-mutation guard
hook with "redirects into the source tree (literal)". The message contained no
redirect — only ASCII arrows (`->`) inside the quoted argument. The hook's
literal-redirect detector matched the bare `>` character without accounting for
it being inside a quoted string, so a purely descriptive log line was blocked as
if it were a write into the source tree.

## why
The guard scans the raw command text for redirect characters rather than parsing
shell tokens, so any `>` in a quoted argument is indistinguishable from a real
`>` redirect. Log lines are exactly where prose arrows are most tempting
("cause -> effect", "A -> B"), so this fires on ordinary bookkeeping.

## how to avoid
When writing `sdd-state log` / `sdd-state set` messages before gate 1, use no
`>` or `<` characters at all — write "becomes", "leads to", "then", or a colon
instead of `->`. If a state-bookkeeping command is refused for "redirects into
the source tree" and the command plainly has no redirect, do not start
diagnosing the worktree or the guard: re-read the quoted text for stray angle
brackets and rephrase, then continue. The same applies to commit messages and
any other quoted prose passed through Bash while the guard is active.

Separately: the guard also blocks any redirect whose target is a shell variable
(`>> "$DIR/INDEX.md"`), because it cannot resolve the path to decide whether it
lands in the source tree. That block is correct-by-default, not a bug. For
appends to files OUTSIDE the tree (learnings indexes, scratchpad notes), use the
Read + Write tools instead of a shell redirect — they are path-explicit and the
guard evaluates them accurately.
