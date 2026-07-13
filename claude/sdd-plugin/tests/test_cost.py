"""tests for cost's calibration and actuals loading."""
import json
import os
import tempfile
import unittest
from unittest import mock

from helpers import load_module

cost = load_module("cost", "bin/sdd-cost")


def rec(session, usd_estimate):
    """a usage record whose est() lands at usd_estimate (output tokens on
    the sonnet base rate of $15/M)."""
    return {"session": session, "model": "claude-sonnet-5",
            "tin": 0, "tout": int(usd_estimate / 15.0 * 1e6),
            "cw": 0, "cr": 0}


class TestCalibration(unittest.TestCase):
    def test_median_ratio(self):
        recs = [rec("s1", 1.0), rec("s2", 1.0), rec("s3", 1.0)]
        actuals = {"s1": {"usd": 2.0}, "s2": {"usd": 3.0},
                   "s3": {"usd": 4.0}}
        factor, n = cost.calibration(recs, actuals)
        self.assertEqual(n, 3)
        self.assertAlmostEqual(factor, 3.0, places=1)

    def test_no_actuals_means_factor_one(self):
        factor, n = cost.calibration([rec("s1", 1.0)], {})
        self.assertEqual((factor, n), (1.0, 0))

    def test_tiny_sessions_excluded(self):
        # sub-$0.10 sessions carry no calibration signal
        factor, n = cost.calibration([rec("s1", 0.05)],
                                     {"s1": {"usd": 5.0}})
        self.assertEqual(n, 0)


class TestLoadActuals(unittest.TestCase):
    def test_merges_legacy_and_current(self):
        with tempfile.TemporaryDirectory() as proj, \
                tempfile.TemporaryDirectory() as cfg:
            legacy = os.path.join(proj, ".claude")
            os.makedirs(legacy)
            with open(os.path.join(legacy, ".cost-actuals.json"), "w") as f:
                json.dump({"old": {"usd": 1.0}, "both": {"usd": 1.0}}, f)
            with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": cfg}):
                cur = cost.st.actuals_path(proj)
                os.makedirs(os.path.dirname(cur))
                with open(cur, "w") as f:
                    json.dump({"new": {"usd": 2.0}, "both": {"usd": 2.0}}, f)
                data = cost.load_actuals(proj)
        self.assertEqual(data["old"]["usd"], 1.0)
        self.assertEqual(data["new"]["usd"], 2.0)
        self.assertEqual(data["both"]["usd"], 2.0)  # current wins

    def test_missing_files_give_empty(self):
        with tempfile.TemporaryDirectory() as proj, \
                tempfile.TemporaryDirectory() as cfg:
            with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": cfg}):
                self.assertEqual(cost.load_actuals(proj), {})


class TestActualsPathIsOutsideProject(unittest.TestCase):
    def test_cache_never_lands_in_repo(self):
        with tempfile.TemporaryDirectory() as proj, \
                tempfile.TemporaryDirectory() as cfg:
            with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": cfg}):
                path = cost.st.actuals_path(proj)
            self.assertTrue(path.startswith(cfg))
            self.assertFalse(path.startswith(proj))


if __name__ == "__main__":
    unittest.main()
