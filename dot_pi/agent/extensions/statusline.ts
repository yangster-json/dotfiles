
import type { AssistantMessage } from "@earendil-works/pi-ai";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { truncateToWidth } from "@earendil-works/pi-tui";

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
const MODE_WIDTH = 13;

function vimModeLabel(statuses: ReadonlyMap<string, string>): string {
	const mode = statuses.get("vim-mode") ?? "INSERT";
	const padding = Math.max(0, MODE_WIDTH - mode.length);
	const text = " ".repeat(Math.floor(padding / 2)) + mode + " ".repeat(Math.ceil(padding / 2));
	if (mode === "INSERT") return `\x1b[1;38;2;30;30;46;48;2;166;227;161m${text}\x1b[0m`;
	if (mode === "NORMAL") return `\x1b[1;38;2;30;30;46;48;2;137;180;250m${text}\x1b[0m`;
	if (mode === "VISUAL") return `\x1b[1;38;2;30;30;46;48;2;249;226;175m${text}\x1b[0m`;
	return `\x1b[1;38;2;30;30;46;48;2;203;166;247m${text}\x1b[0m`;
}

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

type UsageTotals = {
	input: number;
	output: number;
	cost: number;
};

type RawUsage = {
	input?: unknown;
	output?: unknown;
	cost?: unknown;
};

type CompletionPayload = {
	totalTokens?: { input?: unknown; output?: unknown };
	totalCost?: { costUsd?: unknown };
	details?: {
		totalTokens?: { input?: unknown; output?: unknown };
		totalCost?: { costUsd?: unknown };
	};
};

const SUBAGENT_ASYNC_COMPLETE = "subagent:async-complete";
const SUBAGENT_DELEGATION_RESPONSE = "prompt-template:subagent:response";

function numberOrZero(value: unknown): number {
	return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function usageFromCompletion(value: CompletionPayload): UsageTotals {
	const tokens = value.totalTokens ?? value.details?.totalTokens;
	const cost = value.totalCost ?? value.details?.totalCost;
	return {
		input: numberOrZero(tokens?.input),
		output: numberOrZero(tokens?.output),
		cost: numberOrZero(cost?.costUsd),
	};
}

function usageFromRaw(value: RawUsage | undefined): UsageTotals {
	return {
		input: numberOrZero(value?.input),
		output: numberOrZero(value?.output),
		cost: numberOrZero(value?.cost),
	};
}

function runIdOf(value: { runId?: unknown; id?: unknown }): string | null {
	if (typeof value.runId === "string") return value.runId;
	if (typeof value.id === "string") return value.id;
	return null;
}

export default function (pi: ExtensionAPI) {
	let enabled = true;
	let sessionStart = Date.now();

	const runUsage = new Map<string, UsageTotals>();

	const subsumedRuns = new Set<string>();

	function resetSubagentUsage(): void {
		runUsage.clear();
		subsumedRuns.clear();
	}

	function recordRun(runId: string, usage: UsageTotals): void {
		if (subsumedRuns.has(runId)) return;
		runUsage.set(runId, usage);
	}

	function subsumeChildren(children: Array<{ runId?: unknown; id?: unknown }>): void {
		for (const child of children) {
			const id = runIdOf(child);
			if (!id) continue;
			subsumedRuns.add(id);
			runUsage.delete(id);
		}
	}

	function childUsage(): UsageTotals {
		const totals: UsageTotals = { input: 0, output: 0, cost: 0 };
		for (const usage of runUsage.values()) {
			totals.input += usage.input;
			totals.output += usage.output;
			totals.cost += usage.cost;
		}
		return totals;
	}

	pi.events.on(SUBAGENT_ASYNC_COMPLETE, (event) => {
		const completion = event as CompletionPayload & { runId?: unknown; results?: unknown };
		if (typeof completion.runId !== "string") return;
		if (Array.isArray(completion.results)) subsumeChildren(completion.results);
		recordRun(completion.runId, usageFromCompletion(completion));
	});

	pi.events.on(SUBAGENT_DELEGATION_RESPONSE, (event) => {
		const response = event as { runId?: unknown; usage?: RawUsage };
		if (typeof response.runId !== "string") return;
		recordRun(response.runId, usageFromRaw(response.usage));
	});

	pi.on("tool_result", (event) => {
		if (event.toolName !== "subagent") return;
		const details = event.details as {
			results?: Array<{ runId?: unknown; id?: unknown; usage?: RawUsage }>;
		};
		for (const result of details.results ?? []) {
			const id = runIdOf(result);
			if (!id) continue;
			recordRun(id, usageFromRaw(result.usage));
		}
	});

	function applyFooter(ctx: ExtensionContext) {
		ctx.ui.setFooter((tui, _theme, footerData) => {
			const unsub = footerData.onBranchChange(() => tui.requestRender());
			const timer = setInterval(() => tui.requestRender(), 1000);
			timer.unref();
			return {
				dispose() {
					clearInterval(timer);
					unsub();
				},
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

					const child = childUsage();
					const childCost = child.cost;
					const displayedInput = totalInput + child.input;
					const displayedOutput = totalOutput + child.output;
					const displayedCost = totalCost + childCost;
					const contextUsage = ctx.getContextUsage();
					const contextWindow = contextUsage?.contextWindow ?? ctx.model?.contextWindow ?? 200000;
					const ctxTokens = contextUsage?.tokens ?? totalInput + totalCacheRead + totalCacheWrite;
					const ctxPct =
						contextUsage?.percent != null ? Math.round(contextUsage.percent) : 0;

					const branch = footerData.getGitBranch() ?? "";
					const model = ctx.model?.id ?? "unknown";
					const elapsed = Date.now() - sessionStart;

					const costColor = displayedCost >= 2.0 ? RED : displayedCost >= 0.5 ? PEACH : GREEN;
					const ctxColor = ctxPct >= 80 ? RED : ctxPct >= 50 ? YELLOW : BLUE;

					const parts: string[] = [];
					if (branch) parts.push(`${MAUVE}${branch}${RESET}`);
					parts.push(`${PINK}${model}${RESET}`);
					parts.push(
						`${ctxColor}Ctx: ${formatTokens(ctxTokens)}/${formatTokens(contextWindow)} (${ctxPct}%)${RESET}`,
					);
					parts.push(`${costColor}${formatCost(displayedCost)}${RESET}`);
					if (childCost > 0) parts.push(`${PINK}Child: ${formatCost(childCost)}${RESET}`);
					parts.push(`${SAPPHIRE}Cached: ${formatTokens(totalCacheRead)}${RESET}`);
					parts.push(
						`${SKY}In: ${formatTokens(displayedInput)}${RESET}  ${TEAL}Out: ${formatTokens(displayedOutput)}${RESET}`,
					);
					parts.push(`${OVERLAY0}${formatDuration(elapsed)}${RESET}`);

					const line = vimModeLabel(footerData.getExtensionStatuses()) + " " + parts.join(SEP);
					return [truncateToWidth(line, width, "")];
				},
			};
		});
	}

	pi.on("session_start", async (_event, ctx) => {
		sessionStart = Date.now();
		resetSubagentUsage();
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
