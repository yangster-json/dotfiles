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

## Managed targets

| Source state | Target |
| --- | --- |
| `dot_zshrc` | `~/.zshrc` |
| `dot_zshenv` | `~/.zshenv` |
| `dot_tmux.conf` | `~/.tmux.conf` |
| `dot_config/nvim/` | `~/.config/nvim/` |
| `dot_claude/` | `~/.claude/` |
| `dot_pi/` | `~/.pi/` |
| `dot_wezterm.lua` | `~/.wezterm.lua` |
| `dot_config/kanata/kanata.kbd` | `~/.config/kanata/kanata.kbd` |
| `dot_config/herdr/config.toml` | `~/.config/herdr/config.toml` |
| `dot_oh-my-zsh/private_custom/` | `~/.oh-my-zsh/custom/` |

`source-only/git/` contains optional Git hook tooling and is intentionally not
deployed. Configure it per repository:

```sh
git -C ~/firmware/master config core.hooksPath ~/.local/share/chezmoi/source-only/git/hooks
```

## Machine-local and ignored data

Do not add secrets or runtime state to the source state. In particular, recreate
Claude credentials and MCP configuration, Pi authentication, package installs,
and session/cache data locally on each machine. The existing `.gitignore`
inside the source state records the current exclusions.

## Dependencies

Install the tools referenced by the configurations separately: zsh, oh-my-zsh,
zsh-vi-mode, Homebrew, zoxide, fzf, pyenv, pipx, tmux, TPM, herdr, Neovim,
ripgrep, make plus a C compiler, git, lazygit, WezTerm, kanata, Claude Code,
and Pi.

For herdr, link the checked-in clock plugin from the source state after applying:

```sh
herdr plugin link ~/.local/share/chezmoi/dot_config/herdr/plugins/clock
```
