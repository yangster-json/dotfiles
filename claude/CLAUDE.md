@~/.claude/comment-style-rule-file.md

# Searching the codebase

Delegate search-shaped work to the Explore subagent — "where is X handled",
"which files do Y", "what are all the callers of Z", or any question whose
answer is a conclusion rather than the file contents themselves. Say how wide
to search ("medium", or "very thorough" for multiple locations and naming
conventions). A subagent's context is discarded when it returns, so the
excerpts it reads never enter this session's window and are never re-read on
later turns; the same search done inline is paid for again on every turn that
follows it.

Search inline when you already know the file, when you need the content itself
and not a verdict, or for a single cheap lookup where one Grep answers it.

# Re-reading files

Before re-reading a file you have already read this session, ask whether
anything changed it — your own Edit or Write (the astyle hook reformats the file
afterward, so a re-read is how you see what is actually on disk), a Bash
command, a build, or a subagent. If something did, you can re-read; prefer
`offset`/`limit` around the part that changed. If nothing did, the content is
already in context — use it.

<!-- The two firmware-triage rule files that used to be @-imported here are now
     skills — skills/triage-jira and skills/triage-local-logs — loaded on
     demand. They were ~43KB, about 11k tokens resident in EVERY session and
     re-read on every request (plus a cache write per subagent spawn), whether
     or not the session had anything to do with triage. The content is
     unchanged and still governs triage work; it just is not paid for the rest
     of the time. Comment style stays inline: ~3KB, and it applies to any code
     written in any session. -->
