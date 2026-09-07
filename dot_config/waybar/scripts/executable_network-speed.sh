#!/usr/bin/env bash
set -euo pipefail

iface=$(awk '$2 == "00000000" { print $1; exit }' /proc/net/route)
if [[ -z ${iface:-} || ! -r /sys/class/net/$iface/statistics/rx_bytes ]]; then
  # Keep the disconnected output as wide as the live-rate display so the icon
  # remains aligned when Waybar reserves this module's fixed-width slot.
  printf '󰤭 ↓ %4s\n' ""
  exit 0
fi

state_file="${XDG_RUNTIME_DIR:-/tmp}/waybar-network-speed-${UID}-${iface}"
now=$(date +%s)
received=$(<"/sys/class/net/$iface/statistics/rx_bytes")

if [[ -r $state_file ]]; then
  read -r previous_time previous_bytes < "$state_file" || true
  elapsed=$((now - previous_time))
  if (( elapsed > 0 && received >= previous_bytes )); then
    rate=$(((received - previous_bytes) / elapsed))
  else
    rate=0
  fi
else
  rate=0
fi

umask 077
printf '%s %s\n' "$now" "$received" > "$state_file"
speed=$(numfmt --to=si --format='%.0f' "$rate")
# Reserve the final column for the SI suffix, including for byte-per-second rates.
if [[ $speed != *[[:alpha:]] ]]; then
  speed+=" "
fi
printf '󰤨 ↓ %4s\n' "$speed"
