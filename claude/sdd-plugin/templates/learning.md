# learning: <short-kebab-slug>

date: <YYYY-MM-DD>
feature: <feature-slug>
stage: <research | spec | plan | implement | review | test | commit | gate1 | gate2>
tags: <comma-separated — subsystem, file area, failure kind>

## what happened
<the mistake, correction, or veto — one concrete paragraph. quote the
user's words when the lesson came from them.>

## why
<root cause: the wrong assumption, missing check, or bad default>

## how to avoid
<the check or rule a future run applies — phrased as an instruction an
orchestrator or agent can act on (e.g. "before planning tasks in
src/fio/, confirm X", not "be more careful").>

<!-- after writing this file, add one line to THIS scope's INDEX.md:
     project -> run `sdd-git learnings-dir`, then <that-dir>/INDEX.md
                (keyed to this repo, outside the project's own tree —
                nothing to gitignore there)
     global  -> run `sdd-git learnings-dir --global`, then <that-dir>/INDEX.md
                (shared across projects, survives /plugin update; scrub
                codebase-specific detail before writing here)
- [<slug>](<slug>.md) — stage:<stage> tags:<tags> — <one-line hook>
-->
