# Splitting a boundary predicate from its loop hides an off-by-one from every verifier

stage: implement
tags: subspec-authoring, off-by-one, per-task-verification, boundary-conventions

## What happened

A depth-limited graph walk was split across two tasks: one task owned the pure
predicate deciding whether to continue (`select_next_tickets_to_visit(candidates,
visited, current_depth, max_depth)`), another owned the loop that calls it. Each
subspec stated its own half's contract:

- predicate subspec: "returns [] if `current_depth >= max_depth`"
- loop subspec: "for each depth level up to `depth`, fetch every ticket returned by
  the predicate"

Both agents implemented their half faithfully. The loop started at
`current_depth=1`, so at the default `max_depth=1` the predicate saw `1 >= 1` and
returned empty — the walk fetched **nothing**. The feature's entire primary use case
returned zero results.

It survived: 2 spec critics, 9 verifier passes, 123 green tests. The unit test for
the predicate asserted the empty-list result as *expected* behavior, because the
subspec said so. Only an adversarial review reading the two modules *together*
caught it, and all three reviewer stances found it independently.

## Why it survived everything

Per-task verification asks "does this code match its subspec". Both halves did. The
defect lived in the *relationship* between two subspecs, which no single task's
verifier can see — the predicate in isolation is perfectly defensible, and so is the
loop. The test then froze the wrong convention in place, making the bug look
deliberate.

## How to avoid it

- When one task owns a boundary predicate and another owns the loop/caller that
  supplies its arguments, **state the shared semantics of the boundary variable in
  BOTH subspecs, in the same words** — e.g. "`current_depth` counts hops ALREADY
  traversed; the root is 0". A predicate contract without that anchor is
  underspecified no matter how precise it looks.
- Prefer giving one task the predicate *and* at least one caller-level test that
  exercises the boundary end-to-end with a stubbed dependency. If the loop lives in
  a tier the test suite cannot import (network/IO), the boundary is untestable by
  construction — that is a design smell to fix at plan time, not a coverage note to
  accept.
- Boundary conventions worth pinning explicitly every time: 0- vs 1-based counters,
  inclusive vs exclusive bounds, "already done" vs "about to do", and whether the
  root/seed element counts as a level.
- Treat a green suite on a boundary-heavy feature as weak evidence. Ask "would this
  test still pass if the convention were off by one?" — if yes, the test encodes the
  convention rather than verifying it.

Related: [[per-task-verification-cannot-catch-a-wrong-requirement]]
