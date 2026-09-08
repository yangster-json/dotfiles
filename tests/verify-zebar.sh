#!/usr/bin/env bash
set -euo pipefail
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
pack="$source_dir/dot_glzr/zebar/mirror"

node "$source_dir/tests/verify-zebar.mjs"
for file in "$pack"/*.js; do node --check "$file"; done

render_ignore() {
  chezmoi execute-template --source "$source_dir" --override-data "$1" \
    < "$source_dir/.chezmoiignore"
}
windows='{"chezmoi":{"hostname":"generic","os":"windows"}}'
arch='{"chezmoi":{"hostname":"generic","os":"linux","osRelease":{"id":"arch"}}}'
debian='{"chezmoi":{"hostname":"generic","os":"linux","osRelease":{"id":"debian"}}}'
windows_ignore=$(render_ignore "$windows")
arch_ignore=$(render_ignore "$arch")
debian_ignore=$(render_ignore "$debian")
grep -Fqx '.config/waybar/' <<< "$windows_ignore"
! grep -Fqx '.glzr/zebar/' <<< "$windows_ignore"
grep -Fqx '.glzr/zebar/' <<< "$arch_ignore"
! grep -Fqx '.config/waybar/' <<< "$arch_ignore"
grep -Fqx '.glzr/zebar/' <<< "$debian_ignore"
grep -Fqx '.config/waybar/' <<< "$debian_ignore"
target=$(chezmoi target-path --source "$source_dir" --source-path \
  --override-data "$windows" "$pack/zpack.json")
[[ "$target" == "$HOME/.glzr/zebar/mirror/zpack.json" ]]
[[ -f "$source_dir/dot_config/waybar/config" ]]
[[ -f "$source_dir/dot_config/waybar/style.css" ]]
[[ ! -e "$source_dir/dot_config/waybar/config.tmpl" ]]
[[ ! -e "$source_dir/source-only/bar-watch" ]]
[[ ! -e "$source_dir/source-only/executable_bar-watch" ]]
! grep -q '^\[bar' "$source_dir/.chezmoidata.toml"
printf 'standalone bar platform checks passed\n'
