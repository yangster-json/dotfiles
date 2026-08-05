"""tests for the sdd git helper — the choreography must refuse instead of
guessing, and a conflict must leave the feature worktree clean."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from helpers import SDD, load_module

statelib = load_module("statelib", "bin/statelib.py")

GIT_CLI = os.path.join(SDD, "bin", "sdd-git")


def run_cli(args, cwd, expect=0):
    p = subprocess.run([sys.executable, GIT_CLI, *args], cwd=cwd,
                       text=True, capture_output=True)
    if p.returncode != expect:
        raise AssertionError(
            f"exit {p.returncode} (expected {expect}) for {args}\n"
            f"stdout: {p.stdout}\nstderr: {p.stderr}")
    return p


def git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, text=True,
                          capture_output=True, check=True).stdout.strip()


class GitHelperTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sdd-git-test-")
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        git(["init"], self.repo)
        git(["config", "user.email", "t@t"], self.repo)
        git(["config", "user.name", "t"], self.repo)
        with open(os.path.join(self.repo, "a.c"), "w") as f:
            f.write("int a;\n")
        git(["add", "-A"], self.repo)
        git(["commit", "-m", "init"], self.repo)
        self.base = git(["rev-parse", "--abbrev-ref", "HEAD"], self.repo)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def feature(self, slug="feat"):
        p = run_cli(["feature-start", slug, self.base], self.repo)
        path = p.stdout.splitlines()[0].split(": ", 1)[1]
        self.assertTrue(os.path.isdir(path))
        return path

    def test_feature_start_and_refusals(self):
        path = self.feature()
        self.assertEqual(git(["rev-parse", "--abbrev-ref", "HEAD"], path),
                         "sdd/feat")
        run_cli(["feature-start", "feat", self.base], self.repo, expect=1)
        run_cli(["feature-start", "Bad_Slug", self.base], self.repo, expect=1)
        run_cli(["feature-start", "x", "no-such-ref"], self.repo, expect=1)

    def test_task_flow(self):
        fwt = self.feature()
        p = run_cli(["task-start", "feat", "T1"], self.repo)
        twt = p.stdout.splitlines()[0].split(": ", 1)[1]
        with open(os.path.join(twt, "b.c"), "w") as f:
            f.write("int b;\n")
        run_cli(["wip", "T1", "add b"], twt)
        self.assertIn("wip(sdd): T1 add b", git(["log", "-1", "--format=%s"], twt))
        # idempotent when clean
        run_cli(["wip", "T1", "add b"], twt)
        run_cli(["task-merge", "feat", "T1"], self.repo)
        self.assertTrue(os.path.isfile(os.path.join(fwt, "b.c")))
        self.assertFalse(os.path.exists(twt))
        self.assertEqual(subprocess.run(
            ["git", "rev-parse", "--verify", "-q", "refs/heads/sdd/feat-T1"],
            cwd=self.repo, capture_output=True).returncode, 1)

    def test_wip_refuses_off_sdd_branch(self):
        with open(os.path.join(self.repo, "c.c"), "w") as f:
            f.write("int c;\n")
        run_cli(["wip", "T1", "x"], self.repo, expect=1)

    def test_task_merge_refuses_dirty_task_worktree(self):
        self.feature()
        p = run_cli(["task-start", "feat", "T1"], self.repo)
        twt = p.stdout.splitlines()[0].split(": ", 1)[1]
        with open(os.path.join(twt, "b.c"), "w") as f:
            f.write("int b;\n")
        run_cli(["task-merge", "feat", "T1"], self.repo, expect=1)

    def test_task_merge_conflict_aborts(self):
        fwt = self.feature()
        wts = []
        for tid in ("T1", "T2"):
            p = run_cli(["task-start", "feat", tid], self.repo)
            wts.append(p.stdout.splitlines()[0].split(": ", 1)[1])
        for wt, tid in zip(wts, ("T1", "T2")):
            with open(os.path.join(wt, "a.c"), "w") as f:
                f.write(f"int a; /* {tid} */\n")
            run_cli(["wip", tid, "edit a"], wt)
        run_cli(["task-merge", "feat", "T1"], self.repo)
        run_cli(["task-merge", "feat", "T2"], self.repo, expect=2)
        # aborted: feature worktree clean, task branch/worktree kept
        self.assertEqual(git(["status", "--porcelain"], fwt), "")
        self.assertFalse(os.path.exists(os.path.join(
            git(["rev-parse", "--git-dir"], fwt), "MERGE_HEAD")))
        self.assertTrue(os.path.isdir(wts[1]))

    def test_task_abort_reclaims_id_after_conflict(self):
        # merge-conflict recovery: abort the isolated attempt so the task can
        # be re-run serially on the merged feature HEAD.
        fwt = self.feature()
        wts = []
        for tid in ("T1", "T2"):
            p = run_cli(["task-start", "feat", tid], self.repo)
            wts.append(p.stdout.splitlines()[0].split(": ", 1)[1])
        for wt, tid in zip(wts, ("T1", "T2")):
            with open(os.path.join(wt, "a.c"), "w") as f:
                f.write(f"int a; /* {tid} */\n")
            run_cli(["wip", tid, "edit a"], wt)
        run_cli(["task-merge", "feat", "T1"], self.repo)
        run_cli(["task-merge", "feat", "T2"], self.repo, expect=2)
        run_cli(["task-abort", "feat", "T2"], self.repo)
        self.assertFalse(os.path.exists(wts[1]))
        self.assertEqual(subprocess.run(
            ["git", "rev-parse", "--verify", "-q", "refs/heads/sdd/feat-T2"],
            cwd=self.repo, capture_output=True).returncode, 1)
        self.assertEqual(git(["status", "--porcelain"], fwt), "")
        # id is free again -> the task can be re-cut and re-run
        run_cli(["task-start", "feat", "T2"], self.repo)

    def test_task_abort_refuses_unknown_branch(self):
        self.feature()
        run_cli(["task-abort", "feat", "T9"], self.repo, expect=1)

    def test_snapshot(self):
        fwt = self.feature()
        run_cli(["snapshot"], self.repo, expect=1)  # not on an sdd branch
        os.makedirs(os.path.join(fwt, "specs", "feat"))
        with open(os.path.join(fwt, "specs", "feat", "spec.md"), "w") as f:
            f.write("# spec\n")
        with open(os.path.join(fwt, "loose.c"), "w") as f:
            f.write("int l;\n")
        run_cli(["snapshot"], fwt)
        self.assertIn("wip(sdd): specs snapshot",
                      git(["log", "-1", "--format=%s"], fwt))
        self.assertNotIn("loose.c",
                         git(["show", "--name-only", "HEAD"], fwt))
        run_cli(["snapshot"], fwt)  # no-op when specs/ unchanged
        # refuse when non-specs work is already staged
        git(["add", "loose.c"], fwt)
        with open(os.path.join(fwt, "specs", "feat", "spec.md"), "a") as f:
            f.write("more\n")
        run_cli(["snapshot"], fwt, expect=1)

    def test_snapshot_stages_a_gitignored_specs_dir(self):
        with open(os.path.join(self.repo, ".gitignore"), "w") as f:
            f.write("specs/\n")
        git(["add", "-A"], self.repo)
        git(["commit", "-m", "ignore specs"], self.repo)
        fwt = self.feature("ignored")
        os.makedirs(os.path.join(fwt, "specs", "ignored"))
        with open(os.path.join(fwt, "specs", "ignored", "spec.md"), "w") as f:
            f.write("# spec\n")
        run_cli(["snapshot"], fwt)
        self.assertIn("specs/ignored/spec.md",
                      git(["show", "--name-only", "HEAD"], fwt))

    def test_dissolve(self):
        fwt = self.feature()
        run_cli(["dissolve", self.base], fwt)  # nothing to dissolve
        base_sha = git(["rev-parse", "HEAD"], fwt)
        for i, tid in enumerate(("T1", "T2")):
            with open(os.path.join(fwt, f"f{i}.c"), "w") as f:
                f.write("int f;\n")
            run_cli(["wip", tid, "work"], fwt)
        run_cli(["dissolve", self.base], self.repo, expect=1)  # not sdd branch
        run_cli(["dissolve", self.base], fwt)
        self.assertEqual(git(["rev-parse", "HEAD"], fwt), base_sha)
        staged = git(["diff", "--cached", "--name-only"], fwt)
        self.assertIn("f0.c", staged)
        self.assertIn("f1.c", staged)

    def test_dissolve_refuses_non_wip_commits(self):
        fwt = self.feature()
        with open(os.path.join(fwt, "f.c"), "w") as f:
            f.write("int f;\n")
        git(["add", "-A"], fwt)
        git(["commit", "-m", "manual commit"], fwt)
        run_cli(["dissolve", self.base], fwt, expect=1)
        run_cli(["dissolve", self.base, "--force"], fwt)

    def test_dissolve_refuses_dirty_tree(self):
        fwt = self.feature()
        with open(os.path.join(fwt, "a.c"), "a") as f:
            f.write("int more;\n")
        run_cli(["dissolve", self.base], fwt, expect=1)

    def test_learnings_dir_is_per_repo_not_per_worktree(self):
        fwt = self.feature()
        p = run_cli(["task-start", "feat", "T1"], self.repo)
        twt = p.stdout.splitlines()[0].split(": ", 1)[1]
        with tempfile.TemporaryDirectory() as cfg:
            with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": cfg}):
                expected = statelib.project_learnings_path(self.repo)
                for cwd in (self.repo, fwt, twt):
                    p = run_cli(["learnings-dir"], cwd)
                    self.assertEqual(p.stdout.strip(), expected)
                self.assertTrue(os.path.isdir(expected))
                self.assertTrue(expected.startswith(cfg))
                # idempotent: a second call from a different worktree doesn't error
                run_cli(["learnings-dir"], fwt)
        # never written into the project's own tree (.claude/worktrees/
        # legitimately exists there from feature()/task-start above —
        # only .claude/sdd is what learnings-dir must avoid creating)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".claude", "sdd")))

    def test_base_specs_dir_lives_outside_the_repo(self):
        fwt = self.feature()
        with tempfile.TemporaryDirectory() as cfg:
            with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": cfg}):
                expected = statelib.project_base_specs_path(self.repo)
                for cwd in (self.repo, fwt):
                    p = run_cli(["base-specs-dir"], cwd)
                    self.assertEqual(p.stdout.strip(), expected)
                self.assertTrue(os.path.isdir(expected))
                self.assertTrue(expected.startswith(cfg))
        self.assertFalse(os.path.exists(os.path.join(self.repo, "specs")))


if __name__ == "__main__":
    unittest.main()
