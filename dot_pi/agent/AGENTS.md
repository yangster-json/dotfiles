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

# Output budget

Every tool result stays in context for the rest of the session.
- Bound bash output: pipe through `head`/`tail`/`grep -m`/`wc -l`; use
  `--stat`, `-q`, `--oneline`. Send noisy logs to a file and grep it.
- Write a file once; change it with `edit`, never by rewriting it.
- Don't paste file content back into heredocs that already exists on disk.
- Delegate broad log digging/greps to a subagent; take back only the summary.

# Long-running commands

Anything that may outlive a tool call: run it, or a wait loop for a detached
process, through an async `bg-cmd-runner` subagent (standing approval) instead
of blocking or polling. Always pass `timeoutMs`. The task must be the tagged
JSON payload, never prose (prose is rejected). Remote detached process: start
with `setsid nohup`, then task:

```
<BACKGROUND_TEST_RUNNER_JSON>
{"cwd":"/root","command":["bash","-c","while pgrep -f '[p]attern' >/dev/null; do sleep 300; done; grep -q OK log"],"iterations":1,"label":"watch-x","stop_on_failure":true,"remote":{"host":"<host>","ssh_user":"root"}}
</BACKGROUND_TEST_RUNNER_JSON>
```

Bracket the pattern's first char or pgrep matches its own shell.

# Plannotator

Never call the `plannotator` tool (annotate/review/last) on your own initiative.
Open a browser review only when I explicitly ask in that request. `list` and
`close` are fine anytime.

# Communication

- If my request is too ambiguous, ask clarifying questions before doing anything.
- Do not apologize, just fix it and tell me what changed.
- When reporting information to me, be extremely concise and sacrifice grammar
  for sake of concision.

<!-- plannotator-inbox:start v9 · added by Plannotator. Remove it in the Inbox's Settings or with `plannotator uninstall` -->
## Plannotator Inbox

The person keeps a Plannotator Inbox on this computer: a window where they read what agents send and answer when they can.
If you have a `plannotator_inbox` tool or a `plannotator-inbox` MCP server, use its `send_message` to ask a decision only they can make (as a `:::question` block) or to hand over finished long work (a short summary with its pictures in place, `![alt](path)` in the body, and the files to read in `attachments`). Then keep working.
A decision inside a report or summary still goes in a `:::question` block, one block per decision.
When you mention an issue or PR outside the repo you started in, write owner/repo#123 or its full URL every time; a bare #123 links to your own repo.
Their reply comes back to this session by itself where your agent supports that; otherwise read the thread later with `read_thread`.
Be proactive about Inbox updates and about replying to the person through the Inbox when you think they would want you to. Don't withhold important updates or decisions, and don't batch updates to send later: proactivity is better than procrastination.
One thread per work stream, unless the person says otherwise.
A decision you sent to the Inbox stays there. When the person writes in this chat, say what is waiting there (a short summary and the thread's link), but never also ask it in the chat with a blocking question tool (AskUserQuestion or similar): that blocks the chat and splits the answer. Ask in the chat only about something new they raised here that needs no pictures or files, or when they ask for it.
Before reply_to into a thread you have not read in this context window, call read_thread with no id and match the subject.
In a `:::question` block, keep the choices in their natural order and never move your recommendation first; put it on its own line after the choices as `Recommended: <label>`, and never write "(recommended)" in a choice label.
<!-- plannotator-inbox:end -->
