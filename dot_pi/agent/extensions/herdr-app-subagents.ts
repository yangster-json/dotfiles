/**
 * Publish the active subagent count as an hc label for herdr-app.
 * The agents-mine mod shows it as ⏳N; the TUI keeps its own title-suffix.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const LABEL = "pi.subagents";
const EVENTS = ["subagent:jobs-changed", "subagent:async-started", "subagent:async-complete", "subagent:child-status"];

export default function (pi: ExtensionAPI) {
	const terminal = process.env.HC_TERMINAL_ID;
	// only root sessions inside herdr-core terminals
	if (!terminal || process.env.PI_SUBAGENT_CHILD === "1") return;

	let shown = "";
	let busy = false;
	let again = false;

	const label = async (value: string) => {
		if (value === shown) return;
		const r = await pi.exec("hc", ["label", terminal, `${LABEL}=${value}`], { timeout: 5_000 });
		if (r.code === 0) shown = value;
	};

	const count = () =>
		new Promise<number>((resolve) => {
			const requestId = crypto.randomUUID();
			const off = pi.events.on(`subagents:rpc:v1:reply:${requestId}`, (reply: any) => {
				off();
				resolve(reply?.success ? Number(reply.data?.fleet?.totalActive ?? 0) : 0);
			});
			pi.events.emit("subagents:rpc:v1:request", { version: 1, requestId, method: "status", params: {} });
			// no pi-subagents loaded: no reply
			setTimeout(() => { off(); resolve(0); }, 3_000);
		});

	// coalesce event bursts into one status read
	const refresh = async () => {
		if (busy) { again = true; return; }
		busy = true;
		try {
			do {
				again = false;
				const n = await count();
				await label(n > 0 ? String(n) : "").catch(() => {});
			} while (again);
		} finally {
			busy = false;
		}
	};

	for (const e of EVENTS) pi.events.on(e, () => void refresh());
	pi.on("session_start", () => void refresh());
	pi.on("session_shutdown", () => label("").catch(() => {}));
}
