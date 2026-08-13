#!/usr/bin/env python3
"""Map a URL hostname to a site workflow."""

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

RULES = (
    (r"(^|\.)mfg\.purestorage\.com$", "pure-mfg-navigation.md"),
    (r"(^|\.)jira\.purestorage\.com$", "atlassian.md"),
    (r"(^|\.)wiki\.purestorage\.com$", "atlassian.md"),
)
FALLBACK = "generic.md"


def hostname(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    if not parsed.hostname:
        raise ValueError(f"Invalid URL: {url}")
    return parsed.hostname.lower().rstrip(".")


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {Path(sys.argv[0]).name} <url>", file=sys.stderr)
        return 2

    try:
        host = hostname(sys.argv[1])
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    for pattern, workflow in RULES:
        if re.search(pattern, host):
            print(f"sites/{workflow}")
            return 0

    print(f"sites/{FALLBACK}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
