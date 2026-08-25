"""tests for cost's token aggregation and price-table estimate."""
import json
import os
import shutil
import tempfile
import time
import unittest

from helpers import load_module

cost = load_module("cost", "bin/sdd-cost")


def entry(uuid, session, **kw):
    e = {"type": "assistant", "uuid": uuid, "sessionId": session,
         "timestamp": "2026-07-31T12:00:00Z",
         "message": {"id": "msg-" + uuid, "model": "claude-sonnet-5",
                     "usage": {"output_tokens": 1000}}}
    e.update(kw)
    return e


def rec(model="claude-sonnet-5", tin=0, tout=0, cw=0, cr=0, **kw):
    r = {"model": model, "tin": tin, "tout": tout, "cw": cw, "cr": cr}
    r.update(kw)
    return r


LAPSED = "2099-01-01T00:00:00Z"   # past every INTRO expiry


class TestEstimate(unittest.TestCase):
    def test_sonnet_output_rate(self):
        # 1M sonnet output tokens at the $10/M introductory rate
        self.assertAlmostEqual(cost.est(rec(tout=1_000_000)), 10.0, places=2)

    def test_intro_price_lapses_by_request_date(self):
        # the discount is by request date, so a later record pays list ($15/M)
        self.assertAlmostEqual(
            cost.est(rec(tout=1_000_000, ts=LAPSED)), 15.0, places=2)

    def test_opus_input_rate(self):
        # 1M opus input tokens at $5/M (no introductory rate on opus)
        self.assertAlmostEqual(
            cost.est(rec(model="claude-opus-4-8", tin=1_000_000)), 5.0, places=2)

    def test_fable_is_priced_above_opus(self):
        self.assertAlmostEqual(
            cost.est(rec(model="claude-fable-5", tout=1_000_000)), 50.0, places=2)

    def test_fast_mode_is_a_premium_rate(self):
        self.assertAlmostEqual(
            cost.est(rec(model="claude-opus-5", tout=1_000_000, speed="fast")),
            50.0, places=2)

    def test_unknown_model_falls_back_to_default(self):
        # an unrecognized model uses the sonnet default price
        self.assertAlmostEqual(
            cost.est(rec(model="mystery-9", tout=1_000_000, ts=LAPSED)),
            15.0, places=2)


class TestCacheRates(unittest.TestCase):
    """cache rates are multiples of the tier's base input rate. a 1h write
    costs 2x base and a 5m write 1.25x — pricing every write at 1.25x
    understated long runs, which write almost entirely at 1h."""

    def test_read_is_a_tenth_of_input(self):
        self.assertAlmostEqual(
            cost.est(rec(model="claude-opus-5", cr=1_000_000)), 0.50, places=2)

    def test_write_defaults_to_the_5m_rate(self):
        # no cache_creation split recorded -> 1.25x base
        self.assertAlmostEqual(
            cost.est(rec(model="claude-opus-5", cw=1_000_000)), 6.25, places=2)

    def test_a_1h_write_costs_double_base(self):
        self.assertAlmostEqual(
            cost.est(rec(model="claude-opus-5", cw=1_000_000, cw1h=1_000_000)),
            10.0, places=2)

    def test_mixed_ttls_are_priced_separately(self):
        # 1M at 1h (2x) + 1M at 5m (1.25x) on opus = 10.00 + 6.25
        self.assertAlmostEqual(
            cost.est(rec(model="claude-opus-5", cw=2_000_000, cw1h=1_000_000)),
            16.25, places=2)

    def test_records_carry_the_ttl_split(self):
        e = entry("a", "s")
        e["message"]["usage"]["cache_creation_input_tokens"] = 300
        e["message"]["usage"]["cache_creation"] = {
            "ephemeral_1h_input_tokens": 200, "ephemeral_5m_input_tokens": 100}
        r = cost.usage_records([{"type": "assistant", "uuid": "a",
                                 "msg": e["message"], "ts": e["timestamp"]}])[0]
        self.assertEqual((r["cw"], r["cw1h"]), (300, 200))


class TestAgg(unittest.TestCase):
    def test_sums_tokens_and_cached_pct(self):
        # cached = cr / (tin + cw + cr) = 900 / 1000 = 90%
        t = cost.agg([rec(tin=100, cr=900, tout=50), rec(tout=50)])
        self.assertEqual(t["tout"], 100)
        self.assertEqual(t["cr"], 900)
        self.assertAlmostEqual(t["cached_pct"], 90.0, places=1)

    def test_empty_is_zero(self):
        t = cost.agg([])
        self.assertEqual(t["usd"], 0.0)
        self.assertEqual(t["cached_pct"], 0)


class TestSubagentTranscripts(unittest.TestCase):
    """subagents keep their own <session>/subagents/agent-<id>.jsonl file and
    write nothing into the parent transcript — missing them zeroed the
    subagent half of every report while the statusline billed the whole run."""

    SID = "sess-1"

    def setUp(self):
        self.pdir = tempfile.mkdtemp()
        sub = os.path.join(self.pdir, self.SID, "subagents")
        os.makedirs(sub)
        self.write(os.path.join(self.pdir, self.SID + ".jsonl"),
                   [entry("orch-1", self.SID)])
        # own-file subagent: parent's sessionId, its own agentId
        self.write(os.path.join(sub, "agent-aaa.jsonl"),
                   [entry("sub-1", self.SID, isSidechain=True, agentId="aaa")])
        with open(os.path.join(sub, "agent-aaa.meta.json"), "w") as f:
            json.dump({"agentType": "Explore", "description": "Scout: wiring"}, f)

    def tearDown(self):
        shutil.rmtree(self.pdir, ignore_errors=True)

    def write(self, path, entries):
        with open(path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_counts_orchestrator_and_subagents(self):
        recs = cost.usage_records(cost.load(self.pdir))
        self.assertEqual(len(recs), 2)
        self.assertEqual(cost.agg([r for r in recs if not r["side"]])["tout"], 1000)
        self.assertEqual(cost.agg([r for r in recs if r["side"]])["tout"], 1000)

    def test_subagent_bills_to_parent_session(self):
        # the agent file is named agent-aaa, not <sid> — attribution comes
        # from the sessionId field, so a session total covers its subagents
        recs = cost.usage_records(cost.load(self.pdir))
        self.assertEqual({r["session"] for r in recs}, {self.SID})

    def test_chain_keyed_by_agent_id_and_labelled_from_meta(self):
        _, chains = cost.agent_chains(cost.load(self.pdir), self.SID)
        self.assertEqual(list(chains), ["aaa"])
        self.assertEqual(cost.agent_labels(self.pdir)["aaa"], "Scout: wiring")

    def test_legacy_in_parent_sidechains_still_group(self):
        # older sessions thread sidechains into the parent file with no
        # agentId; those walk up to their root instead
        self.write(os.path.join(self.pdir, "sess-2.jsonl"), [
            entry("root", "sess-2", isSidechain=True),
            entry("leaf", "sess-2", isSidechain=True, parentUuid="root"),
        ])
        _, chains = cost.agent_chains(cost.load(self.pdir), "sess-2")
        self.assertEqual(list(chains), ["root"])
        self.assertEqual(len(chains["root"]), 2)


class TestBilled(unittest.TestCase):
    """the as-billed figure comes from claude code via the statusline cache;
    the PRICES estimate is only the fallback."""

    def setUp(self):
        self.saved = os.environ.get("CLAUDE_CONFIG_DIR")
        self.cfg = tempfile.mkdtemp(prefix="sdd-cfg-")
        os.environ["CLAUDE_CONFIG_DIR"] = self.cfg
        self.root = tempfile.mkdtemp(prefix="sdd-repo-")
        # a transcript for one session, so the project's session ids are known
        self.pdir = os.path.join(self.cfg, "projects", cost.st.munge(self.root))
        os.makedirs(self.pdir)
        with open(os.path.join(self.pdir, "sess-1.jsonl"), "w") as f:
            f.write(json.dumps(entry("orch-1", "sess-1")) + "\n")
        self.cache = os.path.join(self.cfg, "statusline-cache")
        os.makedirs(self.cache)

    def tearDown(self):
        if self.saved is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = self.saved
        for d in (self.cfg, self.root):
            shutil.rmtree(d, ignore_errors=True)

    def cached(self, sid, usd, cwd=None, age=0.0):
        with open(os.path.join(self.cache, f"{sid}.json"), "w") as f:
            json.dump({"session_id": sid, "cwd": cwd or self.root,
                       "total_cost_usd": usd,
                       "updated_at": time.time() - age}, f)

    def test_no_cache_means_no_billed_figure(self):
        self.assertIsNone(cost.billed(self.root))
        self.assertIn(" est", cost.brief(self.root))

    def test_a_cached_session_is_used_as_billed(self):
        self.cached("sess-1", 4.25)
        b = cost.billed(self.root)
        self.assertAlmostEqual(b["session"], 4.25)
        self.assertEqual(b["session_id"], "sess-1")
        line = cost.brief(self.root)
        self.assertIn("session $4.25 billed", line)
        # the split can only ever be estimated — claude code bills a session
        self.assertIn("est)", line)

    def test_another_projects_session_is_ignored(self):
        self.cached("sess-elsewhere", 99.0, cwd="/somewhere/else")
        self.assertIsNone(cost.billed(self.root))

    def test_a_worktree_session_counts_by_cwd(self):
        """its transcripts live under a different project dir, so the session
        id will not match — the cwd being inside the repo is what saves it."""
        wt = os.path.join(self.root, ".claude", "worktrees", "sdd", "feat")
        self.cached("sess-wt", 2.5, cwd=wt)
        self.assertAlmostEqual(cost.billed(self.root)["session"], 2.5)

    def test_session_is_the_newest_and_day_only_counts_24h(self):
        self.cached("sess-old", 5.0, age=86400 * 2)
        self.cached("sess-1", 1.0, age=600)
        self.cached("sess-2", 2.0, age=10)
        b = cost.billed(self.root)
        self.assertAlmostEqual(b["session"], 2.0)   # newest update wins
        self.assertAlmostEqual(b["day"], 3.0)       # the 2-day-old one is out
        self.assertEqual(b["sessions"], 3)
        self.assertLess(b["age"], 60)

    def test_unreadable_cache_entries_are_skipped(self):
        with open(os.path.join(self.cache, "sess-bad.json"), "w") as f:
            f.write("{not json")
        self.cached("sess-1", 1.5)
        self.assertAlmostEqual(cost.billed(self.root)["session"], 1.5)

    def test_cost_parts_keeps_the_estimated_split(self):
        self.cached("sess-1", 7.0)
        p = cost.cost_parts(self.root)
        self.assertTrue(p["billed"])
        self.assertAlmostEqual(p["session"], 7.0)
        self.assertIsNotNone(p["orch"])          # still from the transcript
        self.assertNotAlmostEqual(p["session"], p["orch"] + p["agents"])

    def test_parts_without_any_data_at_all(self):
        empty = tempfile.mkdtemp()
        try:
            p = cost.cost_parts(empty)
            self.assertIsNone(p["session"])
            self.assertEqual(cost.brief(empty), "cost: no transcript data")
        finally:
            shutil.rmtree(empty, ignore_errors=True)


class TestContextWindow(unittest.TestCase):
    """occupancy only grows within a lifetime, and a session id outlives
    /clear — so peak must be measured since the last reset, not file-wide."""

    def setUp(self):
        # isolate from the real ~/.claude/settings.json, whose `model` alias
        # would otherwise decide the window under test
        self.saved = {k: os.environ.get(k)
                      for k in ("SDD_CONTEXT_WINDOW", "CLAUDE_CONFIG_DIR")}
        os.environ.pop("SDD_CONTEXT_WINDOW", None)
        self.cfg = tempfile.mkdtemp(prefix="sdd-cfg-")
        os.environ["CLAUDE_CONFIG_DIR"] = self.cfg

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.cfg, ignore_errors=True)

    def r(self, ctx, ts):
        return {"tin": 2, "cw": 1000, "cr": ctx - 1002, "ts": ts}

    def test_lifetimes_split_at_a_reset(self):
        recs = [self.r(c, f"2026-08-01T0{i}:00:00Z") for i, c in
                enumerate([50_000, 200_000, 300_000, 60_000, 90_000])]
        segs = cost.context_lifetimes(recs)
        self.assertEqual([len(s) for s in segs], [3, 2])
        self.assertEqual(cost.ctx_size(segs[-1][-1]), 90_000)

    def test_a_cache_rewrite_is_not_a_reset(self):
        # cr falls and cw rises; the SUM barely moves, so it stays one lifetime
        recs = [{"tin": 2, "cw": 0, "cr": 199_998, "ts": "2026-08-01T00:00:00Z"},
                {"tin": 2, "cw": 90_000, "cr": 108_000, "ts": "2026-08-01T01:00:00Z"}]
        self.assertEqual(len(cost.context_lifetimes(recs)), 1)

    def test_env_overrides_the_window(self):
        os.environ["SDD_CONTEXT_WINDOW"] = "1000000"
        self.assertEqual(cost.configured_window(), (1_000_000, "env"))

    def test_window_widens_past_what_was_observed(self):
        # a 200k assumption can never make occupancy read over 100%
        win, _ = cost.window_size(780_000)
        self.assertGreaterEqual(win, 780_000)

    def test_assumed_window_is_flagged(self):
        win, source = cost.window_size(10_000, root=tempfile.mkdtemp())
        self.assertEqual(win, 200_000)
        self.assertEqual(source, "default")

    def test_project_settings_declare_the_window(self):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, ".claude"))
        with open(os.path.join(root, ".claude", "settings.json"), "w") as f:
            json.dump({"model": "opus[1m]"}, f)
        self.assertEqual(cost.configured_window(root), (1_000_000, "project"))
        shutil.rmtree(root, ignore_errors=True)


class TestContextSession(unittest.TestCase):
    """WHOSE window --context reports. two terminals on one repo, and a run
    whose feature lives in a different repo than the session, both used to be
    answered wrong — the first by newest-wins, the second not at all."""

    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in
                      ("SDD_CONTEXT_WINDOW", "CLAUDE_CONFIG_DIR",
                       "CLAUDE_CODE_SESSION_ID")}
        os.environ.pop("SDD_CONTEXT_WINDOW", None)
        os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        self.cfg = tempfile.mkdtemp(prefix="sdd-cfg-")
        os.environ["CLAUDE_CONFIG_DIR"] = self.cfg
        os.environ["SDD_CONTEXT_WINDOW"] = "200000"
        # session A: the run, 100k in. session B: another terminal, 10k in.
        self.repo = tempfile.mkdtemp(prefix="sdd-repo-")
        self.write_session("A" * 8, self.repo, 100_000, "12:00:00")
        self.write_session("B" * 8, self.repo, 10_000, "13:00:00")

    def tearDown(self):
        for k, v in self.saved.items():
            os.environ.pop(k, None) if v is None else os.environ.update({k: v})
        shutil.rmtree(self.cfg, ignore_errors=True)
        shutil.rmtree(self.repo, ignore_errors=True)

    def write_session(self, session, root, ctx, clock, ndx=1):
        """one transcript with a single request whose input side sums to ctx."""
        pdir = os.path.join(self.cfg, "projects", cost.st.munge(root))
        os.makedirs(pdir, exist_ok=True)
        e = entry(f"u{session}{ndx}", session,
                  timestamp=f"2026-07-31T{clock}Z")
        e["message"]["usage"] = {"input_tokens": 2, "output_tokens": 10,
                                 "cache_creation_input_tokens": 1000,
                                 "cache_read_input_tokens": ctx - 1002}
        path = os.path.join(pdir, f"{session}.jsonl")
        with open(path, "a") as f:
            f.write(json.dumps(e) + "\n")
        return path

    def test_env_session_wins_over_newest(self):
        # B is newer, but A is the session asking — 100k, not 10k
        os.environ["CLAUDE_CODE_SESSION_ID"] = "A" * 8
        c = cost.context_usage(self.repo)
        self.assertEqual(c["used"], 100_000)
        self.assertEqual(c["session"], "A" * 8)
        self.assertTrue(c["pinned"])

    def test_explicit_session_beats_the_env(self):
        os.environ["CLAUDE_CODE_SESSION_ID"] = "A" * 8
        self.assertEqual(cost.context_usage(self.repo, "B" * 8)["used"], 10_000)

    def test_without_an_id_it_guesses_newest_and_says_so(self):
        c = cost.context_usage(self.repo)
        self.assertEqual(c["used"], 10_000)      # B, the newest — a guess
        self.assertFalse(c["pinned"])
        self.assertIn("session guessed", cost.context_brief(self.repo))

    def test_pin_env_off_ignores_the_callers_session(self):
        # the dashboard watches a RUN, not the shell it runs in
        os.environ["CLAUDE_CODE_SESSION_ID"] = "A" * 8
        c = cost.context_usage(self.repo, pin_env=False)
        self.assertEqual(c["used"], 10_000)
        self.assertFalse(c["pinned"])

    def test_cross_repo_run_is_found_by_session_id(self):
        # the feature lives here; the session's transcript is filed under the
        # repo it was LAUNCHED from, so this root has no project dir at all
        other = tempfile.mkdtemp(prefix="sdd-other-")
        try:
            os.environ["CLAUDE_CODE_SESSION_ID"] = "A" * 8
            self.assertIsNone(cost.projects_dir(other))
            c = cost.context_usage(other)
            self.assertEqual(c["used"], 100_000)
            self.assertTrue(c["pinned"])
        finally:
            shutil.rmtree(other, ignore_errors=True)

    def test_cross_repo_without_an_id_falls_back_to_newest_anywhere(self):
        other = tempfile.mkdtemp(prefix="sdd-other-")
        try:
            c = cost.context_usage(other)
            self.assertEqual(c["used"], 10_000)
            self.assertFalse(c["pinned"])
        finally:
            shutil.rmtree(other, ignore_errors=True)

    def test_no_transcripts_anywhere_is_still_none(self):
        shutil.rmtree(os.path.join(self.cfg, "projects"))
        self.assertIsNone(cost.context_usage(self.repo))
        self.assertEqual(cost.context_brief(self.repo), "context: no transcript data")

    def test_pinned_reading_uses_the_last_lifetime_only(self):
        # a /clear keeps the session id: occupancy drops, and the reading must
        # follow the new lifetime rather than the file-wide peak
        os.environ["CLAUDE_CODE_SESSION_ID"] = "A" * 8
        self.write_session("A" * 8, self.repo, 20_000, "14:00:00", ndx=2)
        c = cost.context_usage(self.repo)
        self.assertEqual((c["used"], c["resets"]), (20_000, 1))

    def test_subagent_turns_never_count(self):
        # a subagent's window dies with it — no /clear could act on it
        os.environ["CLAUDE_CODE_SESSION_ID"] = "A" * 8
        pdir = os.path.join(self.cfg, "projects", cost.st.munge(self.repo))
        e = entry("side1", "A" * 8, timestamp="2026-07-31T15:00:00Z",
                  isSidechain=True)
        e["message"]["usage"] = {"input_tokens": 900_000, "output_tokens": 1}
        with open(os.path.join(pdir, f"{'A' * 8}.jsonl"), "a") as f:
            f.write(json.dumps(e) + "\n")
        self.assertEqual(cost.context_usage(self.repo)["used"], 100_000)


class TestFmtTok(unittest.TestCase):
    def test_scales_by_magnitude(self):
        self.assertEqual(cost.fmt_tok(500), "500")
        self.assertEqual(cost.fmt_tok(5000), "5k")
        self.assertEqual(cost.fmt_tok(2_500_000), "2.5M")


if __name__ == "__main__":
    unittest.main()
