"""tests for cost's token aggregation and price-table estimate."""
import unittest

from helpers import load_module

cost = load_module("cost", "bin/sdd-cost")


def rec(model="claude-sonnet-5", tin=0, tout=0, cw=0, cr=0):
    return {"model": model, "tin": tin, "tout": tout, "cw": cw, "cr": cr}


class TestEstimate(unittest.TestCase):
    def test_sonnet_output_rate(self):
        # 1M sonnet output tokens at $15/M
        self.assertAlmostEqual(cost.est(rec(tout=1_000_000)), 15.0, places=2)

    def test_opus_input_rate(self):
        # 1M opus input tokens at $5/M
        self.assertAlmostEqual(
            cost.est(rec(model="claude-opus-4-8", tin=1_000_000)), 5.0, places=2)

    def test_unknown_model_falls_back_to_default(self):
        # an unrecognized model uses the sonnet default price
        self.assertAlmostEqual(
            cost.est(rec(model="mystery-9", tout=1_000_000)), 15.0, places=2)


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


class TestFmtTok(unittest.TestCase):
    def test_scales_by_magnitude(self):
        self.assertEqual(cost.fmt_tok(500), "500")
        self.assertEqual(cost.fmt_tok(5000), "5k")
        self.assertEqual(cost.fmt_tok(2_500_000), "2.5M")


if __name__ == "__main__":
    unittest.main()
