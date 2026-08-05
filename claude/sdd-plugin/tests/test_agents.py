"""tests for agentlib and the sdd-agents view of subagent transcripts.

the transcripts are claude code's, not ours, so the invariants worth holding
are: a record shape we did not anticipate degrades to a thinner row instead of
raising; discovery covers worktrees without dragging in a sibling repo; the
incremental read picks up exactly what was appended; and no rendered row
overflows the pane it was given.
"""
import json
import os
import shutil
import tempfile
import unittest

from helpers import load_module

import agentlib as ag

status_mod = load_module("sdd_status_agents", "bin/sdd-status")


def rec(kind="assistant", ts="2026-08-04T10:00:00.000Z", blocks=None,
        stop=None, **kw):
    """one transcript record, in the shape claude code writes."""
    msg = {"role": kind, "content": blocks if blocks is not None else []}
    if stop:
        msg["stop_reason"] = stop
    out = {"type": kind, "isSidechain": True, "timestamp": ts, "message": msg}
    out.update(kw)
    return out


def tool(name, **inp):
    return {"type": "tool_use", "id": f"tu-{name}", "name": name, "input": inp}


def text(body):
    return {"type": "text", "text": body}


def result(name, error=False):
    return {"type": "tool_result", "tool_use_id": f"tu-{name}",
            "is_error": error, "content": "…"}


class Fixture(unittest.TestCase):
    """a fake claude config dir with a repo, a worktree, and a sibling repo."""

    def setUp(self):
        ag.reset()
        self.tmp = tempfile.mkdtemp()
        self.config = os.path.join(self.tmp, "config")
        self.root = os.path.join(self.tmp, "repo")
        self.worktree = os.path.join(self.root, ".claude", "worktrees", "sdd",
                                     "feat")
        os.makedirs(os.path.join(self.root, "specs"))
        os.makedirs(self.worktree)
        self._env = os.environ.get("CLAUDE_CONFIG_DIR")
        os.environ["CLAUDE_CONFIG_DIR"] = self.config

    def tearDown(self):
        if self._env is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = self._env
        shutil.rmtree(self.tmp, ignore_errors=True)
        ag.reset()

    def agent_file(self, cwd, agent_id, records, meta=None, session="sess-1"):
        """write one subagent transcript where claude code would put it."""
        pdir = os.path.join(self.config, "projects", ag.st.munge(cwd))
        sub = os.path.join(pdir, session, "subagents")
        os.makedirs(sub, exist_ok=True)
        path = os.path.join(sub, f"agent-{agent_id}.jsonl")
        self.append(path, records)
        if meta is not None:
            with open(path[:-6] + ".meta.json", "w") as f:
                json.dump(meta, f)
        return path

    def append(self, path, records):
        with open(path, "a") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    def implementer(self, task="T3", cwd=None, agent_id="aaa", **kw):
        cwd = cwd or self.worktree
        return self.agent_file(
            cwd, agent_id,
            [rec("user", blocks=f"You are implementing task {task} for the "
                                f"SDD feature `feat`.\nWorktree: {cwd}",
                 cwd=cwd, gitBranch="sdd/feat"),
             rec(blocks=[tool("Read", file_path=f"{cwd}/mod.py")],
                 cwd=cwd, attributionAgent="sdd:sdd-implementer"),
             rec("user", blocks=[result("Read")], cwd=cwd)],
            meta={"agentType": "sdd:sdd-implementer",
                  "description": f"Implement {task}", "model": "sonnet"},
            **kw)

    def workflow_agent(self, agent_id, records, meta=None, run="wf_abc123",
                       session="sess-1", returned=None, cwd=None):
        """a transcript where an agent spawned from a Workflow script lands.

        one directory deeper than the Task tool's, with the run's journal
        beside it, and a meta sidecar that names the type and model but no
        description — the layout the implement, review and research stages all
        write.
        """
        cwd = cwd or self.root
        pdir = os.path.join(self.config, "projects", ag.st.munge(cwd))
        wf = os.path.join(pdir, session, "subagents", "workflows", run)
        os.makedirs(wf, exist_ok=True)
        path = os.path.join(wf, f"agent-{agent_id}.jsonl")
        self.append(path, records)
        with open(path[:-6] + ".meta.json", "w") as f:
            json.dump(meta or {"agentType": "sdd:sdd-reviewer",
                               "spawnDepth": 1, "model": "sonnet"}, f)
        journal = [{"type": "started", "agentId": agent_id}]
        for who, value in (returned or {}).items():
            journal.append({"type": "result", "agentId": who,
                            "result": value})
        self.append(os.path.join(wf, "journal.jsonl"), journal)
        return path

    def wf_implementer(self, agent_id="wf1", task="T1", **kw):
        """an implementer as the implement workflow spawns it: a json contract,
        and a worktree of its own named <slug>-<task>."""
        workdir = f"{self.root}/.claude/worktrees/sdd/feat-{task}"
        return self.workflow_agent(
            agent_id,
            [rec("user", blocks='inputs: {"workdir": "%s", "subspec": '
                                '"specs/feat/tasks/%s.md"}\nrun every command '
                                'from workdir.' % (workdir, task),
                 cwd=self.root),
             rec(blocks=[tool("Bash", command=f"pytest {workdir}/tests")],
                 cwd=self.root, attributionAgent="sdd:sdd-implementer"),
             rec("user", blocks=[result("Bash")], cwd=self.root)],
            meta={"agentType": "sdd:sdd-implementer", "model": "sonnet"},
            **kw)


class TestDiscovery(Fixture):
    def test_finds_worktree_agents_from_the_repo_root(self):
        self.implementer()
        self.assertEqual(len(ag.agents(self.root, "feat")), 1)

    def test_a_sibling_repo_sharing_the_prefix_is_excluded(self):
        """`repo-2` munges to the repo's own name plus a separator, so the
        prefix glob finds it and only the recorded cwd rules it out."""
        sibling = self.root + "-2"
        os.makedirs(sibling, exist_ok=True)
        self.implementer(cwd=sibling, agent_id="bbb")
        self.assertIn(ag.st.munge(sibling),
                      " ".join(ag.project_dirs(self.root)))
        self.assertEqual(ag.agents(self.root), [])

    def test_a_symlinked_transcript_is_not_a_second_agent(self):
        """claude code symlinks an agent's transcript into a second session's
        dir; the same agent listed twice reads as two agents doing one job."""
        path = self.implementer()
        other = os.path.join(self.config, "projects",
                             ag.st.munge(self.worktree), "sess-2", "subagents")
        os.makedirs(other)
        os.symlink(path, os.path.join(other, os.path.basename(path)))
        self.assertEqual(len(ag.agents(self.root)), 1)

    def test_no_transcripts_at_all_is_empty_not_an_error(self):
        self.assertEqual(ag.agents(self.root), [])
        self.assertEqual(ag.project_dirs(self.root), [])

    def test_workflow_spawned_agents_are_found_one_level_deeper(self):
        """the regression this class exists for: implement, review and research
        all run as workflows, whose agents land in subagents/workflows/wf_*/.
        globbing only the flat layout showed the spec and plan agents and then
        nothing, so a run in review read as having stalled at the plan."""
        self.wf_implementer()
        self.assertEqual(len(ag.agents(self.root, "feat")), 1)

    def test_both_layouts_are_listed_together(self):
        self.implementer()
        self.wf_implementer()
        self.assertEqual(len(ag.agents(self.root, "feat")), 2)


class TestParse(Fixture):
    def test_meta_names_the_agent(self):
        agent = ag.read(self.implementer())
        self.assertEqual(ag.label(agent), "implementer")
        self.assertEqual(agent["model"], "sonnet")

    def test_task_and_slug_come_from_the_spawn_prompt(self):
        agent = ag.read(self.implementer(task="T7"))
        self.assertEqual(agent["task"], "T7")
        self.assertEqual(agent["slug"], "feat")

    def test_what_does_not_repeat_the_task_id(self):
        agent = ag.read(self.implementer(task="T7"))
        self.assertEqual(ag.what(agent), "T7 Implement")

    def test_tool_calls_are_counted_and_paths_made_relative(self):
        agent = ag.read(self.implementer())
        self.assertEqual(agent["tools"], 1)
        self.assertEqual(agent["events"][-1]["arg"], "mod.py")

    def test_the_prompts_workdir_is_stripped_too(self):
        """for a run driving a worktree in another repo, the recorded cwd is the
        orchestrator's — the workdir is the directory the paths are really in."""
        elsewhere = "/somewhere/else/wt"
        path = self.agent_file(self.root, "wdd", [
            rec("user", blocks=f"slug: feat\nworkdir: {elsewhere}\n\nGo.",
                cwd=self.root),
            rec(blocks=[tool("Bash", command=f"grep -n x {elsewhere}/mod.py")],
                cwd=self.root)])
        agent = ag.read(path)
        self.assertEqual(agent["workdir"], elsewhere)
        self.assertEqual(agent["events"][-1]["arg"], "grep -n x mod.py")

    def test_the_inputs_contract_names_the_workdir_and_the_task(self):
        """the workflow stages state their inputs as one json line instead of a
        `key: value` header, and it is the only place an implementer's workdir
        appears — without it every path keeps its worktree prefix."""
        agent = ag.read(self.wf_implementer(task="T4"))
        self.assertEqual(agent["task"], "T4")
        self.assertTrue(agent["workdir"].endswith("worktrees/sdd/feat-T4"))
        self.assertEqual(agent["events"][-1]["arg"], "pytest tests")

    def test_the_workdir_on_its_own_becomes_a_dot(self):
        """every workflow-stage command opens `cd <workdir> && …` — spelled out
        that is 60 columns saying only "in the worktree, as always"."""
        path = self.wf_implementer(task="T5")
        workdir = ag.read(path)["workdir"]
        self.append(path, [rec(blocks=[tool("Bash",
                                            command=f"cd {workdir} && pytest")])])
        self.assertEqual(ag.read(path)["events"][-1]["arg"], "cd . && pytest")

    def test_a_per_task_worktree_does_not_become_a_feature_of_its_own(self):
        """a task's worktree is <slug>-<task>, so reading the slug straight off
        the path gave `feat-T4` and dropped every implementer and verifier out
        of the feature's own view."""
        agent = ag.read(self.wf_implementer(task="T4"))
        self.assertEqual(agent["slug"], "feat")
        self.assertEqual(len(ag.agents(self.root, "feat")), 1)

    def test_a_stance_from_the_contract_names_a_fanned_out_agent(self):
        """a workflow agent's sidecar has no description, so six reviewers all
        rendered as `reviewer —`. the contract says which is which."""
        agent = ag.read(self.workflow_agent("rev1", [
            rec("user", blocks='workdir: %s\nround 2 — combat.\ninputs: '
                               '{"stance": "attacker", "slug": "feat", '
                               '"own_findings": [{"id": "F2"}]}'
                               % self.worktree, cwd=self.root),
            rec(blocks=[tool("Grep", pattern="x")], cwd=self.root)]))
        self.assertEqual(ag.what(agent), "attacker")
        self.assertEqual(agent["slug"], "feat")
        # and the finding ids quoted into its prompt are not its task
        self.assertEqual(agent["task"], "")

    def test_a_research_angle_names_a_scout(self):
        agent = ag.read(self.workflow_agent("sc1", [
            rec("user", blocks=f"workdir: {self.worktree} — investigate.\n"
                               f"feature (slug feat): build a thing\n"
                               f"your one research angle: test conventions",
                cwd=self.root),
            rec(blocks=[tool("Glob", pattern="*.py")], cwd=self.root)],
            meta={"agentType": "sdd:sdd-researcher", "model": "haiku"}))
        self.assertEqual(ag.what(agent), "test conventions")

    def test_a_failed_call_marks_the_call_not_a_new_row(self):
        path = self.implementer()
        self.append(path, [rec(blocks=[tool("Bash", command="false")]),
                           rec("user", blocks=[result("Bash", error=True)])])
        agent = ag.read(path)
        self.assertEqual(agent["errors"], 1)
        self.assertTrue(agent["events"][-1]["err"])
        self.assertEqual(agent["events"][-1]["name"], "Bash")

    def test_missing_fields_thin_the_row_instead_of_raising(self):
        path = self.agent_file(self.worktree, "ccc", [
            {"type": "assistant"},                       # no message at all
            rec(blocks="a string where a list belongs"),
            rec(blocks=[{"type": "tool_use"}]),           # nameless call
            {"type": "wat"}])
        agent = ag.read(path)
        self.assertEqual(agent["events"][-1]["name"], "?")
        self.assertEqual(ag.label(agent), "agent")

    def test_a_truncated_final_line_is_left_for_the_next_read(self):
        """the file is appended to while it is read, so the last line can be
        half-written — parsing it would drop the record entirely."""
        path = self.implementer()
        with open(path, "a") as f:
            f.write('{"type": "assistant", "mess')
        agent = ag.read(path)
        self.assertEqual(agent["turns"], 1)
        self.append(path, [])                            # completes the line
        with open(path, "a") as f:
            f.write('age": {"content": []}, "type": "assistant"}\n')
        self.assertEqual(ag.read(path)["turns"], 2)

    def test_a_later_read_only_parses_what_was_appended(self):
        path = self.implementer()
        first = ag.read(path)
        offset = first["offset"]
        self.append(path, [rec(blocks=[tool("Edit", file_path="mod.py")])])
        again = ag.read(path)
        self.assertIs(again, first)                      # same live object
        self.assertGreater(again["offset"], offset)
        self.assertEqual(again["tools"], 2)

    def test_a_rotated_file_is_reparsed_from_scratch(self):
        path = self.implementer()
        ag.read(path)
        with open(path, "w") as f:                       # truncated under us
            f.write(json.dumps(rec(blocks=[tool("Read", file_path="x")])) + "\n")
        self.assertEqual(ag.read(path)["tools"], 1)


class TestStatus(Fixture):
    def test_end_turn_is_done_and_keeps_the_final_line(self):
        path = self.implementer()
        self.append(path, [rec(blocks=[text("## Summary\nVerify passed.")],
                               stop="end_turn")])
        agent = ag.read(path)
        self.assertEqual(ag.status(agent), "done")
        # the heading is scaffolding — the first real sentence is the answer
        self.assertEqual(agent["final"], "Verify passed.")

    def test_a_working_agent_is_running_then_stale_then_gone(self):
        agent = ag.read(self.implementer())
        now = os.path.getmtime(agent["path"])
        self.assertEqual(ag.status(agent, now), "running")
        self.assertEqual(ag.status(agent, now + ag.STALE_SECONDS + 1), "stale")
        self.assertEqual(ag.status(agent, now + ag.ABANDONED_SECONDS + 1),
                         "gone")

    def test_work_after_an_end_turn_is_running_again(self):
        path = self.implementer()
        self.append(path, [rec(blocks=[text("done")], stop="end_turn"),
                           rec(blocks=[tool("Bash", command="ls")])])
        self.assertEqual(ag.status(ag.read(path),
                                   os.path.getmtime(path)), "running")

    def test_a_final_message_without_a_stop_reason_is_still_done(self):
        """claude code does not always stamp the last record of a finished agent
        with a stop_reason: a planner that returned its summary read as `gone`
        on stop_reason alone. it spoke and called nothing — that is the end."""
        path = self.implementer()
        self.append(path, [rec(blocks=[text("## Summary\nTasks written.")])])
        agent = ag.read(path)
        now = os.path.getmtime(path)
        self.assertEqual(ag.status(agent, now + ag.SPLIT_GRACE + 1), "done")
        self.assertEqual(agent["final"], "Tasks written.")

    def test_a_mid_turn_text_flush_is_not_yet_done(self):
        """a streamed turn is split across records — a text block flushed on its
        own, then the tool call — so a text-only record is held for the grace
        rather than read as an answer."""
        path = self.implementer()
        self.append(path, [rec(blocks=[text("Let me check the tests.")])])
        agent = ag.read(path)
        self.assertEqual(ag.status(agent, os.path.getmtime(path)), "running")
        self.append(path, [rec(blocks=[tool("Bash", command="pytest")])])
        agent = ag.read(path)
        # the call landed, so the grace expiring makes it quiet, never finished
        self.assertEqual(ag.status(agent, os.path.getmtime(path)
                                   + ag.STALE_SECONDS + 1), "stale")

    def test_a_journal_result_is_done_even_ending_on_a_tool_call(self):
        """an agent the workflow gave a schema to answers by CALLING
        StructuredOutput, so none of the transcript's end-of-turn signals ever
        fire — three reviewers that had returned read as stale, then gone. the
        run's journal records the value it handed back."""
        path = self.workflow_agent("rev2", [
            rec("user", blocks='inputs: {"stance": "breaker", "slug": "feat"}',
                cwd=self.root),
            rec(blocks=[tool("StructuredOutput", description="findings")],
                cwd=self.root),
            rec("user", blocks=[result("StructuredOutput")], cwd=self.root)],
            returned={"rev2": "{'findings': [{'id': 'B1'}]}"})
        agent = ag.read(path)
        self.assertEqual(ag.status(agent, os.path.getmtime(path)), "done")
        self.assertIn("B1", agent["final"])

    def test_a_workflow_agent_with_no_result_yet_is_still_running(self):
        path = self.workflow_agent("rev3", [
            rec("user", blocks='inputs: {"stance": "guardian", "slug": "feat"}',
                cwd=self.root),
            rec(blocks=[tool("Read", file_path="mod.py")], cwd=self.root)])
        agent = ag.read(path)
        self.assertEqual(ag.status(agent, os.path.getmtime(path)), "running")
        self.assertEqual(ag.status(agent, os.path.getmtime(path)
                                   + ag.ABANDONED_SECONDS + 1), "gone")

    def test_a_missing_or_corrupt_journal_leaves_the_transcript_in_charge(self):
        path = self.wf_implementer()
        wf = os.path.dirname(path)
        with open(os.path.join(wf, "journal.jsonl"), "w") as f:
            f.write("{not json at all\n")
        ag.reset()
        agent = ag.read(path)
        self.assertEqual(ag.status(agent, os.path.getmtime(path)), "running")

    def test_since_drops_agents_whose_transcript_went_quiet(self):
        path = self.implementer()
        self.assertEqual(len(ag.agents(self.root, since=3600)), 1)
        old = os.path.getmtime(path) - 7200
        os.utime(path, (old, old))
        ag.reset()
        self.assertEqual(ag.agents(self.root, since=3600), [])

    def test_counts_are_ordered_live_first(self):
        self.implementer(agent_id="aaa")
        path = self.implementer(agent_id="ddd", task="T4")
        self.append(path, [rec(blocks=[text("ok")], stop="end_turn")])
        keys = list(ag.counts(ag.agents(self.root)))
        self.assertEqual(keys, ["running", "done"])


class TestFeatureFilter(Fixture):
    """which feature an agent belongs to comes from its PROMPT.

    the record's cwd and gitBranch describe the orchestrator's session, not the
    agent: an sdd run with no worktree sits on whatever branch the session was
    already on, and one driving a worktree in another repo records that other
    repo's cwd. attributing by branch alone hid every such run's agents.
    """

    def spawned(self, prompt, agent_id="fff", cwd=None, branch="some-branch"):
        cwd = cwd or self.root
        self.agent_file(cwd, agent_id, [
            rec("user", blocks=prompt, cwd=cwd, gitBranch=branch),
            rec(blocks=[tool("Read", file_path="spec.md")], cwd=cwd,
                gitBranch=branch, attributionAgent="sdd:sdd-spec-critic")])
        return ag.agents(self.root)[-1]

    def test_a_leading_slug_line(self):
        agent = self.spawned("slug: feat\nworkdir: /elsewhere\n\nReview it.")
        self.assertEqual(agent["slug"], "feat")

    def test_a_workdir_pointing_at_the_worktree(self):
        agent = self.spawned(f"workdir: {self.worktree}\n\nReview the spec.")
        self.assertEqual(agent["slug"], "feat")

    def test_a_cited_specs_path(self):
        agent = self.spawned("Review specs/feat/spec.md for feasibility.")
        self.assertEqual(agent["slug"], "feat")

    def test_specs_templates_is_not_a_feature(self):
        agent = self.spawned("Read specs/templates/spec.md, then specs/feat/"
                             "spec.md.")
        self.assertEqual(agent["slug"], "feat")

    def test_an_unrelated_branch_does_not_hide_the_agent(self):
        """the failing case: an sdd run with no worktree, on a branch named
        after something else. the prompt still names the feature."""
        agent = self.spawned("slug: feat\n\nWrite specs/feat/spec.md.",
                             branch="fw-xxxxx-unrelated-refactor")
        self.assertEqual(agent["slug"], "feat")
        self.assertEqual(len(ag.agents(self.root, "feat")), 1)

    def test_transcripts_filed_under_another_repo_are_still_found(self):
        """the orchestrator sat in repo A and drove a worktree in repo B, so B's
        project dir holds nothing — the scan widens and attributes by slug."""
        other = os.path.join(self.tmp, "other-repo")
        os.makedirs(other)
        self.agent_file(other, "ggg", [
            rec("user", blocks="slug: feat\n\nWrite specs/feat/spec.md.",
                cwd=other),
            rec(blocks=[tool("Read", file_path="spec.md")], cwd=other,
                attributionAgent="sdd:sdd-spec-writer")])
        self.assertEqual(ag.agents(self.root), [])          # not in this repo
        self.assertEqual(len(ag.agents(self.root, "feat")), 1)

    def test_the_widened_scan_does_not_claim_another_features_agents(self):
        other = os.path.join(self.tmp, "other-repo")
        os.makedirs(other)
        self.agent_file(other, "hhh", [
            rec("user", blocks="slug: unrelated\n\nWrite specs/unrelated/"
                               "spec.md.", cwd=other),
            rec(blocks=[tool("Read", file_path="x")], cwd=other)])
        self.assertEqual(ag.agents(self.root, "feat"), [])

    def test_the_branch_identifies_a_feature_without_a_prompt(self):
        self.agent_file(self.worktree, "eee", [
            rec(blocks=[tool("Read", file_path="x")], cwd=self.worktree,
                gitBranch="sdd/feat", attributionAgent="sdd:sdd-reviewer")])
        self.assertEqual(len(ag.agents(self.root, "feat")), 1)
        self.assertEqual(ag.agents(self.root, "other"), [])

    def test_another_features_agents_are_excluded(self):
        self.implementer()
        self.assertEqual(ag.agents(self.root, "unrelated"), [])

    def test_the_workdir_finds_them_when_no_slug_is_named(self):
        """with the active pointer gone (or `--any`) there is no slug to widen
        the scan on, and an orchestrator sitting in another repo files its
        agents under that repo — so the roster came up empty. the workdir the
        prompt handed the agent points back here."""
        other = os.path.join(self.tmp, "other-repo")
        os.makedirs(other)
        self.agent_file(other, "iii", [
            rec("user", blocks=f"workdir: {self.worktree}\n\nReview it.",
                cwd=other),
            rec(blocks=[tool("Read", file_path="spec.md")], cwd=other,
                attributionAgent="sdd:sdd-reviewer")])
        self.assertEqual(len(ag.agents(self.root)), 1)

    def test_the_widened_no_slug_scan_claims_nothing_it_cannot_place(self):
        """scanning the whole corpus with no slug to filter on would otherwise
        drag in every agent on the machine."""
        other = os.path.join(self.tmp, "other-repo")
        os.makedirs(other)
        self.agent_file(other, "jjj", [
            rec("user", blocks="Go and do something unrelated.", cwd=other),
            rec(blocks=[tool("Read", file_path="x")], cwd=other)])
        self.assertEqual(ag.agents(self.root), [])


class TestRendering(Fixture):
    """the rows are read in a tmux side pane, so width is a hard contract."""

    def rows(self, width):
        agents = ag.agents(self.root)
        out = [ag.plain(ag.row(a, width)) for a in agents]
        out += [ag.plain(ag.event_row(e, width))
                for e in ag.timeline(agents, 20)]
        return out

    def test_nothing_overflows_or_trails_whitespace(self):
        path = self.implementer()
        self.append(path, [
            rec(blocks=[tool("Bash", command="x " * 400)]),
            rec(blocks=[text("a very long sentence " * 30)], stop="end_turn")])
        for width in (52, 60, 80, 100, 140):
            for line in self.rows(width):
                self.assertLessEqual(len(line), width, f"width {width}")
                self.assertEqual(line, line.rstrip())

    def test_a_row_says_which_tool_is_running(self):
        agent = ag.read(self.implementer())
        self.assertIn("Read mod.py", ag.plain(ag.row(agent, 100)))

    def test_dur_stays_narrow(self):
        for secs in (0, 59, 60, 3599, 3600, 86400):
            self.assertLessEqual(len(ag.dur(secs)), 6)

    def test_wrapped_rows_keep_the_width_and_lose_nothing(self):
        """`w` trades rows for completeness — so every wrapped line still has
        to fit the pane, and the text that a clipped row cut has to be back."""
        path = self.implementer()
        self.append(path, [rec(blocks=[tool("Bash", command="pytest " + "x " * 90)])])
        agent = ag.agents(self.root)[0]
        for width in (52, 60, 80, 100, 140):
            lines = [ag.plain(s) for s in ag.rows(agent, width, wrap=True)]
            for line in lines:
                self.assertLessEqual(len(line), width, f"width {width}")
                self.assertEqual(line, line.rstrip())
            self.assertGreater(len(lines), 1)          # it did fold
            joined = " ".join(l.strip() for l in lines)
            self.assertIn("pytest", joined)
            self.assertEqual(joined.count("x"), 90)    # every word survived

    def test_a_wrapped_row_hangs_under_its_columns(self):
        path = self.implementer()
        self.append(path, [rec(blocks=[tool("Bash", command="y " * 80)])])
        lines = [ag.plain(s) for s in ag.rows(ag.agents(self.root)[0], 100,
                                              wrap=True)]
        self.assertTrue(lines[1].startswith("    "),
                        f"continuation must be indented: {lines[1]!r}")

    def test_a_wrapped_event_keeps_its_clock_on_the_first_line_only(self):
        path = self.implementer()
        self.append(path, [rec(blocks=[tool("Grep", pattern="z " * 80)])])
        evs = ag.timeline(ag.agents(self.root), 20)
        lines = [ag.plain(s) for s in ag.event_rows(evs[-1], 80, wrap=True)]
        self.assertTrue(lines[0].startswith("10:00:00"))
        self.assertGreater(len(lines), 1)
        for line in lines[1:]:
            self.assertNotIn("10:00:00", line)
            self.assertLessEqual(len(line), 80)

    def test_an_unbreakable_word_is_cut_rather_than_overflowing(self):
        """a 300-column path has nowhere to wrap — it still may not spill."""
        path = self.implementer()
        self.append(path, [rec(blocks=[tool("Read", file_path="/" + "d" * 300)])])
        for line in [ag.plain(s) for s in ag.rows(ag.agents(self.root)[0], 80,
                                                  wrap=True)]:
            self.assertLessEqual(len(line), 80)

    def test_public_is_json_serializable(self):
        data = ag.public(ag.read(self.implementer()))
        json.dumps(data)                                 # raises if it is not
        self.assertNotIn("pending", data)
        self.assertEqual(data["status"], "running")


class TestStatusPane(Fixture):
    """the `a` pane in sdd-status renders the same rows next to the ladder."""

    def setUp(self):
        super().setUp()
        status_mod.use_color(False)
        status_mod._memo.clear()

    def pane(self, width=100, height=24, wrap=False, view=None):
        view = view or status_mod.View(width=width, height=height,
                                       pane="agents", wrap=wrap)
        return status_mod.render_agent_pane(self.root, "feat", view, width, 8)

    def test_empty_says_so_without_raising(self):
        self.assertIn("no subagent transcripts", "\n".join(self.pane()))

    def test_the_roster_and_the_activity_tail_both_appear(self):
        self.implementer()
        out = "\n".join(self.pane())
        self.assertIn("implementer", out)
        self.assertIn("activity", out)

    def test_the_pane_never_exceeds_the_window(self):
        for i in range(12):
            path = self.implementer(task=f"T{i}", agent_id=f"a{i}")
            # a command far too long for one row: wrapped, every one of these
            # agents is several rows tall
            self.append(path, [rec(blocks=[tool("Bash", command="x " * 200)])])
        for wrap in (False, True):
            for height in (10, 16, 24, 50):
                rows = self.pane(height=height, wrap=wrap)
                self.assertLessEqual(len(rows), max(4, height - 8 - 2) + 1,
                                     f"height {height} wrap {wrap}")
                for line in rows:
                    self.assertLessEqual(len(line), 100)

    def test_wrapping_leaves_the_activity_tail_room_to_exist(self):
        """the roster budget counts rendered LINES — counted in agents, tall
        wrapped rows filled the pane and left no activity section at all."""
        for i in range(6):
            path = self.implementer(task=f"T{i}", agent_id=f"a{i}")
            self.append(path, [rec(blocks=[tool("Bash", command="x " * 200)])])
        out = "\n".join(self.pane(height=30, wrap=True))
        self.assertIn("activity", out)
        self.assertIn("wrapped", out)

    def test_the_wrapped_activity_counter_counts_what_is_on_screen(self):
        """the note may not claim calls the fold pushed off the pane."""
        path = self.implementer()
        for i in range(20):
            self.append(path, [rec(blocks=[tool("Bash",
                                                command=f"cmd{i} " + "q " * 60)])])
        rows = self.pane(height=24, wrap=True)
        head = next(r for r in rows if "activity" in r)
        shown = sum(1 for r in rows[rows.index(head) + 1:] if "Bash" in r)
        self.assertIn(f"of {20 + 1}", head)          # the Read call too
        first, _, last = head.split()[1].split("of")[0].strip().partition("-")
        self.assertEqual(int(last) - int(first) + 1, shown)

    def test_a_working_agent_outranks_a_finished_one_in_a_short_pane(self):
        """the roster is capped by pane height — it must keep the live agents,
        whatever order they started in."""
        for i in range(10):
            path = self.implementer(task=f"T{i}", agent_id=f"a{i}")
            if i:      # everything but the FIRST agent has finished
                self.append(path, [rec(blocks=[text("ok")], stop="end_turn")])
        out = "\n".join(self.pane(height=14))
        self.assertIn("T0", out)

    def test_the_dashboard_section_shows_only_working_agents(self):
        path = self.implementer(task="T1", agent_id="a1")
        self.append(path, [rec(blocks=[text("ok")], stop="end_turn")])
        self.implementer(task="T2", agent_id="a2")
        rows, note = status_mod.agent_segs(ag.agents(self.root, "feat"), 100)
        self.assertEqual(len(rows), 1)
        self.assertIn("T2", rows[0])
        self.assertIn("1 working", note)

    def test_no_working_agents_means_no_dashboard_section(self):
        path = self.implementer()
        self.append(path, [rec(blocks=[text("ok")], stop="end_turn")])
        rows, _ = status_mod.agent_segs(ag.agents(self.root, "feat"), 100)
        self.assertEqual(rows, [])

    def test_an_abandoned_agent_is_not_reported_as_working(self):
        """an unfinished agent from an interrupted run is never coming back —
        counting it as working put a `1 working` note over a ⊘ row."""
        path = self.implementer()
        old = os.path.getmtime(path) - ag.ABANDONED_SECONDS - 60
        os.utime(path, (old, old))
        ag.reset()
        agents = ag.agents(self.root, "feat")
        self.assertEqual(ag.status(agents[0]), "gone")
        self.assertEqual(status_mod.agent_segs(agents, 100)[0], [])


if __name__ == "__main__":
    unittest.main()
