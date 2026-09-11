#!/usr/bin/env bash
set -euo pipefail

updates=$(checkupdates 2>/dev/null || true)
count=$(printf '%s\n' "$updates" | sed '/^$/d' | wc -l)
if (( count > 0 )); then
  tooltip="$count package updates available"$'\nClick to update'
else
  tooltip='System is up to date'
fi

printf '{"text":"󰚰 %3d","tooltip":"%s"}\n' "$count" "$tooltip"
