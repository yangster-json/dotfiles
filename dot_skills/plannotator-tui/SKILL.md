---
name: plannotator-tui
description: >-
  Hand a Markdown plan, design doc, or commit message to the human for line-by-line
  annotation in plannotator-tui; they open it themselves, feedback arrives as your next
  message. Use when a plan or spec needs human review before you act. Not for code review
  or diffs.
---

# plannotator-tui: hand a document to the human for review

Never open the review pane yourself. The human opens it with Herdr `prefix+o`.

## Scope

Plans, specs, design docs, commit messages, prose drafts. Not code review: do not
put diffs or code changes in the document for review. For code review, tell the
human to run `/plannotator-review` instead.

## Steps

1. Write the document as a Markdown file under your current working directory,
   at most 3 levels deep (e.g. `docs/plans/auth.md`). Do not paste it into chat too.
   Put several items in one file.
2. Make sure `prefix+o` picks it. It opens the newest `.md` in the focused pane's
   folder: modified/untracked, not gitignored, git files in a repo, otherwise any
   `.md` within depth 3. Write it last (or `touch` it) and keep it out of
   gitignored paths.
3. Tell the human, in one line, with the path:

   > Review ready: `docs/plans/auth.md`. Press `prefix+o` to open it.

4. **End your turn.** Do not open, wait, poll, or read the pane. The review
   arrives as the next user message as numbered feedback:

   ```
   ## 1. (line 12) Feedback on: "Rotate the token on every…"
   > Rotation on every privilege change will log people out…
   ```

   Address every item, then continue.
