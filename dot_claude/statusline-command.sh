#!/usr/bin/env bash
# Claude Code status line: branch, model, cache, in/out, context, cost, elapsed.
# One jq batch to parse the input, one python3 call to format + color the line.
# Schema: https://code.claude.com/docs/en/statusline
input=$(cat)

eval "$(echo "$input" | jq -r '
  @sh "cur_in=\(.context_window.current_usage.input_tokens // 0)",
  @sh "cache_read=\(.context_window.current_usage.cache_read_input_tokens // 0)",
  @sh "cache_create=\(.context_window.current_usage.cache_creation_input_tokens // 0)",
  @sh "total_in=\(.context_window.total_input_tokens // 0)",
  @sh "total_out=\(.context_window.total_output_tokens // 0)",
  @sh "ctx_size=\(.context_window.context_window_size // 200000)",
  @sh "used_pct=\(.context_window.used_percentage // 0)",
  @sh "model_name=\(.model.display_name // "unknown")",
  @sh "cost_usd=\(.cost.total_cost_usd // 0)",
  @sh "duration_ms=\(.cost.total_duration_ms // 0)",
  @sh "cwd=\(.workspace.current_dir // .cwd // "")",
  @sh "worktree=\(.workspace.git_worktree // "")"
' 2>/dev/null)"

# Prefer the real branch; fall back to the linked-worktree name. Skip optional
# locks so a concurrent git process never blocks the prompt.
git_branch=$(git -C "$cwd" --no-optional-locks rev-parse --abbrev-ref HEAD 2>/dev/null)
[ -z "$git_branch" ] && git_branch="$worktree"

python3 - "$git_branch" "$model_name" "$cache_read" "$total_in" "$total_out" \
    "$cur_in" "$cache_create" "$ctx_size" "$used_pct" "$cost_usd" "$duration_ms" <<'PY'
import sys

(
    branch,
    model,
    cache_read,
    total_in,
    total_out,
    cur_in,
    cache_create,
    ctx_size,
    used_pct,
    cost_usd,
    duration_ms,
) = sys.argv[1:12]

cache_read = int(cache_read)
total_in = int(total_in)
total_out = int(total_out)
ctx_in = int(cur_in) + cache_read + int(cache_create)
ctx_size = int(ctx_size)
ctx_pct = int(round(float(used_pct or 0)))
cost = float(cost_usd or 0)
seconds = int(duration_ms) // 1000


def format_tokens(count):
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}k"
    return str(count)


# Adaptive precision: more decimals when the total is tiny.
if cost < 0.01:
    cost_fmt = f"${cost:.4f}"
elif cost < 1:
    cost_fmt = f"${cost:.3f}"
else:
    cost_fmt = f"${cost:.2f}"

hours, minutes, secs = seconds // 3600, (seconds % 3600) // 60, seconds % 60
duration_fmt = f"{hours}h{minutes:02d}m" if hours else f"{minutes}m{secs:02d}s"

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

# Cost: green <$0.50, peach <$2, red >=$2.
cost_color = RED if cost >= 2.0 else PEACH if cost >= 0.5 else GREEN
# Context: blue <50%, yellow 50-79%, red >=80%.
ctx_color = RED if ctx_pct >= 80 else YELLOW if ctx_pct >= 50 else BLUE

parts = []
if branch:
    parts.append(f"{MAUVE}⎇ {branch}{RESET}")
parts.append(f"{PINK}🤖 {model}{RESET}")
parts.append(
    f"{ctx_color}📊 Ctx: {format_tokens(ctx_in)}/{format_tokens(ctx_size)} "
    f"({ctx_pct}%){RESET}"
)
parts.append(f"{cost_color}💰 {cost_fmt}{RESET}")
parts.append(f"{SAPPHIRE}📦 Cached: {format_tokens(cache_read)}{RESET}")
parts.append(
    f"{SKY}📥 In: {format_tokens(total_in)}{RESET}"
    f"  {TEAL}📤 Out: {format_tokens(total_out)}{RESET}"
)
parts.append(f"{OVERLAY0}⏱ {duration_fmt}{RESET}")

sys.stdout.write("  " + SEP.join(parts) + "\n")
PY
