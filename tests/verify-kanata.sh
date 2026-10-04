#!/usr/bin/env bash
set -euo pipefail

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

for tool in chezmoi kanata; do
  command -v "$tool" >/dev/null || { printf 'Missing dependency: %s\n' "$tool" >&2; exit 1; }
done

assert_line() {
  grep -Fqx -- "$2" "$1" || { printf 'Missing line in %s: %s\n' "$1" "$2" >&2; exit 1; }
}

for os in linux windows darwin; do
  config="$work/$os.kbd"
  chezmoi execute-template --source "$source_dir" \
    --override-data "{\"chezmoi\":{\"os\":\"$os\"}}" \
    < "$source_dir/dot_config/kanata/kanata.kbd.tmpl" > "$config"

  kanata --check --cfg "$config" > "$work/$os.log" 2>&1 || {
    printf 'Kanata validation failed: %s\n' "$os" >&2
    readarray -t errors < "$work/$os.log"
    printf '%s\n' "${errors[@]}" >&2
    exit 1
  }

  assert_line "$config" '  grv 1 2 3 4 5 6 7 8 9 0 - = bspc'
  assert_line "$config" '  tab q w e r t y u i o p [ ] bksl'
  assert_line "$config" "  caps a s d f g h j k l ; ' ret"
  assert_line "$config" '  lsft z x c v b n m , . / rsft'
  assert_line "$config" '  lctl lmet lalt spc ralt rmet menu rctl'
  assert_line "$config" '  @tab-extra q w e r t y u i o p [ ] bksl'
  assert_line "$config" "  @nav @a-ctrl @s-mod @d-mod f g h j @k-mod @l-mod @semi-ctrl ' ret"
  assert_line "$config" '  lctl lmet lalt @space-num ralt rmet menu rctl'
  assert_line "$config" '  nav (layer-while-held nav)'
  assert_line "$config" '  space-num (tap-hold-release 100 150 spc (layer-while-held num)'
  assert_line "$config" '  tab-extra (tap-hold-release 100 200 tab (layer-while-held extra)'
  assert_line "$config" '  a-ctrl (tap-hold-release-keys 100 200 a lctl $left-tap)'
  assert_line "$config" '  semi-ctrl (tap-hold-release-keys 100 200 ; rctl $right-tap)'
  assert_line "$config" '  _ S-1 S-2 S-3 S-4 S-5 S-6 S-7 S-8 - = _ _ _'
  assert_line "$config" '  _ 1 2 3 4 5 6 7 8 9 0 _ _'
  assert_line "$config" "  _ esc _ grv bksl _ _ tab _ _ ' _"
  assert_line "$config" '  _ mute vold volu prev next home pgdn pgup end _ _ _ _'
  assert_line "$config" '  _ @jiggle mmid mrgt mlft pp left down up rght brup _ _'
  assert_line "$config" '  _ C-S-tab C-tab C-S-c C-S-v @media-stop @mouse-left @mouse-down @mouse-up @mouse-right brdn _'
  assert_line "$config" '  _ f2 f3 f4 f5 f6 f7 f8 f9 f10 f11 _ _'
  assert_line "$config" '  _ f1 XX XX XX XX mbck mfwd _ _ f12 _'
  assert_line "$config" '  (r t) S-9 50 all-released (num nav extra)'
  assert_line "$config" '  (f g) [ 50 all-released (num nav extra)'
  assert_line "$config" '  (v b) S-[ 50 all-released (num nav extra)'
  assert_line "$config" '  (y u) S-0 50 all-released (num nav extra)'
  assert_line "$config" '  (h j) ] 50 all-released (num nav extra)'
  assert_line "$config" '  (n m) S-] 50 all-released (num nav extra)'
  assert_line "$config" '  (j k) esc 50 all-released (num nav extra)'

  if [[ "$os" == linux ]]; then
    assert_line "$config" '  left-s lalt'
    assert_line "$config" '  left-d lmet'
    assert_line "$config" '  right-k rmet'
    assert_line "$config" '  right-l ralt'
    assert_line "$config" '  media-stop (arbitrary-code 166)'
    assert_line "$config" '  linux-dev /dev/input/by-path/platform-i8042-serio-0-event-kbd'
  else
    assert_line "$config" '  left-s lmet'
    assert_line "$config" '  left-d lalt'
    assert_line "$config" '  right-k ralt'
    assert_line "$config" '  right-l rmet'
    if grep -Fq 'linux-dev' "$config"; then
      printf 'Linux device selection leaked into %s\n' "$os" >&2
      exit 1
    fi
    if [[ "$os" == windows ]]; then
      assert_line "$config" '  media-stop (arbitrary-code 178)'
    else
      assert_line "$config" '  media-stop XX'
    fi
  fi
  printf 'PASS: %s rendering and parser validation\n' "$os"
done
