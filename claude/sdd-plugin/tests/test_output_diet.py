"""tests for the output diet — the layer that keeps waste out of the window.

the diet hides tool output, so the tests that matter most are the ones that
prove it hides only what is genuinely already there: an exact-match-only dedupe,
a full serve on the second consecutive ask, no shrink outside the configured
command patterns, and no reduction at all below the token threshold. everything
unexpected must fail OPEN — passing a result through untouched is always safe,
so any doubt resolves that way.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from helpers import SDD, load_module

diet = load_module("output_diet", os.path.join("hooks", "output-diet.py"))

CFG = dict(diet.FALLBACK)


def big(n=400, line="a routine line of build output that carries no signal"):
    return "\n".join(f"{i}: {line}" for i in range(n))


def bash(command, response, session="sess-1", cwd="/repo"):
    return {"tool_name": "Bash", "session_id": session, "cwd": cwd,
            "tool_input": {"command": command},
            "tool_response": {"stdout": response}}


def read(path, response, session="sess-1", cwd="/repo"):
    # the real Read shape, from a transcript: the body is one level down
    return {"tool_name": "Read", "session_id": session, "cwd": cwd,
            "tool_input": {"file_path": path},
            "tool_response": {"type": "text",
                              "file": {"filePath": path, "content": response,
                                       "numLines": len(response.splitlines())}}}


class TestResponseShapes(unittest.TestCase):
    """the text has to be found before anything can be done to it. these are the
    shapes real transcripts actually carry, not invented ones."""

    def test_bare_string(self):
        self.assertEqual(diet.text_of("hello"), ("hello", None))

    def test_bash_stdout(self):
        self.assertEqual(
            diet.text_of({"stdout": "out", "stderr": "", "interrupted": False}),
            ("out", "stdout"))

    def test_read_content_is_nested_under_file(self):
        self.assertEqual(
            diet.text_of({"type": "text", "file": {"content": "body"}}),
            ("body", "file.content"))

    def test_an_unknown_shape_is_left_alone(self):
        self.assertEqual(diet.text_of({"weird": 12}), (None, None))
        self.assertEqual(diet.text_of(None), (None, None))

    def test_an_empty_result_is_left_alone(self):
        self.assertEqual(diet.text_of({"stdout": ""}), (None, None))


class TestKey(unittest.TestCase):
    """identity is the whole input, not just the command word."""

    def test_same_call_same_key(self):
        self.assertEqual(diet.key_of("Read", {"file_path": "a.c"}, "/repo"),
                         diet.key_of("Read", {"file_path": "a.c"}, "/repo"))

    def test_a_different_argument_is_a_different_call(self):
        self.assertNotEqual(diet.key_of("Read", {"file_path": "a.c"}, "/repo"),
                            diet.key_of("Read", {"file_path": "b.c"}, "/repo"))

    def test_a_different_directory_is_a_different_call(self):
        self.assertNotEqual(diet.key_of("Bash", {"command": "ls"}, "/repo"),
                            diet.key_of("Bash", {"command": "ls"}, "/other"))

    def test_key_survives_an_unserializable_input(self):
        self.assertTrue(diet.key_of("Bash", {"x": object()}, "/repo"))


class TestDedupe(unittest.TestCase):
    """exact match only, and always an escape hatch."""

    def setUp(self):
        self.ledger = {}
        self.key = "k1"

    def again(self, text):
        self.ledger["step"] = self.ledger.get("step", 0) + 1
        return diet.dedupe("Read", text, self.key, self.ledger, CFG)

    def test_first_sight_passes_through(self):
        self.assertIsNone(self.again(big()))

    def test_an_identical_second_read_becomes_a_pointer(self):
        self.again(big())
        out = self.again(big())
        self.assertIn("identical to the earlier Read result", out)
        self.assertIn("step 1", out)          # names where the content is

    def test_changed_content_is_never_hidden(self):
        self.again(big())
        self.assertIsNone(self.again(big() + "\nnew line after an edit"))

    def test_a_change_then_a_repeat_dedupes_against_the_new_content(self):
        self.again(big())
        edited = big() + "\nedited"
        self.again(edited)
        self.assertIn("identical", self.again(edited))

    def test_the_second_consecutive_ask_serves_the_real_thing(self):
        # the recovery path when the window was cleared and the pointer names
        # content that is no longer there
        self.again(big())
        self.assertIsNotNone(self.again(big()))
        self.assertIsNone(self.again(big()))

    def test_and_then_dedupes_again_afterwards(self):
        for _ in range(3):
            self.again(big())
        self.assertIn("identical", self.again(big()))


class TestShrink(unittest.TestCase):
    """opt-in by command pattern, and it keeps the lines that matter."""

    def test_a_noisy_test_run_is_trimmed(self):
        out = diet.shrink("pytest -v tests/", big(400), CFG)
        self.assertIsNotNone(out)
        self.assertLess(len(out), len(big(400)))
        self.assertIn("lines elided", out)

    def test_an_unlisted_command_is_untouched(self):
        self.assertIsNone(diet.shrink("./my_custom_tool --dump", big(400), CFG))

    def test_a_short_output_is_untouched(self):
        self.assertIsNone(diet.shrink("pytest", big(20), CFG))

    def test_head_and_tail_survive(self):
        out = diet.shrink("make -j8", big(400), CFG)
        self.assertIn("0: a routine line", out)      # first line
        self.assertIn("399: a routine line", out)    # last line

    def test_signal_lines_are_lifted_out_of_the_elided_middle(self):
        lines = big(400).splitlines()
        lines[200] = "200: ERROR: watchdog reset while flushing nvram"
        out = diet.shrink("pytest", "\n".join(lines), CFG)
        self.assertIn("watchdog reset while flushing nvram", out)
        self.assertIn("signal lines from the elided middle", out)

    def test_a_debug_dump_read_is_a_shrink_target(self):
        # the triage skills pull whole *_FAILED_debug_dump.log files in
        out = diet.shrink("/logs/run_FAILED_debug_dump.log", big(500), CFG)
        self.assertIsNotNone(out)

    def test_the_signal_list_is_capped(self):
        lines = [f"{i}: FAIL case {i}" for i in range(600)]
        out = diet.shrink("ctest", "\n".join(lines), dict(CFG, max_signal_lines=10))
        self.assertIn("more signal lines not shown", out)


class TestThresholds(unittest.TestCase):
    """AgentDiet's rule: never spend more than the reduction returns."""

    def test_below_the_threshold_nothing_happens(self):
        ledger = {}
        small = "tiny output"
        diet.reduce_text("Read", "a.c", small, "k", ledger, CFG)
        # the caller gates on est() first; prove the gate is where it claims
        self.assertLess(diet.est(small), CFG["min_tokens"])

    def test_a_shrink_that_saves_too_little_is_dropped(self):
        # just over the elide floor, so the trim is real but tiny
        text = big(120)
        ledger = {}
        new, which = diet.reduce_text("Bash", "pytest", text, "k", ledger, CFG)
        self.assertIsNone(new)

    def test_a_shrink_that_saves_a_lot_is_kept(self):
        new, which = diet.reduce_text("Bash", "pytest", big(2000), "k", {}, CFG)
        self.assertEqual(which, "shrink")
        self.assertGreater(diet.est(big(2000)) - diet.est(new), CFG["min_tokens"])

    def test_dedupe_wins_over_shrink(self):
        ledger = {}
        diet.reduce_text("Bash", "pytest", big(2000), "k", ledger, CFG)
        new, which = diet.reduce_text("Bash", "pytest", big(2000), "k", ledger, CFG)
        self.assertEqual(which, "dedupe")

    def test_each_pass_can_be_turned_off(self):
        ledger = {}
        off = dict(CFG, dedupe=False)
        diet.reduce_text("Bash", "cat x", big(2000), "k", ledger, off)
        self.assertIsNone(
            diet.reduce_text("Bash", "cat x", big(2000), "k", ledger, off)[0])
        self.assertIsNone(
            diet.reduce_text("Bash", "pytest", big(2000), "k", {},
                             dict(CFG, shrink=False))[0])


class TestPost(unittest.TestCase):
    """the hook leg: ledger per session, config resolved once, valid output."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = os.environ.get("CLAUDE_CONFIG_DIR")
        os.environ["CLAUDE_CONFIG_DIR"] = self.tmp.name
        self.real = diet.diet_config
        diet.diet_config = lambda cwd, ledger: dict(CFG)

    def tearDown(self):
        diet.diet_config = self.real
        if self.saved is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = self.saved
        self.tmp.cleanup()

    def test_a_repeat_read_is_replaced(self):
        self.assertEqual(diet.post(read("a.c", big())), (0, None))
        code, out = diet.post(read("a.c", big()))
        self.assertEqual(code, 0)
        hso = out["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "PostToolUse")
        self.assertIn("identical", hso["updatedToolOutput"])
        self.assertIn("dedupe", out["systemMessage"])

    def test_a_small_result_never_touches_the_ledger(self):
        self.assertEqual(diet.post(read("a.c", "short")), (0, None))
        self.assertEqual(diet.read_ledger("sess-1"), {})

    def test_sessions_do_not_share_a_ledger(self):
        diet.post(read("a.c", big()))
        self.assertEqual(diet.post(read("a.c", big(), session="sess-2")),
                         (0, None))

    def test_a_missing_session_is_ignored(self):
        self.assertEqual(diet.post(read("a.c", big(), session="")), (0, None))

    def test_an_edit_result_is_never_rewritten(self):
        # an Edit result carries `content` too, and hiding one would hide the
        # model's own diff back to it
        edit = {"tool_name": "Edit", "session_id": "sess-1", "cwd": "/repo",
                "tool_input": {"file_path": "a.c"},
                "tool_response": {"filePath": "a.c", "content": big()}}
        self.assertEqual(diet.post(edit), (0, None))
        self.assertEqual(diet.post(edit), (0, None))

    def test_disabled_does_nothing(self):
        diet.diet_config = lambda cwd, ledger: dict(CFG, enabled=False)
        diet.post(read("a.c", big()))
        self.assertEqual(diet.post(read("a.c", big())), (0, None))

    def test_the_ledger_stays_bounded(self):
        diet.diet_config = lambda cwd, ledger: dict(CFG, ledger_entries=5)
        for i in range(20):
            diet.post(read(f"file{i}.c", big()))
        self.assertLessEqual(len(diet.read_ledger("sess-1")["seen"]), 5)

    def test_config_is_resolved_once_per_session(self):
        diet.diet_config = self.real
        calls = []
        real_run = subprocess.run

        def counted(*a, **kw):
            calls.append(a)
            return real_run(*a, **kw)

        diet.subprocess.run = counted
        try:
            for _ in range(4):
                diet.post(bash("pytest -q", big(2000)))
        finally:
            diet.subprocess.run = real_run
        self.assertEqual(len(calls), 1)


class TestFailOpen(unittest.TestCase):
    """end-to-end through the real process, on the paths that must never bite."""

    def call(self, payload, env=None):
        e = dict(os.environ, **(env or {}))
        p = subprocess.run(
            [sys.executable, os.path.join(SDD, "hooks", "output-diet.py")],
            input=payload, capture_output=True, text=True, env=e)
        return p.returncode, p.stdout, p.stderr

    def test_malformed_json_exits_clean(self):
        self.assertEqual(self.call("not json")[0], 0)

    def test_missing_fields_exit_clean(self):
        self.assertEqual(self.call("{}")[0], 0)

    def test_an_unwritable_config_dir_does_not_break_the_result(self):
        code, out, err = self.call(json.dumps(read("a.c", big())),
                                   {"CLAUDE_CONFIG_DIR": "/proc/nope"})
        self.assertEqual(code, 0)

    def test_a_real_call_produces_valid_hook_json(self):
        with tempfile.TemporaryDirectory() as d:
            payload = json.dumps(bash("pytest -q", big(2000)))
            self.call(payload, {"CLAUDE_CONFIG_DIR": d})          # first sight
            code, out, err = self.call(payload, {"CLAUDE_CONFIG_DIR": d})
            self.assertEqual(code, 0)
            if out.strip():
                json.loads(out)


if __name__ == "__main__":
    unittest.main()
