"""tests for the sdd state writer — edits must be surgical and survive the
same formatting drift statelib tolerates when reading."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from helpers import SDD, load_module

st = load_module("statelib", "bin/statelib.py")
STATE_CLI = os.path.join(SDD, "bin", "sdd-state")

STATE = """# sdd state: demo

created: 2026-07-10
jira: none
phase: research  <!-- research | spec | plan -->
plan_approved: no    <!-- gate 1 -->
base_ref:            <!-- set at implement -->

## tasks
| id | title | complexity | status | depends_on | parallel_ok |
|----|-------|------------|--------|------------|-------------|
| T1 | add counter | simple | pending | — | no |
| T2 | wire it | standard | **pending** | T1 | no |

## metrics
verify_retries: 0
tasks_blocked: 2

## amendments

## log
- 2026-07-10 feature initialized
"""


def run_cli(args, root, expect=0):
    p = subprocess.run([sys.executable, STATE_CLI, "--root", root, *args],
                       text=True, capture_output=True)
    if p.returncode != expect:
        raise AssertionError(
            f"exit {p.returncode} (expected {expect}) for {args}\n"
            f"stdout: {p.stdout}\nstderr: {p.stderr}")
    return p


class StateCliTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="sdd-state-test-")
        self.write_project(self.root, "demo", STATE)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write_project(self, root, slug, state_text, active=None):
        os.makedirs(os.path.join(root, "specs", slug), exist_ok=True)
        with open(os.path.join(root, "specs", "ACTIVE"), "w") as f:
            f.write(active or slug)
        with open(os.path.join(root, "specs", slug, "state.md"), "w") as f:
            f.write(state_text)

    def text(self, root=None, slug="demo"):
        with open(os.path.join(root or self.root, "specs", slug,
                               "state.md")) as f:
            return f.read()

    def test_set_keeps_trailing_comment(self):
        run_cli(["set", "phase", "implement"], self.root)
        text = self.text()
        self.assertEqual(st.field(text, "phase"), "implement")
        self.assertIn("implement  <!-- research | spec | plan -->", text)

    def test_set_empty_valued_key(self):
        run_cli(["set", "base_ref", "abc123"], self.root)
        self.assertEqual(st.field(self.text(), "base_ref"), "abc123")

    def test_set_inserts_missing_key_in_header(self):
        run_cli(["set", "hw_testbed", "fw-comet02"], self.root)
        text = self.text()
        self.assertEqual(st.field(text, "hw_testbed"), "fw-comet02")
        self.assertLess(text.index("hw_testbed"), text.index("## tasks"))

    def test_set_refuses_counters(self):
        run_cli(["set", "verify_retries", "5"], self.root, expect=1)

    def test_bump(self):
        run_cli(["bump", "verify_retries"], self.root)
        run_cli(["bump", "verify_retries", "3"], self.root)
        self.assertEqual(st.metrics(self.text())["verify_retries"], 4)
        self.assertEqual(st.metrics(self.text())["tasks_blocked"], 2)

    def test_bump_unknown_counter_refused(self):
        p = run_cli(["bump", "no_such_counter"], self.root, expect=1)
        self.assertIn("verify_retries", p.stderr)

    def test_task_status(self):
        run_cli(["task", "t2", "in_progress"], self.root)  # case-insensitive
        rows = {r["id"]: r["status"] for r in st.task_rows(self.text())}
        self.assertEqual(rows["T2"], "in_progress")
        self.assertEqual(rows["T1"], "pending")
        run_cli(["task", "T9", "done"], self.root, expect=1)

    def test_task_drifted_columns(self):
        drifted = STATE.replace(
            "| id | title | complexity | status | depends_on | parallel_ok |",
            "| Status | Task | Title | Complexity | depends_on | parallel_ok |"
        ).replace(
            "| T1 | add counter | simple | pending | — | no |",
            "| pending | T1 | add counter | simple | — | no |"
        ).replace(
            "| T2 | wire it | standard | **pending** | T1 | no |",
            "| pending | T2 | wire it | standard | T1 | no |")
        self.write_project(self.root, "demo", drifted)
        run_cli(["task", "T1", "done"], self.root)
        rows = {r["id"]: r["status"] for r in st.task_rows(self.text())}
        self.assertEqual(rows["T1"], "done")

    def test_log_appends_dated_line(self):
        run_cli(["log", "gate 1 approved"], self.root)
        log_lines = st.sections(self.text())["log"]
        last = [l for l in log_lines if l.strip()][-1]
        self.assertTrue(last.startswith("- 20"))
        self.assertTrue(last.endswith("gate 1 approved"))
        # amendments section must be untouched
        self.assertIn("## amendments\n", self.text())

    def test_log_lands_inside_section_not_after(self):
        state = STATE + "\n## waived findings\n"
        self.write_project(self.root, "demo", state)
        run_cli(["log", "before waived"], self.root)
        text = self.text()
        self.assertLess(text.index("before waived"),
                        text.index("## waived findings"))

    def test_event_applies_every_edit_in_one_call(self):
        p = run_cli(["event",
                     "--set", "phase=implement",
                     "--task", "T2=done",
                     "--bump", "verify_retries",
                     "--log", "implement: T2 verify PASS"], self.root)
        text = self.text()
        self.assertEqual(st.field(text, "phase"), "implement")
        self.assertEqual(
            {r["id"]: r["status"] for r in st.task_rows(text)}["T2"], "done")
        self.assertEqual(st.metrics(text)["verify_retries"], 1)
        self.assertTrue([l for l in st.sections(text)["log"]
                         if l.endswith("implement: T2 verify PASS")])
        # every edit reports, so a batched call is as auditable as N calls
        for want in ("phase: implement", "T2: done", "verify_retries: 1"):
            self.assertIn(want, p.stdout)

    def test_event_repeats_a_flag(self):
        run_cli(["event", "--bump", "verify_retries=2", "--bump", "tasks_blocked",
                 "--log", "one", "--log", "two"], self.root)
        m = st.metrics(self.text())
        self.assertEqual((m["verify_retries"], m["tasks_blocked"]), (2, 3))
        logged = [l for l in st.sections(self.text())["log"] if l.strip()]
        self.assertTrue(logged[-2].endswith("one"))
        self.assertTrue(logged[-1].endswith("two"))

    def test_event_log_value_may_contain_equals(self):
        run_cli(["event", "--log", "test: EXPECT=3 got=4"], self.root)
        self.assertTrue([l for l in st.sections(self.text())["log"]
                         if l.endswith("test: EXPECT=3 got=4")])

    def test_event_applies_in_fixed_order_not_argument_order(self):
        # log last, so its line describes state as it now reads
        run_cli(["event", "--log", "phase flip", "--set", "phase=review"],
                self.root)
        text = self.text()
        self.assertEqual(st.field(text, "phase"), "review")

    def test_event_rejects_bad_input_without_writing(self):
        before = self.text()
        run_cli(["event"], self.root, expect=1)                       # no ops
        run_cli(["event", "--nope", "x"], self.root, expect=1)        # bad flag
        run_cli(["event", "--set", "phase"], self.root, expect=1)     # no `=`
        run_cli(["event", "--log"], self.root, expect=1)              # no value
        self.assertEqual(self.text(), before)

    def test_event_is_atomic_when_a_later_edit_fails(self):
        """one write at the end, so a bad counter cannot half-apply the batch."""
        before = self.text()
        run_cli(["event", "--set", "phase=implement",
                 "--bump", "no_such_counter"], self.root, expect=1)
        self.assertEqual(self.text(), before)

    def test_get(self):
        p = run_cli(["get", "phase"], self.root)
        self.assertEqual(p.stdout.strip(), "research")
        p = run_cli(["get", "tasks_blocked"], self.root)
        self.assertEqual(p.stdout.strip(), "2")
        run_cli(["get", "nonexistent"], self.root, expect=1)

    def test_worktree_pointer_followed(self):
        outer = tempfile.mkdtemp(prefix="sdd-state-outer-")
        try:
            wt = os.path.join(outer, "wt")
            self.write_project(wt, "demo", STATE)
            os.makedirs(os.path.join(outer, "specs"), exist_ok=True)
            with open(os.path.join(outer, "specs", "ACTIVE"), "w") as f:
                f.write("worktree: wt")
            run_cli(["set", "phase", "spec"], outer)
            self.assertEqual(st.field(self.text(root=wt), "phase"), "spec")
        finally:
            shutil.rmtree(outer, ignore_errors=True)

    def test_no_active_feature(self):
        empty = tempfile.mkdtemp(prefix="sdd-state-empty-")
        try:
            run_cli(["get", "phase"], empty, expect=1)
        finally:
            shutil.rmtree(empty, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
