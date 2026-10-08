# Filesystem search scope

For filesystem discovery without an explicit search path, search from `~`, never `/`.
Only search from `/` when the user explicitly requests a root-filesystem search.
Honor an explicit path supplied by the user. Do not broaden a home-directory search
into `/` as a fallback. This applies to `find`, `rg`, `grep`, `du`, and similar
commands.

# Chunked reads

Read precise line ranges. Never load entire files larger than 100 lines.

# No repetition

Reuse previous tool outputs. Never run identical or highly similar search and
read queries.

# Re-reading files

Re-read only if something changed the file: your Edit/Write, a Bash command, a
build, or output from a subprocess you spawned. Prefer `offset`/`limit` around
the change instead of the whole file.

# Repetitive edits

N Edits to one file = N context re-reads. Mechanical change (strip a marker,
rename a symbol) → one `sed`, one Write, or one `edit` call with multiple
`edits[]` entries. Batch independent tool calls into one message.
Preplan tool calls; batch the independent ones.

# Long-running commands

Anything that may outlive a tool call: run it, or a wait loop for a detached
process, through an async `bg-cmd-runner` subagent (standing approval) instead
of blocking or polling. Always pass `timeoutMs`. Remote detached process: start
with `setsid nohup`, then payload `remote.host` + `command`
`["bash","-c","while pgrep -f '[p]attern' >/dev/null; do sleep 300; done; grep -q OK log"]`
(bracket the pattern's first char or pgrep matches its own shell).

# Communication

- If my request is too ambiguous, ask clarifying questions before doing anything.
- Do not apologize, just fix it and tell me what changed.
- When reporting information to me, be extremely concise and sacrifice grammar
  for sake of concision.
