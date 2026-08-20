#!/usr/bin/env python3
"""Read/write Jira and Confluence over REST."""

import argparse
import base64
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ENV_FILES = (
    os.path.expanduser("~/.pi/agent/.atlassian.env"),
    os.path.expanduser("~/.pi/agent/.atlassian-cloud.env"),
)


def load_env():
    """Loads Jira credentials from local environment files."""
    cfg = {}
    for env_file in ENV_FILES:
        if not os.path.exists(env_file):
            continue
        with open(env_file) as input_file:
            for line in input_file:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    cfg[key.strip()] = value.strip()
    for key in (
            "JIRA_URL", "JIRA_PERSONAL_TOKEN", "JIRA_CLOUD_URL",
            "JIRA_CLOUD_EMAIL", "JIRA_CLOUD_API_TOKEN", "CONFLUENCE_URL",
            "CONFLUENCE_PERSONAL_TOKEN"):
        if os.environ.get(key):
            cfg[key] = os.environ[key]
    return cfg


def api(base, authorization, path, params=None, data=None, method=None, raw=False):
    """Sends an authenticated REST request."""
    url = base.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    body = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(url, data=body, method=method or ("POST" if data else "GET"))
    request.add_header("Authorization", authorization)
    request.add_header("Accept", "application/json")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            content = response.read()
            return content if raw else json.loads(content)
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:500]
        raise RuntimeError(f"HTTP {error.code} {url}\n{detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"connection failed: {error.reason}\n{url}") from error


def jira_config(cfg, cloud):
    """Selects Jira Server or Cloud credentials."""
    if cloud:
        missing = [key for key in ("JIRA_CLOUD_URL", "JIRA_CLOUD_EMAIL", "JIRA_CLOUD_API_TOKEN")
                   if not cfg.get(key)]
        if missing:
            raise RuntimeError("missing " + ", ".join(missing) + " — configure " + ENV_FILES[1])
        credentials = f"{cfg['JIRA_CLOUD_EMAIL']}:{cfg['JIRA_CLOUD_API_TOKEN']}".encode()
        return cfg["JIRA_CLOUD_URL"], "Basic " + base64.b64encode(credentials).decode(), "/rest/api/3", True
    missing = [key for key in ("JIRA_URL", "JIRA_PERSONAL_TOKEN") if not cfg.get(key)]
    if missing:
        raise RuntimeError("missing " + ", ".join(missing) + " — configure " + ENV_FILES[0])
    return cfg["JIRA_URL"], "Bearer " + cfg["JIRA_PERSONAL_TOKEN"], "/rest/api/2", False


def adf_text(node, indent=""):
    """Flattens Atlassian document format into readable text."""
    if not node:
        return ""
    if isinstance(node, list):
        return "".join(adf_text(child, indent) for child in node)
    node_type = node.get("type")
    if node_type == "text":
        return node.get("text", "")
    if node_type == "hardBreak":
        return "\n"
    contents = node.get("content", [])
    if node_type == "listItem":
        return indent + "- " + adf_text(contents, indent + "  ").strip() + "\n"
    if node_type in ("bulletList", "orderedList"):
        return adf_text(contents, indent)
    text = adf_text(contents, indent)
    if node_type in ("paragraph", "heading", "codeBlock"):
        return text.rstrip() + "\n\n"
    return text


def jira_text(value, cloud):
    """Converts Jira Server markup or Cloud ADF to text."""
    return adf_text(value).strip() if cloud and isinstance(value, dict) else (value or "").strip()


def cloud_comment(body):
    """Converts plain text to a minimal Cloud comment document."""
    paragraphs = []
    for paragraph in body.strip().split("\n\n"):
        paragraphs.append({"type": "paragraph", "content": [{"type": "text", "text": paragraph}]})
    return {"type": "doc", "version": 1, "content": paragraphs}


def strip_html(value):
    """Flattens confluence storage-format markup into readable text."""
    if not value:
        return ""
    value = re.sub(r"<(br|/p|/h[1-6]|/li|/tr)[^>]*>", "\n", value)
    value = re.sub(r"<li[^>]*>", "- ", value)
    value = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(value)).strip()


JIRA_FIELDS = ("summary,status,resolution,priority,assignee,reporter,created,updated,"
               "labels,components,issuelinks,description,attachment")


def cmd_issue(cfg, args):
    base, authorization, api_path, cloud = jira_config(cfg, args.cloud)
    fields = JIRA_FIELDS + (",comment" if args.comments else "")
    issue = api(base, authorization, f"{api_path}/issue/{args.key}", {"fields": fields})
    fields = issue["fields"]
    name = lambda value: (value or {}).get("displayName") or (value or {}).get("name") or "-"
    print(f"{issue['key']}: {fields.get('summary', '')}")
    print(f"{base}/browse/{issue['key']}")
    print(f"status={(fields.get('status') or {}).get('name')}  "
          f"resolution={(fields.get('resolution') or {}).get('name', '-')}  "
          f"priority={(fields.get('priority') or {}).get('name', '-')}")
    print(f"assignee={name(fields.get('assignee'))}  reporter={name(fields.get('reporter'))}")
    print(f"created={fields.get('created', '')[:19]}  updated={fields.get('updated', '')[:19]}")
    if fields.get("labels"):
        print("labels: " + ", ".join(fields["labels"]))
    if fields.get("components"):
        print("components: " + ", ".join(component["name"] for component in fields["components"]))
    for attachment in fields.get("attachment") or []:
        print(f"attachment: {attachment['filename']} ({attachment.get('size', 0)} bytes)")
    description = jira_text(fields.get("description"), cloud)
    if description:
        print("\n--- description ---\n" + description)
    for comment in (fields.get("comment") or {}).get("comments", []):
        print(f"\n--- comment by {name(comment.get('author'))} {comment.get('created', '')[:19]} ---")
        print(jira_text(comment.get("body"), cloud))


def cmd_search(cfg, args):
    base, authorization, api_path, _ = jira_config(cfg, args.cloud)
    result = api(base, authorization, f"{api_path}/search",
                 {"jql": args.jql, "maxResults": args.limit,
                  "fields": "key,summary,status,created,assignee"})
    print(f"{result.get('total', 0)} match, showing {len(result.get('issues', []))}")
    for issue in result.get("issues", []):
        fields = issue["fields"]
        print(f"{issue['key']:14s} {(fields.get('status') or {}).get('name', '')[:12]:13s} "
              f"{fields.get('created', '')[:10]}  {fields.get('summary', '')[:90]}")


def cmd_attachments(cfg, args):
    base, authorization, api_path, _ = jira_config(cfg, args.cloud)
    issue = api(base, authorization, f"{api_path}/issue/{args.key}", {"fields": "attachment"})
    attachments = issue["fields"].get("attachment") or []
    if not attachments:
        print("no attachments")
        return
    os.makedirs(args.dest, exist_ok=True)
    for attachment in attachments:
        request = urllib.request.Request(attachment["content"])
        request.add_header("Authorization", authorization)
        with urllib.request.urlopen(request, timeout=120) as response:
            blob = response.read()
        output = os.path.join(args.dest, attachment["filename"])
        with open(output, "wb") as output_file:
            output_file.write(blob)
        print(f"{output}  ({len(blob)} bytes)")


def cmd_comment(cfg, args):
    base, authorization, api_path, cloud = jira_config(cfg, args.cloud)
    body = args.body if args.body != "-" else sys.stdin.read()
    data = {"body": cloud_comment(body)} if cloud else {"body": body}
    result = api(base, authorization, f"{api_path}/issue/{args.key}/comment", data=data)
    print(f"posted comment {result.get('id')} to {base}/browse/{args.key}")


def cmd_page(cfg, args):
    page_id = re.sub(r".*(?:pageId=|/pages/)(\d+).*", r"\1", args.page)
    if not cfg.get("CONFLUENCE_URL") or not cfg.get("CONFLUENCE_PERSONAL_TOKEN"):
        raise RuntimeError("missing Confluence credentials — configure " + ENV_FILES[0])
    result = api(cfg["CONFLUENCE_URL"], "Bearer " + cfg["CONFLUENCE_PERSONAL_TOKEN"],
                 f"/rest/api/content/{page_id}", {"expand": "body.storage,space,version"})
    print(f"{result['title']}  (id={result['id']}, space={(result.get('space') or {}).get('key', '-')}"
          f", v{(result.get('version') or {}).get('number', '?')})")
    print(strip_html((result.get("body", {}).get("storage") or {}).get("value", "")))


def main():
    parser = argparse.ArgumentParser(prog="atl", description=__doc__)
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    for command, help_text in (("issue", "fetch a Jira issue"), ("search", "run a Jira JQL search"),
                               ("attachments", "download Jira attachments"), ("comment", "post a Jira comment")):
        subparser = subparsers.add_parser(command, help=help_text)
        subparser.add_argument("--cloud", action="store_true", help="use purestorage.atlassian.net")
        if command == "issue":
            subparser.add_argument("key")
            subparser.add_argument("--comments", action="store_true")
            subparser.set_defaults(fn=cmd_issue)
        elif command == "search":
            subparser.add_argument("jql")
            subparser.add_argument("--limit", type=int, default=10)
            subparser.set_defaults(fn=cmd_search)
        elif command == "attachments":
            subparser.add_argument("key")
            subparser.add_argument("dest", nargs="?", default=".")
            subparser.set_defaults(fn=cmd_attachments)
        else:
            subparser.add_argument("key")
            subparser.add_argument("body")
            subparser.set_defaults(fn=cmd_comment)
    subparser = subparsers.add_parser("page", help="fetch a Confluence page as text")
    subparser.add_argument("page")
    subparser.set_defaults(fn=cmd_page)
    args = parser.parse_args()
    try:
        args.fn(load_env(), args)
    except RuntimeError as error:
        sys.exit(str(error))


if __name__ == "__main__":
    main()
