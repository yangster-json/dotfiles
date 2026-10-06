# Jira & Confluence (`atl.py`, direct REST)

```
A=~/.skills/web-browse/sites/atlassian/atl.py
```

| Command | Purpose |
|---|---|
| `python3 $A issue FW-29029 [--comments] [--cloud]` | ticket: status, assignee, labels, attachments, description |
| `python3 $A search '<JQL>' [--limit N] [--cloud]` | Jira search (default 10) |
| `python3 $A attachments FAIL-1095379 [dest] [--cloud]` | download all attachments (default `.`) |
| `python3 $A comment FW-29029 '<body>' [--cloud]` | post comment; body `-` = stdin |
| `python3 $A page <id\|url>` | Confluence page text (id from `pageId=` or `/pages/<id>`) |
| `python3 $A cql '<CQL>' [--limit N]` | Confluence search |

- Triage needs `--comments` (PTA Bot + human notes live there).
- Server/DC default, wiki markup (`h2.`, `{{code}}`). `--cloud` = `purestorage.atlassian.net` (e.g. `MFGDFM-447`); reads ADF, posts plain text as ADF.
- Text search: `text ~ "watchdog" AND project = FW ORDER BY created DESC`.
- Comments are public: confirm exact body with user unless already told to post. Long body: `python3 $A comment FAIL-1095379 - <<'EOF' ... EOF`.
- Creds: `~/.skills/.atlassian.env` (`JIRA_URL`, `JIRA_PERSONAL_TOKEN`, `CONFLUENCE_URL`, `CONFLUENCE_PERSONAL_TOKEN`); Cloud `~/.skills/.atlassian-cloud.env` (`JIRA_CLOUD_URL`, `JIRA_CLOUD_EMAIL`, `JIRA_CLOUD_API_TOKEN`); env vars override. 401/403 → regenerate token in profile. Never echo/commit.
