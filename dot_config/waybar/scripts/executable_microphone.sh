#!/usr/bin/env bash
set -euo pipefail

escape_json() {
  local value=$1
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  value=${value//$'\n'/\\n}
  printf '%s' "$value"
}

status=$(wpctl get-volume @DEFAULT_AUDIO_SOURCE@ 2>/dev/null || true)
if [[ -z $status ]]; then
  printf '%s\n' '{"text":"󰍭","class":"unavailable","tooltip":"No microphone available"}'
  exit 0
fi

device=$(wpctl inspect @DEFAULT_AUDIO_SOURCE@ 2>/dev/null | awk -F' = ' '/node.description = / { gsub(/^"|"$/, "", $2); print $2; exit }' || true)
device=${device:-Unknown input device}
volume=$(awk '{ printf "%.0f", $2 * 100 }' <<< "$status")
if [[ $status == *MUTED* ]]; then
  icon='󰍭'
  class='muted'
  state='Muted'
else
  icon='󰍬'
  class='unmuted'
  state='Active'
fi

tooltip=$(escape_json "Input: $device"$'\n'"Volume: $volume%"$'\n'"Status: $state")
printf '{"text":"%s","class":"%s","tooltip":"%s"}\n' "$icon" "$class" "$tooltip"
