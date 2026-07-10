"""tests for the plan-approval guard hook — the enforcement layer."""
import os
import subprocess
import sys
import tempfile
import unittest

from helpers import SDD, load_module

hook = load_module("hook", os.path.join("hooks", "require-plan-approval.py"))

STATE_UNAPPROVED = """# sdd state: feat
phase: plan
plan_approved: no
## log
- 2026-07-10 note: will set plan_approved: yes at gate 1
"""

STATE_APPROVED = STATE_UNAPPROVED.replace("plan_approved: no",
                                          "plan_approved: yes")


def edit(path):
    return {"tool_name": "Edit", "tool_input": {"file_path": path}}


def notebook(path):
    return {"tool_name": "NotebookEdit", "tool_input": {"notebook_path": path}}


def bash(cmd):
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


class HookProject(unittest.TestCase):
    """temp project with an active, unapproved feature."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.write("specs/ACTIVE", "feat\n")
        self.write("specs/feat/state.md", STATE_UNAPPROVED)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, content):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

    def allowed(self, data):
        code, _ = hook.decide(data, self.root)
        return code == 0

    def in_root(self, rel):
        return os.path.join(self.root, rel)


class TestFileTools(HookProject):
    def test_source_edit_blocked(self):
        self.assertFalse(self.allowed(edit(self.in_root("src/main.c"))))

    def test_notebook_edit_blocked(self):
        self.assertFalse(self.allowed(notebook(self.in_root("nb.ipynb"))))

    def test_specs_and_claude_allowed(self):
        self.assertTrue(self.allowed(edit(self.in_root("specs/feat/spec.md"))))
        self.assertTrue(self.allowed(edit(self.in_root(".claude/x.json"))))

    def test_outside_project_allowed(self):
        self.assertTrue(self.allowed(edit("/somewhere/else/file.c")))

    def test_approved_unblocks(self):
        self.write("specs/feat/state.md", STATE_APPROVED)
        self.assertTrue(self.allowed(edit(self.in_root("src/main.c"))))

    def test_log_mention_of_approval_does_not_unblock(self):
        # STATE_UNAPPROVED's log contains "plan_approved: yes" mid-line;
        # the anchored match must not treat that as approval
        self.assertFalse(self.allowed(edit(self.in_root("src/main.c"))))

    def test_emphasized_approval_line_still_counts(self):
        self.write("specs/feat/state.md",
                   "phase: implement\n**plan_approved**: yes\n")
        self.assertTrue(self.allowed(edit(self.in_root("src/main.c"))))

    def test_no_active_feature_allows_everything(self):
        os.remove(os.path.join(self.root, "specs", "ACTIVE"))
        self.assertTrue(self.allowed(edit(self.in_root("src/main.c"))))

    def test_worktree_pointer_followed(self):
        self.write("specs/ACTIVE", "worktree: wt\n")
        self.write("wt/specs/ACTIVE", "feat\n")
        self.write("wt/specs/feat/state.md", STATE_UNAPPROVED)
        self.assertFalse(self.allowed(edit(self.in_root("src/main.c"))))
        self.write("wt/specs/feat/state.md", STATE_APPROVED)
        self.assertTrue(self.allowed(edit(self.in_root("src/main.c"))))


class TestBash(HookProject):
    def test_read_only_allowed(self):
        for cmd in ("ls -la src/",
                    "git log --oneline -5",
                    "grep -rn foo src/ | head -20",
                    "wc -l src/a.c",
                    "make test 2>&1 | tail -5",
                    "git diff origin/master --stat"):
            self.assertTrue(self.allowed(bash(cmd)), cmd)

    def test_safe_redirect_targets_allowed(self):
        for cmd in ("git diff > /tmp/d.txt",
                    "echo notes >> specs/feat/notes.md",
                    "sort src/a.c > /dev/null"):
            self.assertTrue(self.allowed(bash(cmd)), cmd)

    def test_source_redirect_blocked(self):
        for cmd in ("echo x > src/main.c",
                    "sort names.txt > names.sorted",
                    "cat patch.txt >> src/module/init.c"):
            self.assertFalse(self.allowed(bash(cmd)), cmd)

    def test_mutators_blocked(self):
        for cmd in ("rm src/main.c",
                    "rm -rf build",
                    "mv src/a.c src/b.c",
                    "sed -i 's/a/b/' src/main.c",
                    "perl -pi -e 's/a/b/' src/main.c",
                    "git apply fix.patch",
                    "git checkout -- src/main.c",
                    "tee src/main.c",
                    "dd if=/dev/zero of=src/x.bin"):
            self.assertFalse(self.allowed(bash(cmd)), cmd)

    def test_mutators_on_allowed_paths_pass(self):
        for cmd in ("cp specs/feat/spec.md specs/feat/spec.bak.md",
                    "rm /tmp/scratch.txt",
                    "git worktree add .claude/worktrees/sdd/feat -b sdd/feat origin/master"):
            self.assertTrue(self.allowed(bash(cmd)), cmd)

    def test_sed_without_inplace_allowed(self):
        self.assertTrue(self.allowed(bash("sed 's/a/b/' src/main.c | head")))

    def test_approved_unblocks_bash(self):
        self.write("specs/feat/state.md", STATE_APPROVED)
        self.assertTrue(self.allowed(bash("sed -i 's/a/b/' src/main.c")))


class TestMainFailOpen(unittest.TestCase):
    def test_malformed_stdin_exits_zero(self):
        proc = subprocess.run(
            [sys.executable,
             os.path.join(SDD, "hooks", "require-plan-approval.py")],
            input="not json", capture_output=True, text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": "/nonexistent"})
        self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
