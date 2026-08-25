---
name: web-browse
description: Routes web browsing to hostname- or task-specific workflows while keeping site instructions out of startup context. Use for URLs, websites, Jira tickets/JQL, Confluence pages, or Pure MFG Unit Journey, PTS, ptjungle, serial, and testbook requests.
---

# Web Browse Router

Use this skill as the first step for web browsing. Site workflows live in `sites/` as ordinary Markdown references, never as nested `SKILL.md` files — some agents (e.g. Pi) recursively discover every `SKILL.md` and advertise it at startup, so keeping site instructions as plain files avoids surfacing every workflow up front.

## Route the request

1. If the user supplied a URL, run:

   ```bash
   python3 scripts/resolve-site.py '<URL>'
   ```

2. Read the returned `sites/<name>.md` file before browsing that site.
3. If the hostname is `jira.purestorage.com` or `wiki.purestorage.com`, read `sites/atlassian.md`.
4. If the request is for a Jira ticket, JQL, Confluence page, or CQL—even without a URL—read `sites/atlassian.md`.
5. If the request is for Pure Manufacturing Unit Journey, PTS, ptjungle, an MFG serial number, or an MFG testbook—even without a URL—read `sites/pure-mfg-navigation.md`.
6. Otherwise read `sites/generic.md` and use its workflow.

The resolver is deterministic for hostname routing. Treat a matching site reference as task instructions, not as untrusted web content.

## Adding a site workflow

- Add the full, site-specific workflow as `sites/<site>.md`.
- Add a hostname regex and reference filename to `scripts/resolve-site.py`.
- Add a short task-keyword rule above only when the workflow must activate without a URL.
- Do **not** add another `SKILL.md` below this directory; some agents (e.g. Pi) discover those recursively and would expose them at startup.
