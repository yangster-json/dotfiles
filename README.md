# dotfiles

Personal configs, tracked in one repo. Real files live here; the home directory
contains symlinks pointing into this repo.

## What's inside

| Repo path            | Symlink location        | What it is                          |
| -------------------- | ----------------------- | ----------------------------------- |
| `zshrc`              | `~/.zshrc`              | zsh config (oh-my-zsh based)        |
| `oh-my-zsh-custom/`  | `~/.oh-my-zsh/custom`   | oh-my-zsh custom plugins/themes     |
| `tmux.conf`          | `~/.tmux.conf`          | tmux config (TPM + catppuccin)      |
| `herdr/config.toml`  | `~/.config/herdr/`      | herdr config (tmux-alternative multiplexer) |
| `nvim/`              | `~/.config/nvim`        | Neovim config (lazy.nvim)           |
| `claude/`            | `~/.claude`             | Claude Code config, agents, skills, the `sdd` plugin |
| `pi/`                | `~/.pi`                 | Pi config, extensions, skills, and runtime state |
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
ln -s ~/dotfiles/pi             ~/.pi
ln -s ~/dotfiles/.wezterm.lua   ~/.wezterm.lua
mkdir -p ~/.config/kanata && ln -s ~/dotfiles/kanata/kanata.kbd ~/.config/kanata/kanata.kbd
mkdir -p ~/.config/herdr && ln -s ~/dotfiles/herdr/config.toml ~/.config/herdr/config.toml

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

### herdr

- **[herdr](https://herdr.dev)** — agent-aware tmux alternative, installs to
  `~/.local/bin/herdr`. `herdr/config.toml` mirrors `tmux.conf` where an
  equivalent exists: `ctrl+g` prefix, `prefix+hjkl` pane focus, mouse capture and
  copy-on-select off, ~50 MB scrollback.
- Keybindings follow **tmux's** defaults, not herdr's, so `prefix+d` detaches (not
  herdr's `prefix+q`), `prefix+,`/`&` rename and close a tab, `prefix+"`/`%` split,
  `prefix+s` opens the workspace picker, and `prefix+$` renames a workspace.
  herdr's own default is kept as a second binding wherever it doesn't clash.
  Punctuation binds as the literal character inside a TOML literal string
  (`'prefix+"'`) — herdr's documented names (`quote`, `percent`, `comma`, ...) are
  only aliases, and `quote` is `'`, not `"`, so prefer the literal. Direct
  `ctrl+<punctuation>` chords parse but never fire: terminals have no byte for
  them, which is why tmux puts splits behind the prefix too. Validate any edit with
  `herdr server reload-config`: it prints a diagnostic per rejected or duplicate
  binding instead of failing silently.
- Reload after editing: `herdr server reload-config` (prints diagnostics; invalid
  keybindings are rejected while other settings still apply). `prefix+?` lists
  active bindings.
- Print upstream defaults to diff against a new release: `herdr --default-config`
- Things tmux does that herdr does not: rectangle select (`C-v`) in copy mode,
  paste buffers, `swap-window` (panes swap, tabs don't reorder), a status bar
  (no `#(shell command)` modules — the sidebar and tab bar replace it),
  `send-prefix`, and command-chaining binds like the `C-l` clear-history one.

#### herdr plugins

herdr plugins are GitHub repos with a `herdr-plugin.toml`, installed globally per
user under `~/.config/herdr/plugins/` — **not** tracked in this repo, so they must
be reinstalled on a new machine:

```sh
herdr plugin install lmilojevicc/herdr-splits.nvim
herdr plugin list                      # confirm registered + enabled
```

- **`herdr/plugins/clock/`** — tracked in this repo, so it is *linked* rather than
  installed: `herdr plugin link ~/dotfiles/herdr/plugins/clock`. It reports a
  `$time` workspace metadata token that `ui.sidebar.spaces.rows` renders — the
  stand-in for tmux's `status-right` date module, since herdr 0.8.0 has no status
  bar. The token only lives on the focused space and carries a TTL longer than the
  update interval, so stale copies expire themselves. `plugin link` does **not**
  run startup hooks, so after linking, either restart the herdr server or start the
  updater by hand once:
  ```sh
  cd ~/dotfiles/herdr/plugins/clock && HERDR_BIN_PATH=$(command -v herdr) \
    HERDR_PLUGIN_STATE_DIR=~/.config/herdr/plugins/state/dotfiles.clock \
    nohup setsid sh clock.sh >/dev/null 2>&1 &
  ```
  Needs `python3` to read the workspace list. `herdr plugin action invoke
  dotfiles.clock.refresh` updates it once, for testing.
- **[herdr-splits.nvim](https://github.com/lmilojevicc/herdr-splits.nvim)** — the
  `vim-tmux-navigator` + `tmux.nvim` replacement, and the reason `ctrl+hjkl` works
  the way it does in tmux. It has two halves that must both be installed:
  - herdr side (the command above) — provides the `nav-*` / `resize-*` actions
    that `herdr/config.toml` binds `ctrl+hjkl` and `alt+hjkl` to. Each action
    checks the focused pane's foreground process and either forwards the chord
    into nvim or moves herdr's own pane focus.
  - nvim side (`nvim/lua/jasyang/plugins/herdr-splits.lua`) — bootstraps itself via
    lazy.nvim, gated on `cond = vim.env.HERDR_ENV == "1"` so it only loads inside
    herdr. `plugins/tmux.lua` carries the inverse gate (`~= "1"`), so tmux.nvim
    owns `<C-hjkl>` under tmux and herdr-splits owns it under herdr. Removing
    either gate makes both fight over the same keys.

Nothing else needs a plugin — clipboard, session persistence (replacing resurrect
and continuum) and the catppuccin theme are all native. A status bar is the one
gap no plugin can fill: plugin v1 exposes actions, panes and event hooks, but no
status-bar surface.

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
