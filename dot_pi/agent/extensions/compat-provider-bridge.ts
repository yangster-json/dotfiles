/**
 * Mirror extension-registered providers into pi-ai's compat api registry.
 *
 * pi keeps extension providers in its own ModelRuntime map and never calls
 * pi-ai's registerApiProvider — `grep -r registerApiProvider` over pi's dist is
 * empty — so pi-ai's compat registry only knows the built-in apis. Packages that
 * drive their own agent loops with the raw compat streamSimple therefore die on
 * a custom provider with "No API provider registered for api: <name>":
 * pi-observational-memory's observer/reflector/dropper pass it explicitly, and
 * pi-experiences' advisor falls back to it. Re-registering the provider's own
 * streamSimple under its api name makes that raw path resolve.
 *
 * Resolution matters more than it looks: there is a second pi-ai copy under
 * ~/.pi/node_modules, and a bare specifier from this directory resolves to it —
 * a different module instance with its own registry, so the fix would silently
 * do nothing. argv[1] is the bin symlink, not dist/cli.js, so realpath it first
 * and resolve from there to land in the same instance pi actually streams with.
 */

import { existsSync, realpathSync } from "node:fs";
import { pathToFileURL } from "node:url";

const bridged = new Set<string>();

async function loadCompat(): Promise<any> {
	// pi-ai's exports map has no "./compat" subpath, so require.resolve on the
	// specifier fails; the file has to be reached by path.
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
			// fall through
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
	// session_start covers the normal path; before_agent_start re-checks in case a
	// provider registers later or a background loop runs before the first turn.
	pi.on("session_start", (_e: unknown, ctx: any) => bridgeProviders(ctx));
	pi.on("before_agent_start", (_e: unknown, ctx: any) => bridgeProviders(ctx));
}
