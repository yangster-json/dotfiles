#!/usr/bin/env bash
set -euo pipefail

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
settings="$source_dir/dot_pi/agent/settings.json.tmpl"
rename_config="$source_dir/dot_pi/agent/config/pi-herdr-rename.json.tmpl"
btw_config="$source_dir/dot_pi/agent/pi-btw.json.tmpl"
ignore="$source_dir/.chezmoiignore"

render() {
  local hostname=$1
  local os=$2
  local template=$3

  chezmoi execute-template --source "$source_dir" \
    --override-data "{\"chezmoi\":{\"hostname\":\"$hostname\",\"os\":\"$os\"}}" \
    < "$template"
}

assert_contains() {
  local content=$1
  local expected=$2

  grep -Fqx -- "$expected" <<<"$content" >/dev/null || {
    printf 'expected %q in rendered output\n' "$expected" >&2
    exit 1
  }
}

assert_excludes() {
  local content=$1
  local unexpected=$2

  ! grep -Fqx -- "$unexpected" <<<"$content" || {
    printf 'did not expect %q in rendered output\n' "$unexpected" >&2
    exit 1
  }
}

fw_settings=$(render dev-jasyang linux "$settings")
generic_settings=$(render generic-host linux "$settings")
fw_rename_config=$(render dev-jasyang linux "$rename_config")
generic_rename_config=$(render generic-host linux "$rename_config")
fw_btw_config=$(render dev-jasyang linux "$btw_config")
generic_btw_config=$(render generic-host linux "$btw_config")
windows_ignore=$(render generic-host windows "$ignore")

jq -e '.defaultProvider == "everpure-foundry" and .defaultModel == "cascade/gpt-5.6-terra"' \
  <<<"$fw_settings" >/dev/null
jq -e '.defaultProvider == "openai-codex" and .defaultModel == "gpt-5.6-terra"' \
  <<<"$generic_settings" >/dev/null
jq -e '.model == "everpure-foundry/cascade/gpt-5.6-luna"' \
  <<<"$fw_rename_config" >/dev/null
jq -e '.model == "openai-codex/gpt-5.6-luna"' \
  <<<"$generic_rename_config" >/dev/null
jq -e '.model == "everpure-foundry/cascade/gpt-5.6-luna"' \
  <<<"$fw_btw_config" >/dev/null
jq -e '.model == "openai-codex/gpt-5.6-luna"' \
  <<<"$generic_btw_config" >/dev/null

assert_contains "$windows_ignore" '.pi/agent/skills/firmware-tlogs-search'
assert_contains "$windows_ignore" '.pi/agent/skills/remote-testbed*'
assert_excludes "$windows_ignore" '.wezterm.lua'

printf 'profile verification passed\n'
