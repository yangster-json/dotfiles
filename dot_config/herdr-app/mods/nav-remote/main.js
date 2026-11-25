// ctrl+hjkl front for splits-nav: remote nvim gets the key itself.
// splits-nav reaches nvim over laptop 127.0.0.1 only; remote nvim
// moves its own splits and sets nvim.nav at an edge.
import { View, div } from "gpui-kit";
import { focused, panes, terminals, run, hc, nextCommand, checking } from "herdr";

const KEYS = { left: "h", down: "j", up: "k", right: "l" };

export default class NavRemote extends View {
  init(_props, cx) {
    this.primed = false;
    this.seen = new Map();
    if (checking()) return;
    cx.spawn(async () => {
      for (;;) {
        const dir = await nextCommand();
        if (KEYS[dir]) await this.nav(dir);
      }
    });
  }

  async nav(dir) {
    const f = focused();
    const pane = f?.pane ? panes().find((p) => p.pane === f.pane) : null;
    const remote = pane?.terminal?.includes("/");
    if (remote && pane.program?.key === "nvim") {
      const r = await hc(["keys", pane.terminal, `ctrl+${KEYS[dir]}`]).catch(() => null);
      if (r?.code === 0) return;
    }
    run(`splits-nav.${dir}`);
  }

  // rerenders on label changes: catch remote nvim edge hits
  render(cx) {
    const shown = focused()?.terminal;
    for (const t of terminals()) {
      const v = t.labels?.["nvim.nav"];
      if (!v || this.seen.get(t.address) === v) continue;
      this.seen.set(t.address, v);
      const dir = v.split(":")[0];
      // first pass is a baseline: labels left from before load
      if (this.primed && KEYS[dir] && t.address === shown) {
        cx.timer.after(0, () => run("pane.go", { direction: dir }));
      }
    }
    this.primed = true;
    return div().w(0).h(0);
  }
}
