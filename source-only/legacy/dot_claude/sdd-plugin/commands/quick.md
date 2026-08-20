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
   `$(sdd-path templates/state.md)`; parse a `jira=` token if given),
   write `specs/ACTIVE`. Check both learnings indexes for entries matching
   the touched area and honor them — project (`sdd-git
   learnings-dir`, then that directory's `INDEX.md`) and global
   (`sdd-git learnings-dir --global`, then its `INDEX.md`) — and grep the
   living base specs (`sdd-git base-specs-dir`, config.spec_base) for
   contracts covering it — a quick change that
   alters a contracted behavior must say so in the mini-spec, never
   contradict the base silently. Explore the code yourself just
   enough to write `specs/<slug>/spec.md`: 1–3 EARS requirements, a
   non-goals line, the exact file list, a `verify:` command. Ask at most
   ONE clarifying question, only if the behavior is genuinely ambiguous.

3. **Single gate.** Show the mini-spec PLUS the current branch and its
   upstream (`git rev-parse --abbrev-ref HEAD` / `@{upstream}`) — quick
   changes land on the current checkout, so the user is confirming that
   base too. On approval set `plan_approved: yes` and `phase: implement` in
   one step. Record `base_ref` and the confirmed base as `upstream:`.

4. **Implement + verify.** Judge complexity honestly: mechanical
   pattern-following → `sdd:sdd-implementer-lite`, otherwise `sdd:sdd-implementer`.
   When spawning any `sdd:sdd-<name>` here, route its tier the same way
   /sdd:run does: the `config.models` key is the agent's file basename (the
   whole `sdd-<name>`, e.g. `sdd-implementer`). If the pipeline file's
   `config.models` has that key, pass its value as the spawn's `model`;
   otherwise pass none and let the agent's frontmatter default stand (effort
   stays in frontmatter).
   Write the task as a subspec — `specs/<slug>/tasks/Q1.md` from the
   subspec template (full requirement text; the agent reads no other spec
   files) — and record `git status --porcelain` BEFORE spawning. Pass
   `{workdir: <project root>, subspec: specs/<slug>/tasks/Q1.md}`.
   Verification follows the pipeline rule: simple → run the verify command
   and a `git diff --stat` scope check yourself, no spawn; standard →
   `sdd:sdd-verifier` with the same workdir/subspec plus the pre-recorded dirty
   paths as `preexisting_dirty` (quick runs in place, so unrelated local
   changes must not read as scope violations). On fail, climb the same
   config.recovery.task_attempts ladder /sdd:run uses — escalating retry with
   the failure evidence, then a diagnosis-first attempt that amends the
   subspec (`sdd-state bump verify_retries` per retry) — and only report the
   task blocked once it is exhausted. A needs_files report you
   adjudicate yourself — you wrote the file list; amend the subspec, log
   it, re-spawn. A behavioral ambiguity does NOT stop for the user: resolve
   it with best judgment, record it as an `(assumption)` amendment in
   state.md, and note it in the final report — never pause mid-flow. Never
   write the code yourself.

5. **Test + commit.** Run the task's verify command's suite; then commit per
   the pipeline's commit stage — the `fw-commit` skill when installed,
   otherwise config.commit_standard from `sdd-pipeline --section config` (it
   resolves project-over-bundled and the `extends:` chain; do not Read
   pipeline.yaml, which is ~54KB of mostly comments). Stage
   `specs/<slug>/` per config.specs_tracking (untracked, the default → never
   stage it, `git restore --staged specs` if anything crept in, and leave it
   for /sdd:cleanup to archive; with_feature → include; own_commit →
   separate final commit). Keep the commit spec-free: no R-numbers or task
   ids in the message, and strip any comment in the diff that points at the
   spec. Never push. Set `phase: done`, delete
   `specs/ACTIVE`, report.
