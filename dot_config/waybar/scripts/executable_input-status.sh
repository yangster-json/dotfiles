#!/usr/bin/env bash
set -euo pipefail

keymap="$(hyprctl devices -j 2>/dev/null | jq -r '.keyboards[] | select(.main == true) | .active_keymap' 2>/dev/null | head -n1 || true)"
case "$keymap" in
  English*) language="eng" ;;
  Arabic*) language="ara" ;;
  *) language="---" ;;
esac

keyboard="<span color='#f9e2af'>󰌌</span> <span color='#cdd6f4'>${language}</span>"
if systemctl is-active --quiet kanata.service; then
  jq -nc --arg text "<span color='#a6e3a1'>󰌌</span> ${keyboard}" --arg tooltip "Kanata enabled — ${keymap:-keyboard unavailable}" '{text: $text, tooltip: $tooltip, class: "enabled"}'
else
  jq -nc --arg text "$keyboard" --arg tooltip "${keymap:-Keyboard unavailable}" '{text: $text, tooltip: $tooltip, class: "disabled"}'
fi
