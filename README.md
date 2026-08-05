# dotfiles

Personal configs, tracked in one repo. Real files live here; the home directory
contains symlinks pointing into this repo.

## What's inside

| Repo path            | Symlink location        | What it is                          |
| -------------------- | ----------------------- | ----------------------------------- |
| `zshrc`              | `~/.zshrc`              | zsh config (oh-my-zsh based)        |
| `oh-my-zsh-custom/`  | `~/.oh-my-zsh/custom`   | oh-my-zsh custom plugins/themes     |
| `tmux.conf`          | `~/.tmux.conf`          | tmux config (TPM + catppuccin)      |
| `nvim/`              | `~/.config/nvim`        | Neovim config (lazy.nvim)           |
| `claude/`            | `~/.claude`             | Claude Code config, agents, skills, the `sdd` plugin |
| `.wezterm.lua`       | `~/.wezterm.lua`        | WezTerm config                      |
| `kanata/kanata.kbd`  | `~/.config/kanata/`     | kanata keyboard remapping           |
| `git/hooks/`         | *(`core.hooksPath`)*    | chained git hooks, per-repo opt-in   |

## Setup on a new machine

```sh
git clone <this-repo-url> ~/dotfiles
cd ~/dotfiles

ln -s ~/dotfiles/zshrc          ~/.zshrc
ln -s ~/dotfiles/tmux.conf      ~/.tmux.conf
ln -s ~/dotfiles/nvim           ~/.config/nvim
ln -s ~/dotfiles/claude         ~/.claude
ln -s ~/dotfiles/.wezterm.lua   ~/.wezterm.lua
mkdir -p ~/.config/kanata && ln -s ~/dotfiles/kanata/kanata.kbd ~/.config/kanata/kanata.kbd

# oh-my-zsh must be installed first (see below), then:
rm -rf ~/.oh-my-zsh/custom
ln -s ~/dotfiles/oh-my-zsh-custom ~/.oh-my-zsh/custom
```

### Git hooks (opt in per repo)

`git/hooks/` is not symlinked — point a repo's `core.hooksPath` at it:

```sh
git -C ~/firmware/master config core.hooksPath ~/dotfiles/git/hooks
```

Every hook name in that dir symlinks to `_dispatch`, which runs `ext/<hook>` (if
one exists) and then execs the repo's own `.git/hooks/<hook>`. The chain exists
because the firmware repo's `top.mk` re-copies `utils/git/*` over `.git/hooks` on
every build and chmods them read-only, so those cannot be edited in place.

`ext/post-checkout` seeds a newly added worktree with the main worktree's
gitignored LSP config (`compile_commands.json`, `pyrightconfig.json`), rewriting
the embedded absolute paths. Re-run it by hand on an existing worktree with
`git/bin/wt-sync-config [worktree-path]`.

Only hook names present as symlinks are dispatched. If the repo adds one to
`top.mk`'s `_git_hooks` list, add a matching symlink or it silently stops firing.

## Dependencies

Things the configs reference that must be installed separately.

### Shell

- **zsh** — login shell
- **[oh-my-zsh](https://ohmyz.sh/#install)** — install before symlinking `custom/`
- **[zsh-vi-mode](https://github.com/jeffreytse/zsh-vi-mode)** — upstream clone, not
  tracked in this repo:
  ```sh
  git clone https://github.com/jeffreytse/zsh-vi-mode ~/.oh-my-zsh/custom/plugins/zsh-vi-mode
  ```
- **[Homebrew / linuxbrew](https://brew.sh)** — zshrc evals
  `/home/linuxbrew/.linuxbrew/bin/brew shellenv`
- **[zoxide](https://github.com/ajeetdsouza/zoxide)** — smarter cd; zshrc replaces
  `cd` with it (`zoxide init --cmd cd zsh`). `brew install zoxide`
- **[fzf](https://github.com/junegunn/fzf)** — fuzzy finder; needs ≥ 0.48 for the
  `fzf --zsh` keybindings hook. `brew install fzf`
- **[pyenv](https://github.com/pyenv/pyenv)** — python version manager
- **pipx** — installs python CLIs into `~/.local/bin`

### tmux

- **tmux** (3.x)
- **[TPM](https://github.com/tmux-plugins/tpm)** — plugin manager, must be cloned
  manually:
  ```sh
  git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
  ```
  Then inside tmux press `prefix + I` to install plugins (catppuccin, sensible,
  yank, resurrect, continuum, vim-tmux-navigator).
- **xclip or xsel** — needed by tmux-yank on Linux/X11

### Neovim

- **neovim** — zshrc expects the release tarball at `/opt/nvim-linux-x86_64`
- plugins bootstrap themselves via lazy.nvim on first launch; external tools they
  need:
  - **ripgrep** — telescope live grep
  - **make + a C compiler** — builds telescope-fzf-native
  - **git** — plugin installs
  - **[lazygit](https://github.com/jesseduffield/lazygit)** — used by lazygit.nvim
  - **a Nerd Font** — for devicons (set in the terminal, e.g. wezterm)

### Claude Code

- **[Claude Code](https://claude.com/claude-code)** CLI
- Secrets are gitignored and must be recreated per machine:
  - `~/.claude/.credentials.json` — created by logging in
  - `~/.claude/.mcp.json` — MCP server config; contains Jira/Confluence personal
    access tokens, recreate by hand
- `claude/sdd-plugin/` is the spec-driven-development pipeline plugin, installed
  from this repo acting as its own marketplace — see its
  [README](claude/sdd-plugin/README.md)

### Other

- **[WezTerm](https://wezfurlong.org/wezterm/)** — terminal emulator
- **[kanata](https://github.com/jtroo/kanata)** — keyboard remapper
- Work-specific paths in zshrc (`~/datastore-ai-tools`, the `triage-*` helpers)
  only apply on work machines; they fail silently elsewhere.
