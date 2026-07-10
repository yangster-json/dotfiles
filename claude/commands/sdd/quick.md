---
description: sdd fast path for small changes — mini-spec, one implementer/verifier pair. skips research, critics, combative review.
argument-hint: <small change description> [jira=FW-XXXXX]
---

Run the SDD fast path for: $ARGUMENTS

For changes small enough that the full pipeline is ceremony (a bug fix, a
config knob, a small refactor). Keeps: a written spec, the edit gate,
independent verification, the commit standard. Drops: scouts, critics,
planner, combative review.

1. **Size check.** More than ~2 tasks or ~4 files → say so and recommend
   `/sdd:run`. Continue only if the user insists.

2. **Mini-spec.** Derive a slug, create `specs/<slug>/state.md` from the
   state template (the project's `specs/templates/state.md` if present, else
   `~/.claude/sdd/templates/state.md`; parse a `jira=` token if given),
   write `specs/ACTIVE`. Check `specs/learnings/INDEX.md` for entries
   matching the touched area and honor them. Explore the code yourself just
   enough to write `specs/<slug>/spec.md`: 1–3 EARS requirements, a
   non-goals line, the exact file list, a `verify:` command. Ask at most
   ONE clarifying question, only if the behavior is genuinely ambiguous.

3. **Single gate.** Show the mini-spec PLUS the current branch and its
   upstream (`git rev-parse --abbrev-ref HEAD` / `@{upstream}`) — quick
   changes land on the current checkout, so the user is confirming that
   base too. On approval set `plan_approved: yes` and `phase: implement` in
   one step. Record `base_ref` and the confirmed base as `upstream:`.

4. **Implement + verify.** Judge complexity honestly: mechanical
   pattern-following → `sdd-implementer-lite`, otherwise `sdd-implementer`.
   Write the task as a subspec — `specs/<slug>/tasks/Q1.md` from the
   subspec template (full requirement text; the agent reads no other spec
   files) — and record `git status --porcelain` BEFORE spawning. Pass
   `{workdir: <project root>, subspec: specs/<slug>/tasks/Q1.md}`.
   Verification follows the pipeline rule: simple → run the verify command
   and a `git diff --stat` scope check yourself, no spawn; standard →
   `sdd-verifier` with the same workdir/subspec plus the pre-recorded dirty
   paths as `preexisting_dirty` (quick runs in place, so unrelated local
   changes must not read as scope violations). One retry on fail with the
   failure evidence (update `## metrics`). A needs_files report you
   adjudicate yourself — you wrote the file list; amend the subspec, log
   it, re-spawn. Behavioral ambiguities stop the line and become
   amendments. Never write the code yourself.

5. **Test + commit.** Run the task's verify command's suite; then commit per
   the pipeline's commit stage — the `fw-commit` skill when installed,
   otherwise config.commit_standard from the sdd pipeline file (project
   `.claude/sdd/pipeline.yaml`, else `~/.claude/sdd/pipeline.yaml`). Include
   `specs/<slug>/`, never push. Set `phase: done`, delete `specs/ACTIVE`,
   report.
