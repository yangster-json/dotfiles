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
