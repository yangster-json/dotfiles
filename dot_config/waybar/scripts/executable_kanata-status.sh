#!/usr/bin/env bash
set -euo pipefail

if systemctl is-active --quiet kanata.service; then
  printf '%s\n' '{"text":"󰌌","tooltip":"Kanata enabled","class":"enabled"}'
else
  printf '%s\n' '{"text":"","class":"disabled"}'
fi
