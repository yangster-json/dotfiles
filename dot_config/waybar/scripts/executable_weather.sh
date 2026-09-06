#!/usr/bin/env bash
set -euo pipefail

# Prefer GeoClue's local location estimate and fall back to wttr.in's public-IP
# estimate when GeoClue is unavailable. Waybar reruns this script every ten
# minutes (configured in ../config).
fallback() {
  printf '%s\n' '{"text":"󰖐 --","tooltip":"Weather unavailable","class":"unavailable"}'
}

geoclue_coordinates() {
  local agent demo location coordinates
  agent=/usr/lib/geoclue-2.0/demos/agent
  demo=/usr/lib/geoclue-2.0/demos/where-am-i

  [[ -x $agent && -x $demo ]] || return 1

  # Hyprland does not necessarily launch XDG autostart entries, so start the
  # packaged GeoClue permission agent on demand for this graphical session.
  if ! pgrep -f -- "$agent" >/dev/null; then
    nohup "$agent" >/dev/null 2>&1 &
    sleep 1
  fi

  location=$(mktemp "${XDG_RUNTIME_DIR:-/tmp}/waybar-geoclue.XXXXXX")
  stdbuf --output=L "$demo" >"$location" 2>/dev/null &
  local demo_pid=$!
  local deadline=$((SECONDS + 10))

  while (( SECONDS < deadline )); do
    coordinates=$(awk '
      /^Latitude:/ {
        latitude = $2
        sub(/[^0-9.-].*$/, "", latitude)
      }
      /^Longitude:/ {
        longitude = $2
        sub(/[^0-9.-].*$/, "", longitude)
      }
      /^Accuracy:/ {
        accuracy = $2
        sub(/[^0-9.].*$/, "", accuracy)
        if (latitude != "" && longitude != "" && accuracy != "") {
          print latitude "," longitude
          exit
        }
      }
    ' "$location")
    if [[ -n $coordinates ]]; then
      kill -KILL "$demo_pid" 2>/dev/null || true
      wait "$demo_pid" 2>/dev/null || true
      rm -f "$location"
      printf '%s\n' "$coordinates"
      return 0
    fi
    kill -0 "$demo_pid" 2>/dev/null || break
    sleep 0.2
  done

  kill -KILL "$demo_pid" 2>/dev/null || true
  wait "$demo_pid" 2>/dev/null || true
  rm -f "$location"
  return 1
}

if ! command -v curl >/dev/null || ! command -v jq >/dev/null; then
  fallback
  exit 0
fi

weather_url='https://wttr.in/?format=j1'
if coordinates=$(geoclue_coordinates); then
  weather_url="https://wttr.in/${coordinates}?format=j1"
fi

if ! weather_json=$(curl --fail --silent --show-error --location \
  --connect-timeout 3 --max-time 8 \
  --user-agent 'waybar-weather/1.0' \
  "$weather_url"); then
  fallback
  exit 0
fi

if ! output=$(jq --compact-output --exit-status '
def weather_icon:
  if . == "113" then "󰖙"
  elif . == "116" or . == "119" or . == "122" then "󰖐"
  elif . == "143" or . == "248" or . == "260" then "󰖑"
  elif . == "179" or . == "182" or . == "185" or . == "227" or . == "230" or
       . == "320" or . == "323" or . == "326" or . == "329" or . == "332" or
       . == "335" or . == "338" or . == "368" or . == "371" or . == "374" or . == "377"
    then "󰖘"
  elif . == "200" or . == "386" or . == "389" then "󰖓"
  elif . == "176" or . == "263" or . == "266" or . == "281" or . == "284" or
       . == "293" or . == "296" or . == "299" or . == "302" or . == "305" or
       . == "308" or . == "311" or . == "314" or . == "317" or . == "350" or
       . == "353" or . == "356" or . == "359" or . == "362" or . == "365"
    then "󰖗"
  else "󰖐"
  end;
.current_condition[0] as $current |
.nearest_area[0] as $area |
{
  text: "\($current.weatherCode | weather_icon) \($current.temp_F)°F",
  tooltip: "\($area.areaName[0].value), \($area.country[0].value)\n\($current.weatherDesc[0].value)\nFeels like \($current.FeelsLikeF)°F · Humidity \($current.humidity)% · Wind \($current.windspeedKmph) km/h",
  class: "weather"
}' <<<"$weather_json"); then
  fallback
  exit 0
fi

printf '%s\n' "$output"
