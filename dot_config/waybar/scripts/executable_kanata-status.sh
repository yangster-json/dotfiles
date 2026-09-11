#!/usr/bin/env bash
set -euo pipefail

if systemctl is-active --quiet kanata.service; then
  text="<span color='#cba6f7'>󰔡</span>"
  tooltip='Kanata enabled — click to disable'
  class='enabled'
else
  text="<span color='#cba6f7'>󰔢</span>"
  tooltip='Kanata disabled — click to enable'
  class='disabled'
fi

jq -nc --arg text "$text" --arg tooltip "$tooltip" --arg class "$class" '{text: $text, tooltip: $tooltip, class: $class}'
