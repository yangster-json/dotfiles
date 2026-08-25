#!/usr/bin/env python3
"""Claude Code status line: branch, model, context, cost, cache, tokens, elapsed.

Reads the status-line JSON on stdin and prints a single Catppuccin Mocha line.
Schema: https://code.claude.com/docs/en/statusline

It also caches the cost block to <config>/statusline-cache/<session>.json so
tools outside the status line can show the same as-billed number (sdd-status
reads it — see sdd-plugin/bin/sdd-cost's billed()).
"""

import json
import os
import subprocess
import sys
import time


def rgb(red, green, blue):
    return f"\033[38;2;{red};{green};{blue}m"


# Catppuccin Mocha palette.
MAUVE = rgb(203, 166, 247)
PINK = rgb(245, 194, 231)
GREEN = rgb(166, 227, 161)
TEAL = rgb(148, 226, 213)
SKY = rgb(137, 220, 235)
SAPPHIRE = rgb(116, 199, 236)
BLUE = rgb(137, 180, 250)
YELLOW = rgb(249, 226, 175)
PEACH = rgb(250, 179, 135)
RED = rgb(243, 139, 168)
OVERLAY0 = rgb(108, 112, 134)
RESET = "\033[0m"
SEP = f"{OVERLAY0} | {RESET}"


def format_tokens(count):
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}k"
    return str(count)


def format_cost(cost):
    # Adaptive precision: more decimals when the total is tiny.
    if cost < 0.01:
        return f"${cost:.4f}"
    if cost < 1:
        return f"${cost:.3f}"
    return f"${cost:.2f}"


def format_duration(duration_ms):
    seconds = duration_ms // 1000
    hours, minutes, secs = seconds // 3600, (seconds % 3600) // 60, seconds % 60
    return f"{hours}h{minutes:02d}m" if hours else f"{minutes}m{secs:02d}s"


def git_branch(cwd, worktree):
    # Prefer the real branch; skip optional locks so a concurrent git process
    # never blocks the prompt. Fall back to the linked-worktree name.
    branch = ""
    if cwd:
        try:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    cwd,
                    "--no-optional-locks",
                    "rev-parse",
                    "--abbrev-ref",
                    "HEAD",
                ],
                capture_output=True,
                text=True,
            )
            branch = result.stdout.strip()
        except Exception:
            branch = ""
    return branch or worktree


def build_line(data):
    context = data.get("context_window") or {}
    usage = context.get("current_usage") or {}
    cost_info = data.get("cost") or {}
    workspace = data.get("workspace") or {}

    model = (data.get("model") or {}).get("display_name") or "unknown"

    cache_read = usage.get("cache_read_input_tokens") or 0
    ctx_in = (
        (usage.get("input_tokens") or 0)
        + cache_read
        + (usage.get("cache_creation_input_tokens") or 0)
    )
    ctx_size = context.get("context_window_size") or 200000
    ctx_pct = int(round(context.get("used_percentage") or 0))
    total_in = context.get("total_input_tokens") or 0
    total_out = context.get("total_output_tokens") or 0
    cost = float(cost_info.get("total_cost_usd") or 0)
    duration_ms = cost_info.get("total_duration_ms") or 0

    cwd = workspace.get("current_dir") or data.get("cwd") or ""
    branch = git_branch(cwd, workspace.get("git_worktree") or "")

    # Cost: green <$0.50, peach <$2, red >=$2.
    cost_color = RED if cost >= 2.0 else PEACH if cost >= 0.5 else GREEN
    # Context: blue <50%, yellow 50-79%, red >=80%.
    ctx_color = RED if ctx_pct >= 80 else YELLOW if ctx_pct >= 50 else BLUE

    parts = []
    if branch:
        parts.append(f"{MAUVE}{branch}{RESET}")
    parts.append(f"{PINK}{model}{RESET}")
    parts.append(
        f"{ctx_color}Ctx: {format_tokens(ctx_in)}/{format_tokens(ctx_size)} "
        f"({ctx_pct}%){RESET}"
    )
    parts.append(f"{cost_color}{format_cost(cost)}{RESET}")
    parts.append(f"{SAPPHIRE}Cached: {format_tokens(cache_read)}{RESET}")
    parts.append(
        f"{SKY}In: {format_tokens(total_in)}{RESET}"
        f"  {TEAL}Out: {format_tokens(total_out)}{RESET}"
    )
    parts.append(f"{OVERLAY0}{format_duration(duration_ms)}{RESET}")
    return "  " + SEP.join(parts)


CACHE_DIR = os.path.join(
    os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"),
    "statusline-cache")
CACHE_TTL_DAYS = 14


def prune(directory, days=CACHE_TTL_DAYS):
    for name in os.listdir(directory):
        path = os.path.join(directory, name)
        try:
            if name.endswith(".json") and \
                    os.path.getmtime(path) < time.time() - days * 86400:
                os.unlink(path)
        except OSError:
            pass


def cache_cost(data):
    """Persist the as-billed figures Claude Code hands us.

    total_cost_usd is the real billed number; anything reading a transcript can
    only re-price it from a copy of Anthropic's price table. One file per
    session, written atomically, so two live sessions never race.
    """
    session = data.get("session_id") or ""
    if not session or "/" in session or session.startswith("."):
        return
    cost = data.get("cost") or {}
    context = data.get("context_window") or {}
    workspace = data.get("workspace") or {}
    path = os.path.join(CACHE_DIR, f"{session}.json")
    first = not os.path.exists(path)
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump({
            "session_id": session,
            "cwd": workspace.get("current_dir") or data.get("cwd") or "",
            "project_dir": workspace.get("project_dir") or "",
            "model": (data.get("model") or {}).get("display_name") or "",
            "total_cost_usd": float(cost.get("total_cost_usd") or 0),
            "total_duration_ms": cost.get("total_duration_ms") or 0,
            "total_api_duration_ms": cost.get("total_api_duration_ms") or 0,
            "lines_added": cost.get("total_lines_added") or 0,
            "lines_removed": cost.get("total_lines_removed") or 0,
            "total_input_tokens": context.get("total_input_tokens") or 0,
            "total_output_tokens": context.get("total_output_tokens") or 0,
            "used_percentage": context.get("used_percentage") or 0,
            "updated_at": time.time(),
        }, f)
    os.replace(tmp, path)      # atomic — a reader never sees half a file
    if first:
        prune(CACHE_DIR)       # once per session, not once per render


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    try:
        cache_cost(data)
    except Exception:
        pass                   # the line matters; the cache does not
    sys.stdout.write(build_line(data) + "\n")


if __name__ == "__main__":
    main()
