
import { existsSync, realpathSync } from "node:fs";
import { pathToFileURL } from "node:url";

const bridged = new Set<string>();

async function loadCompat(): Promise<any> {

	const entry = process.argv[1];
	if (entry) {
		try {
			const root = realpathSync(entry).replace(/\/dist\/cli\.js$/, "");
			const candidates = [
				`${root}/node_modules/@earendil-works/pi-ai/dist/compat.js`,
				`${root}/../pi-ai/dist/compat.js`,
			];
			for (const candidate of candidates) {
				if (existsSync(candidate)) return await import(pathToFileURL(candidate).href);
			}
		} catch {

		}
	}
	return await import("@earendil-works/pi-ai/compat");
}

async function bridgeProviders(ctx: any): Promise<void> {
	const registry = ctx?.modelRegistry;
	if (!registry?.getRegisteredProviderIds || !registry.getRegisteredProviderConfig) return;
	let compat: any;
	for (const id of registry.getRegisteredProviderIds()) {
		const cfg = registry.getRegisteredProviderConfig(id);
		if (!cfg?.api || !cfg.streamSimple || bridged.has(cfg.api)) continue;
		compat ??= await loadCompat();
		if (!compat.getApiProvider?.(cfg.api)) {
			compat.registerApiProvider({ api: cfg.api, stream: cfg.stream, streamSimple: cfg.streamSimple });
		}
		bridged.add(cfg.api);
	}
}

export default function (pi: any) {

	pi.on("session_start", (_e: unknown, ctx: any) => bridgeProviders(ctx));
	pi.on("before_agent_start", (_e: unknown, ctx: any) => bridgeProviders(ctx));
}
