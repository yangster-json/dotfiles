#!/usr/bin/env bash
set -euo pipefail

keymap="$(hyprctl devices -j 2>/dev/null | jq -r '.keyboards[] | select(.main == true) | .active_keymap' 2>/dev/null | head -n1 || true)"
case "$keymap" in
  English*) language="eng" ;;
  Arabic*) language="ara" ;;
  *) language="---" ;;
esac

keyboard="<span color='#cba6f7'>󰌌</span> <span color='#cba6f7'>${language}</span>"
jq -nc --arg text "$keyboard" --arg tooltip "${keymap:-Keyboard unavailable}" '{text: $text, tooltip: $tooltip}'
