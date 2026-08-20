---
name: atlassian
description: Read and write Pure's Jira (jira.purestorage.com) and Confluence wiki (wiki.purestorage.com) from the command line — fetch a FAIL-/FW- ticket with its comments, run JQL searches, download ticket attachments, post a triage comment, read a wiki page, or run a CQL search. Use whenever a Jira ticket id, Jira URL, JQL query, Confluence page or wiki URL appears in the request, or when triaging a firmware ticket needs the ticket contents.
---

# Jira & Confluence access

`atl.py` talks to the Jira and Confluence REST APIs directly. It replaces the old
`jira-mcp-server` and `wiki-mcp-server` MCP servers, which loaded ~75 tool definitions
into every session to serve the five calls actually used.

```
A=~/.claude/skills/atlassian/atl.py
```

## Commands

| Command | Purpose |
|---|---|
| `python3 $A issue FW-29029 [--comments]` | Fetch a ticket — status, assignee, labels, links, attachments, description |
| `python3 $A search '<JQL>' [--limit N]` | JQL search (default 10 results) |
| `python3 $A attachments FAIL-1095379 [dest]` | Download all attachments to `dest` (default `.`) |
| `python3 $A comment FW-29029 '<body>'` | Post a comment; body `-` reads stdin |
| `python3 $A page <id\|url>` | Confluence page as readable text |
| `python3 $A cql '<CQL>' [--limit N]` | Confluence search |

## Usage notes

- **`--comments` matters for triage.** FAIL tickets carry PTA Bot analysis and human
  triage notes in comments; without the flag you get only the description. It is
  omitted by default because busy tickets run long.
- **Jira is Server/DC, not Cloud.** Bodies are wiki markup (`h2.`, `{{code}}`), not ADF.
  Write comments in wiki markup.
- `page` accepts a bare page id or a full URL — it pulls the id out of `pageId=` or
  `/pages/<id>`.
- JQL/CQL text search uses `~`, e.g. `text ~ "watchdog" AND project = FW ORDER BY created DESC`.

## Posting comments

`comment` writes to a real ticket that other people read. Confirm the exact body with
the user before posting unless they have already told you to post it. For long bodies,
pipe to avoid shell quoting problems:

```
python3 $A comment FAIL-1095379 - <<'EOF'
h3. Triage
...
EOF
```

## Credentials

Personal access tokens live in `~/.claude/.atlassian.env` (mode 600, gitignored):
`JIRA_URL`, `JIRA_PERSONAL_TOKEN`, `CONFLUENCE_URL`, `CONFLUENCE_PERSONAL_TOKEN`.
Real environment variables override the file. On HTTP 401/403 the token has expired —
regenerate it in Jira/Confluence profile settings and update that file. Never echo the
token or commit it.
