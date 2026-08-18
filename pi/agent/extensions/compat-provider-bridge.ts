/**
 * Mirror extension-registered providers into pi-ai's compat api registry.
 *
 * pi keeps extension providers in its own ModelRuntime map and never calls
 * pi-ai's registerApiProvider — `grep -r registerApiProvider` over pi's dist is
 * empty. So pi-ai's compat registry only ever knows the built-in apis. Packages
 * that drive their own agent loops with the raw compat streamSimple therefore
 * die on a custom provider with "No API provider registered for api: <name>":
 * pi-observational-memory's observer/reflector/dropper pass it explicitly, and
 * pi-experiences' advisor falls back to it. Re-registering the provider's own
 * streamSimple under its api name makes that raw path resolve.
 *
 * session_start fires after every extension has registered, so everpure-foundry
 * is present by then. Resolving compat off the running CLI's own package keeps
 * us in the same module instance as the code that crashes — a second copy would
 * have its own registry and fix nothing.
 */

import { pathToFileURL } from "node:url";

const bridged = new Set<string>();

async function loadCompat(): Promise<any> {
	const cli = process.argv[1] ?? "";
	const root = cli.replace(/\/dist\/cli\.js$/, "");
	if (root && root !== cli) {
		try {
			return await import(
				pathToFileURL(`${root}/node_modules/@earendil-works/pi-ai/dist/compat.js`).href
			);
		} catch {
			// fall through to bare specifier
		}
	}
	return await import("@earendil-works/pi-ai/compat");
}

export default function (pi: any) {
	pi.on("session_start", async (_event: unknown, ctx: any) => {
		const registry = ctx?.modelRegistry;
		if (!registry?.getRegisteredProviderIds || !registry.getRegisteredProviderConfig) return;

		let compat: any;
		for (const id of registry.getRegisteredProviderIds()) {
			const cfg = registry.getRegisteredProviderConfig(id);
			if (!cfg?.api || !cfg.streamSimple || bridged.has(cfg.api)) continue;
			compat ??= await loadCompat();
			if (compat.getApiProvider?.(cfg.api)) {
				bridged.add(cfg.api);
				continue;
			}
			compat.registerApiProvider({
				api: cfg.api,
				stream: cfg.stream,
				streamSimple: cfg.streamSimple,
			});
			bridged.add(cfg.api);
		}
	});
}
