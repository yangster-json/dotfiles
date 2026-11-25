// mod.open can't pass props; route to shipped worktree dialog.
import { View, div } from "gpui-kit";
import { closeOverlay, openOverlay, panes, props, spaces } from "herdr";

export const ACTION = "new";

export function openWorktree(action, cx) {
  const overlay = props()?.overlay;
  if (!overlay) return; // `herdr-app check` must have no side effects.
  const space = spaces().find(s => s.active);
  const size = action === "open" ? { width: 560, height: 480 } : { width: 460, height: 280 };
  openOverlay({ mod: "worktree", kind: "dialog", ...size,
    props: { space: space?.id, folder: panes().find(p => p.focused)?.cwd ?? space?.folder, action } });
  // close router after dialog is up
  cx.timer.after(200, () => closeOverlay(overlay));
}

export default class WorktreeNew extends View {
  init(_props, cx) { openWorktree(ACTION, cx); }
  render() { return div(); }
}
