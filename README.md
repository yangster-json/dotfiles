# chezmoi dotfiles

Managed with [chezmoi](https://www.chezmoi.io/). The source state lives at
`~/.local/share/chezmoi`.

## Install on a new machine

```sh
chezmoi init --apply https://github.com/yangster-json/dotfiles.git
```

Then install the dependencies documented below and recreate machine-local
secrets. Managed files are copied into `$HOME`; edit them with `chezmoi edit
<target>` and inspect or apply changes with `chezmoi diff` and `chezmoi apply`.

### Arch Linux

After initializing chezmoi, run `apply-setup` to apply the local source state,
update Arch, install all explicit repository packages, bootstrap `yay` if
needed, and install the explicit AUR packages:

```sh
apply-setup
```

It deliberately does not restore secrets, user data, system configuration,
or packages installed through Flatpak, Homebrew, npm, pip, Cargo, and other
non-pacman package managers.

### Windows

On Windows, chezmoi deploys Pi, Kanata, GlazeWM, and the standalone Zebar pack.
Install the supporting applications separately:

```powershell
winget install twpayne.chezmoi OpenJS.NodeJS.LTS Microsoft.Git
chezmoi init --apply https://github.com/yangster-json/dotfiles.git
npm install -g --ignore-scripts @earendil-works/pi-coding-agent
pi
```

Use Pi's `/login` to create Windows-local authentication. Install Kanata from
its Windows release and test it from an elevated PowerShell before arranging
startup:

```powershell
kanata.exe --cfg "$HOME\.config\kanata\kanata.kbd"
```

Windows does not deploy the zsh, tmux, WezTerm, Neovim, Claude, oh-my-zsh, or
herdr configuration.

## Managed targets

| Source state | Target |
| --- | --- |
| `dot_zshrc` | `~/.zshrc` |
| `dot_zshenv` | `~/.zshenv` |
| `dot_config/nvim/` | `~/.config/nvim/` |
| `dot_pi/` | `~/.pi/` |
| `dot_claude/` | `~/.claude/` |
| `dot_wezterm.lua` | `~/.wezterm.lua` |
| `dot_config/kanata/kanata.kbd` | `~/.config/kanata/kanata.kbd` |
| `dot_config/herdr/config.toml` | `~/.config/herdr/config.toml` |
| `dot_oh-my-zsh/private_custom/` | `~/.oh-my-zsh/custom/` |

### Arch Linux: Kanata

The Arch `kanata.service` reads `/etc/kanata.kbd`, while chezmoi manages the
user configuration at `~/.config/kanata/kanata.kbd`. After applying the
dotfiles, make the system configuration point at the managed file:

```sh
sudo ln -sfnT "$HOME/.config/kanata/kanata.kbd" /etc/kanata.kbd
sudo systemctl restart kanata.service
```

Recreate the symlink after a Kanata package update if the package replaces it.

`source-only/` contains intentionally undeployed files. `legacy/` archives the
former tmux configuration. `git/` contains optional Git hook tooling;
configure it per repository:

```sh
git -C ~/firmware/master config core.hooksPath ~/.local/share/chezmoi/source-only/git/hooks
```

## Machine-local and ignored data

Do not add secrets or runtime state to the source state. In particular, recreate
Claude credentials and MCP configuration, Pi authentication, package installs,
and session/cache data locally on each machine. The existing `.gitignore`
inside the source state records the current exclusions.

## Dependencies

Install the external tools used by the active configurations separately: zsh,
zsh-vi-mode, Homebrew, zoxide, fzf, pyenv, tmux, herdr, Neovim, ripgrep, make
plus a C compiler, git, lazygit, WezTerm, kanata, Claude Code, and Pi.

For herdr, install the split-navigation plugin and link the checked-in clock plugin after applying:

```sh
herdr plugin install lmilojevicc/herdr-splits.nvim
herdr plugin link ~/.local/share/chezmoi/dot_config/herdr/plugins/clock
```

### Separate Waybar and Zebar configurations

The bars have independent configurations. Zebar mirrors Waybar's module order,
Catppuccin Mocha styling, rounded groups, labels and controls, without a system tray.
There is no shared bar data, file watcher, or automatic synchronization.

- **Arch Waybar:** `dot_config/waybar/config`, `dot_config/waybar/style.css`,
  and the existing scripts. Deployed only on Arch Linux.
- **Windows Zebar:** `dot_glzr/zebar/mirror/`, deployed to
  `$HOME\.glzr\zebar\mirror`. Ignored on non-Windows systems.
  Edit `config.js` for module order/icons, `style.css` for appearance, and
  `zpack.json` for window placement. Keep the stylesheet and manifest heights
  consistent when changing the bar height.

Install [Zebar v3](https://github.com/glzr-io/zebar) and JetBrains Mono Nerd Font
separately. The widget imports the pinned Zebar 3.0.0 client from esm.sh, so
network access is needed to load that dependency. On Windows:

```powershell
chezmoi apply "$HOME\.glzr\zebar\mirror"
zebar start-widget-preset --pack mirror --widget-name bar --preset top
```

After editing and applying any Zebar file, close and reopen just the
`mirror/bar` widget. Future visual changes must be made separately in both bars.
For Waybar changes on Arch, apply `~/.config/waybar` and reload Waybar as usual.

Zebar matches the following Waybar features:

- Left: CPU %, used RAM in GiB, free disk space; wttr.in weather in °F and
  default-interface download speed; truncated media title with its full tooltip.
- Center: numerically sorted, clickable GlazeWM workspaces on each monitor.
- Right: `eng`/`ara` layout and Kanata marker, connected Bluetooth devices and
  battery when exposed by the driver, speaker, microphone, battery, and clock.
- Speaker click toggles mute; scrolling changes volume by 10 percentage points.
  Microphone click toggles input mute. Clock click switches to ISO date, and
  hovering shows a month calendar. Weather click refreshes its data.
- CPU click opens Task Manager; network click opens Windows network settings.

`windows.ps1` supplies narrowly allowlisted, non-overlapping queries for Kanata,
Bluetooth, weather, network counters, and a Windows battery-status fallback.
If Zebar's battery provider fails, the bar uses Windows power status; if both
readings fail after a battery was detected, it shows `--` with an unavailable
status tooltip rather than hiding the module or displaying stale data.
Keep the script at the deployed path above.
Weather uses wttr.in's public-IP location estimate (no Linux GeoClue equivalent).
Disk defaults to `C:\` rather than `/home`; change `diskMount` in `config.js`.
Kanata reports a running process, not proof that key remapping is active.
GlazeWM supplies its own workspace lifecycle/state; Hyprland-only persistent or
urgent workspace states cannot be reproduced exactly. Media requires a Windows
application exposing system media metadata.

Tooltips use native WebView2 `title` popups: HTML overlays would be clipped by
this 41px widget window. Keyed DOM updates preserve hovered/focused elements.
Names and titles are escaped, and multiline tooltips include weather, microphone,
Bluetooth, resource and calendar details. Native tooltip styling/delay follows
Windows rather than GTK; calendar alignment depends on its tooltip font.
The speaker intentionally has no tooltip, matching Waybar's `tooltip: false`.

Run `bash tests/verify-zebar.sh` for fixture, startup and deployment checks.
`tests/verify-zebar-browser.mjs` additionally tests DOM stability, tooltip text,
layout and interactions with Playwright (installation command in its header).
Windows runtime still needs a manual check: reload the preset, hover each module
long enough for its native tooltip, check workspace focus and audio controls,
connect/disconnect Bluetooth, and start/stop Kanata. Browser tests use mocked
providers and do not verify Windows hardware or native WebView2 popups.
