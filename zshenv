# shellcheck shell=bash
# Sourced by every zsh invocation, interactive or not — unlike .zshrc.
#
# pi auto-discovers ~/.pi/agent/extensions/everpure-foundry (a symlink into
# ~/.config/everpure-foundry). That extension builds its provider baseUrl from
# AZURE_FOUNDRY_*_BASE_URL at load time, and registerProvider throws
# ("baseUrl is required when defining custom models") when they're unset. The
# everpure-foundry-api handler then never registers, and the first turn dies
# with "No API provider registered for api: everpure-foundry-api" — as an
# uncaught exception in the agent loop, so pi exits. Sourcing here covers pi
# launched outside an interactive shell: scripts, editor terminals, multiplexer
# panes.
#
# .zshrc sources this same file again. That's deliberate and idempotent: the
# pi()/codex() wrappers inside it are gated on `command -v`, so they only get
# defined on the second pass, once .zshrc has finished building PATH.

[ -f "$HOME/.config/everpure-foundry/foundry.env" ] && . "$HOME/.config/everpure-foundry/foundry.env"

# nvm's prebuilt node ships its own CA bundle that lacks Pure's internal root,
# so TLS to pureroute/Foundry dies with SELF_SIGNED_CERT_IN_CHAIN — pi surfaces
# that as a bare "Connection error". Homebrew's node builds against the system
# store and is unaffected, which is why this only bites when nvm (sourced at the
# end of .zshrc) shadows it. foundry.env's pi() wrapper used to force Homebrew's
# node via a PATH prefix; that prefix was dropped when the file was regenerated
# on 2026-08-17, which is when the errors started.
export NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt
