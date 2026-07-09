#!/bin/sh
# combined statusline: base line (statusline-command.py) + sdd segment when
# an sdd feature is active in the current project. registered in
# ~/.claude/settings.json.
input=$(cat)
base=$(printf '%s' "$input" | python3 "$HOME/.claude/statusline-command.py" 2>/dev/null)
sdd=$(printf '%s' "$input" | python3 "$HOME/.claude/sdd/statusline-segment.py" 2>/dev/null)
if [ -n "$sdd" ]; then
    printf '%s  \033[2m|\033[0m %s\n' "$base" "$sdd"
else
    printf '%s\n' "$base"
fi
