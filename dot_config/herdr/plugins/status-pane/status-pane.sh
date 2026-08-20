#!/bin/sh

HERDR="${HERDR_BIN_PATH:-herdr}"
STATE="${HERDR_PLUGIN_STATE_DIR:-/tmp}"
INTERVAL=30
TTL=45000
SOURCE=dotfiles-statusline
PIDFILE="$STATE/statusline.pid"

workspace_ids() {
    "$HERDR" workspace list 2>/dev/null |
        jq -r '(.result.workspaces // .workspaces // [])[] | .workspace_id // empty' 2>/dev/null
}

report() {
    date=$(TZ=America/Los_Angeles date '+%a %b %d')
    time=$(TZ=America/Los_Angeles date '+%H:%M')

    workspace_ids | while IFS= read -r workspace; do
        [ -n "$workspace" ] || continue
        "$HERDR" workspace report-metadata "$workspace" \
            --source "$SOURCE" \
            --token "sys_date=$date" \
            --token "sys_time=$time" \
            --ttl-ms "$TTL" >/dev/null 2>&1
    done
}

mkdir -p "$STATE" 2>/dev/null

if [ "${1:-}" = "--once" ]; then
    report
    exit 0
fi

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
    exit 0
fi
printf '%s\n' "$$" > "$PIDFILE"

while :; do
    report
    sleep "$INTERVAL"
done
