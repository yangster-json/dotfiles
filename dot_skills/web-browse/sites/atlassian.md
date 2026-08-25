---
name: atlassian
description: Read and write Pure's Jira (jira.purestorage.com) and Confluence wiki (wiki.purestorage.com) from the command line — fetch a FAIL-/FW- ticket with its comments, run JQL searches, download ticket attachments, post a triage comment, read a wiki page, or run a CQL search. Use whenever a Jira ticket id, Jira URL, JQL query, Confluence page or wiki URL appears in the request, or when triaging a firmware ticket needs the ticket contents.
---

# Jira & Confluence access

`atl.py` in this site workflow talks to the Jira and Confluence REST APIs directly. It replaces the old
`jira-mcp-server` and `wiki-mcp-server` MCP servers, which loaded ~75 tool definitions
into every session to serve the five calls actually used.

```
A=~/.skills/web-browse/sites/atlassian/atl.py
```

## Commands

| Command | Purpose |
|---|---|
| `python3 $A issue FW-29029 [--comments]` | Fetch a Server/DC ticket — status, assignee, labels, attachments, description |
| `python3 $A issue MFGDFM-447 --cloud [--comments]` | Fetch a Jira Cloud ticket |
| `python3 $A search '<JQL>' [--limit N]` | Search Server/DC Jira (default 10 results) |
| `python3 $A search '<JQL>' --cloud [--limit N]` | Search Jira Cloud |
| `python3 $A attachments FAIL-1095379 [dest] [--cloud]` | Download all attachments to `dest` (default `.`) |
| `python3 $A comment FW-29029 '<body>' [--cloud]` | Post a comment; body `-` reads stdin |
| `python3 $A page <id\|url>` | Confluence page as readable text |
| `python3 $A cql '<CQL>' [--limit N]` | Confluence search |

## Usage notes

- **`--comments` matters for triage.** FAIL tickets carry PTA Bot analysis and human
  triage notes in comments; without the flag you get only the description. It is
  omitted by default because busy tickets run long.
- Server/DC is the default and uses wiki markup (`h2.`, `{{code}}`). Use `--cloud` for `purestorage.atlassian.net`; it reads Cloud ADF and posts plain text as ADF.
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

Server/DC personal access tokens live in `~/.skills/.atlassian.env` (mode 600):
`JIRA_URL`, `JIRA_PERSONAL_TOKEN`, `CONFLUENCE_URL`, `CONFLUENCE_PERSONAL_TOKEN`.
Cloud credentials live in `~/.skills/.atlassian-cloud.env` (mode 600):
`JIRA_CLOUD_URL`, `JIRA_CLOUD_EMAIL`, `JIRA_CLOUD_API_TOKEN`. Real environment variables
override either file. On HTTP 401/403, regenerate the applicable token in the Jira or
Confluence profile settings. Never echo tokens or commit either file.
