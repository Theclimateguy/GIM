"""Tests for forecast skill scoring (Phase 2-A)."""

import math
import unittest

from gim.scoring import (
    crps_ensemble,
    interval_coverage,
    mae,
    persistence_forecast,
    rmse,
    score_series,
    skill_score,
    trend_forecast,
)


class PointScoreTests(unittest.TestCase):
    def test_rmse_and_mae(self):
        pred = {2015: 1.0, 2016: 2.0, 2017: 3.0}
        obs = {2015: 1.0, 2016: 3.0, 2017: 3.0}
        self.assertAlmostEqual(mae(pred, obs), 1.0 / 3)
        self.assertAlmostEqual(rmse(pred, obs), math.sqrt(1.0 / 3))

    def test_perfect_prediction_zero_error(self):
        s = {2015: 5.0, 2016: 6.0}
        self.assertEqual(rmse(s, s), 0.0)


class CRPSTests(unittest.TestCase):
    def test_single_member_is_mae(self):
        self.assertAlmostEqual(crps_ensemble(3.0, [5.0]), 2.0)

    def test_crps_nonnegative_and_sharper_when_centered(self):
        centered = crps_ensemble(0.0, [-1.0, 0.0, 1.0])
        biased = crps_ensemble(0.0, [4.0, 5.0, 6.0])
        self.assertGreaterEqual(centered, 0.0)
        self.assertLess(centered, biased)


class CoverageTests(unittest.TestCase):
    def test_coverage_fraction(self):
        obs = {1: 0.5, 2: 0.5, 3: 5.0}
        lo = {1: 0.0, 2: 0.0, 3: 0.0}
        hi = {1: 1.0, 2: 1.0, 3: 1.0}
        self.assertAlmostEqual(interval_coverage(obs, lo, hi), 2.0 / 3)


class BaselineTests(unittest.TestCase):
    def test_persistence_carries_anchor(self):
        obs = {2015: 10.0, 2016: 12.0, 2017: 14.0}
        p = persistence_forecast(obs, 2015)
        self.assertEqual(p[2016], 10.0)
        self.assertEqual(p[2017], 10.0)

    def test_trend_fits_linear_series_exactly(self):
        obs = {y: 2.0 * y - 100.0 for y in range(2015, 2024)}
        t = trend_forecast(obs, list(range(2015, 2019)))
        self.assertAlmostEqual(rmse(t, obs), 0.0, places=6)

    def test_skill_score_sign(self):
        self.assertGreater(skill_score(0.5, 1.0), 0.0)   # model better
        self.assertLess(skill_score(2.0, 1.0), 0.0)      # model worse


class ScoreSeriesTests(unittest.TestCase):
    def test_structure_and_perfect_model_beats_persistence(self):
        obs = {2015: 1.0, 2016: 2.0, 2017: 3.0, 2018: 4.0}
        s = score_series(obs, obs, anchor_year=2015, train_years=[2015, 2016])
        self.assertEqual(
            set(s),
            {"model_rmse", "persistence_rmse", "trend_rmse", "skill_vs_persistence", "skill_vs_trend"},
        )
        self.assertEqual(s["model_rmse"], 0.0)         # model == obs
        self.assertAlmostEqual(s["skill_vs_persistence"], 1.0)  # perfect skill


if __name__ == "__main__":
    unittest.main()
