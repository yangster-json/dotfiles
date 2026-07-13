"""tests for the quality aggregator's collection logic."""
import os
import tempfile
import unittest
from unittest import mock

from helpers import load_module

quality = load_module("quality", "bin/sdd-quality")

STATE_A = """# sdd state: feat-a
phase: done
## tasks
| id | title | complexity | status | depends_on | parallel_ok |
|----|-------|------------|--------|------------|-------------|
| T1 | one | simple | done | — | no |
| T2 | two | standard | done | T1 | no |
## metrics
verify_retries: 1
findings_confirmed: 2
findings_rejected: 1
findings_waived: 1
"""

STATE_B = """# sdd state: feat-b
phase: implement
## tasks
| id | title | complexity | status | depends_on | parallel_ok |
|----|-------|------------|--------|------------|-------------|
| T1 | one | standard | blocked | — | no |
## metrics
verify_retries: 2
tasks_blocked: 1
file_list_fixes: 2
merge_conflicts: 1
"""


class TestCollect(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self._state("specs/feat-a/state.md", STATE_A)
        self._state("specs/archive/feat-b/state.md", STATE_B)

    def tearDown(self):
        self.tmp.cleanup()

    def _state(self, rel, content):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

    def test_collects_active_and_archived(self):
        rows = quality.collect(self.root)
        self.assertEqual({r["slug"] for r in rows}, {"feat-a", "feat-b"})

    def test_task_and_metric_extraction(self):
        rows = {r["slug"]: r for r in quality.collect(self.root)}
        a, b = rows["feat-a"], rows["feat-b"]
        self.assertEqual((a["tasks"], a["done"]), (2, 2))
        self.assertEqual(a["findings_confirmed"], 2)
        self.assertEqual(b["blocked_now"], 1)
        self.assertEqual(b["merge_conflicts"], 1)

    def test_totals(self):
        t = quality.totals(quality.collect(self.root))
        self.assertEqual(t["verify_retries"], 3)
        self.assertEqual(t["tasks"], 3)
        self.assertEqual(t["findings_waived"], 1)
        self.assertEqual(t["file_list_fixes"], 2)

    def test_render_smoke(self):
        out = quality.render(self.root)
        self.assertIn("feat-a", out)
        self.assertIn("feat-b", out)

    def test_empty_project(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "specs"))
            self.assertEqual(quality.collect(d), [])

    def test_learnings_counted_from_keyed_claude_config_dir(self):
        with tempfile.TemporaryDirectory() as cfg:
            with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": cfg}):
                learnings_dir = quality.st.project_learnings_path(self.root)
                os.makedirs(learnings_dir)
                with open(os.path.join(learnings_dir, "foo.md"), "w") as f:
                    f.write("# learning: foo\n")
                with open(os.path.join(learnings_dir, "INDEX.md"), "w") as f:
                    f.write("- [foo](foo.md) — stage:plan tags:x — hook\n")
                out = quality.render(self.root)
        self.assertIn("1 recorded", out)
        # never looked inside the project itself for learnings
        self.assertFalse(os.path.exists(os.path.join(self.root, ".claude")))


if __name__ == "__main__":
    unittest.main()
