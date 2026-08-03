---
description: clean up a finished sdd feature — remove its worktrees and branches, harvest learnings, merge the spec into the living base, clear pointers. run after the pr merges.
argument-hint: "[feature-slug] [delete] — no slug: menu of cleanup candidates"
---

Clean up the SDD feature: $ARGUMENTS

Run this from the MAIN checkout (first path in `git worktree list`), after
the feature's PR has merged. This is the deliberate counterpart to the
pipeline's commit stage, which keeps the worktree on purpose.

1. **Pick the target.** Slug from $ARGUMENTS if given. Otherwise enumerate
   candidates — `git worktree list` entries under `.claude/worktrees/sdd/`
   plus `specs/*/state.md` phases — and present a menu. A feature whose
   phase is not `done` is in flight: cleaning it up discards state, so
   require explicit confirmation and name what would be lost.

2. **Safety checks** (in the feature worktree, if it still exists):
   - Uncommitted changes → stop and show them; the user decides.
   - Is `sdd/<slug>` merged into its upstream (the `upstream:` in
     state.md)? Check with `git merge-base --is-ancestor`. Unmerged → warn
     that deletion orphans the work and require confirmation (branch
     removal will need `-D`).

3. **Harvest learnings first.** If state.md shows waived findings, blocked
   tasks, or nonzero reroute/conflict metrics with no matching entry in
   either learnings index — project (`sdd-git learnings-dir`,
   then that directory's `INDEX.md`) or global
   (`sdd-git learnings-dir --global`, then its `INDEX.md`) — write the learning files now
   (template: project `specs/templates/learning.md` if present, else
   `$(sdd-path templates/learning.md)`), in whichever scope the lesson
   fits (see run.md's learnings section for the project/global split) —
   cleanup is the last chance.

4. **Merge the spec into the living base** (config.spec_base in the sdd
   pipeline file, default `specs/base/`). Only for a feature that actually
   merged (step 2's ancestor check) — never fold unshipped requirements
   into the base. Assemble the AS-BUILT requirements from
   `specs/<slug>/spec.md` + state.md: amendments override the requirements
   they touch; drop any requirement whose tasks all ended blocked. Pick
   the area file `specs/base/<area>.md` — <area> is the subsystem the
   feature touched; match an existing file before inventing a new name,
   and create a missing one from the base-spec template (project
   `specs/templates/base-spec.md` if present, else
   `$(sdd-path templates/base-spec.md)`). Then, per requirement: if it
   changes a behavior an existing line contracts, REPLACE that line and
   note the supersession in its provenance comment; otherwise append it
   under the next `<AREA>-R<n>` id. Every line keeps provenance:
   `<!-- from <slug> R<n>, <date>, <jira> -->`. This edits the main
   checkout's working tree — tell the user to commit it.

5. **Remove worktrees and branches.**
   - Leftover task worktrees first: `.claude/worktrees/sdd/<slug>-*` →
     `git worktree remove <path>` and `git branch -d sdd/<slug>-<id>`.
   - Then the feature worktree and `git branch -d sdd/<slug>`.
   - Use `--force`/`-D` only after the user has confirmed the specific
     loss (uncommitted changes / unmerged commits).
   - Finish with `git worktree prune`.

6. **Spec directory.**
   - Tracked in the main checkout (the normal case — it merged with the
     PR): leave it; it is part of history and feeds
     `sdd-quality`. With `delete` in $ARGUMENTS, `git rm -r
     specs/<slug>` after confirmation and tell the user to commit.
   - Untracked (aborted or never-merged feature, or the project runs
     `config.specs_tracking: untracked` — the normal case there): offer
     archive
     (`mv specs/<slug> specs/archive/<slug>` — quality still finds it
     there) or delete. Default to archive.

7. **Clear pointers.** Delete `specs/ACTIVE` in the main checkout if it
   names this slug or its worktree. Never touch another feature's pointer.

8. **Report** what was removed, what was archived or kept, learnings
   harvested, base-spec lines added or superseded, and any branch that
   needed force-deletion.

Never push, never touch remote branches, never delete the project learnings
directory (`sdd-git learnings-dir`), the global one (`sdd-git learnings-dir
--global`), or `specs/base/`. Both learnings directories live outside the
project tree (under `<claude-config>/sdd-learnings/`, keyed to the repo — see
run.md's learnings section), so worktree/branch removal never touches them.
