"""Tests for history-matching calibration (Phase 2-B)."""

import unittest

from gim.calibration_hm import (
    DEFAULT_CALIBRATION_PARAMS,
    DEFAULT_TOLERANCES,
    backtest_rmses,
    constrained_priors,
    history_match,
    implausibility,
)
from gim.core.priors import key_priors


class ImplausibilityTests(unittest.TestCase):
    def test_max_over_outputs(self):
        rmses = {"world_gdp": 3.0, "global_co2": 1.0, "temperature": 0.30}
        imp = implausibility(rmses, DEFAULT_TOLERANCES)
        # gdp 3/6=0.5, co2 1/2=0.5, temp 0.30/0.15=2.0 -> max 2.0
        self.assertAlmostEqual(imp["temperature"], 2.0)
        self.assertAlmostEqual(imp["max"], 2.0)

    def test_small_errors_are_plausible(self):
        rmses = {"world_gdp": 1.0, "global_co2": 0.5, "temperature": 0.1}
        self.assertLess(implausibility(rmses)["max"], 3.0)


class BacktestRmseTests(unittest.TestCase):
    def test_default_backtest_rmses_reasonable(self):
        r = backtest_rmses({})
        self.assertLess(r["temperature"], 0.25)
        self.assertLess(r["global_co2"], 3.0)
        self.assertGreater(r["world_gdp"], 0.0)

    def test_override_changes_co2(self):
        base = backtest_rmses({})
        scaled = backtest_rmses({"EMISSIONS_SCALE": 1.05})
        self.assertNotAlmostEqual(base["global_co2"], scaled["global_co2"], places=4)


class HistoryMatchTests(unittest.TestCase):
    def test_runs_and_constrains(self):
        res = history_match(n_samples=6, threshold=3.0, seed=2026)
        self.assertEqual(len(res.members), 6)
        self.assertLessEqual(len(res.nroy()), 6)
        cons = res.constraints()
        for n in DEFAULT_CALIBRATION_PARAMS:
            self.assertIn(n, cons)
            self.assertLess(cons[n]["prior_min"], cons[n]["prior_max"])
        best = res.to_dict()["best"]
        self.assertTrue(0.0 <= best["implausibility"]["max"] < float("inf"))

    def test_deterministic(self):
        a = history_match(n_samples=5, seed=2026)
        b = history_match(n_samples=5, seed=2026)
        self.assertEqual(
            a.to_dict()["best"]["implausibility"]["max"],
            b.to_dict()["best"]["implausibility"]["max"],
        )


class ConstrainedPriorsTests(unittest.TestCase):
    def test_nroy_priors_are_within_base_bounds(self):
        res = history_match(n_samples=8, seed=2026)
        base = key_priors()
        cp = constrained_priors(res, base)
        # Calibrated params' constrained priors must lie within the original prior support.
        for name in res.names:
            self.assertGreaterEqual(cp[name].low, base[name].low - 1e-9)
            self.assertLessEqual(cp[name].high, base[name].high + 1e-9)
        # Non-calibrated key priors are unchanged.
        self.assertEqual(cp["BASE_BIRTH_RATE"].low, base["BASE_BIRTH_RATE"].low)


if __name__ == "__main__":
    unittest.main()
