"""tests for the context guard — the layer that makes the stop real.

the guard replaces an instruction the orchestrator was free to skip (and did:
a measured run reached 44% with no occupancy figure in its log), so what
matters here is that it fires exactly at stage boundaries, that its verdict
matches the config, that the stop it records blocks the next spawn, and that it
lets go the moment the window is actually cleared. Everything unexpected must
fail OPEN — a guard that can brick a session is worse than the drift.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from helpers import SDD, load_module

guard = load_module("context_guard", os.path.join("hooks", "context-guard.py"))

CFG = {"clear_point_at_pct": 20, "hard_stop_at_pct": 35,
       "stop_at_every_stage": False, "stop_floor_pct": 8,
       "announce_clear_points": True}


def ctx(pct, used=None):
    return {"pct": pct, "used": used if used is not None else int(pct * 10_000),
            "window": 1_000_000, "requests": 100, "session": "s", "peak": 0}


def bash(command, session="sess-1", cwd="/tmp"):
    return {"tool_name": "Bash", "session_id": session, "cwd": cwd,
            "tool_input": {"command": command}}


class TestBoundaryDetection(unittest.TestCase):
    """a boundary is a phase WRITE — reads and unrelated commands are not."""

    def hits(self, command):
        m = guard.PHASE_SET.search(command)
        return m.group(1) if m else None

    def test_set_phase(self):
        self.assertEqual(self.hits("sdd-state set phase implement"), "implement")

    def test_event_set_phase(self):
        self.assertEqual(
            self.hits('sdd-state event --set phase=review --log "done"'), "review")

    def test_a_read_is_not_a_boundary(self):
        self.assertIsNone(self.hits("sdd-state get phase"))

    def test_another_field_is_not_a_boundary(self):
        self.assertIsNone(self.hits("sdd-state set plan_approved yes"))

    def test_unrelated_command_is_not_a_boundary(self):
        self.assertIsNone(self.hits("git log --oneline -5 | grep phase"))

    def test_a_later_pipe_stage_cannot_forge_one(self):
        # the phase word has to belong to the sdd-state call itself
        self.assertIsNone(self.hits("echo hi | grep 'set phase implement'"))


class TestVerdict(unittest.TestCase):
    def test_below_the_clear_point_is_a_note(self):
        kind, msg = guard.verdict(ctx(8), CFG, "spec")
        self.assertEqual(kind, "note")
        self.assertIn("healthy", msg)

    def test_at_the_clear_point_it_recommends(self):
        kind, msg = guard.verdict(ctx(20), CFG, "spec")
        self.assertEqual(kind, "recommend")
        self.assertIn("ADVISED", msg)
        self.assertIn("Do not stop", msg)

    def test_past_the_hard_stop_it_stops(self):
        kind, msg = guard.verdict(ctx(44), CFG, "test")
        self.assertEqual(kind, "stop")
        self.assertIn("STOP HERE", msg)
        self.assertIn("phase: test", msg)     # the resume point, named

    def test_hard_stop_zero_disables_the_threshold_stop(self):
        cfg = dict(CFG, hard_stop_at_pct=0)
        self.assertEqual(guard.verdict(ctx(90), cfg, "test")[0], "recommend")

    def test_every_stage_stops_well_below_the_threshold(self):
        cfg = dict(CFG, stop_at_every_stage=True)
        kind, msg = guard.verdict(ctx(12), cfg, "plan")
        self.assertEqual(kind, "stop")
        self.assertIn("stop_at_every_stage", msg)

    def test_every_stage_respects_the_floor(self):
        # an almost-empty window costs more to re-establish than it saves —
        # the first boundary of a run, and all of /sdd:quick, live here
        cfg = dict(CFG, stop_at_every_stage=True)
        self.assertEqual(guard.verdict(ctx(3), cfg, "research")[0], "note")
        self.assertEqual(guard.verdict(ctx(8), cfg, "research")[0], "stop")

    def test_the_terminal_phase_never_stops(self):
        cfg = dict(CFG, stop_at_every_stage=True)
        kind, msg = guard.verdict(ctx(80), cfg, "done")
        self.assertEqual(kind, "note")
        self.assertIn("nothing follows", msg)


class TestPost(unittest.TestCase):
    """the PostToolUse leg: measure, feed back, record."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = os.environ.get("CLAUDE_CONFIG_DIR")
        os.environ["CLAUDE_CONFIG_DIR"] = self.tmp.name
        self.real = (guard.occupancy, guard.context_config)
        guard.context_config = lambda cwd: dict(CFG)

    def tearDown(self):
        guard.occupancy, guard.context_config = self.real
        if self.saved is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = self.saved
        self.tmp.cleanup()

    def at(self, pct, **cfg):
        guard.occupancy = lambda session, cwd: ctx(pct)
        if cfg:
            guard.context_config = lambda cwd: dict(CFG, **cfg)
        return guard.post(bash("sdd-state set phase implement"))

    def test_non_boundary_costs_nothing(self):
        guard.occupancy = lambda *a: self.fail("should not measure")
        self.assertEqual(guard.post(bash("ls -la")), (0, None))

    def test_non_bash_tool_is_ignored(self):
        guard.occupancy = lambda *a: self.fail("should not measure")
        self.assertEqual(guard.post({"tool_name": "Edit"}), (0, None))

    def test_boundary_feeds_the_figure_back(self):
        code, out = self.at(44)
        self.assertEqual(code, 0)
        ac = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("44%", ac)
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PostToolUse")

    def test_a_stop_is_recorded_for_the_pre_leg(self):
        self.at(44)
        mark = guard.read_marker("sess-1")
        self.assertEqual((mark["kind"], mark["phase"], mark["limit"]),
                         ("stop", "implement", 35))

    def test_a_healthy_boundary_records_nothing(self):
        self.at(8)
        self.assertIsNone(guard.read_marker("sess-1"))

    def test_a_healthy_boundary_lifts_a_stale_stop(self):
        # the window was cleared and the run resumed: the next boundary is the
        # place that removes the block, not a manual step
        guard.write_marker("sess-1", {"kind": "stop", "used": 900_000, "limit": 35})
        self.at(4)
        self.assertIsNone(guard.read_marker("sess-1"))

    def test_silent_when_announcements_are_off_and_healthy(self):
        self.assertEqual(self.at(8, announce_clear_points=False), (0, None))

    def test_a_stop_speaks_even_with_announcements_off(self):
        code, out = self.at(44, announce_clear_points=False)
        self.assertIn("STOP HERE", out["hookSpecificOutput"]["additionalContext"])

    def test_unmeasurable_says_nothing(self):
        guard.occupancy = lambda session, cwd: None
        self.assertEqual(guard.post(bash("sdd-state set phase spec")), (0, None))


class TestPre(unittest.TestCase):
    """the PreToolUse leg: block spawns while the stop stands, and only then."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = os.environ.get("CLAUDE_CONFIG_DIR")
        os.environ["CLAUDE_CONFIG_DIR"] = self.tmp.name
        self.real = guard.occupancy

    def tearDown(self):
        guard.occupancy = self.real
        if self.saved is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = self.saved
        self.tmp.cleanup()

    def spawn(self, session="sess-1"):
        return {"tool_name": "Task", "session_id": session, "cwd": "/tmp",
                "tool_input": {}}

    def test_no_marker_no_measurement(self):
        guard.occupancy = lambda *a: self.fail("should not measure")
        self.assertEqual(guard.pre(self.spawn()), (0, None))

    def test_blocks_while_the_window_is_still_full(self):
        guard.write_marker("sess-1", {"kind": "stop", "used": 440_000,
                                      "pct": 44, "phase": "test", "limit": 35})
        guard.occupancy = lambda *a: ctx(44, 445_000)
        code, message = guard.pre(self.spawn())
        self.assertEqual(code, 2)
        self.assertIn("no new agent or workflow may start", message)
        self.assertIn("phase test", message)

    def test_a_clear_lifts_it_even_though_the_session_id_is_unchanged(self):
        # /clear starts a new context lifetime inside the SAME session id, so
        # the drop in occupancy is the only evidence available
        guard.write_marker("sess-1", {"kind": "stop", "used": 440_000,
                                      "pct": 44, "phase": "test", "limit": 35})
        guard.occupancy = lambda *a: ctx(3, 30_000)
        self.assertEqual(guard.pre(self.spawn()), (0, None))
        self.assertIsNone(guard.read_marker("sess-1"))

    def test_every_stage_stop_needs_a_clear_not_a_low_number(self):
        # occupancy under the threshold must NOT lift a stop that was never
        # about a threshold — only a fresh window does
        guard.write_marker("sess-1", {"kind": "stop", "used": 60_000, "pct": 6,
                                      "phase": "spec", "limit": 35,
                                      "every_stage": True})
        guard.occupancy = lambda *a: ctx(6, 61_000)
        self.assertEqual(guard.pre(self.spawn())[0], 2)

    def test_unmeasurable_keeps_a_recorded_stop(self):
        guard.write_marker("sess-1", {"kind": "stop", "used": 440_000,
                                      "pct": 44, "phase": "test", "limit": 35})
        guard.occupancy = lambda *a: None
        self.assertEqual(guard.pre(self.spawn())[0], 2)

    def test_another_session_is_unaffected(self):
        guard.write_marker("sess-1", {"kind": "stop", "used": 440_000,
                                      "limit": 35})
        guard.occupancy = lambda *a: self.fail("should not measure")
        self.assertEqual(guard.pre(self.spawn("sess-2")), (0, None))


class TestFailOpen(unittest.TestCase):
    """end-to-end through the real process, on the paths that must never bite."""

    def call(self, mode, payload, env=None):
        e = dict(os.environ, **(env or {}))
        p = subprocess.run(
            [sys.executable, os.path.join(SDD, "hooks", "context-guard.py"), mode],
            input=payload, capture_output=True, text=True, env=e)
        return p.returncode, p.stdout, p.stderr

    def test_malformed_json_exits_clean(self):
        self.assertEqual(self.call("--post", "not json")[0], 0)

    def test_missing_fields_exit_clean(self):
        self.assertEqual(self.call("--post", "{}")[0], 0)
        self.assertEqual(self.call("--pre", "{}")[0], 0)

    def test_unknown_config_dir_does_not_block_a_spawn(self):
        with tempfile.TemporaryDirectory() as d:
            code, out, err = self.call(
                "--pre", json.dumps({"tool_name": "Task", "session_id": "x"}),
                {"CLAUDE_CONFIG_DIR": d})
            self.assertEqual((code, err), (0, ""))

    def test_a_real_boundary_call_produces_valid_hook_json(self):
        # no transcript for this session id -> unmeasurable -> silent, and
        # whatever it prints must be parseable hook output
        with tempfile.TemporaryDirectory() as d:
            code, out, err = self.call("--post", json.dumps(bash(
                "sdd-state set phase spec", session="no-such-session")),
                {"CLAUDE_CONFIG_DIR": d})
            self.assertEqual(code, 0)
            if out.strip():
                json.loads(out)


if __name__ == "__main__":
    unittest.main()
