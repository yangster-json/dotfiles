#!/bin/sh
# SessionStart/UserPromptSubmit/Stop hook: report the Claude Code session
# title (/rename or auto-generated summary) to herdr as pane metadata.
#
# Adapted from https://github.com/bcihanc/herdr-claude-session-title.
# No-ops outside a herdr pane or without python3; never blocks Claude Code.
set -eu

[ "${HERDR_ENV:-}" = "1" ] || exit 0
[ -n "${HERDR_SOCKET_PATH:-}" ] || exit 0
[ -n "${HERDR_PANE_ID:-}" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$script_dir/herdr-claude-session-title.py"
