import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import type { Message } from "@earendil-works/pi-ai";
import { getAgentDir } from "@earendil-works/pi-coding-agent";
import type { AgentConfig } from "./agents.ts";

export interface LiveUsageStats {
	input: number;
	output: number;
	cacheRead: number;
	cacheWrite: number;
	cost: number;
	contextTokens: number;
	turns: number;
}

export interface LiveAgentResult {
	agent: string;
	agentSource: "user" | "project" | "unknown";
	task: string;
	exitCode: number;
	messages: Message[];
	stderr: string;
	usage: LiveUsageStats;
	model?: string;
	stopReason?: string;
	errorMessage?: string;
	step?: number;
}

export type LiveAgentStatus = "starting" | "running" | "complete" | "failed" | "killed";

export interface LiveAgentSnapshot {
	id: string;
	agent: string;
	model?: string;
	task: string;
	status: LiveAgentStatus;
	transcript: string[];
	events: unknown[];
	result: LiveAgentResult;
	startedAt: number;
	sessionId: string;
	sessionDir: string;
	cwd: string;
}

interface LiveAgent extends LiveAgentSnapshot {
	config: AgentConfig;
	cwd: string;
	proc?: ChildProcessWithoutNullStreams;
	sessionId: string;
	settled: boolean;
	resolveDone: (result: LiveAgentResult) => void;
	done: Promise<LiveAgentResult>;
	onUpdate?: (result: LiveAgentResult) => void;
	listeners: Set<() => void>;
	liveTextIndex?: number;
}

const agents = new Map<string, LiveAgent>();
const sessionDir = path.join(getAgentDir(), "subagent-sessions");
const MAX_TRANSCRIPT_LINES = 800;
const MAX_EVENTS = 2_000;

function newUsage(): LiveUsageStats {
	return { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0, contextTokens: 0, turns: 0 };
}

function getPiInvocation(args: string[]): { command: string; args: string[] } {
	const currentScript = process.argv[1];
	const isBunVirtualScript = currentScript?.startsWith("/$bunfs/root/");
	if (currentScript && !isBunVirtualScript && fs.existsSync(currentScript)) {
		return { command: process.execPath, args: [currentScript, ...args] };
	}

	const execName = path.basename(process.execPath).toLowerCase();
	if (!/^(node|bun)(\.exe)?$/.test(execName)) return { command: process.execPath, args };
	return { command: "pi", args };
}

function appendTranscript(agent: LiveAgent, line: string): void {
	if (!line) return;
	agent.transcript.push(line);
	if (agent.transcript.length > MAX_TRANSCRIPT_LINES) agent.transcript.splice(0, agent.transcript.length - MAX_TRANSCRIPT_LINES);
}

function appendEvent(agent: LiveAgent, event: unknown): void {
	agent.events.push(event);
	if (agent.events.length > MAX_EVENTS) agent.events.splice(0, agent.events.length - MAX_EVENTS);
}

function notifyUpdate(agent: LiveAgent): void {
	agent.onUpdate?.(agent.result);
	for (const listener of agent.listeners) listener();
}

function send(proc: ChildProcessWithoutNullStreams, command: Record<string, unknown>): void {
	if (!proc.stdin.writable) throw new Error("Subagent control channel is closed.");
	proc.stdin.write(`${JSON.stringify(command)}\n`);
}

function finish(agent: LiveAgent, status: LiveAgentStatus, exitCode: number, error?: string): void {
	if (agent.settled) return;
	agent.settled = true;
	agent.status = status;
	agent.result.exitCode = exitCode;
	if (error) agent.result.errorMessage = error;
	notifyUpdate(agent);
	agent.resolveDone(agent.result);
}

function recordMessage(agent: LiveAgent, message: Message): void {
	agent.result.messages.push(message);
	if (message.role !== "assistant") return;

	agent.result.usage.turns++;
	const usage = message.usage;
	if (usage) {
		agent.result.usage.input += usage.input || 0;
		agent.result.usage.output += usage.output || 0;
		agent.result.usage.cacheRead += usage.cacheRead || 0;
		agent.result.usage.cacheWrite += usage.cacheWrite || 0;
		agent.result.usage.cost += usage.cost?.total || 0;
		agent.result.usage.contextTokens = usage.totalTokens || 0;
	}
	if (!agent.result.model && message.model) agent.result.model = message.model;
	if (message.stopReason) agent.result.stopReason = message.stopReason;
	if (message.errorMessage) agent.result.errorMessage = message.errorMessage;
}

function formatEvent(event: any): string | undefined {
	if (event.type === "message_update") {
		const update = event.assistantMessageEvent;
		if (update?.type === "toolcall_end") return `→ ${update.toolCall.name} ${JSON.stringify(update.toolCall.arguments)}`;
	}
	if (event.type === "tool_execution_start") return `→ ${event.toolName} ${JSON.stringify(event.args)}`;
	if (event.type === "tool_execution_end") return event.isError ? `✗ ${event.toolName}` : `✓ ${event.toolName}`;
	if (event.type === "agent_start") return "agent started";
	if (event.type === "agent_settled") return "agent settled";
	return undefined;
}

function launch(agent: LiveAgent, resume: boolean): void {
	fs.mkdirSync(sessionDir, { recursive: true, mode: 0o700 });
	const args = ["--mode", "rpc", "--session-id", agent.sessionId, "--session-dir", sessionDir, "--name", `subagent ${agent.agent}`];
	if (agent.config.model) args.push("--model", agent.config.model);
	if (agent.config.tools?.length) args.push("--tools", agent.config.tools.join(","));
	if (agent.config.systemPrompt.trim()) args.push("--append-system-prompt", agent.config.systemPrompt);

	const invocation = getPiInvocation(args);
	const proc = spawn(invocation.command, invocation.args, {
		cwd: agent.cwd,
		shell: false,
		stdio: ["pipe", "pipe", "pipe"],
	});
	agent.proc = proc;
	agent.status = "starting";
	agent.settled = false;
	appendTranscript(agent, resume ? "reviving agent" : "starting agent");
	notifyUpdate(agent);

	let buffer = "";
	const processLine = (line: string) => {
		if (!line.trim()) return;
		let event: any;
		try {
			event = JSON.parse(line);
		} catch {
			appendTranscript(agent, line);
			return;
		}

		appendEvent(agent, event);

		if (event.type === "message_update") {
			const update = event.assistantMessageEvent;
			if (update?.type === "text_start") {
				agent.liveTextIndex = agent.transcript.length;
				appendTranscript(agent, "assistant: ");
			}
			if (update?.type === "text_delta") {
				if (agent.liveTextIndex === undefined) {
					agent.liveTextIndex = agent.transcript.length;
					appendTranscript(agent, "assistant: ");
				}
				agent.transcript[agent.liveTextIndex] += update.delta;
			}
		}
		if (event.type === "message_end" && event.message) {
			recordMessage(agent, event.message as Message);
			agent.liveTextIndex = undefined;
		}
		const text = formatEvent(event);
		if (text) appendTranscript(agent, text);
		if (event.type === "agent_start") agent.status = "running";
		if (event.type === "agent_settled") {
			finish(agent, "complete", 0);
			proc.kill("SIGTERM");
		} else {
			notifyUpdate(agent);
		}
	};

	proc.stdout.on("data", data => {
		buffer += data.toString();
		const lines = buffer.split("\n");
		buffer = lines.pop() || "";
		for (const line of lines) processLine(line.endsWith("\r") ? line.slice(0, -1) : line);
	});
	proc.stderr.on("data", data => {
		agent.result.stderr += data.toString();
		appendTranscript(agent, data.toString().trim());
	});
	proc.on("error", error => finish(agent, "failed", 1, error.message));
	proc.on("close", code => {
		if (buffer.trim()) processLine(buffer);
		if (!agent.settled) {
			const status = agent.status === "killed" ? "killed" : "failed";
			finish(agent, status, code ?? 1, agent.result.stderr || `Subagent exited with code ${code ?? 1}.`);
		}
	});

	try {
		send(proc, {
			type: "prompt",
			message: resume
				? `Resume the delegated task: ${agent.task}\nReview your prior work, then continue and finish it.`
				: `Task: ${agent.task}`,
		});
	} catch (error) {
		finish(agent, "failed", 1, error instanceof Error ? error.message : String(error));
	}
}

export function startLiveAgent(options: {
	config: AgentConfig;
	task: string;
	cwd: string;
	step?: number;
	onUpdate?: (result: LiveAgentResult) => void;
	liveTextIndex?: number;
}): { agent: LiveAgentSnapshot; done: Promise<LiveAgentResult> } {
	const id = crypto.randomUUID();
	let resolveDone!: (result: LiveAgentResult) => void;
	const done = new Promise<LiveAgentResult>(resolve => {
		resolveDone = resolve;
	});
	const result: LiveAgentResult = {
		agent: options.config.name,
		agentSource: options.config.source,
		task: options.task,
		exitCode: -1,
		messages: [],
		stderr: "",
		usage: newUsage(),
		model: options.config.model,
		step: options.step,
	};
	const agent: LiveAgent = {
		id,
		agent: options.config.name,
		model: options.config.model,
		task: options.task,
		status: "starting",
		transcript: [],
		events: [],
		result,
		startedAt: Date.now(),
		config: options.config,
		cwd: options.cwd,
		sessionId: `subagent-${id}`,
		sessionDir,
		settled: false,
		resolveDone,
		done,
		onUpdate: options.onUpdate,
		listeners: new Set(),
	};
	agents.set(id, agent);
	launch(agent, false);
	return { agent, done };
}

export function listLiveAgents(): LiveAgentSnapshot[] {
	return Array.from(agents.values())
		.sort((a, b) => b.startedAt - a.startedAt)
		.map(({ config: _config, proc: _proc, settled: _settled, resolveDone: _resolveDone, done: _done, onUpdate: _onUpdate, listeners: _listeners, liveTextIndex: _liveTextIndex, ...snapshot }) => snapshot);
}

export function getLiveAgent(id: string): LiveAgentSnapshot | undefined {
	const agent = Array.from(agents.values()).find(candidate => candidate.id === id || candidate.id.startsWith(id));
	if (!agent) return undefined;
	const { config: _config, proc: _proc, settled: _settled, resolveDone: _resolveDone, done: _done, onUpdate: _onUpdate, listeners: _listeners, liveTextIndex: _liveTextIndex, ...snapshot } = agent;
	return snapshot;
}

export function subscribeLiveAgent(id: string, listener: () => void): () => void {
	const agent = findAgent(id);
	if (!agent) return () => {};
	agent.listeners.add(listener);
	return () => agent.listeners.delete(listener);
}

export function getLiveAgentSessionFile(id: string): string | undefined {
	const agent = findAgent(id);
	if (!agent) return undefined;
	try {
		const entry = fs.readdirSync(sessionDir).find(candidate => candidate.endsWith(`_${agent.sessionId}.jsonl`));
		return entry ? path.join(sessionDir, entry) : undefined;
	} catch {
		return undefined;
	}
}

function findAgent(id: string): LiveAgent | undefined {
	return Array.from(agents.values()).find(agent => agent.id === id || agent.id.startsWith(id));
}

export function steerLiveAgent(id: string, message: string): string {
	const agent = findAgent(id);
	if (!agent) throw new Error(`Unknown agent: ${id}`);
	if (agent.status !== "starting" && agent.status !== "running") throw new Error(`${agent.agent} is not running.`);
	if (!message.trim()) throw new Error("Steering message is empty.");
	send(agent.proc!, { type: "steer", message });
	appendTranscript(agent, `› steer: ${message}`);
	return agent.id;
}

export function killLiveAgent(id: string): string {
	const agent = findAgent(id);
	if (!agent) throw new Error(`Unknown agent: ${id}`);
	if (!agent.proc || agent.status !== "starting" && agent.status !== "running") throw new Error(`${agent.agent} is not running.`);
	agent.status = "killed";
	appendTranscript(agent, "agent killed by user");
	try {
		send(agent.proc, { type: "abort" });
	} catch {

	}
	agent.proc.kill("SIGTERM");
	setTimeout(() => agent.proc && !agent.proc.killed && agent.proc.kill("SIGKILL"), 5000).unref();
	return agent.id;
}

export function reviveLiveAgent(id: string): string {
	const agent = findAgent(id);
	if (!agent) throw new Error(`Unknown agent: ${id}`);
	if (agent.status === "starting" || agent.status === "running") throw new Error(`${agent.agent} is already running.`);
	let resolveDone!: (result: LiveAgentResult) => void;
	agent.done = new Promise<LiveAgentResult>(resolve => {
		resolveDone = resolve;
	});
	agent.resolveDone = resolveDone;
	agent.result.exitCode = -1;
	agent.result.errorMessage = undefined;
	launch(agent, true);
	return agent.id;
}

export function shutdownLiveAgents(): void {
	for (const agent of agents.values()) {
		if (agent.status === "starting" || agent.status === "running") killLiveAgent(agent.id);
	}
}
