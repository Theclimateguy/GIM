"""Tests for the criticality early-warning layer (F5)."""

import math
import random
import unittest

from gim.criticality import early_warning_scan, early_warning_score, rolling_indicators


def _stationary(n=80, seed=1):
    rng = random.Random(seed)
    return [rng.gauss(0.0, 1.0) for _ in range(n)]


def _approaching_transition(n=120, seed=1):
    # AR(1) with rho rising 0 -> ~0.95 and FIXED innovation variance: this is true critical
    # slowing down - both lag-1 autocorrelation AND variance (sigma^2/(1-rho^2)) rise.
    rng = random.Random(seed)
    x, prev = [], 0.0
    for t in range(n):
        rho = 0.95 * t / (n - 1)
        prev = rho * prev + rng.gauss(0.0, 1.0)
        x.append(prev)
    return x


class EarlyWarningTests(unittest.TestCase):
    def test_stationary_series_gives_no_warning(self):
        score = early_warning_score(_stationary())
        self.assertFalse(score["warning"])

    def test_approaching_transition_is_flagged(self):
        score = early_warning_score(_approaching_transition())
        self.assertGreater(score["autocorr_trend"], 0.3)
        self.assertTrue(score["warning"])

    def test_rolling_indicators_length(self):
        roll = rolling_indicators(list(range(20)), window=8)
        self.assertEqual(len(roll["autocorrelation"]), 20 - 8 + 1)

    def test_scan_multiple_series(self):
        out = early_warning_scan({"calm": _stationary(), "tipping": _approaching_transition()})
        self.assertFalse(out["calm"]["warning"])
        self.assertTrue(out["tipping"]["warning"])


if __name__ == "__main__":
    unittest.main()
