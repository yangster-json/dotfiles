// Terminal blocks in a floating window still have Herdr's Terminal key context.
// Short-lived entries route terminal shortcuts even when Float is hidden or
// absent from the layout. Their mod.json props choose a route; none takes focus.
import { View, div } from "gpui-kit";
import { appHome, closeOverlay, focused, hc, nextCommand, openOverlay, props, run, terminals } from "herdr";

const ROUTES = {
  new: { receiver: "float-space-new", fallback: "tab.new" },
  next: { receiver: "float-space-next", fallback: "tab.next" },
  prev: { receiver: "float-space-prev", fallback: "tab.prev" },
  notes: { receiver: "float-space-notes", fallback: "space.new" },
  close: { receiver: "float-space-close", fallback: "tab.close" },
};

async function ownsFocus(focus, terminal) {
  if (focus?.pane !== null || !focus.terminal) return false;
  if (terminal) return terminal.state === "live"
    && terminal.labels?.["herdr.mod"] === "float-space"
    && terminal.labels?.["herdr.float-space"] === appHome();
  // A newly created terminal can take focus before it reaches the live cache.
  const result = await hc(["ls", "--json", "--label", "herdr.mod=float-space",
    "--label", `herdr.float-space=${appHome()}`]);
  if (result.code !== 0) throw new Error(result.stderr.trim() || "Could not check Float terminal ownership");
  return JSON.parse(result.stdout).terminals.some(item => item.address === focus.terminal && item.state === "live");
}

export default class TerminalShortcut extends View {
  init(_props, cx) {
    const overlay = props()?.overlay;
    if (!overlay) return; // `herdr-app check` must have no side effects.
    const command = props()?.shortcut ?? "new";
    const route = Object.hasOwn(ROUTES, command) ? ROUTES[command] : null;
    if (!route) { closeOverlay(overlay); return; }
    const focus = focused();
    const terminal = focus?.terminal && terminals().find(item => item.address === focus.terminal);
    cx.spawn(async cx => {
      try {
        if (await ownsFocus(focus, terminal)) {
          // Closing the router early can cancel the command copy's core reply.
          // Match this invocation's acknowledgement, not another shortcut's.
          const token = `finished-${Date.now()}-${Math.random().toString(36).slice(2)}`;
          const finished = nextCommand();
          cx.timer.after(45000, () => closeOverlay(overlay));
          openOverlay({ mod: "float-space", kind: "window", frame: "none", width: 2, height: 2, at: { x: 0, y: 0 },
            props: { role: "run", command: command === "close" ? `end-${focus.terminal}` : command,
              shortcut: `${route.receiver}.${token}` } });
          let reply = await finished;
          while (reply !== token) reply = await nextCommand();
        } else {
          run(route.fallback);
        }
      } finally {
        closeOverlay(overlay);
      }
    });
  }

  render() { return div(); }
}
