#!/usr/bin/env bash
# PostToolUse hook: format the edited C/C++/Python file with the repo's pure_astyle.
#
# Wired to Edit|Write|MultiEdit in ~/.claude/settings.json. Runs on every edit but
# no-ops unless a pure_astyle script is found by walking up from the edited file, so
# it only acts inside firmware checkouts. Never blocks a tool call — always exits 0.

set -u

# hook payload arrives as JSON on stdin
payload="$(cat)"

# prefer the tool response path, fall back to the tool input path
file="$(printf '%s' "$payload" | jq -r '.tool_response.filePath // .tool_input.file_path // empty' 2>/dev/null)"
[ -n "$file" ] && [ -f "$file" ] || exit 0

# only languages pure_astyle handles (astyle for C/C++, black for python)
case "$file" in
    *.c|*.cc|*.cpp|*.cxx|*.h|*.hpp|*.hxx|*.py) ;;
    *) exit 0 ;;
esac

# walk up from the file's dir to find an executable pure_astyle
dir="$(cd "$(dirname "$file")" && pwd)" || exit 0
astyle=""
while : ; do
    if [ -x "$dir/pure_astyle" ]; then
        astyle="$dir/pure_astyle"
        break
    fi
    [ "$dir" = "/" ] && break
    dir="$(dirname "$dir")"
done
[ -n "$astyle" ] || exit 0

# format in place; stay silent and never fail the edit
"$astyle" "$file" >/dev/null 2>&1 || true
exit 0
