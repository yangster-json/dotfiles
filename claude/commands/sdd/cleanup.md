---
description: clean up a finished sdd feature — remove its worktrees and branches, harvest learnings, clear pointers. run after the pr merges.
argument-hint: [feature-slug] [delete] — no slug: menu of cleanup candidates
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
   `specs/learnings/INDEX.md`, write the learning files now (template:
   project `specs/templates/learning.md` if present, else
   `~/.claude/sdd/templates/learning.md`) — cleanup is the last chance.

4. **Remove worktrees and branches.**
   - Leftover task worktrees first: `.claude/worktrees/sdd/<slug>-*` →
     `git worktree remove <path>` and `git branch -d sdd/<slug>-<id>`.
   - Then the feature worktree and `git branch -d sdd/<slug>`.
   - Use `--force`/`-D` only after the user has confirmed the specific
     loss (uncommitted changes / unmerged commits).
   - Finish with `git worktree prune`.

5. **Spec directory.**
   - Tracked in the main checkout (the normal case — it merged with the
     PR): leave it; it is part of history and feeds
     `~/.claude/sdd/quality`. With `delete` in $ARGUMENTS, `git rm -r
     specs/<slug>` after confirmation and tell the user to commit.
   - Untracked (aborted or never-merged feature): offer archive
     (`mv specs/<slug> specs/archive/<slug>` — quality still finds it
     there) or delete. Default to archive.

6. **Clear pointers.** Delete `specs/ACTIVE` in the main checkout if it
   names this slug or its worktree. Never touch another feature's pointer.

7. **Report** what was removed, what was archived or kept, learnings
   harvested, and any branch that needed force-deletion.

Never push, never touch remote branches, never delete `specs/learnings/`.
