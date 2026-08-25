# Searching the codebase

Delegate search-shaped work — answer is a conclusion, not the file contents —
to Explore; say "medium" or "very thorough". A subagent's context is discarded
on return, so an inline search is re-paid on every later turn. Search inline
when you know the file, need the content itself, or one Grep answers it.

# No repetition

Reuse previous tool outputs. Never run identical or highly similar search and
read queries.

# Re-reading files

Re-read only if something changed the file: your Edit/Write (the astyle hook
reformats afterward, so this is how you see what is on disk), Bash, a build, or
a subagent. Prefer `offset`/`limit` around the change.

# Repetitive edits

N Edits to one file = N context re-reads. Mechanical change (strip a marker,
rename a symbol) → one `sed`, one `replace_all` Edit, or one Write. Batch
independent calls into one message.
