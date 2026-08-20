/**
 * Format C/C++/Python files touched by edit/write with the repo's pure_astyle,
 * once per prompt instead of once per tool call — and only inside the
 * firmware repo (~/firmware/master and its worktrees).
 *
 * Port of ~/.claude/hooks/pure_astyle_format.sh (a Claude Code PostToolUse
 * hook that ran astyle/black after every single Edit/Write). Pi has no
 * per-tool-call hook point that fires *after* the whole turn settles, so
 * this collects touched paths on tool_call and flushes them once at
 * agent_end — formatting doesn't interrupt mid-edit tool calls, and a file
 * touched by 5 edits only gets formatted once.
 *
 * Scoping: the original hook no-oped unless a `pure_astyle` script existed
 * somewhere above the edited file, which happened to only be true inside
 * firmware checkouts. That's too loose here — any repo that happens to ship
 * a same-named script would trigger it. Instead this checks the file's git
 * common-dir (`git rev-parse --git-common-dir`) against the firmware repo's
 * `.git`, which is shared by ~/firmware/master and every one of its worktrees
 * (~/firmware/plp, ~/firmware/shutdown_ina, .claude/worktrees/*, etc.) —
 * matching worktrees by path prefix alone would miss siblings that live
 * outside ~/firmware/master's own directory tree.
 *
 * Never blocks or reports errors back to the model — formatting failures
 * are silent, same as the original hook.
 */

import { isToolCallEventType, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { existsSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, resolve } from "node:path";

const FORMATTABLE = /\.(c|cc|cpp|cxx|h|hpp|hxx|py)$/;
const FIRMWARE_GIT_DIR = resolve(homedir(), "firmware", "master", ".git");

// Walk up from the file's directory looking for an executable pure_astyle.
function findAstyle(filePath: string): string | undefined {
	let dir = dirname(resolve(filePath));
	for (;;) {
		const candidate = resolve(dir, "pure_astyle");
		if (existsSync(candidate)) {
			try {
				const st = statSync(candidate);
				if (st.isFile() && (st.mode & 0o111) !== 0) return candidate;
			} catch {
				// ignore, keep walking
			}
		}
		const parent = dirname(dir);
		if (parent === dir) return undefined;
		dir = parent;
	}
}

// True if `filePath` lives in a checkout (main or worktree) of the firmware
// repo — i.e. its git common-dir resolves to ~/firmware/master/.git.
async function isInFirmwareRepo(pi: ExtensionAPI, filePath: string): Promise<boolean> {
	try {
		const result = await pi.exec(
			"git",
			["-C", dirname(filePath), "rev-parse", "--path-format=absolute", "--git-common-dir"],
			{ timeout: 5000 },
		);
		if (result.code !== 0) return false;
		return resolve(result.stdout.trim()) === FIRMWARE_GIT_DIR;
	} catch {
		return false;
	}
}

export default function (pi: ExtensionAPI) {
	// Paths touched this turn, in first-touched order; deduped on flush.
	const pending = new Set<string>();

	pi.on("tool_call", (event, ctx) => {
		if (isToolCallEventType("edit", event) || isToolCallEventType("write", event)) {
			if (FORMATTABLE.test(event.input.path)) pending.add(resolve(ctx.cwd, event.input.path));
		}
	});

	pi.on("agent_end", async () => {
		if (pending.size === 0) return;
		const paths = [...pending];
		pending.clear();

		for (const path of paths) {
			if (!(await isInFirmwareRepo(pi, path))) continue;
			const astyle = findAstyle(path);
			if (!astyle) continue;
			try {
				await pi.exec(astyle, [path], { timeout: 30000 });
			} catch {
				// stay silent — never surface formatting failures to the model
			}
		}
	});
}
