#!/usr/bin/env bash
set -euo pipefail

# No output hides this module when no MPRIS player provides media metadata.
title=$(playerctl metadata xesam:title 2>/dev/null | head -n 1 || true)
if [[ -n $title ]]; then
  printf '%s\n' "$title"
fi
