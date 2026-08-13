/**
 * Status line
 *
 * Mirrors ~/.claude/statusline-command.py: branch, model, context usage,
 * cost, cached tokens, in/out tokens, elapsed time — same Catppuccin Mocha
 * palette, same icons, same color thresholds. Replaces pi's built-in footer.
 *
 * Toggle with /statusline (on by default).
 */

import type { AssistantMessage } from "@earendil-works/pi-ai";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { truncateToWidth } from "@earendil-works/pi-tui";

// ---- Catppuccin Mocha palette (matches statusline-command.py) ----
function rgb(r: number, g: number, b: number): string {
	return `\x1b[38;2;${r};${g};${b}m`;
}

const MAUVE = rgb(203, 166, 247);
const PINK = rgb(245, 194, 231);
const SAPPHIRE = rgb(116, 199, 236);
const SKY = rgb(137, 220, 235);
const TEAL = rgb(148, 226, 213);
const BLUE = rgb(137, 180, 250);
const YELLOW = rgb(249, 226, 175);
const PEACH = rgb(250, 179, 135);
const RED = rgb(243, 139, 168);
const GREEN = rgb(166, 227, 161);
const OVERLAY0 = rgb(108, 112, 134);
const RESET = "\x1b[0m";
const SEP = `${OVERLAY0} | ${RESET}`;

function formatTokens(count: number): string {
	if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
	if (count >= 1_000) return `${(count / 1_000).toFixed(1)}k`;
	return `${count}`;
}

function formatCost(cost: number): string {
	if (cost < 0.01) return `$${cost.toFixed(4)}`;
	if (cost < 1) return `$${cost.toFixed(3)}`;
	return `$${cost.toFixed(2)}`;
}

function formatDuration(durationMs: number): string {
	const seconds = Math.floor(durationMs / 1000);
	const hours = Math.floor(seconds / 3600);
	const minutes = Math.floor((seconds % 3600) / 60);
	const secs = seconds % 60;
	return hours > 0
		? `${hours}h${String(minutes).padStart(2, "0")}m`
		: `${minutes}m${String(secs).padStart(2, "0")}s`;
}

export default function (pi: ExtensionAPI) {
	let enabled = true;
	let sessionStart = Date.now();

	function applyFooter(ctx: ExtensionContext) {
		ctx.ui.setFooter((tui, _theme, footerData) => {
			const unsub = footerData.onBranchChange(() => tui.requestRender());
			return {
				dispose: unsub,
				invalidate() {},
				render(width: number): string[] {
					let totalInput = 0;
					let totalOutput = 0;
					let totalCacheRead = 0;
					let totalCacheWrite = 0;
					let totalCost = 0;

					for (const entry of ctx.sessionManager.getBranch()) {
						if (entry.type === "message" && entry.message.role === "assistant") {
							const m = entry.message as AssistantMessage;
							totalInput += m.usage.input;
							totalOutput += m.usage.output;
							totalCacheRead += m.usage.cacheRead;
							totalCacheWrite += m.usage.cacheWrite;
							totalCost += m.usage.cost.total;
						}
					}

					const contextUsage = ctx.getContextUsage();
					const contextWindow = contextUsage?.contextWindow ?? ctx.model?.contextWindow ?? 200000;
					const ctxTokens = contextUsage?.tokens ?? totalInput + totalCacheRead + totalCacheWrite;
					const ctxPct =
						contextUsage?.percent != null ? Math.round(contextUsage.percent) : 0;

					const branch = footerData.getGitBranch() ?? "";
					const model = ctx.model?.id ?? "unknown";
					const elapsed = Date.now() - sessionStart;

					const costColor = totalCost >= 2.0 ? RED : totalCost >= 0.5 ? PEACH : GREEN;
					const ctxColor = ctxPct >= 80 ? RED : ctxPct >= 50 ? YELLOW : BLUE;

					const parts: string[] = [];
					if (branch) parts.push(`${MAUVE}⎇ ${branch}${RESET}`);
					parts.push(`${PINK}🤖 ${model}${RESET}`);
					parts.push(
						`${ctxColor}📊 Ctx: ${formatTokens(ctxTokens)}/${formatTokens(contextWindow)} (${ctxPct}%)${RESET}`,
					);
					parts.push(`${costColor}💰 ${formatCost(totalCost)}${RESET}`);
					parts.push(`${SAPPHIRE}📦 Cached: ${formatTokens(totalCacheRead)}${RESET}`);
					parts.push(
						`${SKY}📥 In: ${formatTokens(totalInput)}${RESET}  ${TEAL}📤 Out: ${formatTokens(totalOutput)}${RESET}`,
					);
					parts.push(`${OVERLAY0}⏱ ${formatDuration(elapsed)}${RESET}`);

					const line = "  " + parts.join(SEP);
					return [truncateToWidth(line, width, "")];
				},
			};
		});
	}

	pi.on("session_start", async (_event, ctx) => {
		sessionStart = Date.now();
		if (!ctx.hasUI) return;
		if (enabled) applyFooter(ctx);
	});

	pi.registerCommand("statusline", {
		description: "Toggle the status line footer",
		handler: async (_args, ctx) => {
			enabled = !enabled;
			if (enabled) {
				applyFooter(ctx);
			} else {
				ctx.ui.setFooter(undefined);
			}
			ctx.ui.notify(`Status line ${enabled ? "enabled" : "disabled"}`, "info");
		},
	});
}
