# tasks: <feature-slug>

<!-- immutable after gate 1; statuses are tracked in state.md, not here -->

## coverage
| requirement | tasks |
|-------------|-------|
| R1 | T1 |

## tasks

### T1: <title>
- **requirements:** R1
- **files:** <exact paths this task may touch — test files included>
- **depends_on:** — <!-- or: T<n>, T<m> -->
- **parallel_ok:** no <!-- yes only if the file set is disjoint from every task it could run alongside -->
- **complexity:** standard <!-- simple = mechanical/pattern-following, runs on haiku; standard = sonnet -->
- **verify:** `<shell command that objectively passes or fails>`

<what to build, precisely enough that a fresh-context implementer needs no
follow-up questions: behavior, integration points, test expectations>

### T<final>: integration
- **requirements:** all
- **files:** —
- **depends_on:** <every other task>
- **parallel_ok:** no
- **complexity:** simple
- **verify:** `<full test suite command>`

run the full suite; fix nothing (report failures instead).
