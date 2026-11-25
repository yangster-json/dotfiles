// Opens lazygit in Float Space for the folder you're in (a key's `mod.open`
// can't pass props, so this short-lived copy hands Float the command). It
// stays until Float acknowledges, since closing a router early can cancel the
// command copy's first core call.
import { View, div } from "gpui-kit";
import { closeOverlay, nextCommand, openOverlay, props } from "herdr";

export default class FloatLazygit extends View {
  init(_props, cx) {
    const overlay = props()?.overlay;
    if (!overlay) return; // `herdr-app check` must have no side effects.
    const token = `finished-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    cx.spawn(async () => {
      try {
        const finished = nextCommand();
        cx.timer.after(45000, () => closeOverlay(overlay));
        openOverlay({ mod: "float-space", kind: "window", frame: "none", width: 2, height: 2, at: { x: 0, y: 0 },
          props: { role: "run", command: "lazygit", shortcut: `float-space-lazygit.${token}` } });
        let reply = await finished;
        while (reply !== token) reply = await nextCommand();
      } finally {
        closeOverlay(overlay);
      }
    });
  }

  render() { return div(); }
}
