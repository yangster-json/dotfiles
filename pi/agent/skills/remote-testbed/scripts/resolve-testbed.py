#!/usr/bin/env python3
"""Resolve a testbed nickname through RAS without third-party dependencies."""

import json
import sys
from urllib.error import HTTPError
from urllib.request import urlopen

RAS_URL = "https://ras.dev.purestorage.com/api/node/{}"


def get_node(name):
    with urlopen(RAS_URL.format(name), timeout=30) as response:
        return json.load(response)


def main():
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {sys.argv[0]} <testbed>")

    requested_name = sys.argv[1]
    candidates = [requested_name]
    if not requested_name.startswith("lp-"):
        candidates.append(f"lp-{requested_name}")

    last_error = None
    for candidate in candidates:
        try:
            node = get_node(candidate)
            print(json.dumps(node, indent=2, sort_keys=True))
            return
        except HTTPError as error:
            last_error = error
            if error.code != 404:
                raise

    raise SystemExit(f"RAS target not found: {requested_name} ({last_error})")


if __name__ == "__main__":
    main()
