#!/usr/bin/env bash
set -euo pipefail

updates=$(checkupdates 2>/dev/null || true)
count=$(printf '%s\n' "$updates" | sed '/^$/d' | wc -l)
if (( count > 0 )); then
  tooltip="$count package updates available"$'\nClick to update'
  printf '{"text":"󰚰 %d","tooltip":"%s","class":"has-updates"}\n' "$count" "$tooltip"
else
  printf '{"text":"","tooltip":"","class":"hidden"}\n'
fi
