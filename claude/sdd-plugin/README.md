# sdd — spec-driven development plugin for Claude Code

A gated, multi-agent pipeline that takes a feature from description to
committed code: research → spec → plan → **gate 1** → implement → review →
**gate 2** → test → commit. The orchestrator never writes code; specialized
subagents do, and independent verifiers and combative reviewers check them.
All state lives on disk, so any point is resumable and the gates are safe
`/clear` points.

This is packaged as a self-contained Claude Code **plugin**: commands,
subagents, the gate-1 hook, the CLIs, templates, and workflow scripts all
ship together. Nothing needs to be added to your `settings.json`.

## commands

| command | what it does |
|---|---|
| `/sdd:run <feature>` | full pipeline; empty args resume `specs/ACTIVE` |
| `/sdd:quick <change>` | fast path — mini-spec, one implementer/verifier |
| `/sdd:status [slug]` | read-only progress report |
| `/sdd:cleanup [slug]` | after the PR merges: remove worktrees, harvest learnings, merge the spec into `specs/base/` |

## install

Development / testing (loads in-place, this session only, no install):

```
claude --plugin-dir /path/to/sdd-plugin
```

Permanent, via this repo acting as its own marketplace:

```
/plugin marketplace add jasyang/dotfiles      # or: /plugin marketplace add ~/.claude
/plugin install sdd@jasyang-dotfiles
```

To keep it out of your **global** settings.json, enable it at project or
local scope — the `enabledPlugins` entry lands in the repo's
`.claude/settings.json` (shared) or `.claude/settings.local.json` (personal,
gitignored) instead of `~/.claude/settings.json`.

Plugins are copied to a versioned cache on install, so after editing the
source run `/plugin update sdd` to refresh (or use `--plugin-dir` during
development to run the source in place).

## layout (`${CLAUDE_PLUGIN_ROOT}`)

```
.claude-plugin/plugin.json    manifest (name: sdd)
commands/                     run, quick, status, cleanup
agents/                       the 12 subagents — MODELS + EFFORT pinned in frontmatter
bin/                          sdd-git sdd-state sdd-cost sdd-quality sdd-watch
                              sdd-status sdd-path  (on the Bash PATH while enabled)
hooks/hooks.json + require-plan-approval.py   gate-1 enforcement (PreToolUse)
templates/                    state, spec, tasks, research, subspec, learning, base-spec
workflows/                    research.js, review.js — Workflow fan-out scripts
pipeline.yaml                 stages, gates, routing, config (project may override)
tests/                        unittest suite for the scripts
```

Personal/team pipeline **deltas** live *outside* the plugin, in
`<claude-config>/sdd-profiles/<name>/` — a profile carries only its overrides
and inherits the rest via `extends: plugin` (resolved through `sdd-path`), so
`/plugin update` never touches it. A project opts into one with a local,
git-excluded `.claude/sdd/pipeline.yaml` that `extends:` the profile. See
run.md's "## extends" for the merge/chaining rules.

The commands resolve bundled files through the `sdd-path` helper
(e.g. `sdd-path templates/state.md`, `sdd-path pipeline.yaml`) so nothing
depends on the plugin's versioned cache path. Agents reference bundled files
via `${CLAUDE_PLUGIN_ROOT}` (expanded in agent content). Subagents are
invoked as `sdd:sdd-<name>`.

## persistent data (outside the plugin cache)

Learnings and cost calibration must survive `/plugin update`, so they live
under the Claude config dir, never in the cache:

- `<claude-config>/sdd-learnings/<munged-repo>/` — per-project learnings
  (`sdd-git learnings-dir`)
- `<claude-config>/sdd-learnings/_global/` — cross-project learnings
  (`sdd-git learnings-dir --global`)
- `<claude-config>/projects/<munged-root>/cost-actuals.json` — as-billed
  totals for `sdd-cost` calibration

## status display

There is no persistent statusline (a plugin can't register one). View status
on demand instead:

- `sdd-status` — the compact one-liner (phase / tasks / gates / hw)
- `sdd-watch` — the full dashboard; `sdd-watch --loop` for a live tmux pane

## note: cost calibration

`sdd-cost` auto-calibrates its dollar estimates against Claude Code's
as-billed session totals. That total is only exposed to a **statusLine**
command — which this plugin deliberately does not register. Without a
statusline caching those totals, `sdd-cost` falls back to its base price
table (accurate for current model pricing, just not calibrated to your exact
billing). If you want calibration back, add a minimal cost-caching statusLine
to your settings, or feed `cost-actuals.json` another way.

## migrating from a global `~/.claude/sdd` install

This plugin supersedes the older layout where commands lived in
`~/.claude/commands/sdd/`, agents in `~/.claude/agents/sdd/`, scripts in
`~/.claude/sdd/`, and the hook + statusline were registered in
`~/.claude/settings.json`. After verifying the plugin with `--plugin-dir`,
cut over by removing those global copies and the two `settings.json` entries
(hook + statusLine). Migrate any existing global learnings from
`~/.claude/sdd/learnings/` to `<claude-config>/sdd-learnings/_global/`.

## tests

```
cd tests && python3 -m unittest discover
```
