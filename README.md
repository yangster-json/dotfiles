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

### Windows

On Windows, chezmoi intentionally deploys only Pi and Kanata configuration.
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
