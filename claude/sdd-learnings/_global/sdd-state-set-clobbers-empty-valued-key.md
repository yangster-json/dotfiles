# learning: sdd-state-set-clobbers-empty-valued-key

date: 2026-07-31
feature: harden-vpd-record-updates
stage: implement
tags: pipeline, sdd-state, state-file, data-loss, tooling

## what happened
`sdd-state set base_ref <sha>` corrupted state.md. The `base_ref:` field was
present but had an EMPTY value (the state template ships it that way). Instead of
appending the value after the colon, the setter emitted the value on the FOLLOWING
line, which overwrote the next key. Before:

    base_ref:
    hw_testbed: none     <!-- comment -->
    hw_bay: none

After:

    base_ref:
    768903a1db     <!-- comment -->
    hw_bay: none

The `hw_testbed` key was destroyed outright and `base_ref` was left empty. The
command printed `base_ref: 768903a1db` and exited 0, so it reported success while
silently losing a field. Only the harness's file-changed notification surfaced it.

## why
The setter appears to match the key then write the value at the start of the next
line when the existing value is empty, rather than in place after the colon. Any
template field that ships empty is exposed: in the sdd state template that is
`base_ref:` (and any field a run leaves blank).

## how to avoid
Do not use `sdd-state set` on a field whose current value is EMPTY — use the Edit
tool on state.md instead, which is path- and string-explicit. In the sdd pipeline
this specifically means `base_ref`, set once at implement setup.

More generally: `sdd-state set` reports success unconditionally, so after ANY
`sdd-state set` on a field that was blank, re-read the surrounding lines of
state.md before trusting it. If the harness reports state.md as externally
modified right after an `sdd-state set`, that is the corruption signature, not a
linter — read the diff and repair the clobbered key immediately, because a lost
`hw_testbed` / `autopilot` / `findings_policy` value silently changes how later
stages behave.
