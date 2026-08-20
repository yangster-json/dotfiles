
import { isToolCallEventType, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { existsSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, resolve } from "node:path";

const FORMATTABLE = /\.(c|cc|cpp|cxx|h|hpp|hxx|py)$/;
const FIRMWARE_GIT_DIR = resolve(homedir(), "firmware", "master", ".git");

function findAstyle(filePath: string): string | undefined {
	let dir = dirname(resolve(filePath));
	for (;;) {
		const candidate = resolve(dir, "pure_astyle");
		if (existsSync(candidate)) {
			try {
				const st = statSync(candidate);
				if (st.isFile() && (st.mode & 0o111) !== 0) return candidate;
			} catch {

			}
		}
		const parent = dirname(dir);
		if (parent === dir) return undefined;
		dir = parent;
	}
}

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

			}
		}
	});
}
