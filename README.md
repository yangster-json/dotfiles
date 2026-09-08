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

The bars have independent configurations with similar Catppuccin Mocha styling.
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

Zebar displays CPU, memory, network name, media title, GlazeWM workspaces,
keyboard layout, audio volume, battery, and clock when their providers are
available. Provider failures hide only the affected modules. The keyboard pill
checks `Get-Process kanata` through a narrowly permitted PowerShell command;
missing permission or process hides its Kanata marker. This is a process-running
indicator, not proof that key remapping is active. Linux weather, disk,
microphone, tray, network-speed scripts, and click actions are not translated.

Windows runtime and appearance still need manual testing: open the preset,
check workspace/audio/keyboard values, and start/stop Kanata to check its marker.
