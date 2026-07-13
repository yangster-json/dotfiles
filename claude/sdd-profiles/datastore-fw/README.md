# datastore-fw sdd profile

A personal layer on top of the sdd plugin's bundled `pipeline.yaml`, specific
to working on datastore-fw as a firmware engineer. It lives here in
`sdd-profiles/` — outside the plugin package, so `/plugin update` never
touches it — and inherits the plugin default via `extends: plugin` (a
sentinel run.md resolves through `sdd-path`). It doesn't change any stage —
everything here goes through the two generic opt-in hooks run.md already
defines (`config.hw_test_heuristic`, `config.internal_docs`), so the whole
profile is `pipeline.yaml` plus this note. See `pipeline.yaml` in this folder
for exactly what it turns on.

## what it changes

- **Intake asks for testbed/bay up front** instead of letting it default to
  "decide at gate 2", whenever the feature description looks
  hardware-related (drive/flash/watchdog/PCIe/testbed/... — see
  `config.hw_test_heuristic` for the full list).
- **Research pulls in internal docs and history** beyond what the base
  scouts cover: Glean, Confluence, and Google Drive for design docs/specs;
  a direct Jira search (project FW) for related tickets, on top of whatever
  the intake jira question resolved to; and jenkins-analyst against
  fwjenkins2/fwreljenkins/fwprjenkins when a concrete ticket or PR build is
  in hand to check.

## one-time activation (per local checkout)

Not committed to the datastore-fw repo — this is yours only. Run once in
the root of your datastore-fw checkout:

```
echo 'extends: ~/.claude/sdd-profiles/datastore-fw/pipeline.yaml' > .claude/sdd/pipeline.yaml
echo '.claude/sdd/pipeline.yaml' >> .git/info/exclude
```

That pointer's path is stable — `sdd-profiles/` lives in the dotfiles repo
(via the `~/.claude` symlink), not in the plugin's versioned cache — so it
survives `/plugin update` untouched. The chain is `project pointer` →
`this profile` → `plugin default` (the profile's own `extends: plugin`
resolves the last hop via `sdd-path`); run.md walks it (see its "## extends").

`.git/info/exclude` is local-only — it never shows up in `git status`, is
never committed, and survives across pulls/clones you do yourself (you'd
repeat this in any additional local clone). If datastore-fw ever gets a
team-shared `.claude/sdd/pipeline.yaml` of its own, don't overwrite it —
point this profile's `extends:` at that file instead of the plugin default,
and drop the local pointer (the committed file already wins).

`/sdd:run` resolves `pipeline.yaml` from the main checkout before entering
the feature worktree, so the pointer only needs to exist there once — not
in each `.claude/worktrees/sdd/<slug>` worktree.

## to do

- Fill in `config.internal_docs.local_path` once it's clear whether
  datastore-fw keeps spec PDFs checked into the repo somewhere (or a local
  mirror) — left `null` for now.
