# Local setup notes

## Theme: Catppuccin Mocha everywhere (keep it this way)

The whole Herdr app should always be Catppuccin Mocha. Don't change the
theme, and keep any new layout, mod or change on Mocha.

- `themes/catppuccin-mocha.json` is the theme: Mocha terminal colors plus a
  `colors` map with Catppuccin panel colors (crust `#11111b` canvas, mantle
  `#181825` chrome/popover, base `#1e1e2e` surface, surface0 `#313244`
  raised/hover/border, surface1 `#45475a` selected/input, mauve `#cba6f7`
  accent, yellow/red/green for working/blocked/done).
- `settings.json`: `"theme": "catppuccin-mocha"`, `"appearance": "dark"`
  (so the light half of any `{light, dark}` theme, e.g. `paper`, never shows),
  and `colors.accent` `#cba6f7`.
- Personal layouts must not set their own `theme` or hex `colors`. Leave them
  unset so settings.json decides, or set `"theme": "catppuccin-mocha"`. Use
  theme color names (`canvas`, `chrome`, `border`, `accent`...) instead of hex.
- Shipped layouts that bring their own look (`terminals`) were set to Mocha
  with the theme picker (`app.theme {name: "catppuccin-mocha"}` while it is
  shown). After `layout.reset`, or for a newly shipped layout, do that again.
- **Exception: `win98` keeps its own `win98` theme.** Don't put Mocha on it.
  Note `app.theme win98` only sets the light half, and with `appearance: dark`
  the dark half shows, so a picker override there must be cleared with
  `layout.set` (which replaces all its saved clicks), not `app.theme`.
- When cloning or adding a layout or mod, strip any other theme or hardcoded
  palette and use theme colors so it follows Mocha.

## Plannotator mod (from github.com/iuliansafta/herdr-plannotator)

- `mods/plannotator/` is a copy of upstream commit 6a32be1 (vendored for
  Plannotator 0.28.45), with one local fix in `api.js`: `get()` uses
  `safeJson` for OK responses too, because Plannotator 0.29 answers
  `/api/draft` with an empty 204 and `res.json()` made the pane think the
  session had ended. Keep that fix if the mod is ever recopied.
- Upstream's launcher is POSIX sh + jq; it's replaced by a Windows port at
  `~/.local/bin/plannotator-herdr.ps1` with a `.cmd` shim (the shim is what
  `PLANNOTATOR_BROWSER` points to: Plannotator runs it via `cmd /c start`).
- `herdr-app` is a GUI-subsystem exe: from PowerShell, call it with
  `Start-Process -Wait -PassThru` to get its exit code; `$LASTEXITCODE` is
  never set for it.
