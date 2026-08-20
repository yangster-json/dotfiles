#!/bin/sh

HERDR="${HERDR_BIN_PATH:-herdr}"
STATE="${HERDR_PLUGIN_STATE_DIR:-/tmp}"
INTERVAL=30
TTL=45000        # > interval, so a token left on an unfocused space expires itself

focused_workspace() {
    "$HERDR" workspace list 2>/dev/null | python3 -c '
import sys, json
try:
    ws = json.load(sys.stdin)["result"]["workspaces"]
except Exception:
    sys.exit(0)
print(next((w["workspace_id"] for w in ws if w.get("focused")), ""))
'
}

report() {
    ws=$(focused_workspace)
    [ -n "$ws" ] || return 0
    "$HERDR" workspace report-metadata "$ws" \
        --source dotfiles-clock \
        --token time="$(TZ=America/Los_Angeles date +'%H:%M %d-%b-%y')" \
        --ttl-ms "$TTL" >/dev/null 2>&1
}

if [ "$1" = "--once" ]; then
    report
    exit 0
fi

PIDFILE="$STATE/clock.pid"
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE" 2>/dev/null)" 2>/dev/null; then
    exit 0
fi
echo $$ > "$PIDFILE"

while :; do
    report
    sleep "$INTERVAL"
done
