"""tests for the sdd status/watch dashboard.

the renderer is decoration, so the tests that matter are the layout
invariants a tmux side pane depends on — nothing overflows the width,
nothing carries trailing whitespace, and no state.md field is required to
be present — plus the fields the dashboard newly surfaces (metrics,
policies, auto-approved gates).
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from helpers import SDD, load_module

status = load_module("sdd_status", "bin/sdd-status")

ANSI = re.compile(r"\033\[[0-9;]*m")

STATE = """# sdd state: demo

created: 2026-07-28
jira: FW-25177
upstream: origin/master
phase: implement
plan_approved: yes
gate1_auto_approved: yes
review_approved: no
gate2_auto_approved: no
autopilot: gate1=skip,gate2=ask
findings_policy: waive
test_fail_policy: proceed
pr: open
stages_skipped: research (the living base spec already covers this area)
tier_offset: heavy (cross-cutting change with subtle invariants)
base_ref: HEAD
hw_testbed: fw-comet02
hw_bay: 19

## tasks
| id | title | complexity | status | depends_on | parallel_ok |
|----|-------|------------|--------|------------|-------------|
| T1 | add nvme io stat counters to the monitor | simple | done | — | no |
| T2 | wire the activity led blink to those counters | standard | done | T1 | no |
| T3 | hide the nvram namespace so background reads stop re-arming the hold \
| standard | in_progress | T2 | yes |
| T4 | add unit tests for the blink hold timeout | simple | blocked | T2 | yes |
| T5 | update the monitor docs | simple | pending | T3 | no |

## metrics
verify_retries: 2
tasks_blocked: 1
ambiguities: 1
file_list_fixes: 0
findings_confirmed: 0
findings_rejected: 0
findings_waived: 0
gate1_reroutes: 0
gate2_reroutes: 0
test_failures: 0
merge_conflicts: 1

## amendments
- A1 (2026-07-30): blink hold on nvram reads? -> hide namespace-2 (assumption)

## waived findings

## tests run

## log
- 2026-07-28 feature initialized
- 2026-07-29 spec complete
- 2026-07-29 plan complete · gate 1 auto-approved
- 2026-07-30 T1 done
- 2026-07-30 T2 done after 2 verify retries
- 2026-07-31 T4 blocked — the verify command needs hardware on another bay
"""

# a feature that has only just been created: no tasks, no metrics, no sections
MINIMAL = "# sdd state: demo\n\nphase: research\n"


def plain(s):
    return ANSI.sub("", s)


def make_project(text, mtime=None):
    """a throwaway sdd project with one active feature. the caller registers
    cleanup; mtime backdates state.md to fake an idle run."""
    root = tempfile.mkdtemp(prefix="sdd-status-tmp-")
    os.makedirs(os.path.join(root, "specs", "demo"))
    with open(os.path.join(root, "specs", "ACTIVE"), "w") as f:
        f.write("demo")
    path = os.path.join(root, "specs", "demo", "state.md")
    with open(path, "w") as f:
        f.write(text)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return root


class StatusTest(unittest.TestCase):
    def setUp(self):
        status.use_color(False)
        self.root = tempfile.mkdtemp(prefix="sdd-status-test-")
        self.write("demo", STATE)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, slug, text, active=None):
        os.makedirs(os.path.join(self.root, "specs", slug), exist_ok=True)
        with open(os.path.join(self.root, "specs", "ACTIVE"), "w") as f:
            f.write(active if active is not None else slug)
        with open(os.path.join(self.root, "specs", slug, "state.md"), "w") as f:
            f.write(text)

    def full(self, slug=None, **kw):
        kw.setdefault("width", 80)
        return status.render_full(self.root, slug, status.View(**kw))

    # ---- layout invariants (what a narrow tmux pane depends on) -----------

    def test_no_line_exceeds_the_width(self):
        for width in (52, 56, 62, 72, 80, 96, 120):
            for text in (STATE, MINIMAL):
                self.write("demo", text)
                for line in self.full(width=width).splitlines():
                    self.assertLessEqual(
                        len(plain(line)), width,
                        f"width {width} overflowed: {line!r}")

    def test_animated_frames_keep_the_layout_invariants(self):
        """the animation must not cost a column anywhere, on any frame."""
        anim = status.Anim(enabled=True)
        for frame in range(24):
            anim.frame = frame
            for width in (52, 80, 96):
                out = self.full(width=width, anim=anim)
                for line in out.splitlines():
                    self.assertLessEqual(len(plain(line)), width,
                                         f"frame {frame} w{width}: {line!r}")
                    self.assertEqual(line, line.rstrip())

    def test_no_trailing_whitespace(self):
        for line in self.full(width=62).splitlines():
            self.assertEqual(line, line.rstrip(), f"trailing ws: {line!r}")

    def test_color_can_be_disabled_and_enabled(self):
        self.assertNotIn("\033[", self.full())
        try:
            status.use_color(True)
            self.assertIn("\033[", self.full())
        finally:
            status.use_color(False)

    def test_renders_without_any_optional_field(self):
        """state.md is LLM-written; a half-filled one must still render."""
        self.write("demo", MINIMAL)
        out = self.full()
        self.assertIn("sdd: demo", out)
        self.assertIn("research", out)

    # ---- information the dashboard surfaces ------------------------------

    def test_metrics_shows_nonzero_counters_only(self):
        out = self.full()
        self.assertIn("retries 2", out)
        self.assertIn("blocked 1", out)
        self.assertIn("conflicts 1", out)
        self.assertNotIn("file-fixes", out)   # 0 -> hidden
        self.assertNotIn("rejected", out)     # 0 -> hidden

    def test_metrics_section_absent_when_all_counters_zero(self):
        self.write("demo", STATE.replace("verify_retries: 2", "verify_retries: 0")
                   .replace("tasks_blocked: 1", "tasks_blocked: 0")
                   .replace("ambiguities: 1", "ambiguities: 0")
                   .replace("merge_conflicts: 1", "merge_conflicts: 0"))
        self.assertNotIn("metrics", self.full())

    def test_policies_and_autoroute_are_shown(self):
        out = self.full()
        self.assertIn("gates skip/ask", out)
        self.assertIn("findings waive", out)
        self.assertIn("test-fail proceed", out)
        self.assertIn("pr open", out)
        self.assertIn("tier heavy", out)
        self.assertIn("skipped:", out)

    def test_tier_hidden_when_standard(self):
        self.write("demo", STATE.replace(
            "tier_offset: heavy (cross-cutting change with subtle invariants)",
            "tier_offset: standard"))
        self.assertNotIn("tier ", self.full())

    def test_auto_approved_gate_is_distinguished(self):
        self.assertIn("✔auto", self.full())
        self.write("demo", STATE.replace("gate1_auto_approved: yes",
                                         "gate1_auto_approved: no"))
        self.assertNotIn("✔auto", self.full())

    def test_task_rows_and_progress(self):
        out = self.full(width=96)
        self.assertIn("2/5 done", out)
        for tid in ("T1", "T2", "T3", "T4", "T5"):
            self.assertIn(tid, out)
        self.assertIn("in_progress", out)
        self.assertIn("blocked", out)

    def test_assumption_amendment_is_flagged(self):
        self.assertIn("assumption(s) to veto", self.full(width=96))

    def test_log_limit_and_full_log(self):
        last = "T4 blocked"
        first = "feature initialized"
        out = self.full(log_limit=2)
        self.assertIn(last, out)
        self.assertNotIn(first, out)
        self.assertIn("last 2 of 6", out)
        self.assertIn(first, self.full(log_limit=0))

    def test_artifacts_report_presence(self):
        fdir = os.path.join(self.root, "specs", "demo")
        out = self.full()
        self.assertIn("research ─", out)  # absent
        with open(os.path.join(fdir, "research.md"), "w") as f:
            f.write("a\nb\n")
        os.makedirs(os.path.join(fdir, "tasks"), exist_ok=True)
        for tid in ("T1", "T2"):
            open(os.path.join(fdir, "tasks", f"{tid}.md"), "w").close()
        out = self.full()
        self.assertIn("research 2L", out)
        self.assertIn("subspecs 2", out)

    def test_stall_warning_only_when_stale_and_unfinished(self):
        path = os.path.join(self.root, "specs", "demo", "state.md")
        old = time.time() - status.STALL_SECONDS - 60
        os.utime(path, (old, old))
        self.assertIn("stalled", self.full())
        # a finished feature is not stalled, however old its state.md is
        self.write("demo", STATE.replace("phase: implement", "phase: done"))
        os.utime(path, (old, old))
        self.assertNotIn("stalled", self.full())

    # ---- one-line summary -------------------------------------------------

    def test_brief(self):
        line = plain(status.render_brief(self.root))
        self.assertIn("sdd:demo", line)
        self.assertIn("implement", line)
        self.assertIn("tasks 2/5", line)
        self.assertIn("(T3)", line)          # the in-progress task
        self.assertIn("1 blocked", line)
        self.assertIn("tier heavy", line)
        self.assertIn("hw fw-comet02/19", line)
        self.assertIn("│", line)             # separators survive color-off

    def test_brief_silent_without_active_feature(self):
        os.remove(os.path.join(self.root, "specs", "ACTIVE"))
        self.assertIsNone(status.render_brief(self.root))

    def test_full_reports_missing_active_feature(self):
        os.remove(os.path.join(self.root, "specs", "ACTIVE"))
        self.assertIn("no active sdd feature", self.full())

    def test_worktree_pointer_followed(self):
        outer = tempfile.mkdtemp(prefix="sdd-status-outer-")
        try:
            inner, self.root = self.root, outer
            os.makedirs(os.path.join(outer, "specs"), exist_ok=True)
            with open(os.path.join(outer, "specs", "ACTIVE"), "w") as f:
                f.write(f"worktree: {inner}")
            self.assertIn("sdd: demo", self.full())
            self.assertIn("sdd:demo", plain(status.render_brief(outer)))
        finally:
            self.root = inner
            shutil.rmtree(outer, ignore_errors=True)

    # ---- helpers ----------------------------------------------------------

    def test_pack_never_exceeds_width_and_keeps_segments_intact(self):
        segs = ["alpha one", "beta two", "gamma three", "delta four"]
        lines = status.pack(segs, 24)
        for line in lines:
            self.assertLessEqual(len(line), 24)
        joined = " · ".join(l.strip() for l in lines)
        for s in segs:
            self.assertIn(s, joined)

    def test_pack_counts_printable_width_only(self):
        status.use_color(True)
        try:
            colored = [f"\033[32m{'x' * 10}\033[0m" for _ in range(3)]
            self.assertEqual(len(status.pack(colored, 40)), 1)
        finally:
            status.use_color(False)

    def test_ago(self):
        self.assertEqual(status.ago(9), "9s")
        self.assertEqual(status.ago(600), "10m")
        self.assertEqual(status.ago(7200), "2.0h")
        self.assertEqual(status.ago(172800), "2d")

    def test_bar_fills_exactly_the_requested_width(self):
        for counts in ({"done": 5}, {"done": 1, "pending": 4},
                       {"done": 1, "in_progress": 1, "blocked": 1,
                        "pending": 2}):
            total = sum(counts.values())
            self.assertEqual(len(plain(status.bar(counts, total, 18))), 18)
        self.assertEqual(status.bar({}, 0), "")

    def test_section_drops_an_unfittable_note(self):
        out = plain(status.section("amendments", "a very long note indeed", 30))
        self.assertNotIn("very long", out)
        self.assertLessEqual(len(out), 30)


class AnimTest(unittest.TestCase):
    """the animation carries meaning (moving vs parked, changed vs not), so
    these assert the mapping, not the prettiness."""

    def setUp(self):
        status.use_color(False)

    def test_pick_cycles_and_freezes_when_disabled(self):
        a = status.Anim(enabled=True)
        seen = []
        for f in range(len(status.Anim.SPIN) + 2):
            a.frame = f
            seen.append(a.pick(status.Anim.SPIN))
        self.assertEqual(len(set(seen)), len(status.Anim.SPIN))
        self.assertEqual(seen[0], seen[len(status.Anim.SPIN)])  # wraps
        off = status.Anim(enabled=False)
        off.frame = 5
        self.assertEqual(off.pick(status.Anim.SPIN), status.Anim.SPIN[0])

    def test_spinner_when_moving_pulse_when_idle(self):
        a = status.Anim(enabled=True)
        self.assertIn(a.phase_glyph(idle=False), status.Anim.SPIN)
        self.assertIn(a.phase_glyph(idle=True), status.Anim.WAIT)
        self.assertEqual(status.Anim(enabled=False).phase_glyph(False), "▶")

    def test_first_note_primes_without_flashing_everything(self):
        a = status.Anim(enabled=True)
        rows = [{"id": "T1", "status": "done"}, {"id": "T2", "status": "pending"}]
        a.note(rows, 3, now=100.0)
        self.assertFalse(a.fresh("T1"))
        self.assertFalse(a.fresh("T2"))
        self.assertEqual(a.new_log_lines(), 0)

    def test_status_change_flashes_then_expires(self):
        a = status.Anim(enabled=True)
        a.note([{"id": "T1", "status": "pending"}], 1, now=100.0)
        a.note([{"id": "T1", "status": "done"}], 1, now=101.0)
        self.assertTrue(a.fresh("T1"))
        a.note([{"id": "T1", "status": "done"}],
               1, now=101.0 + status.Anim.FLASH + 0.1)
        self.assertFalse(a.fresh("T1"))

    def test_a_brand_new_task_row_flashes(self):
        a = status.Anim(enabled=True)
        a.note([{"id": "T1", "status": "done"}], 1, now=1.0)
        a.note([{"id": "T1", "status": "done"},
                {"id": "F1", "status": "pending"}], 1, now=2.0)
        self.assertTrue(a.fresh("F1"))    # a gate-2 fix task appearing
        self.assertFalse(a.fresh("T1"))

    def test_new_log_lines_counted_then_expire(self):
        a = status.Anim(enabled=True)
        a.note([], 5, now=1.0)
        a.note([], 8, now=2.0)
        self.assertEqual(a.new_log_lines(), 3)
        a.note([], 8, now=2.0 + status.Anim.FLASH + 0.1)
        self.assertEqual(a.new_log_lines(), 0)

    def test_nothing_flashes_when_animation_is_off(self):
        a = status.Anim(enabled=False)
        a.note([{"id": "T1", "status": "pending"}], 1, now=1.0)
        a.note([{"id": "T1", "status": "done"}], 2, now=2.0)
        self.assertFalse(a.fresh("T1"))
        self.assertEqual(a.new_log_lines(), 0)

    def test_gauge_width_is_exact_on_every_frame(self):
        a = status.Anim(enabled=True)
        counts = {"done": 2, "in_progress": 1, "blocked": 1, "pending": 3}
        for f in range(20):
            a.frame = f
            self.assertEqual(len(plain(status.bar(counts, 7, 18, anim=a))), 18)

    def test_mark_last_never_marks_more_than_the_window(self):
        rows = status.log_lines(["- 2026-07-01 a", "- 2026-07-02 b"], 60,
                               mark_last=9)
        self.assertEqual(sum(1 for r in rows if r.startswith("▸")), 2)

    def project(self, text, mtime=None):
        root = make_project(text, mtime)
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        return root

    def test_static_render_is_deterministic(self):
        """--full must be a still frame: no animation state may leak into it."""
        root = self.project(STATE)
        a, b = (status.render_full(root, None, status.View(width=80))
                for _ in range(2))
        self.assertEqual(a, b)
        self.assertIn("▶", a)  # the static in-progress marker, not a spinner
        for g in status.Anim.SPIN:
            self.assertNotIn(g, a)

    def test_done_phase_sparkles_and_never_spins(self):
        root = self.project(STATE.replace("phase: implement", "phase: done"))
        anim = status.Anim(enabled=True)
        seen = set()
        for frame in range(12):
            anim.frame = frame
            out = status.render_full(root, None,
                                     status.View(width=80, anim=anim))
            self.assertIn("done ✔", out)
            seen |= {g for g in status.Anim.SPARK if g in out}
            for g in status.Anim.SPIN:      # a finished run is not working
                self.assertNotIn(g, out)
        self.assertGreater(len(seen), 1)    # the sparkle actually animates

    def test_idle_run_pulses_and_never_spins(self):
        """stale state.md: the pane must not imply work is happening."""
        root = self.project(STATE, mtime=time.time() - status.STALL_SECONDS - 60)
        anim = status.Anim(enabled=True)
        pulses = set()
        for frame in range(12):
            anim.frame = frame
            out = status.render_full(root, None,
                                     status.View(width=80, anim=anim))
            self.assertIn("stalled", out)
            pulses |= {g for g in status.Anim.WAIT if g in out}
            for g in status.Anim.SPIN:
                self.assertNotIn(g, out)
        self.assertGreater(len(pulses), 1)

    def test_paint_does_not_full_clear(self):
        """a \\033[2J per frame strobes at 8 fps — this is the guard."""
        out = status.paint("one\ntwo")
        self.assertNotIn("\033[2J", out)
        self.assertEqual(out.count("\033[K"), 2)
        self.assertTrue(out.startswith("\033[H"))
        self.assertTrue(out.endswith("\033[J"))


class CostSectionTest(unittest.TestCase):
    """the cost section names its source: claude code's as-billed figure when
    the statusline has cached one, the price-table estimate otherwise."""

    BILLED = {"billed": True, "session": 4.25, "orch": 3.10, "agents": 0.90,
              "day": 12.5, "age": 4.0, "sessions": 2}
    EST = dict(BILLED, billed=False, session=4.0, age=None)

    def setUp(self):
        status.use_color(False)
        self.root = make_project(STATE)
        self.saved = dict(status._cost)

    def tearDown(self):
        status._cost.clear()
        status._cost.update(self.saved)
        shutil.rmtree(self.root, ignore_errors=True)

    def prime(self, parts):
        """stand in for sdd-cost so no real transcript is read."""
        status._cost.update(at=time.time(), parts=parts)

    def segs(self, parts):
        self.prime(parts)
        return status.cost_segs(self.root, max_age=999)

    def test_billed_figure_is_labelled_as_billed(self):
        segs, note = self.segs(self.BILLED)
        self.assertIn("as billed", note)
        joined = plain(" ".join(segs))
        self.assertIn("session $4.25", joined)
        # the split is the estimate even when the total is not
        self.assertIn("orch $3.10 est", joined)
        self.assertIn("agents $0.90 est", joined)

    def test_estimate_says_it_is_an_estimate(self):
        segs, note = self.segs(self.EST)
        self.assertIn("estimate", note)
        self.assertIn("no statusline cache", note)
        self.assertNotIn("est", plain(" ".join(segs)))   # the note carries it

    def test_a_frozen_cache_is_called_out(self):
        """a session that ended stops updating; a stale number presented as
        live is worse than no number. it goes in a segment, not the note,
        because section() clips notes to fit the rule."""
        fresh, _ = self.segs(dict(self.BILLED, age=30))
        self.assertNotIn("updated", plain(" ".join(fresh)))
        stale, _ = self.segs(dict(self.BILLED, age=3600))
        self.assertIn("updated 1.0h ago", plain(" ".join(stale)))
        for width in (52, 80):
            self.prime(dict(self.BILLED, age=3600))
            out = plain(status.render_full(
                self.root, None,
                status.View(width=width, want_cost=True, cost_age=999)))
            self.assertIn("updated 1.0h ago", out)

    def test_no_data_at_all(self):
        segs, note = self.segs({"billed": False, "session": None})
        self.assertEqual(segs, [])
        self.assertIn("no transcript data", note)
    def test_a_broken_sdd_cost_never_takes_the_dashboard_down(self):
        real = status._sdd_cost
        status._cost.update(at=0.0, parts=None)
        try:
            status._sdd_cost = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
            self.assertEqual(status.cost_segs(self.root), ([], "unavailable"))
        finally:
            status._sdd_cost = real

    def test_the_cost_section_never_overflows_a_narrow_pane(self):
        """it used to be one unwrapped line — 68 columns in a 52-column pane."""
        for parts in (self.BILLED, self.EST, {"billed": False, "session": None}):
            self.prime(parts)
            for width in (52, 62, 80):
                view = status.View(width=width, want_cost=True, cost_age=999)
                out = status.render_full(self.root, None, view)
                self.assertIn("cost", out)
                for line in plain(out).splitlines():
                    self.assertLessEqual(len(line), width, repr(line))


class DashScrollTest(unittest.TestCase):
    """the dashboard in a window too short to hold it.

    the frame has to stay inside the window — `paint()` homes the cursor, so
    a body one line too tall scrolls its own top away and every later frame
    paints from the middle of the previous one.
    """

    def setUp(self):
        status.use_color(False)
        self.root = tempfile.mkdtemp(prefix="sdd-dashscroll-test-")
        entries = "".join(f"- 2026-07-01 12:0{i % 10} entry {i}\n"
                          for i in range(1, 21))
        os.makedirs(os.path.join(self.root, "specs", "demo"))
        with open(os.path.join(self.root, "specs", "ACTIVE"), "w") as f:
            f.write("demo")
        with open(os.path.join(self.root, "specs", "demo", "state.md"), "w") as f:
            f.write(STATE.split("## log")[0] + "## log\n" + entries)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def render(self, view):
        return status.render_full(self.root, None, view)

    def test_the_painted_frame_always_fits_the_window(self):
        for height in range(4, 45):
            view = status.View(width=76, height=height, log_limit=0)
            body = self.render(view)
            n = len(status.frame(body, "foot", height, 76).splitlines())
            self.assertLessEqual(n, height, f"{n} rows at height {height}")
            # above the degenerate sizes the pinned header fits on its own, so
            # the frame is whole — no truncation of the run's context
            if height >= 10:
                self.assertLessEqual(len(body.splitlines()) + 1, height)

    def test_unmeasured_height_is_never_clipped(self):
        """--full is a still frame in the terminal's own scrollback."""
        out = self.render(status.View(width=76, log_limit=0))
        self.assertNotIn("j/k scroll", out)
        self.assertIn("entry 20", out)

    def test_marker_only_when_it_does_not_fit(self):
        tall = self.render(status.View(width=76, height=60, log_limit=0))
        self.assertNotIn("j/k scroll", tall)
        short = self.render(status.View(width=76, height=16, log_limit=0))
        self.assertIn("j/k scroll", short)
        self.assertRegex(plain(short), r"1-\d+ of \d+ · ↓ \d+ · j/k scroll")

    def test_header_stays_pinned_at_every_offset(self):
        view = status.View(width=76, height=16, log_limit=0)
        for offset in (0, 5, 10, 10 ** 6):
            view.offset = offset
            out = plain(self.render(view))
            self.assertIn("sdd: demo", out)
            self.assertIn("impl", out)      # the phase ladder

    def test_scrolling_reaches_the_bottom_and_clamps(self):
        view = status.View(width=76, height=16, log_limit=0)
        top = plain(self.render(view))
        self.assertIn("policies for this feature", top)
        self.assertNotIn("entry 20", top)

        view.offset = 10 ** 6               # 'G'
        end = plain(self.render(view))
        self.assertIn("entry 20", end)
        self.assertNotIn("policies for this feature", end)
        clamped = view.offset
        view.offset = 10 ** 6 + 500         # cannot scroll past the end
        self.assertEqual(plain(self.render(view)), end)
        self.assertEqual(view.offset, clamped)

    def test_page_matches_what_is_on_screen(self):
        """space/b move by the visible rows, or a keypress lies."""
        view = status.View(width=76, height=20, log_limit=0)
        out = self.render(view)
        m = re.search(r"(\d+)-(\d+) of (\d+)", plain(out))
        self.assertEqual(view.page, int(m.group(2)) - int(m.group(1)) + 1)

    def test_clipped_frames_keep_the_width(self):
        for width in (52, 62, 80):
            for height in (8, 14, 20, 30):
                view = status.View(width=width, height=height, log_limit=0)
                view.offset = 4
                for line in plain(self.render(view)).splitlines():
                    self.assertLessEqual(len(line), width)

    def test_frame_clamps_a_window_shorter_than_the_header(self):
        body = "\n".join(f"line {i}" for i in range(30))
        for height in (1, 2, 3, 8, 40):
            rows = status.frame(body, "footer", height, 76)
            n = len(rows.splitlines())
            self.assertLessEqual(n, max(2, height))
            self.assertIn("footer", rows.splitlines()[-1])

    def test_frame_without_a_height_keeps_everything(self):
        body = "\n".join(f"line {i}" for i in range(30))
        self.assertEqual(len(status.frame(body, "f", 0, 76).splitlines()), 31)

    def test_log_pane_also_stays_inside_a_tiny_window(self):
        for height in (6, 8, 12):
            view = status.View(width=76, height=height, pane="log")
            body = self.render(view)
            n = len(status.frame(body, "foot", height, 76).splitlines())
            self.assertLessEqual(n, height)


class LogViewTest(unittest.TestCase):
    """expanding and scrolling the log."""

    def setUp(self):
        status.use_color(False)
        self.root = tempfile.mkdtemp(prefix="sdd-logview-test-")
        entries = "".join(f"- 2026-07-01 entry {i}\n" for i in range(1, 31))
        os.makedirs(os.path.join(self.root, "specs", "demo"))
        with open(os.path.join(self.root, "specs", "ACTIVE"), "w") as f:
            f.write("demo")
        with open(os.path.join(self.root, "specs", "demo", "state.md"), "w") as f:
            f.write(STATE.split("## log")[0] + "## log\n" + entries)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def render(self, view):
        return status.render_full(self.root, None, view)

    def test_log_window_math(self):
        lines = list("abcdefghij")
        self.assertEqual(status.log_window(lines, 3, 0), (["h", "i", "j"], 0))
        self.assertEqual(status.log_window(lines, 3, 2), (["f", "g", "h"], 2))
        # an over-large offset clamps to the oldest page, never goes negative
        self.assertEqual(status.log_window(lines, 3, 999),
                         (["a", "b", "c"], 7))
        # everything fits -> no window, no offset
        self.assertEqual(status.log_window(lines, 20, 5), (lines, 0))

    def test_expanded_view_fills_the_pane_and_scrolls(self):
        view = status.View(width=76, pane="log", height=20)
        out = plain(self.render(view))
        self.assertIn("of 30", out)
        self.assertIn("newest", out)
        self.assertIn("entry 30", out)      # newest visible
        self.assertNotIn("entry 1 ", out)   # oldest scrolled off
        page = view.page
        self.assertGreater(page, 3)

        view.offset = 999               # 'g' — the renderer clamps it
        out = plain(self.render(view))
        self.assertIn("entry 1", out)
        self.assertNotIn("entry 30", out)
        self.assertEqual(view.offset, 30 - page)

    def test_expanded_view_shows_more_than_the_dashboard(self):
        dash = plain(self.render(status.View(width=76, log_limit=8)))
        wide = plain(self.render(status.View(width=76, pane="log",
                                            height=30)))
        self.assertLess(dash.count("entry "), wide.count("entry "))

    def test_render_logs_dumps_every_entry_wrapped(self):
        out = plain(status.render_logs(self.root, None, 60))
        self.assertIn("30 entries", out)
        for i in (1, 15, 30):
            self.assertIn(f"entry {i}", out)
        for line in out.splitlines():
            self.assertLessEqual(len(line), 60)
            self.assertNotIn("…", line)   # wrapped, never clipped

    def test_expanded_view_with_an_empty_log(self):
        with open(os.path.join(self.root, "specs", "demo", "state.md")) as f:
            text = f.read()
        with open(os.path.join(self.root, "specs", "demo", "state.md"), "w") as f:
            f.write(text.split("## log")[0] + "## log\n")
        out = plain(self.render(status.View(width=76, pane="log",
                                           height=20)))
        self.assertIn("nothing logged yet", out)


class KeysTest(unittest.TestCase):
    """key decoding and dispatch — no tty needed."""

    def test_decode_plain_and_escape_sequences(self):
        d = status.Keys.decode
        self.assertEqual(d(b"l"), ["l"])
        self.assertEqual(d(b"\033[A"), ["k"])       # up   -> older
        self.assertEqual(d(b"\033[B"), ["j"])       # down -> newer
        self.assertEqual(d(b"\033[5~"), [" "])      # page up
        self.assertEqual(d(b"\033[6~"), ["b"])      # page down
        self.assertEqual(d(b"\033[H"), ["g"])       # home -> oldest
        self.assertEqual(d(b"\033[F"), ["G"])       # end  -> newest
        self.assertEqual(d(b"\033"), [])            # bare esc ignored
        self.assertEqual(d(b""), [])

    def test_decode_keeps_every_key_in_a_burst(self):
        """the bug this guards: a buffered read stranded all but the first."""
        self.assertEqual(status.Keys.decode(b"lq\033[Ak"), ["l", "q", "k", "k"])

    def test_handle_keys(self):
        v = status.View(log_limit=8)
        v.page = 7

        self.assertFalse(status.handle_keys(["l"], v))
        self.assertEqual(v.pane, "log")
        status.handle_keys(["l"], v)         # same key toggles back
        self.assertEqual(v.pane, "dash")
        status.handle_keys(["l"], v)

        status.handle_keys(["k", "k", "k"], v)
        self.assertEqual(v.offset, 3)
        status.handle_keys(["j"], v)
        self.assertEqual(v.offset, 2)
        status.handle_keys([" "], v)
        self.assertEqual(v.offset, 9)
        status.handle_keys(["b"], v)
        self.assertEqual(v.offset, 2)
        status.handle_keys(["G"], v)
        self.assertEqual(v.offset, 0)
        status.handle_keys(["j"], v)            # never scrolls past the newest
        self.assertEqual(v.offset, 0)
        status.handle_keys(["g"], v)
        self.assertGreater(v.offset, 100)  # renderer clamps to the oldest

        status.handle_keys(["+", "+"], v)
        self.assertEqual(v.log_limit, 12)
        status.handle_keys(["-", "-", "-"], v)
        self.assertEqual(v.log_limit, 6)
        status.handle_keys(["c"], v)
        self.assertTrue(v.want_cost)

        self.assertTrue(status.handle_keys(["x", "q"], v))

    def test_dashboard_scrolls_top_down_like_a_document(self):
        """no pane switch needed — j/k scroll the dashboard itself when the
        window is too short for it, and offset 0 is its top."""
        v = status.View()
        self.assertEqual(v.pane, "dash")
        status.handle_keys(["j", "j", "j"], v)
        self.assertEqual(v.offset, 3)
        status.handle_keys(["k"], v)
        self.assertEqual(v.offset, 2)
        status.handle_keys(["g"], v)              # top
        self.assertEqual(v.offset, 0)
        status.handle_keys(["k"], v)              # cannot go above the top
        self.assertEqual(v.offset, 0)
        status.handle_keys(["G"], v)              # bottom — renderer clamps
        self.assertGreater(v.offset, 100)

    def test_log_limit_stays_in_range(self):
        v = status.View(log_limit=1)
        status.handle_keys(["-"] * 5, v)
        self.assertEqual(v.log_limit, 1)
        status.handle_keys(["+"] * 60, v)
        self.assertLessEqual(v.log_limit, 60)

    def test_v_opens_the_doc_pane_and_n_p_cycle(self):
        v = status.View()
        status.handle_keys(["v"], v)
        self.assertEqual(v.pane, "doc")
        status.handle_keys(["n", "n"], v)
        self.assertEqual(v.doc, 2)
        status.handle_keys(["p"], v)
        self.assertEqual(v.doc, 1)
        status.handle_keys(["v"], v)
        self.assertEqual(v.pane, "dash")
        status.handle_keys(["n"], v)          # n only means "next doc" in doc
        self.assertEqual(v.doc, 1)

    def test_switching_pane_resets_the_scroll(self):
        v = status.View()
        status.handle_keys(["l", "k", "k"], v)
        self.assertEqual(v.offset, 2)
        status.handle_keys(["v"], v)          # log -> doc
        self.assertEqual(v.pane, "doc")
        self.assertEqual(v.offset, 0)

    def test_scroll_direction_flips_between_log_and_doc(self):
        """offset 0 is the NEWEST log entry but the TOP of a document, so j/k
        have to swap meaning or one of the two panes scrolls backwards."""
        v = status.View()
        status.handle_keys(["l", "j"], v)     # log: already at the newest
        self.assertEqual(v.offset, 0)
        status.handle_keys(["k"], v)          # log: back into history
        self.assertEqual(v.offset, 1)
        v2 = status.View()
        status.handle_keys(["v", "j", "j"], v2)   # doc: down the file
        self.assertEqual(v2.offset, 2)
        status.handle_keys(["k"], v2)
        self.assertEqual(v2.offset, 1)
        status.handle_keys(["g"], v2)             # doc: g is the top
        self.assertEqual(v2.offset, 0)


class DocPaneTest(unittest.TestCase):
    """the `v` pane: state.md, the stage artifacts, and the subspecs."""

    def setUp(self):
        status.use_color(False)
        self.root = make_project(STATE)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.fdir = os.path.join(self.root, "specs", "demo")
        os.makedirs(os.path.join(self.fdir, "tasks"))
        for name, body in [
                ("spec.md", "# spec\n\n## requirements\n- R1 blink the led\n"),
                ("tasks.md", "| id | title |\n|----|-------|\n| T1 | go |\n"),
                ("research.md", "# research\n" + "a long line " * 30 + "\n")]:
            with open(os.path.join(self.fdir, name), "w") as f:
                f.write(body)
        for tid in ("T1", "T3"):
            with open(os.path.join(self.fdir, "tasks", f"{tid}.md"), "w") as f:
                f.write(f"# subspec {tid}\nverify: make test\n")
        with open(os.path.join(self.root, "specs", "standards-digest.md"),
                  "w") as f:
            f.write("# digest\n- lowercase comments\n")

    def docs(self):
        return [n for n, _ in status.documents(self.root, "demo")]

    def render(self, **kw):
        kw.setdefault("width", 76)
        kw.setdefault("height", 24)
        kw.setdefault("pane", "doc")
        return plain(status.render_full(self.root, None, status.View(**kw)))

    def test_document_list_is_ordered_and_only_real_files(self):
        self.assertEqual(self.docs(), [
            "state.md", "research.md", "spec.md", "tasks.md",
            "tasks/T1.md", "tasks/T3.md", "standards-digest.md"])
        os.remove(os.path.join(self.fdir, "spec.md"))
        self.assertNotIn("spec.md", self.docs())

    def test_each_document_renders_with_the_header_kept(self):
        for i, name in enumerate(self.docs()):
            out = self.render(doc=i)
            self.assertIn(f"view {name}", out)
            self.assertIn("sdd: demo", out)     # never lose the feature/phase
            self.assertIn("impl", out)

    def test_doc_pane_shows_the_raw_state_file(self):
        """the raw fields, not the dashboard's interpretation of them."""
        out = self.render(doc=0)
        self.assertIn("autopilot: gate1=skip", out)
        self.assertIn("1-", out)                  # windowed, it does not fit
        view = status.View(width=76, height=24, pane="doc", doc=0)
        view.offset = 10 ** 6                     # scroll to the end
        end = plain(status.render_full(self.root, None, view))
        self.assertIn("## amendments", end)       # sections past page 1 reachable
        self.assertIn("## log", end)

    def test_doc_pane_scrolls_and_clamps(self):
        view = status.View(width=76, height=16, pane="doc", doc=0)  # state.md
        first = plain(status.render_full(self.root, None, view))
        self.assertIn("1-", first)
        self.assertIn("# sdd state: demo", first)
        view.offset = 10 ** 6
        last = plain(status.render_full(self.root, None, view))
        self.assertNotEqual(first, last)
        self.assertNotIn("# sdd state: demo", last)   # scrolled off the top
        self.assertIn("2026-07-31", last)             # the final log entry
        page = view.page
        self.assertEqual(view.offset, 58 - page)      # exactly the last page

    def test_doc_index_wraps_around(self):
        n = len(self.docs())
        view = status.View(width=76, height=24, pane="doc", doc=n)
        self.assertIn("view state.md", plain(
            status.render_full(self.root, None, view)))
        view.doc = -1
        self.assertIn("view standards-digest.md", plain(
            status.render_full(self.root, None, view)))

    def test_doc_pane_never_overflows_the_width(self):
        for width in (52, 76, 100):
            for i in range(len(self.docs())):
                for line in self.render(width=width, doc=i).splitlines():
                    self.assertLessEqual(len(line), width,
                                         f"{self.docs()[i]}: {line!r}")

    def test_no_artifacts_yet(self):
        bare = make_project(STATE)
        self.addCleanup(shutil.rmtree, bare, ignore_errors=True)
        os.remove(os.path.join(bare, "specs", "demo", "state.md"))
        view = status.View(width=76, height=20, pane="doc")
        out = plain(status.render_full(bare, "demo", view))
        self.assertIn("no state.md", out)

    def test_render_show_defaults_to_state_and_matches_loosely(self):
        out = plain(status.render_show(self.root, None, 76))
        self.assertIn("state.md", out)
        self.assertIn("## metrics", out)
        self.assertIn("spec.md", plain(
            status.render_show(self.root, None, 76, "spec")))
        self.assertIn("subspec T3", plain(
            status.render_show(self.root, None, 76, "T3")))

    def test_render_show_lists_options_on_a_miss(self):
        out = plain(status.render_show(self.root, None, 76, "nope"))
        self.assertIn("no artifact matching", out)
        self.assertIn("state.md", out)

    def test_a_flag_value_is_never_read_as_the_slug(self):
        """`--show spec` used to resolve "spec" as the feature slug."""
        cli = os.path.join(SDD, "bin", "sdd-status")
        for extra in (["--show", "spec"], ["--show", "T3"],
                      ["--logs"], ["--full", "--log", "3"],
                      ["--full", "--width", "70"]):
            p = subprocess.run([sys.executable, cli, *extra, "--no-color",
                                "--no-pager"],
                               cwd=self.root, text=True, capture_output=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("sdd: demo", p.stdout, f"{extra}: {p.stdout!r}")
            self.assertNotIn("no state.md", p.stdout)

    def test_doc_lines_styles_without_changing_content(self):
        text = "# head\n\n<!-- note -->\n| a | b |\n```\ncode\n```\nplain\n"
        rendered = plain("\n".join(status.doc_lines(text, 60)))
        for token in ("# head", "<!-- note -->", "| a | b |", "code", "plain"):
            self.assertIn(token, rendered)


class LogStampTest(unittest.TestCase):
    """sdd-state now stamps HH:MM; both shapes must render."""

    def setUp(self):
        status.use_color(False)

    def test_dated_and_timestamped_entries_both_parse(self):
        rows = status.log_lines(
            ["- 2026-07-31 old style entry",
             "- 2026-07-31 14:32 new style entry",
             "- 2026-07-31 14:32:07 with seconds"], 70)
        self.assertIn("2026-07-31 old style entry", rows[0])
        self.assertIn("2026-07-31 14:32 new style entry", rows[1])
        self.assertIn("2026-07-31 14:32:07 with seconds", rows[2])

    def test_timestamp_is_kept_when_the_message_is_clipped(self):
        long = "- 2026-07-31 14:32 " + "x" * 200
        row = status.log_lines([long], 60)[0]
        self.assertIn("2026-07-31 14:32", row)
        self.assertLessEqual(len(row), 60)
        self.assertTrue(row.rstrip().endswith("…"))


class ContextGaugeTest(unittest.TestCase):
    """the gauge tells the user whether to take a clear point, so the advice
    it prints — not just the number — is the contract."""

    def setUp(self):
        status.use_color(False)
        self.root = tempfile.mkdtemp(prefix="sdd-ctx-test-")
        os.makedirs(os.path.join(self.root, "specs", "demo"))
        with open(os.path.join(self.root, "specs", "ACTIVE"), "w") as f:
            f.write("demo")
        with open(os.path.join(self.root, "specs", "demo", "state.md"), "w") as f:
            f.write(STATE)
        self._real = status.context_data

    def tearDown(self):
        status.context_data = self._real
        shutil.rmtree(self.root, ignore_errors=True)

    def fake(self, pct, used=100_000, window=1_000_000, requests=40, resets=0):
        status.context_data = lambda root, age=0: {
            "session": "s", "used": used, "peak": used, "window": window,
            "pct": pct, "requests": requests, "resets": resets,
            "over": pct >= 75}

    def test_meter_fills_proportionally(self):
        self.assertEqual(status.meter(0, width=10).count("█"), 0)
        self.assertEqual(status.meter(50, width=10).count("█"), 5)
        self.assertEqual(status.meter(100, width=10).count("█"), 10)

    def test_meter_never_overflows_its_width(self):
        for pct in (-5, 0, 50, 100, 140):
            bar = ANSI.sub("", status.meter(pct, width=12))
            self.assertEqual(len(bar), 12, f"pct={pct}")

    def test_advice_escalates_with_occupancy(self):
        for pct, want in ((10, "healthy"), (60, "next stage boundary"),
                          (85, "clear point advised")):
            self.fake(pct)
            _, note = status.context_segs(self.root)
            self.assertIn(want, note, f"pct={pct}")

    def test_panel_renders_and_respects_the_width(self):
        self.fake(85, used=850_000)
        for width in (52, 62, 80, 120):
            out = status.render_full(
                self.root, None, status.View(width=width, want_ctx=True))
            self.assertIn("context", out)
            self.assertIn("clear point advised", out)
            for line in out.splitlines():
                self.assertLessEqual(len(ANSI.sub("", line).rstrip()), width)

    def test_resets_shown_only_when_a_clear_happened(self):
        self.fake(20, resets=0)
        segs, _ = status.context_segs(self.root)
        self.assertNotIn("resets", " ".join(segs))
        self.fake(20, resets=2)
        segs, _ = status.context_segs(self.root)
        self.assertIn("resets", " ".join(segs))

    def test_missing_transcripts_render_no_panel(self):
        status.context_data = lambda root, age=0: None
        segs, _ = status.context_segs(self.root)
        self.assertEqual(segs, [])
        out = status.render_full(self.root, None,
                                 status.View(width=80, want_ctx=True))
        self.assertNotIn("clear point", out)


if __name__ == "__main__":
    unittest.main()
