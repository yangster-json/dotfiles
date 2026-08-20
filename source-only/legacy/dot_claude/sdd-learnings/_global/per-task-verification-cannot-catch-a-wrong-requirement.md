# learning: per-task-verification-cannot-catch-a-wrong-requirement

date: 2026-07-31
feature: harden-vpd-record-updates
stage: review
tags: verification, review, test-design, spec-quality, regression

## what happened
A feature shipped through nine verifier passes, 30+ mutation tests, and a
traceability audit — all green — while containing a regression that made a real
failure mode WORSE than the code it replaced. The combative review stage caught
it; nothing before that could have.

The defect: a merge across two redundant on-flash copies picked the "base" copy's
instance of a record by NAME only, ignoring a per-record validity flag the scan
had already computed. So a corrupt instance in the base copy shadowed a good
instance in the other copy, and the save wrote the corrupt bytes to both. The
code it replaced had self-healed that case.

Two artifacts caused it, and both were mine as orchestrator:
1. **The requirement mandated it.** The spec said "when the same id appears in
   both copies, the base copy's instance SHALL win", keyed on name. Every
   implementer and verifier correctly matched the code to that rule.
2. **The task subspec specified a test that could not detect it.** It said to
   corrupt the record "in BOTH copies" — correct for proving verbatim retention,
   and structurally incapable of proving precedence, because with both copies
   corrupt there is no good instance to prefer.

A second review round then found two more defects created by the FIRST round's
fixes: the merge was made validity-aware while the write-ORDERING that decides
which copy to erase first was left validity-blind, so the sole good copy could be
erased first. Fixing one half of a two-half invariant left the halves
inconsistent.

## why
Per-task verification is defined as "does the code satisfy its requirement". That
is the wrong question when the requirement is wrong, and no amount of it
converges on the right one — a verifier that finds the code faithful to a bad rule
reports PASS, correctly. Mutation testing has the same ceiling: it proves a test
can fail if the code deviates from the spec, not that the spec is right.

The tell was visible and unremarked for nine tasks: the scan computed a validity
flag per record and **nothing ever read it**. A computed-and-never-consulted value
is almost always a check that went missing.

## how to avoid
- **Run the adversarial review even when every task passed.** Its value is
  highest exactly when per-task verification is clean, because that is when the
  remaining defects are in the requirements rather than the code. Do not treat a
  green implement stage as a reason to shorten it.
- **When writing a test for "X is preserved", check whether the test can
  distinguish preservation from selection.** Corrupting/removing a thing in ALL
  replicas proves retention but makes every precedence rule unobservable. Any
  requirement of the form "prefer A over B" needs an ASYMMETRIC fixture, and the
  subspec must say so — the implementer will build what the subspec describes.
- **Grep the diff for computed-but-never-read fields before declaring a stage
  done.** It is a one-command check and it is where a missing decision hides.
- **After fixing one side of a paired invariant, re-derive the other side.** If a
  fix teaches component A to consider some property, list every other component
  that decides on the same property and check each. Budget a second review round
  for fix rounds specifically; the first round's fixes are unreviewed code.
- Prefer one more review round over one more verifier pass when the question is
  "is this the right behavior" rather than "does this match the spec".
