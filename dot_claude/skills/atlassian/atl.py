#!/usr/bin/env python3
"""Read/write Jira and Confluence over REST, replacing the atlassian MCP servers."""

import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ENV_FILE = os.path.expanduser("~/.claude/.atlassian.env")


def load_env():
    """Load PATs from the environment, falling back to the gitignored env file."""
    cfg = {}
    if os.path.exists(ENV_FILE):
        for line in open(ENV_FILE):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    # real env wins so a session can point at a different instance
    for k in ("JIRA_URL", "JIRA_PERSONAL_TOKEN", "CONFLUENCE_URL", "CONFLUENCE_PERSONAL_TOKEN"):
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    return cfg


def api(base, token, path, params=None, data=None, method=None, raw=False):
    url = base.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method or ("POST" if data else "GET"))
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            content = r.read()
            return content if raw else json.loads(content)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        sys.exit(f"HTTP {e.code} {url}\n{detail}")
    except urllib.error.URLError as e:
        sys.exit(f"connection failed: {e.reason}\n{url}")


def strip_html(s):
    """Flatten confluence storage-format markup into readable text."""
    if not s:
        return ""
    s = re.sub(r"<(br|/p|/h[1-6]|/li|/tr)[^>]*>", "\n", s)
    s = re.sub(r"<li[^>]*>", "- ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


# --- jira ----------------------------------------------------------------

JIRA_FIELDS = ("summary,status,resolution,priority,assignee,reporter,created,updated,"
               "labels,components,issuelinks,description,attachment")


def cmd_issue(cfg, a):
    fields = JIRA_FIELDS + (",comment" if a.comments else "")
    d = api(cfg["JIRA_URL"], cfg["JIRA_PERSONAL_TOKEN"], f"/rest/api/2/issue/{a.key}",
            {"fields": fields})
    f = d["fields"]
    name = lambda x: (x or {}).get("displayName") or (x or {}).get("name") or "-"
    print(f"{d['key']}: {f.get('summary','')}")
    print(f"{cfg['JIRA_URL']}/browse/{d['key']}")
    print(f"status={(f.get('status') or {}).get('name')}  "
          f"resolution={(f.get('resolution') or {}).get('name','-')}  "
          f"priority={(f.get('priority') or {}).get('name','-')}")
    print(f"assignee={name(f.get('assignee'))}  reporter={name(f.get('reporter'))}")
    print(f"created={f.get('created','')[:19]}  updated={f.get('updated','')[:19]}")
    if f.get("labels"):
        print("labels: " + ", ".join(f["labels"]))
    if f.get("components"):
        print("components: " + ", ".join(c["name"] for c in f["components"]))
    for l in f.get("issuelinks") or []:
        other = l.get("outwardIssue") or l.get("inwardIssue")
        if other:
            rel = l["type"]["outward"] if l.get("outwardIssue") else l["type"]["inward"]
            print(f"link: {rel} {other['key']} — {other['fields']['summary'][:70]}")
    for at in f.get("attachment") or []:
        print(f"attachment: {at['filename']} ({at.get('size',0)} bytes)")
    if f.get("description"):
        print("\n--- description ---\n" + f["description"].strip())
    for c in (f.get("comment") or {}).get("comments", []):
        print(f"\n--- comment by {name(c.get('author'))} {c.get('created','')[:19]} ---")
        print(c["body"].strip())


def cmd_search(cfg, a):
    d = api(cfg["JIRA_URL"], cfg["JIRA_PERSONAL_TOKEN"], "/rest/api/2/search",
            {"jql": a.jql, "maxResults": a.limit, "fields": "key,summary,status,created,assignee"})
    print(f"{d.get('total', 0)} match, showing {len(d.get('issues', []))}")
    for i in d.get("issues", []):
        f = i["fields"]
        print(f"{i['key']:14s} {(f.get('status') or {}).get('name','')[:12]:13s} "
              f"{f.get('created','')[:10]}  {f.get('summary','')[:90]}")


def cmd_attachments(cfg, a):
    d = api(cfg["JIRA_URL"], cfg["JIRA_PERSONAL_TOKEN"], f"/rest/api/2/issue/{a.key}",
            {"fields": "attachment"})
    atts = d["fields"].get("attachment") or []
    if not atts:
        print("no attachments")
        return
    os.makedirs(a.dest, exist_ok=True)
    for at in atts:
        req = urllib.request.Request(at["content"])
        req.add_header("Authorization", f"Bearer {cfg['JIRA_PERSONAL_TOKEN']}")
        with urllib.request.urlopen(req, timeout=120) as r:
            blob = r.read()
        out = os.path.join(a.dest, at["filename"])
        open(out, "wb").write(blob)
        print(f"{out}  ({len(blob)} bytes)")


def cmd_comment(cfg, a):
    body = a.body if a.body != "-" else sys.stdin.read()
    d = api(cfg["JIRA_URL"], cfg["JIRA_PERSONAL_TOKEN"],
            f"/rest/api/2/issue/{a.key}/comment", data={"body": body})
    print(f"posted comment {d.get('id')} to {cfg['JIRA_URL']}/browse/{a.key}")


# --- confluence ----------------------------------------------------------

def cmd_page(cfg, a):
    pid = a.page
    m = re.search(r"pageId=(\d+)", pid) or re.search(r"/pages/(\d+)", pid)
    if m:
        pid = m.group(1)
    d = api(cfg["CONFLUENCE_URL"], cfg["CONFLUENCE_PERSONAL_TOKEN"],
            f"/rest/api/content/{pid}", {"expand": "body.storage,space,version"})
    print(f"{d['title']}  (id={d['id']}, space={(d.get('space') or {}).get('key','-')}, "
          f"v{(d.get('version') or {}).get('number','?')})")
    print(f"{cfg['CONFLUENCE_URL']}/pages/viewpage.action?pageId={d['id']}\n")
    print(strip_html((d.get("body", {}).get("storage") or {}).get("value", "")))


def cmd_cql(cfg, a):
    d = api(cfg["CONFLUENCE_URL"], cfg["CONFLUENCE_PERSONAL_TOKEN"],
            "/rest/api/content/search", {"cql": a.cql, "limit": a.limit})
    results = d.get("results", [])
    print(f"{len(results)} result(s)")
    for r in results:
        print(f"{r['id']:12s} {r.get('type',''):6s} {r.get('title','')[:80]}")


def main():
    p = argparse.ArgumentParser(prog="atl", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("issue", help="fetch a jira issue")
    s.add_argument("key")
    s.add_argument("--comments", action="store_true", help="include all comments")
    s.set_defaults(fn=cmd_issue)

    s = sub.add_parser("search", help="jira JQL search")
    s.add_argument("jql")
    s.add_argument("--limit", type=int, default=10)
    s.set_defaults(fn=cmd_search)

    s = sub.add_parser("attachments", help="download a jira issue's attachments")
    s.add_argument("key")
    s.add_argument("dest", nargs="?", default=".")
    s.set_defaults(fn=cmd_attachments)

    s = sub.add_parser("comment", help="post a jira comment (body '-' reads stdin)")
    s.add_argument("key")
    s.add_argument("body")
    s.set_defaults(fn=cmd_comment)

    s = sub.add_parser("page", help="fetch a confluence page as text")
    s.add_argument("page", help="page id or url")
    s.set_defaults(fn=cmd_page)

    s = sub.add_parser("cql", help="confluence CQL search")
    s.add_argument("cql")
    s.add_argument("--limit", type=int, default=10)
    s.set_defaults(fn=cmd_cql)

    a = p.parse_args()
    cfg = load_env()
    need = ("CONFLUENCE_URL", "CONFLUENCE_PERSONAL_TOKEN") if a.cmd in ("page", "cql") \
        else ("JIRA_URL", "JIRA_PERSONAL_TOKEN")
    missing = [k for k in need if not cfg.get(k)]
    if missing:
        sys.exit(f"missing {', '.join(missing)} — set in env or {ENV_FILE}")
    a.fn(cfg, a)


if __name__ == "__main__":
    main()
