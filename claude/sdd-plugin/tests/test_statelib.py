"""tests for statelib.py — the parsing must survive LLM formatting drift."""
import os
import tempfile
import unittest

from helpers import load_module

st = load_module("statelib", "bin/statelib.py")

STATE = """# sdd state: my-feature

created: 2026-07-10
jira: FW-12345
phase: implement  <!-- research | spec | ... -->
plan_approved: yes
review_approved: no

## tasks
| id | title | complexity | status | depends_on | parallel_ok |
|----|-------|------------|--------|------------|-------------|
| T1 | add stats counter | simple | done | — | no |
| T2 | wire into fio path | standard | **in_progress** | T1 | no |
| F1 | fix leak from review | standard | pending | T2 | no |

## metrics
verify_retries: 2
tasks_blocked: 0
findings_confirmed: 3

## log
- 2026-07-10 feature initialized
- 2026-07-10 note: user said plan_approved: yes should wait
"""

# same content, formatted the way a drifting orchestrator might write it
STATE_DRIFTED = """# sdd state: my-feature

- **created**: 2026-07-10
- **Phase**: implement
- **plan_approved**: Yes

## Tasks
| Status | Task | Title | Complexity |
|--------|------|-------|------------|
| done | T1 | add stats counter | simple |
| blocked | T2 | wire into fio path | standard |

## Metrics
- verify_retries: 1
"""


class TestField(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(st.field(STATE, "phase"), "implement")

    def test_comment_stripped(self):
        self.assertEqual(st.field(STATE, "jira"), "FW-12345")

    def test_bold_key_and_dash_prefix(self):
        self.assertEqual(st.field(STATE_DRIFTED, "phase"), "implement")
        self.assertEqual(st.field(STATE_DRIFTED, "created"), "2026-07-10")

    def test_case_insensitive(self):
        self.assertEqual(st.field(STATE_DRIFTED, "PHASE"), "implement")

    def test_default(self):
        self.assertEqual(st.field(STATE, "nope", "dflt"), "dflt")


class TestFlag(unittest.TestCase):
    def test_yes_no(self):
        self.assertTrue(st.flag(STATE, "plan_approved"))
        self.assertFalse(st.flag(STATE, "review_approved"))

    def test_capitalized_yes_bold_key(self):
        self.assertTrue(st.flag(STATE_DRIFTED, "plan_approved"))

    def test_log_mention_does_not_leak(self):
        # "plan_approved: yes" inside a log line must not read as the flag
        text = ("plan_approved: no\n"
                "## log\n"
                "- 2026-07-10 user said plan_approved: yes should wait\n")
        self.assertFalse(st.flag(text, "plan_approved"))


class TestTaskRows(unittest.TestCase):
    def test_canonical_table(self):
        rows = st.task_rows(STATE)
        self.assertEqual([r["id"] for r in rows], ["T1", "T2", "F1"])
        self.assertEqual(rows[1]["status"], "in_progress")  # emphasis stripped
        self.assertEqual(rows[2]["complexity"], "standard")

    def test_reordered_and_aliased_columns(self):
        rows = st.task_rows(STATE_DRIFTED)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["id"], "T1")
        self.assertEqual(rows[0]["status"], "done")
        self.assertEqual(rows[1]["status"], "blocked")

    def test_non_task_tables_ignored(self):
        text = ("## coverage\n"
                "| requirement | tasks |\n|---|---|\n| R1 | T1 |\n")
        self.assertEqual(st.task_rows(text), [])


class TestMetrics(unittest.TestCase):
    def test_counters(self):
        m = st.metrics(STATE)
        self.assertEqual(m["verify_retries"], 2)
        self.assertEqual(m["findings_confirmed"], 3)

    def test_dashed_and_capitalized_section(self):
        self.assertEqual(st.metrics(STATE_DRIFTED)["verify_retries"], 1)

    def test_absent(self):
        self.assertEqual(st.metrics("# nothing"), {})


class TestResolveActive(unittest.TestCase):
    def _make(self, root, rel, content):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

    def test_plain_slug(self):
        with tempfile.TemporaryDirectory() as d:
            self._make(d, "specs/ACTIVE", "my-feature\n")
            self.assertEqual(st.resolve_active(d), (d, "my-feature"))

    def test_worktree_pointer(self):
        with tempfile.TemporaryDirectory() as d:
            self._make(d, "specs/ACTIVE", "worktree: wt\n")
            self._make(d, "wt/specs/ACTIVE", "my-feature\n")
            root, slug = st.resolve_active(d)
            self.assertEqual(slug, "my-feature")
            self.assertEqual(os.path.realpath(root),
                             os.path.realpath(os.path.join(d, "wt")))

    def test_missing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(st.resolve_active(d))

    def test_dangling_pointer(self):
        with tempfile.TemporaryDirectory() as d:
            self._make(d, "specs/ACTIVE", "worktree: gone\n")
            self.assertIsNone(st.resolve_active(d))


if __name__ == "__main__":
    unittest.main()
