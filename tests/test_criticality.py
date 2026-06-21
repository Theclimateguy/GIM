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


class LiveEWSTests(unittest.TestCase):
    def test_run_and_scan_structure_and_calm_baseline(self):
        from gim.criticality import run_and_scan

        rep = run_and_scan(years=25, max_agents=10, window=8)
        for key in ("world_gdp", "mean_social_tension", "mean_regime_stability", "max_debt_gdp"):
            self.assertIn(key, rep)
            self.assertIn("combined", rep[key])
            self.assertIn("warning", rep[key])
        # A stable baseline projection should not raise a critical-slowing-down warning.
        self.assertFalse(rep["world_gdp"]["warning"])


class PowerLawSeverityTests(unittest.TestCase):
    def test_severity_is_mean_one_and_fat_tailed(self):
        from gim.criticality import powerlaw_severity

        rng = random.Random(7)
        s = [powerlaw_severity(rng, alpha=1.5, a=1.0, b=20.0) for _ in range(40000)]
        mean = sum(s) / len(s)
        self.assertAlmostEqual(mean, 1.0, delta=0.06)          # golden-neutral on average
        p99 = sorted(s)[int(0.99 * len(s))]
        self.assertGreater(p99, 3.0)                            # heavy upper tail
        self.assertGreater(sum(1 for v in s if v < 0.5) / len(s), 0.2)  # most events milder

    def test_crisis_severity_toggle(self):
        from types import SimpleNamespace
        from gim.core.social import _crisis_severity

        world = SimpleNamespace()  # not used when disabled
        off = SimpleNamespace(CRISIS_SEVERITY_POWERLAW=False)
        self.assertEqual(_crisis_severity(world, off), 1.0)


if __name__ == "__main__":
    unittest.main()
