/**
 * Subagent Tool - Delegate tasks to specialized agents
 *
 * Spawns a separate `pi` process for each subagent invocation,
 * giving it an isolated context window.
 *
 * Supports three modes:
 *   - Single: { agent: "name", task: "..." }
 *   - Parallel: { tasks: [{ agent: "name", task: "..." }, ...] }
 *   - Chain: { chain: [{ agent: "name", task: "... {previous} ..." }, ...] }
 *
 * Uses JSON mode to capture structured output from subagents.
 */

import { spawn } from "node:child_process";
import * as os from "node:os";
import * as path from "node:path";
import type { AgentToolResult } from "@earendil-works/pi-agent-core";
import type { Message } from "@earendil-works/pi-ai";
import { StringEnum } from "@earendil-works/pi-ai";
import {
	CONFIG_DIR_NAME,
	type ExtensionAPI,
	getAgentDir,
	getMarkdownTheme,
} from "@earendil-works/pi-coding-agent";
import { Input, Key, Markdown, Container, Spacer, Text, matchesKey, truncateToWidth, visibleWidth, wrapTextWithAnsi } from "@earendil-works/pi-tui";
import { Type } from "typebox";
import { type AgentConfig, type AgentScope, discoverAgents } from "./agents.ts";
import {
	getLiveAgent,
	getLiveAgentSessionFile,
	killLiveAgent,
	listLiveAgents,
	reviveLiveAgent,
	shutdownLiveAgents,
	startLiveAgent,
	steerLiveAgent,
	subscribeLiveAgent,
	type LiveAgentResult,
} from "./live.ts";

const MAX_PARALLEL_TASKS = 8;
const MAX_CONCURRENCY = 4;
const COLLAPSED_ITEM_COUNT = 10;
const PER_TASK_OUTPUT_CAP = 50 * 1024;

function formatTokens(count: number): string {
	if (count < 1000) return count.toString();
	if (count < 10000) return `${(count / 1000).toFixed(1)}k`;
	if (count < 1000000) return `${Math.round(count / 1000)}k`;
	return `${(count / 1000000).toFixed(1)}M`;
}

function formatUsageStats(
	usage: {
		input: number;
		output: number;
		cacheRead: number;
		cacheWrite: number;
		cost: number;
		contextTokens?: number;
		turns?: number;
	},
	model?: string,
): string {
	const parts: string[] = [];
	if (usage.turns) parts.push(`${usage.turns} turn${usage.turns > 1 ? "s" : ""}`);
	if (usage.input) parts.push(`↑${formatTokens(usage.input)}`);
	if (usage.output) parts.push(`↓${formatTokens(usage.output)}`);
	if (usage.cacheRead) parts.push(`R${formatTokens(usage.cacheRead)}`);
	if (usage.cacheWrite) parts.push(`W${formatTokens(usage.cacheWrite)}`);
	if (usage.cost) parts.push(`$${usage.cost.toFixed(4)}`);
	if (usage.contextTokens && usage.contextTokens > 0) {
		parts.push(`ctx:${formatTokens(usage.contextTokens)}`);
	}
	if (model) parts.push(model);
	return parts.join(" ");
}

function formatToolCall(
	toolName: string,
	args: Record<string, unknown>,
	themeFg: (color: any, text: string) => string,
): string {
	const shortenPath = (p: string) => {
		const home = os.homedir();
		return p.startsWith(home) ? `~${p.slice(home.length)}` : p;
	};

	switch (toolName) {
		case "bash": {
			const command = (args.command as string) || "...";
			const preview = command.length > 60 ? `${command.slice(0, 60)}...` : command;
			return themeFg("muted", "$ ") + themeFg("toolOutput", preview);
		}
		case "read": {
			const rawPath = (args.file_path || args.path || "...") as string;
			const filePath = shortenPath(rawPath);
			const offset = args.offset as number | undefined;
			const limit = args.limit as number | undefined;
			let text = themeFg("accent", filePath);
			if (offset !== undefined || limit !== undefined) {
				const startLine = offset ?? 1;
				const endLine = limit !== undefined ? startLine + limit - 1 : "";
				text += themeFg("warning", `:${startLine}${endLine ? `-${endLine}` : ""}`);
			}
			return themeFg("muted", "read ") + text;
		}
		case "write": {
			const rawPath = (args.file_path || args.path || "...") as string;
			const filePath = shortenPath(rawPath);
			const content = (args.content || "") as string;
			const lines = content.split("\n").length;
			let text = themeFg("muted", "write ") + themeFg("accent", filePath);
			if (lines > 1) text += themeFg("dim", ` (${lines} lines)`);
			return text;
		}
		case "edit": {
			const rawPath = (args.file_path || args.path || "...") as string;
			return themeFg("muted", "edit ") + themeFg("accent", shortenPath(rawPath));
		}
		case "ls": {
			const rawPath = (args.path || ".") as string;
			return themeFg("muted", "ls ") + themeFg("accent", shortenPath(rawPath));
		}
		case "find": {
			const pattern = (args.pattern || "*") as string;
			const rawPath = (args.path || ".") as string;
			return themeFg("muted", "find ") + themeFg("accent", pattern) + themeFg("dim", ` in ${shortenPath(rawPath)}`);
		}
		case "grep": {
			const pattern = (args.pattern || "") as string;
			const rawPath = (args.path || ".") as string;
			return (
				themeFg("muted", "grep ") +
				themeFg("accent", `/${pattern}/`) +
				themeFg("dim", ` in ${shortenPath(rawPath)}`)
			);
		}
		default: {
			const argsStr = JSON.stringify(args);
			const preview = argsStr.length > 50 ? `${argsStr.slice(0, 50)}...` : argsStr;
			return themeFg("accent", toolName) + themeFg("dim", ` ${preview}`);
		}
	}
}

type SingleResult = LiveAgentResult;

interface SubagentDetails {
	mode: "single" | "parallel" | "chain";
	agentScope: AgentScope;
	projectAgentsDir: string | null;
	results: SingleResult[];
}

function getFinalOutput(messages: Message[]): string {
	for (let i = messages.length - 1; i >= 0; i--) {
		const msg = messages[i];
		if (msg.role === "assistant") {
			for (const part of msg.content) {
				if (part.type === "text") return part.text;
			}
		}
	}
	return "";
}

function isFailedResult(result: SingleResult): boolean {
	return result.exitCode !== 0 || result.stopReason === "error" || result.stopReason === "aborted";
}

function getResultOutput(result: SingleResult): string {
	if (isFailedResult(result)) return result.errorMessage || result.stderr || getFinalOutput(result.messages) || "(no output)";
	return getFinalOutput(result.messages) || "(no output)";
}

function truncateParallelOutput(output: string): string {
	const byteLength = Buffer.byteLength(output, "utf8");
	if (byteLength <= PER_TASK_OUTPUT_CAP) return output;

	let truncated = output.slice(0, PER_TASK_OUTPUT_CAP);
	while (Buffer.byteLength(truncated, "utf8") > PER_TASK_OUTPUT_CAP) truncated = truncated.slice(0, -1);
	return `${truncated}\n\n[Output truncated: ${byteLength - Buffer.byteLength(truncated, "utf8")} bytes omitted. Full output preserved in tool details.]`;
}

type DisplayItem = { type: "text"; text: string } | { type: "toolCall"; name: string; args: Record<string, any> };

function getDisplayItems(messages: Message[]): DisplayItem[] {
	const items: DisplayItem[] = [];
	for (const msg of messages) {
		if (msg.role !== "assistant") continue;
		for (const part of msg.content) {
			if (part.type === "text") items.push({ type: "text", text: part.text });
			else if (part.type === "toolCall") items.push({ type: "toolCall", name: part.name, args: part.arguments });
		}
	}
	return items;
}

async function mapWithConcurrencyLimit<TIn, TOut>(items: TIn[], concurrency: number, fn: (item: TIn, index: number) => Promise<TOut>): Promise<TOut[]> {
	if (items.length === 0) return [];
	const results: TOut[] = new Array(items.length);
	let nextIndex = 0;
	await Promise.all(new Array(Math.max(1, Math.min(concurrency, items.length))).fill(null).map(async () => {
		while (true) {
			const index = nextIndex++;
			if (index >= items.length) return;
			results[index] = await fn(items[index], index);
		}
	}));
	return results;
}

type OnUpdateCallback = (partial: AgentToolResult<SubagentDetails>) => void;

async function runSingleAgent(
	defaultCwd: string,
	agents: AgentConfig[],
	agentName: string,
	task: string,
	cwd: string | undefined,
	step: number | undefined,
	signal: AbortSignal | undefined,
	onUpdate: OnUpdateCallback | undefined,
	makeDetails: (results: SingleResult[]) => SubagentDetails,
): Promise<SingleResult> {
	const agent = agents.find(candidate => candidate.name === agentName);
	if (!agent) {
		const available = agents.map(candidate => `"${candidate.name}"`).join(", ") || "none";
		return { agent: agentName, agentSource: "unknown", task, exitCode: 1, messages: [], stderr: `Unknown agent: "${agentName}". Available agents: ${available}.`, usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0, contextTokens: 0, turns: 0 }, step };
	}

	const live = startLiveAgent({
		config: agent,
		task,
		cwd: cwd ?? defaultCwd,
		step,
		onUpdate: result => onUpdate?.({ content: [{ type: "text", text: getFinalOutput(result.messages) || "(running...)" }], details: makeDetails([result]) }),
	});
	const abort = () => {
		try { killLiveAgent(live.agent.id); } catch { /* agent already settled */ }
	};
	if (signal?.aborted) abort();
	else signal?.addEventListener("abort", abort, { once: true });
	try {
		return await live.done;
	} finally {
		signal?.removeEventListener("abort", abort);
	}
}

const TaskItem = Type.Object({
	agent: Type.String({ description: "Name of the agent to invoke" }),
	task: Type.String({ description: "Task to delegate to the agent" }),
	cwd: Type.Optional(Type.String({ description: "Working directory for the agent process" })),
});

const ChainItem = Type.Object({
	agent: Type.String({ description: "Name of the agent to invoke" }),
	task: Type.String({ description: "Task with optional {previous} placeholder for prior output" }),
	cwd: Type.Optional(Type.String({ description: "Working directory for the agent process" })),
});

const AgentScopeSchema = StringEnum(["user", "project", "both"] as const, {
	description: 'Which agent directories to use. Default: "user". Use "both" to include project-local agents.',
	default: "user",
});

const SubagentParams = Type.Object({
	agent: Type.Optional(Type.String({ description: "Name of the agent to invoke (for single mode)" })),
	task: Type.Optional(Type.String({ description: "Task to delegate (for single mode)" })),
	tasks: Type.Optional(Type.Array(TaskItem, { description: "Array of {agent, task} for parallel execution" })),
	chain: Type.Optional(Type.Array(ChainItem, { description: "Array of {agent, task} for sequential execution" })),
	agentScope: Type.Optional(AgentScopeSchema),
	confirmProjectAgents: Type.Optional(
		Type.Boolean({ description: "Prompt before running project-local agents. Default: true.", default: true }),
	),
	cwd: Type.Optional(Type.String({ description: "Working directory for the agent process (single mode)" })),
});

export default function (pi: ExtensionAPI) {
	const openNativeSession = async (id: string, ctx: any) => {
		const agent = getLiveAgent(id);
		const sessionFile = getLiveAgentSessionFile(id);
		if (!agent || !sessionFile) throw new Error("Subagent session is not available yet.");
		if (agent.status === "starting" || agent.status === "running") {
			throw new Error("Stop or complete the subagent before opening its native Pi session.");
		}

		const workspace = process.env.HERDR_WORKSPACE_ID;
		if (!workspace) throw new Error("Open-native-session requires a Herdr workspace.");
		const label = `agent ${agent.agent} ${agent.id.slice(0, 6)}`;
		const created = await pi.exec("herdr", ["tab", "create", "--workspace", workspace, "--cwd", agent.cwd, "--label", label, "--no-focus"]);
		if (created.code !== 0 || created.killed) throw new Error(created.stderr || "Could not create Herdr tab.");
		let payload: any;
		try { payload = JSON.parse(created.stdout); } catch { throw new Error("Herdr did not return tab metadata."); }
		const paneId = payload?.result?.tab?.root_pane_id ?? payload?.result?.root_pane_id ?? payload?.tab?.root_pane_id ?? payload?.root_pane_id;
		if (typeof paneId !== "string") throw new Error("Herdr response did not include a root pane ID.");
		const command = `exec pi --session ${JSON.stringify(sessionFile)}`;
		const launched = await pi.exec("herdr", ["pane", "run", paneId, command]);
		if (launched.code !== 0 || launched.killed) throw new Error(launched.stderr || "Could not open subagent session.");
		ctx.ui.notify(`Opened ${label} in Herdr.`, "info");
	};

	const statusIcon = (agent: any, theme: any) => {
		if (agent.status === "running" || agent.status === "starting") return theme.fg("warning", "●");
		if (agent.status === "complete") return theme.fg("success", "✓");
		return theme.fg("error", "✗");
	};

	const telescopeFrame = (title: string, lines: string[], width: number, theme: any): string[] => {
		const innerWidth = Math.max(1, width - 2);
		const border = (text: string) => theme.fg("accent", text);
		const frameLine = (line: string) => {
			const clipped = truncateToWidth(line, innerWidth, "", true);
			return border("│") + clipped + " ".repeat(Math.max(0, innerWidth - visibleWidth(clipped))) + border("│");
		};
		const heading = theme.fg("accent", theme.bold(` ${title} `));
		const topFill = Math.max(0, innerWidth - visibleWidth(heading) - 1);
		const top = border("╭─") + heading + border(`${"─".repeat(topFill)}╮`);
		const body = lines.flatMap(line => String(line).split("\n").flatMap(part => wrapTextWithAnsi(part, innerWidth)));
		return [top, ...body.map(frameLine), border(`╰${"─".repeat(innerWidth)}╯`)];
	};

	const eventText = (content: unknown): string => Array.isArray(content)
		? content.filter((part: any) => part?.type === "text" && typeof part.text === "string").map((part: any) => part.text).join("\n")
		: "";

	const eventJson = (value: unknown): string => {
		if (value === undefined || value === null) return "";
		try { return JSON.stringify(value, null, 2); } catch { return String(value); }
	};

	const formatInspectorEvents = (agent: any, theme: any, width: number): string[] => {
		const lines: string[] = [];
		const activeAssistant = new Map<number, number>();
		const activeThinking = new Map<number, number>();
		const activeTools = new Map<string, number>();
		const finalizedTools = new Set<string>();
		let assistantActive = false;

		const add = (label: string, text: string, color: string = "toolOutput") => {
			lines.push(theme.fg("accent", label));
			lines.push(text ? theme.fg(color, text) : theme.fg("dim", "(empty)"));
			return lines.length - 1;
		};
		const replace = (index: number | undefined, text: string, color: string = "toolOutput") => {
			if (index !== undefined) lines[index] = text ? theme.fg(color, text) : theme.fg("dim", "(empty)");
		};

		for (const event of agent.events) {
			const entry = event as any;
			if (entry.type === "message_start" && entry.message?.role === "assistant") {
				assistantActive = true;
				activeAssistant.clear();
				activeThinking.clear();
				continue;
			}
			if (entry.type === "message_start" && entry.message?.role === "user") {
				add("User", eventText(entry.message.content), "userMessageText");
				continue;
			}
			if (entry.type === "message_update") {
				const update = entry.assistantMessageEvent;
				const index = update?.contentIndex ?? 0;
				if (update?.type === "text_start") activeAssistant.set(index, add("Assistant", ""));
				else if (update?.type === "text_delta") {
					const line = activeAssistant.get(index);
					const current = line === undefined ? "" : lines[line].replace(/\x1b\[[0-9;]*m/g, "");
					if (line === undefined) activeAssistant.set(index, add("Assistant", update.delta ?? ""));
					else replace(line, current + (update.delta ?? ""));
				} else if (update?.type === "thinking_start") activeThinking.set(index, add("Thinking", "", "thinkingHigh"));
				else if (update?.type === "thinking_delta") {
					const line = activeThinking.get(index);
					const current = line === undefined ? "" : lines[line].replace(/\x1b\[[0-9;]*m/g, "");
					if (line === undefined) activeThinking.set(index, add("Thinking", update.delta ?? "", "thinkingHigh"));
					else replace(line, current + (update.delta ?? ""), "thinkingHigh");
				} else if (update?.type === "toolcall_end") {
					add("Tool call", `→ ${update.toolCall?.name ?? "unknown"} ${eventJson(update.toolCall?.arguments)}`, "muted");
				}
				continue;
			}
			if (entry.type === "message_end" && entry.message?.role === "assistant") {
				for (let index = 0; index < (entry.message.content?.length ?? 0); index++) {
					const part = entry.message.content[index];
					if (part.type === "text") {
						const line = activeAssistant.get(index);
						if (line === undefined) add("Assistant", part.text);
						else replace(line, part.text);
					} else if (part.type === "thinking") {
						const line = activeThinking.get(index);
						if (line === undefined) add("Thinking", part.thinking, "thinkingHigh");
						else replace(line, part.thinking, "thinkingHigh");
					}
				}
				assistantActive = false;
				continue;
			}
			if (entry.type === "tool_execution_start") {
				activeTools.set(entry.toolCallId, add(`Tool · ${entry.toolName}`, `→ ${eventJson(entry.args)}`, "muted"));
				continue;
			}
			if (entry.type === "tool_execution_update") {
				const text = eventText(entry.partialResult?.content);
				const details = eventJson(entry.partialResult?.details);
				replace(activeTools.get(entry.toolCallId), [text, details].filter(Boolean).join("\n\n"));
				continue;
			}
			if (entry.type === "tool_execution_end") {
				const text = eventText(entry.result?.content);
				const details = eventJson(entry.result?.details);
				replace(activeTools.get(entry.toolCallId), [entry.isError ? "✗ error" : "✓ complete", text, details].filter(Boolean).join("\n\n"), entry.isError ? "error" : "toolOutput");
				finalizedTools.add(entry.toolCallId);
				continue;
			}
			if (entry.type === "message_end" && entry.message?.role === "toolResult" && !finalizedTools.has(entry.message.toolCallId)) {
				add(`Tool result · ${entry.message.toolName}`, [eventText(entry.message.content), eventJson(entry.message.details)].filter(Boolean).join("\n\n"));
				continue;
			}
			if (!assistantActive && entry.type !== "message_start") add(entry.type ?? "event", eventJson(entry), "dim");
		}
		return lines.length > 0 ? lines : [theme.fg("dim", "(waiting for transcript events)")];
	};

	const formatRawEvents = (agent: any, theme: any): string[] => agent.events.flatMap((event: unknown) => {
		const entry = event as any;
		return [theme.fg("accent", entry.type ?? "event"), theme.fg("toolOutput", eventJson(entry))];
	});

	const formatTerminalEvents = (agent: any, theme: any, width: number, expanded: boolean): string[] => {
		const lines: string[] = [];
		const toolLines = new Map<string, number>();
		let assistantLine: number | undefined;
		const upsert = (index: number | undefined, text: string, color: string) => {
			if (index === undefined) { lines.push(theme.fg(color, text)); return lines.length - 1; }
			lines[index] = theme.fg(color, text);
			return index;
		};
		for (const event of agent.events) {
			const entry = event as any;
			if (entry.type === "message_update") {
				const update = entry.assistantMessageEvent;
				if (update?.type === "text_delta") {
					const prior = assistantLine === undefined ? "" : lines[assistantLine].replace(/\x1b\[[0-9;]*m/g, "");
					assistantLine = upsert(assistantLine, prior + update.delta, "toolOutput");
				} else if (update?.type === "toolcall_end") {
					lines.push(formatToolCall(update.toolCall?.name ?? "tool", update.toolCall?.arguments ?? {}, theme.fg.bind(theme)));
				}
				continue;
			}
			if (entry.type === "message_end" && entry.message?.role === "assistant") {
				const text = eventText(entry.message.content);
				if (text) {
					const rendered = new Markdown(text, 0, 0, getMarkdownTheme()).render(width);
					if (assistantLine === undefined) lines.push(...rendered);
					else lines.splice(assistantLine, 1, ...rendered);
					assistantLine = undefined;
				}
				continue;
			}
			if (entry.type === "tool_execution_start") {
				toolLines.set(entry.toolCallId, lines.length);
				lines.push(formatToolCall(entry.toolName, entry.args ?? {}, theme.fg.bind(theme)) + theme.fg("dim", " …"));
				continue;
			}
			if (entry.type === "tool_execution_update" || entry.type === "tool_execution_end") {
				const result = entry.type === "tool_execution_update" ? entry.partialResult : entry.result;
				const text = eventText(result?.content).trim();
				const line = toolLines.get(entry.toolCallId);
				if (entry.type === "tool_execution_end" && line !== undefined) {
					const prior = lines[line].replace(/\x1b\[[0-9;]*m/g, "").replace(/ …$/, "");
					lines[line] = theme.fg(entry.isError ? "error" : "success", `${entry.isError ? "✗ " : "✓ "}${prior}`);
				}
				if (expanded && text) lines.push(theme.fg(entry.isError ? "error" : "toolOutput", text));
				continue;
			}
			if (entry.type === "agent_start") lines.push(theme.fg("dim", "subagent started"));
			if (entry.type === "agent_settled") lines.push(theme.fg("dim", "subagent settled"));
		}
		return lines.length ? lines : [theme.fg("dim", "waiting for subagent output…")];
	};

	const inspectAgent = async (id: string, ctx: any) => {
		if (ctx.mode !== "tui") return;
		await ctx.ui.custom<void>((tui: any, theme: any, _keybindings: any, done: () => void) => {
			const input = new Input();
			let scroll = 0;
			let steering = false;
			let rawEvents = false;
			let terminalView = true;
			let expanded = false;
			let pageSize = 12;
			const unsubscribe = subscribeLiveAgent(id, () => tui.requestRender());
			const render = (width: number) => {
				const agent = getLiveAgent(id);
				if (!agent) return [theme.fg("error", "Subagent no longer exists.")];
				const terminalHeight = tui.terminal?.height ?? 40;
				const overlayHeight = Math.max(12, Math.floor(terminalHeight * 0.8));
				const contentWidth = Math.max(20, width - 2);
				const transcript = rawEvents
					? formatRawEvents(agent, theme)
					: terminalView
						? formatTerminalEvents(agent, theme, contentWidth, expanded)
						: formatInspectorEvents(agent, theme, contentWidth);
				const header = [
					theme.fg("accent", theme.bold(`${statusIcon(agent, theme)} ${agent.agent}`)) + theme.fg("dim", `  ${agent.model ?? "default"}  ${agent.status}  [${agent.id.slice(0, 8)}]`),
					theme.fg("dim", `↑↓/jk scroll  ^u/^d half  ^b/^f page  ^o ${expanded ? "collapse" : "expand"} tool output  t detail  v raw  s steer  X kill  r revive  o native  esc back`),
					theme.fg("muted", rawEvents ? "─── raw RPC events ───" : terminalView ? "─── live terminal ───" : "─── detailed transcript ───"),
				];
				const renderedTranscript = rawEvents || !terminalView
					? transcript.flatMap(line => String(line).split("\n").flatMap(part => wrapTextWithAnsi(part, contentWidth)))
					: transcript;
				const steeringLines = steering
					? [theme.fg("muted", "─── steering ───"), ...input.render(contentWidth)]
					: [];
				if (steering) input.focused = true;
				const physicalTranscript = renderedTranscript.flatMap(line => String(line).split("\n").flatMap(part => wrapTextWithAnsi(part, contentWidth)));
				const bodyHeight = Math.max(1, overlayHeight - 2 - header.length - steeringLines.length);
				pageSize = bodyHeight;
				const maxScroll = Math.max(0, physicalTranscript.length - bodyHeight);
				scroll = Math.min(scroll, maxScroll);
				const start = Math.max(0, physicalTranscript.length - bodyHeight - scroll);
				const viewport = physicalTranscript.slice(start, start + bodyHeight);
				while (viewport.length < bodyHeight) viewport.push("");
				return telescopeFrame(`Agent Inspector · ${agent.agent}`, [...header, ...viewport, ...steeringLines], width, theme);
			};
			return {
				render,
				invalidate() {},
				dispose() { unsubscribe(); },
				handleInput(data: string) {
					const agent = getLiveAgent(id);
					if (!agent) return done();
					if (steering) {
						if (matchesKey(data, Key.alt("a"))) done();
						else if (matchesKey(data, Key.escape)) { steering = false; input.setValue(""); }
						else if (matchesKey(data, Key.enter)) {
							try { steerLiveAgent(id, input.getValue()); } catch (error) { ctx.ui.notify(error instanceof Error ? error.message : String(error), "error"); }
							steering = false;
							input.setValue("");
						} else input.handleInput(data);
					} else if (matchesKey(data, Key.alt("a")) || matchesKey(data, Key.escape)) done();
					else if (matchesKey(data, Key.up) || data === "k") scroll = Math.min(scroll + 1, 10_000);
					else if (matchesKey(data, Key.down) || data === "j") scroll = Math.max(0, scroll - 1);
					else if (matchesKey(data, Key.ctrl("u"))) scroll = Math.min(scroll + Math.ceil(pageSize / 2), 10_000);
					else if (matchesKey(data, Key.ctrl("d"))) scroll = Math.max(0, scroll - Math.ceil(pageSize / 2));
					else if (matchesKey(data, Key.ctrl("b"))) scroll = Math.min(scroll + pageSize, 10_000);
					else if (matchesKey(data, Key.ctrl("f"))) scroll = Math.max(0, scroll - pageSize);
					else if (matchesKey(data, Key.ctrl("o"))) { expanded = !expanded; scroll = 0; }
					else if (data === "v") { rawEvents = !rawEvents; scroll = 0; }
					else if (data === "t") { terminalView = !terminalView; rawEvents = false; scroll = 0; }
					else if (data === "s") steering = true;
					else if (data === "X") { try { killLiveAgent(id); } catch (error) { ctx.ui.notify(error instanceof Error ? error.message : String(error), "error"); } }
					else if (data === "r") { try { reviveLiveAgent(id); } catch (error) { ctx.ui.notify(error instanceof Error ? error.message : String(error), "error"); } }
					else if (data === "o") void openNativeSession(id, ctx).catch(error => ctx.ui.notify(error instanceof Error ? error.message : String(error), "error"));
					tui.requestRender();
				},
			};
		}, {
			overlay: true,
			overlayOptions: {
				anchor: "center",
				width: "80%",
				minWidth: 72,
				maxHeight: "80%",
				margin: 1,
			},
			onHandle: handle => handle.focus(),
		});
	};

	const showAgentHub = async (ctx: any) => {
		if (ctx.mode !== "tui") {
			ctx.ui.notify("Agent Hub requires TUI mode.", "warning");
			return;
		}
		await ctx.ui.custom<void>((tui: any, theme: any, _keybindings: any, done: () => void) => {
			let selected = 0;
			const timer = setInterval(() => tui.requestRender(), 250);
			return {
				render(width: number) {
					const agents = listLiveAgents();
					const lines = [theme.fg("accent", theme.bold("Agent Hub")) + theme.fg("dim", "  ↑↓/jk select  enter inspect  s steer  X kill  r revive  o native  esc hide")];
					if (agents.length === 0) lines.push(theme.fg("muted", "No subagents have run in this parent session."));
					if (selected >= agents.length) selected = Math.max(0, agents.length - 1);
					for (let index = 0; index < agents.length; index++) {
						const agent = agents[index];
						const marker = index === selected ? theme.fg("accent", "› ") : "  ";
						lines.push(truncateToWidth(`${marker}${statusIcon(agent, theme)} ${theme.fg("accent", agent.agent)} ${theme.fg("dim", `[${agent.id.slice(0, 8)}] ${agent.model ?? "default"} · ${agent.status}`)}`, width));
					}
					const current = agents[selected];
					if (current) {
						lines.push(theme.fg("muted", "─── selected ───"));
						lines.push(...wrapTextWithAnsi(theme.fg("dim", current.task), width));
						for (const line of current.transcript.slice(-8)) lines.push(...wrapTextWithAnsi(line, width));
					}
					return telescopeFrame("Agent Hub", lines, width, theme);
				},
				invalidate() {},
				dispose() { clearInterval(timer); },
				handleInput(data: string) {
					const agents = listLiveAgents();
					if (matchesKey(data, Key.alt("a")) || matchesKey(data, Key.escape)) return done();
					if (matchesKey(data, Key.up) || data === "k") selected = Math.max(0, selected - 1);
					else if (matchesKey(data, Key.down) || data === "j") selected = Math.min(Math.max(0, agents.length - 1), selected + 1);
					else if (matchesKey(data, Key.enter) && agents[selected]) void inspectAgent(agents[selected].id, ctx);
					else if (data === "s" && agents[selected]) void ctx.ui.input("Steer subagent", "Message to selected agent").then((message: string | undefined) => message && steerLiveAgent(agents[selected].id, message));
					else if (data === "X" && agents[selected]) { try { killLiveAgent(agents[selected].id); } catch (error) { ctx.ui.notify(error instanceof Error ? error.message : String(error), "error"); } }
					else if (data === "r" && agents[selected]) { try { reviveLiveAgent(agents[selected].id); } catch (error) { ctx.ui.notify(error instanceof Error ? error.message : String(error), "error"); } }
					else if (data === "o" && agents[selected]) void openNativeSession(agents[selected].id, ctx).catch(error => ctx.ui.notify(error instanceof Error ? error.message : String(error), "error"));
					tui.requestRender();
				},
			};
		}, {
			overlay: true,
			overlayOptions: {
				anchor: "center",
				width: "75%",
				minWidth: 62,
				maxHeight: "50%",
				margin: 1,
			},
			onHandle: handle => handle.focus(),
		});
	};

	pi.registerCommand("agent-hub", {
		description: "Open the live subagent transcript and controls",
		handler: async (_args, ctx) => showAgentHub(ctx),
	});
	pi.registerCommand("agent-steer", {
		description: "Steer a running subagent: /agent-steer <id> <message>",
		handler: async (args, ctx) => {
			const [id, ...message] = args.trim().split(/\s+/);
			try { steerLiveAgent(id ?? "", message.join(" ")); ctx.ui.notify(`Steered ${id}.`, "info"); }
			catch (error) { ctx.ui.notify(error instanceof Error ? error.message : String(error), "error"); }
		},
	});
	pi.registerCommand("agent-kill", {
		description: "Stop a running subagent: /agent-kill <id>",
		handler: async (args, ctx) => {
			try { const id = killLiveAgent(args.trim()); ctx.ui.notify(`Killed ${id.slice(0, 8)}.`, "info"); }
			catch (error) { ctx.ui.notify(error instanceof Error ? error.message : String(error), "error"); }
		},
	});
	pi.registerCommand("agent-revive", {
		description: "Resume a stopped subagent: /agent-revive <id>",
		handler: async (args, ctx) => {
			try { const id = reviveLiveAgent(args.trim()); ctx.ui.notify(`Revived ${id.slice(0, 8)}.`, "info"); }
			catch (error) { ctx.ui.notify(error instanceof Error ? error.message : String(error), "error"); }
		},
	});
	pi.registerCommand("agent-open", {
		description: "Open a completed subagent session in a Herdr tab: /agent-open <id>",
		handler: async (args, ctx) => {
			try { await openNativeSession(args.trim(), ctx); }
			catch (error) { ctx.ui.notify(error instanceof Error ? error.message : String(error), "error"); }
		},
	});
	pi.registerShortcut("alt+a", { description: "Open Agent Hub", handler: async ctx => showAgentHub(ctx) });
	pi.on("session_shutdown", () => shutdownLiveAgents());
	pi.registerTool({
		name: "subagent",
		label: "Subagent",
		description: [
			"Delegate tasks to specialized subagents with isolated context.",
			"Modes: single (agent + task), parallel (tasks array), chain (sequential with {previous} placeholder).",
			`Default agent scope is "user" (from ${path.join(getAgentDir(), "agents")}).`,
			`To enable project-local agents in ${CONFIG_DIR_NAME}/agents, set agentScope: "both" (or "project").`,
		].join(" "),
		promptSnippet: "Delegate broad independent reconnaissance, planning, or review to isolated subagents",
		promptGuidelines: [
			"Use subagent proactively for repository-wide reconnaissance, independent investigations, implementation planning, or code review.",
			"Use parallel scout tasks when two or more independent repository areas can be investigated concurrently.",
			"Keep trivial, single-file, tightly sequential, or time-sensitive work in the parent session.",
			"Before editing a broad unfamiliar codebase, use a scout unless the parent already has the needed evidence.",
		],
		parameters: SubagentParams,

		async execute(_toolCallId, params, signal, onUpdate, ctx) {
			const agentScope: AgentScope = params.agentScope ?? "user";
			const discovery = discoverAgents(ctx.cwd, agentScope);
			const agents = discovery.agents;
			const confirmProjectAgents = params.confirmProjectAgents ?? true;

			const hasChain = (params.chain?.length ?? 0) > 0;
			const hasTasks = (params.tasks?.length ?? 0) > 0;
			const hasSingle = Boolean(params.agent && params.task);
			const modeCount = Number(hasChain) + Number(hasTasks) + Number(hasSingle);

			const makeDetails =
				(mode: "single" | "parallel" | "chain") =>
				(results: SingleResult[]): SubagentDetails => ({
					mode,
					agentScope,
					projectAgentsDir: discovery.projectAgentsDir,
					results,
				});

			if (modeCount !== 1) {
				const available = agents.map((a) => `${a.name} (${a.source})`).join(", ") || "none";
				return {
					content: [
						{
							type: "text",
							text: `Invalid parameters. Provide exactly one mode.\nAvailable agents: ${available}`,
						},
					],
					details: makeDetails("single")([]),
				};
			}

			if ((agentScope === "project" || agentScope === "both") && confirmProjectAgents && ctx.hasUI) {
				const requestedAgentNames = new Set<string>();
				if (params.chain) for (const step of params.chain) requestedAgentNames.add(step.agent);
				if (params.tasks) for (const t of params.tasks) requestedAgentNames.add(t.agent);
				if (params.agent) requestedAgentNames.add(params.agent);

				const projectAgentsRequested = Array.from(requestedAgentNames)
					.map((name) => agents.find((a) => a.name === name))
					.filter((a): a is AgentConfig => a?.source === "project");

				if (projectAgentsRequested.length > 0) {
					const names = projectAgentsRequested.map((a) => a.name).join(", ");
					const dir = discovery.projectAgentsDir ?? "(unknown)";
					const ok = await ctx.ui.confirm(
						"Run project-local agents?",
						`Agents: ${names}\nSource: ${dir}\n\nProject agents are repo-controlled. Only continue for trusted repositories.`,
					);
					if (!ok)
						return {
							content: [{ type: "text", text: "Canceled: project-local agents not approved." }],
							details: makeDetails(hasChain ? "chain" : hasTasks ? "parallel" : "single")([]),
						};
				}
			}

			if (params.chain && params.chain.length > 0) {
				const results: SingleResult[] = [];
				let previousOutput = "";

				for (let i = 0; i < params.chain.length; i++) {
					const step = params.chain[i];
					const taskWithContext = step.task.replace(/\{previous\}/g, previousOutput);

					// Create update callback that includes all previous results
					const chainUpdate: OnUpdateCallback | undefined = onUpdate
						? (partial) => {
								// Combine completed results with current streaming result
								const currentResult = partial.details?.results[0];
								if (currentResult) {
									const allResults = [...results, currentResult];
									onUpdate({
										content: partial.content,
										details: makeDetails("chain")(allResults),
									});
								}
							}
						: undefined;

					const result = await runSingleAgent(
						ctx.cwd,
						agents,
						step.agent,
						taskWithContext,
						step.cwd,
						i + 1,
						signal,
						chainUpdate,
						makeDetails("chain"),
					);
					results.push(result);

					const isError = isFailedResult(result);
					if (isError) {
						const errorMsg = getResultOutput(result);
						return {
							content: [{ type: "text", text: `Chain stopped at step ${i + 1} (${step.agent}): ${errorMsg}` }],
							details: makeDetails("chain")(results),
							isError: true,
						};
					}
					previousOutput = getFinalOutput(result.messages);
				}
				return {
					content: [{ type: "text", text: getFinalOutput(results[results.length - 1].messages) || "(no output)" }],
					details: makeDetails("chain")(results),
				};
			}

			if (params.tasks && params.tasks.length > 0) {
				if (params.tasks.length > MAX_PARALLEL_TASKS)
					return {
						content: [
							{
								type: "text",
								text: `Too many parallel tasks (${params.tasks.length}). Max is ${MAX_PARALLEL_TASKS}.`,
							},
						],
						details: makeDetails("parallel")([]),
					};

				// Track all results for streaming updates
				const allResults: SingleResult[] = new Array(params.tasks.length);

				// Initialize placeholder results
				for (let i = 0; i < params.tasks.length; i++) {
					allResults[i] = {
						agent: params.tasks[i].agent,
						agentSource: "unknown",
						task: params.tasks[i].task,
						exitCode: -1, // -1 = still running
						messages: [],
						stderr: "",
						usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0, contextTokens: 0, turns: 0 },
					};
				}

				const emitParallelUpdate = () => {
					if (onUpdate) {
						const running = allResults.filter((r) => r.exitCode === -1).length;
						const done = allResults.filter((r) => r.exitCode !== -1).length;
						onUpdate({
							content: [
								{ type: "text", text: `Parallel: ${done}/${allResults.length} done, ${running} running...` },
							],
							details: makeDetails("parallel")([...allResults]),
						});
					}
				};

				const results = await mapWithConcurrencyLimit(params.tasks, MAX_CONCURRENCY, async (t, index) => {
					const result = await runSingleAgent(
						ctx.cwd,
						agents,
						t.agent,
						t.task,
						t.cwd,
						undefined,
						signal,
						// Per-task update callback
						(partial) => {
							if (partial.details?.results[0]) {
								allResults[index] = partial.details.results[0];
								emitParallelUpdate();
							}
						},
						makeDetails("parallel"),
					);
					allResults[index] = result;
					emitParallelUpdate();
					return result;
				});

				const successCount = results.filter((r) => !isFailedResult(r)).length;
				const summaries = results.map((r) => {
					const output = truncateParallelOutput(getResultOutput(r));
					const status = isFailedResult(r)
						? `failed${r.stopReason && r.stopReason !== "end" ? ` (${r.stopReason})` : ""}`
						: "completed";
					return `### [${r.agent}] ${status}\n\n${output}`;
				});
				return {
					content: [
						{
							type: "text",
							text: `Parallel: ${successCount}/${results.length} succeeded\n\n${summaries.join("\n\n---\n\n")}`,
						},
					],
					details: makeDetails("parallel")(results),
				};
			}

			if (params.agent && params.task) {
				const result = await runSingleAgent(
					ctx.cwd,
					agents,
					params.agent,
					params.task,
					params.cwd,
					undefined,
					signal,
					onUpdate,
					makeDetails("single"),
				);
				const isError = isFailedResult(result);
				if (isError) {
					const errorMsg = getResultOutput(result);
					return {
						content: [{ type: "text", text: `Agent ${result.stopReason || "failed"}: ${errorMsg}` }],
						details: makeDetails("single")([result]),
						isError: true,
					};
				}
				return {
					content: [{ type: "text", text: getFinalOutput(result.messages) || "(no output)" }],
					details: makeDetails("single")([result]),
				};
			}

			const available = agents.map((a) => `${a.name} (${a.source})`).join(", ") || "none";
			return {
				content: [{ type: "text", text: `Invalid parameters. Available agents: ${available}` }],
				details: makeDetails("single")([]),
			};
		},

		renderCall(args, theme, _context) {
			const scope: AgentScope = args.agentScope ?? "user";
			if (args.chain && args.chain.length > 0) {
				let text =
					theme.fg("toolTitle", theme.bold("subagent ")) +
					theme.fg("accent", `chain (${args.chain.length} steps)`) +
					theme.fg("muted", ` [${scope}]`);
				for (let i = 0; i < Math.min(args.chain.length, 3); i++) {
					const step = args.chain[i];
					// Clean up {previous} placeholder for display
					const cleanTask = step.task.replace(/\{previous\}/g, "").trim();
					const preview = cleanTask.length > 40 ? `${cleanTask.slice(0, 40)}...` : cleanTask;
					text +=
						"\n  " +
						theme.fg("muted", `${i + 1}.`) +
						" " +
						theme.fg("accent", step.agent) +
						theme.fg("dim", ` ${preview}`);
				}
				if (args.chain.length > 3) text += `\n  ${theme.fg("muted", `... +${args.chain.length - 3} more`)}`;
				return new Text(text, 0, 0);
			}
			if (args.tasks && args.tasks.length > 0) {
				let text =
					theme.fg("toolTitle", theme.bold("subagent ")) +
					theme.fg("accent", `parallel (${args.tasks.length} tasks)`) +
					theme.fg("muted", ` [${scope}]`);
				for (const t of args.tasks.slice(0, 3)) {
					const preview = t.task.length > 40 ? `${t.task.slice(0, 40)}...` : t.task;
					text += `\n  ${theme.fg("accent", t.agent)}${theme.fg("dim", ` ${preview}`)}`;
				}
				if (args.tasks.length > 3) text += `\n  ${theme.fg("muted", `... +${args.tasks.length - 3} more`)}`;
				return new Text(text, 0, 0);
			}
			const agentName = args.agent || "...";
			const preview = args.task ? (args.task.length > 60 ? `${args.task.slice(0, 60)}...` : args.task) : "...";
			let text =
				theme.fg("toolTitle", theme.bold("subagent ")) +
				theme.fg("accent", agentName) +
				theme.fg("muted", ` [${scope}]`);
			text += `\n  ${theme.fg("dim", preview)}`;
			return new Text(text, 0, 0);
		},

		renderResult(result, { expanded }, theme, _context) {
			const details = result.details as SubagentDetails | undefined;
			if (!details || details.results.length === 0) {
				const text = result.content[0];
				return new Text(text?.type === "text" ? text.text : "(no output)", 0, 0);
			}

			const mdTheme = getMarkdownTheme();

			const renderDisplayItems = (items: DisplayItem[], limit?: number) => {
				const toShow = limit ? items.slice(-limit) : items;
				const skipped = limit && items.length > limit ? items.length - limit : 0;
				let text = "";
				if (skipped > 0) text += theme.fg("muted", `... ${skipped} earlier items\n`);
				for (const item of toShow) {
					if (item.type === "text") {
						const preview = expanded ? item.text : item.text.split("\n").slice(0, 3).join("\n");
						text += `${theme.fg("toolOutput", preview)}\n`;
					} else {
						text += `${theme.fg("muted", "→ ") + formatToolCall(item.name, item.args, theme.fg.bind(theme))}\n`;
					}
				}
				return text.trimEnd();
			};

			if (details.mode === "single" && details.results.length === 1) {
				const r = details.results[0];
				const isError = isFailedResult(r);
				const icon = isError ? theme.fg("error", "✗") : theme.fg("success", "✓");
				const displayItems = getDisplayItems(r.messages);
				const finalOutput = getFinalOutput(r.messages);

				if (expanded) {
					const container = new Container();
					let header = `${icon} ${theme.fg("toolTitle", theme.bold(r.agent))}${theme.fg("muted", ` (${r.agentSource})`)}`;
					if (isError && r.stopReason) header += ` ${theme.fg("error", `[${r.stopReason}]`)}`;
					container.addChild(new Text(header, 0, 0));
					if (isError && r.errorMessage)
						container.addChild(new Text(theme.fg("error", `Error: ${r.errorMessage}`), 0, 0));
					container.addChild(new Spacer(1));
					container.addChild(new Text(theme.fg("muted", "─── Task ───"), 0, 0));
					container.addChild(new Text(theme.fg("dim", r.task), 0, 0));
					container.addChild(new Spacer(1));
					container.addChild(new Text(theme.fg("muted", "─── Output ───"), 0, 0));
					if (displayItems.length === 0 && !finalOutput) {
						container.addChild(new Text(theme.fg("muted", "(no output)"), 0, 0));
					} else {
						for (const item of displayItems) {
							if (item.type === "toolCall")
								container.addChild(
									new Text(
										theme.fg("muted", "→ ") + formatToolCall(item.name, item.args, theme.fg.bind(theme)),
										0,
										0,
									),
								);
						}
						if (finalOutput) {
							container.addChild(new Spacer(1));
							container.addChild(new Markdown(finalOutput.trim(), 0, 0, mdTheme));
						}
					}
					const usageStr = formatUsageStats(r.usage, r.model);
					if (usageStr) {
						container.addChild(new Spacer(1));
						container.addChild(new Text(theme.fg("dim", usageStr), 0, 0));
					}
					return container;
				}

				let text = `${icon} ${theme.fg("toolTitle", theme.bold(r.agent))}${theme.fg("muted", ` (${r.agentSource})`)}`;
				if (isError && r.stopReason) text += ` ${theme.fg("error", `[${r.stopReason}]`)}`;
				if (isError && r.errorMessage) text += `\n${theme.fg("error", `Error: ${r.errorMessage}`)}`;
				else if (displayItems.length === 0) text += `\n${theme.fg("muted", "(no output)")}`;
				else {
					text += `\n${renderDisplayItems(displayItems, COLLAPSED_ITEM_COUNT)}`;
					if (displayItems.length > COLLAPSED_ITEM_COUNT) text += `\n${theme.fg("muted", "(Ctrl+O to expand)")}`;
				}
				const usageStr = formatUsageStats(r.usage, r.model);
				if (usageStr) text += `\n${theme.fg("dim", usageStr)}`;
				return new Text(text, 0, 0);
			}

			const aggregateUsage = (results: SingleResult[]) => {
				const total = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0, turns: 0 };
				for (const r of results) {
					total.input += r.usage.input;
					total.output += r.usage.output;
					total.cacheRead += r.usage.cacheRead;
					total.cacheWrite += r.usage.cacheWrite;
					total.cost += r.usage.cost;
					total.turns += r.usage.turns;
				}
				return total;
			};

			if (details.mode === "chain") {
				const successCount = details.results.filter((r) => r.exitCode === 0).length;
				const icon = successCount === details.results.length ? theme.fg("success", "✓") : theme.fg("error", "✗");

				if (expanded) {
					const container = new Container();
					container.addChild(
						new Text(
							icon +
								" " +
								theme.fg("toolTitle", theme.bold("chain ")) +
								theme.fg("accent", `${successCount}/${details.results.length} steps`),
							0,
							0,
						),
					);

					for (const r of details.results) {
						const rIcon = r.exitCode === 0 ? theme.fg("success", "✓") : theme.fg("error", "✗");
						const displayItems = getDisplayItems(r.messages);
						const finalOutput = getFinalOutput(r.messages);

						container.addChild(new Spacer(1));
						container.addChild(
							new Text(
								`${theme.fg("muted", `─── Step ${r.step}: `) + theme.fg("accent", r.agent)} ${rIcon}`,
								0,
								0,
							),
						);
						container.addChild(new Text(theme.fg("muted", "Task: ") + theme.fg("dim", r.task), 0, 0));

						// Show tool calls
						for (const item of displayItems) {
							if (item.type === "toolCall") {
								container.addChild(
									new Text(
										theme.fg("muted", "→ ") + formatToolCall(item.name, item.args, theme.fg.bind(theme)),
										0,
										0,
									),
								);
							}
						}

						// Show final output as markdown
						if (finalOutput) {
							container.addChild(new Spacer(1));
							container.addChild(new Markdown(finalOutput.trim(), 0, 0, mdTheme));
						}

						const stepUsage = formatUsageStats(r.usage, r.model);
						if (stepUsage) container.addChild(new Text(theme.fg("dim", stepUsage), 0, 0));
					}

					const usageStr = formatUsageStats(aggregateUsage(details.results));
					if (usageStr) {
						container.addChild(new Spacer(1));
						container.addChild(new Text(theme.fg("dim", `Total: ${usageStr}`), 0, 0));
					}
					return container;
				}

				// Collapsed view
				let text =
					icon +
					" " +
					theme.fg("toolTitle", theme.bold("chain ")) +
					theme.fg("accent", `${successCount}/${details.results.length} steps`);
				for (const r of details.results) {
					const rIcon = r.exitCode === 0 ? theme.fg("success", "✓") : theme.fg("error", "✗");
					const displayItems = getDisplayItems(r.messages);
					text += `\n\n${theme.fg("muted", `─── Step ${r.step}: `)}${theme.fg("accent", r.agent)} ${rIcon}`;
					if (displayItems.length === 0) text += `\n${theme.fg("muted", "(no output)")}`;
					else text += `\n${renderDisplayItems(displayItems, 5)}`;
				}
				const usageStr = formatUsageStats(aggregateUsage(details.results));
				if (usageStr) text += `\n\n${theme.fg("dim", `Total: ${usageStr}`)}`;
				text += `\n${theme.fg("muted", "(Ctrl+O to expand)")}`;
				return new Text(text, 0, 0);
			}

			if (details.mode === "parallel") {
				const running = details.results.filter((r) => r.exitCode === -1).length;
				const successCount = details.results.filter((r) => r.exitCode !== -1 && !isFailedResult(r)).length;
				const failCount = details.results.filter((r) => r.exitCode !== -1 && isFailedResult(r)).length;
				const isRunning = running > 0;
				const icon = isRunning
					? theme.fg("warning", "⏳")
					: failCount > 0
						? theme.fg("warning", "◐")
						: theme.fg("success", "✓");
				const status = isRunning
					? `${successCount + failCount}/${details.results.length} done, ${running} running`
					: `${successCount}/${details.results.length} tasks`;

				if (expanded && !isRunning) {
					const container = new Container();
					container.addChild(
						new Text(
							`${icon} ${theme.fg("toolTitle", theme.bold("parallel "))}${theme.fg("accent", status)}`,
							0,
							0,
						),
					);

					for (const r of details.results) {
						const rIcon = isFailedResult(r) ? theme.fg("error", "✗") : theme.fg("success", "✓");
						const displayItems = getDisplayItems(r.messages);
						const finalOutput = getFinalOutput(r.messages);

						container.addChild(new Spacer(1));
						container.addChild(
							new Text(`${theme.fg("muted", "─── ") + theme.fg("accent", r.agent)} ${rIcon}`, 0, 0),
						);
						container.addChild(new Text(theme.fg("muted", "Task: ") + theme.fg("dim", r.task), 0, 0));

						// Show tool calls
						for (const item of displayItems) {
							if (item.type === "toolCall") {
								container.addChild(
									new Text(
										theme.fg("muted", "→ ") + formatToolCall(item.name, item.args, theme.fg.bind(theme)),
										0,
										0,
									),
								);
							}
						}

						// Show final output as markdown
						if (finalOutput) {
							container.addChild(new Spacer(1));
							container.addChild(new Markdown(finalOutput.trim(), 0, 0, mdTheme));
						}

						const taskUsage = formatUsageStats(r.usage, r.model);
						if (taskUsage) container.addChild(new Text(theme.fg("dim", taskUsage), 0, 0));
					}

					const usageStr = formatUsageStats(aggregateUsage(details.results));
					if (usageStr) {
						container.addChild(new Spacer(1));
						container.addChild(new Text(theme.fg("dim", `Total: ${usageStr}`), 0, 0));
					}
					return container;
				}

				// Collapsed view (or still running)
				let text = `${icon} ${theme.fg("toolTitle", theme.bold("parallel "))}${theme.fg("accent", status)}`;
				for (const r of details.results) {
					const rIcon =
						r.exitCode === -1
							? theme.fg("warning", "⏳")
							: isFailedResult(r)
								? theme.fg("error", "✗")
								: theme.fg("success", "✓");
					const displayItems = getDisplayItems(r.messages);
					text += `\n\n${theme.fg("muted", "─── ")}${theme.fg("accent", r.agent)} ${rIcon}`;
					if (displayItems.length === 0)
						text += `\n${theme.fg("muted", r.exitCode === -1 ? "(running...)" : "(no output)")}`;
					else text += `\n${renderDisplayItems(displayItems, 5)}`;
				}
				if (!isRunning) {
					const usageStr = formatUsageStats(aggregateUsage(details.results));
					if (usageStr) text += `\n\n${theme.fg("dim", `Total: ${usageStr}`)}`;
				}
				if (!expanded) text += `\n${theme.fg("muted", "(Ctrl+O to expand)")}`;
				return new Text(text, 0, 0);
			}

			const text = result.content[0];
			return new Text(text?.type === "text" ? text.text : "(no output)", 0, 0);
		},
	});
}
