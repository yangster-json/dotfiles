#!/usr/bin/env bash
set -euo pipefail

updates=$(checkupdates 2>/dev/null || true)
count=$(printf '%s\n' "$updates" | sed '/^$/d' | wc -l)
(( count > 0 )) || exit 0

printf '{"text":"󰚰 %s","tooltip":"%s package updates available\\nClick to update"}\n' "$count" "$count"
