#!/usr/bin/env bash
set -euo pipefail

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
settings="$source_dir/dot_pi/agent/settings.json.tmpl"
rename_config="$source_dir/dot_pi/agent/config/pi-herdr-rename.json.tmpl"
btw_config="$source_dir/dot_pi/agent/pi-btw.json.tmpl"
ignore="$source_dir/.chezmoiignore"
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT
test_home="$test_dir/existing"
mkdir -p "$test_home/.pi/agent" "$test_dir/fresh"
printf '{"lastChangelogVersion":"local-version"}\n' > "$test_home/.pi/agent/settings.json"

render() {
  local hostname=$1
  local os=$2
  local template=$3
  local home=${4:-$test_home}
  local data
  data=$(jq -nc --arg hostname "$hostname" --arg os "$os" --arg home "$home" \
    '{chezmoi: {hostname: $hostname, os: $os, homeDir: $home}}')

  chezmoi execute-template --source "$source_dir" \
    --override-data "$data" < "$template"
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

jq -e '.defaultProvider == "gpulab" and
  .defaultModel == "claude-opus-5-5" and
  .enabledModels[0] == "gpulab/claude-opus-5-5" and
  (.enabledModels | length) == 7 and
  .subagents.agentOverrides.oracle.model == "gpulab/claude-opus-5-5" and
  .subagents.agentOverrides.advisor.model == "gpulab/claude-opus-5-5" and
  .subagents.agentOverrides.worker.model == "gpulab/gpt-6-sol-claude-compatible[1m]" and
  .subagents.agentOverrides.researcher.model == "gpulab/gpt-6-sol-claude-compatible[1m]" and
  .subagents.agentOverrides.reviewer.model == "gpulab/gpt-6-sol-claude-compatible[1m]" and
  .subagents.agentOverrides.scout.model == "gpulab/gpt-6-luna-claude-compatible[1m]" and
  .subagents.agentOverrides.delegate.model == "gpulab/gpt-6-luna-claude-compatible[1m]"' \
  <<<"$fw_settings" >/dev/null
jq -e '.defaultProvider == "openai-codex" and
  .defaultModel == "gpt-6.1-sol" and
  .enabledModels[0] == "openai-codex/gpt-6.1-sol" and
  (.enabledModels | index("openai-codex/gpt-6-astra")) == null and
  .subagents.agentOverrides.oracle.model == "openai-codex/gpt-6.1-sol" and
  .subagents.agentOverrides.advisor.model == "openai-codex/gpt-6.1-sol" and
  .subagents.agentOverrides.worker.model == "openai-codex/gpt-6-sol" and
  .subagents.agentOverrides.researcher.model == "openai-codex/gpt-6-sol" and
  .subagents.agentOverrides.reviewer.model == "openai-codex/gpt-6-sol" and
  .subagents.agentOverrides.scout.model == "openai-codex/gpt-6-luna" and
  .subagents.agentOverrides.delegate.model == "openai-codex/gpt-6-luna"' \
  <<<"$generic_settings" >/dev/null
jq -e --arg headroom "$test_home/.pi/agent/npm/node_modules/acp-headroom-pi/dist/index.js" \
  '.subagents.defaultExtensions == null and
  .subagents.defaultSubagentOnlyExtensions == ["/u/jasyang/.config/everpure-foundry/pi-extension", $headroom]' \
  <<<"$fw_settings" >/dev/null
jq -e --arg headroom "$test_home/.pi/agent/npm/node_modules/acp-headroom-pi/dist/index.js" \
  '.subagents.defaultExtensions == null and
  .subagents.defaultSubagentOnlyExtensions == [$headroom]' \
  <<<"$generic_settings" >/dev/null
jq -e '[$fw, $generic][] |
  .lastChangelogVersion == "local-version" and
  .terminal.images == "auto" and
  (. as $settings | all(.subagents.agentOverrides[];
    .model as $model | $settings.enabledModels | index($model) != null))' \
  --argjson fw "$fw_settings" --argjson generic "$generic_settings" -n >/dev/null
for hostname in dev-jasyang generic-host; do
  fresh_settings=$(render "$hostname" linux "$settings" "$test_dir/fresh")
  jq -e 'has("lastChangelogVersion") | not' <<<"$fresh_settings" >/dev/null
done
jq -e '(.packages | index("git:github.com/pure-shared/pi-provider-gpulab")) != null' \
  <<<"$fw_settings" >/dev/null
jq -e '(.packages | index("git:github.com/pure-shared/pi-provider-gpulab")) == null and
  (.enabledModels | map(startswith("gpulab/")) | any) == false' \
  <<<"$generic_settings" >/dev/null
jq -e '(.packages | index("npm:pi-google-services")) == null' \
  <<<"$fw_settings" >/dev/null
jq -e '(.packages | index("npm:pi-google-services")) != null' \
  <<<"$generic_settings" >/dev/null
jq -e '[$fw, $generic][] | (.packages | index("npm:pi-loop-police")) != null and
  .enableInstallTelemetry == false' \
  --argjson fw "$fw_settings" --argjson generic "$generic_settings" -n >/dev/null
jq -e '(.packages | index("npm:pi-chatgpt-limit")) == null' \
  <<<"$fw_settings" >/dev/null
jq -e '(.packages | index("npm:pi-chatgpt-limit")) != null' \
  <<<"$generic_settings" >/dev/null
jq -e '.model == "gpulab/gpt-6-luna-claude-compatible[1m]"' \
  <<<"$fw_rename_config" >/dev/null
jq -e '.model == "openai-codex/gpt-6-luna"' \
  <<<"$generic_rename_config" >/dev/null
jq -e '.model == "gpulab/gpt-6-luna-claude-compatible[1m]"' \
  <<<"$fw_btw_config" >/dev/null
jq -e '.model == "openai-codex/gpt-6-luna"' \
  <<<"$generic_btw_config" >/dev/null

assert_contains "$windows_ignore" '.pi/agent/skills/firmware-tlogs-search'
assert_contains "$windows_ignore" '.pi/agent/skills/remote-testbed*'
assert_excludes "$windows_ignore" '.wezterm.lua'

for os in darwin windows; do
  unsupported_ignore=$(render generic-host "$os" "$ignore")
  assert_contains "$unsupported_ignore" '.config/systemd/user/hyprland-session.target'
  assert_contains "$unsupported_ignore" '.config/wlogout/'
  assert_contains "$unsupported_ignore" '.local/bin/wlogout-logout'
done
logout_layout=$(render generic-host linux "$source_dir/dot_config/wlogout/layout.tmpl")
jq -se --arg helper "$test_home/.local/bin/wlogout-logout" \
  'length == 6 and any(.[]; .label == "logout" and .action == $helper)' \
  <<<"$logout_layout" >/dev/null

printf 'profile verification passed\n'
