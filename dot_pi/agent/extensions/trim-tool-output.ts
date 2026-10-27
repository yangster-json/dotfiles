/**
 * Drop pi-memory's file-preview echo from memory_write/scratchpad results.
 * The model already knows what it wrote; the preview costs ~1k tokens a call.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const PREVIEW_TOOLS = new Set(["memory_write", "scratchpad"]);
const PREVIEW_RE = /\n\n(Existing daily log|Existing MEMORY\.md|Scratchpad) preview[\s\S]*$/;

export default function (pi: ExtensionAPI) {
	pi.on("tool_result", (event) => {
		if (!PREVIEW_TOOLS.has(event.toolName) || event.isError) return;
		// keep scratchpad list output; it is the point of that action
		if (event.toolName === "scratchpad" && event.input.action === "list") return;
		let changed = false;
		const content = event.content.map((c) => {
			if (c.type !== "text" || !PREVIEW_RE.test(c.text)) return c;
			changed = true;
			return { ...c, text: c.text.replace(PREVIEW_RE, "") };
		});
		if (changed) return { content };
	});
}
