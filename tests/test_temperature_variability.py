"""Tests for AR(1) red-noise internal temperature variability (T2.4)."""

import statistics
import unittest

from gim.core.climate import _sample_temperature_variability
from gim.core.params import build_params
from gim.core.world_factory import make_world_from_csv

STATE_CSV = "data/agent_states_operational_2026_calibrated.csv"


def _series(rho, seed, n=600, sigma=0.08):
    w = make_world_from_csv(STATE_CSV, max_agents=2, base_year=2000)
    w.params = build_params().with_overrides({"TEMP_NATURAL_VARIABILITY_AR1_RHO": rho})
    w.global_state._temperature_variability_sigma = sigma
    w.global_state._temperature_variability_seed = seed
    w.global_state._temperature_variability_state = 0.0
    out = []
    for t in range(n):
        w.time = t
        out.append(_sample_temperature_variability(w, 1.0))
    return out


def _lag1(s):
    m = statistics.mean(s)
    denom = sum((x - m) ** 2 for x in s)
    return sum((s[i] - m) * (s[i + 1] - m) for i in range(len(s) - 1)) / denom


class AR1Tests(unittest.TestCase):
    def test_lag1_autocorrelation_tracks_rho(self):
        self.assertAlmostEqual(_lag1(_series(0.65, 123)), 0.65, delta=0.08)

    def test_rho_zero_is_iid(self):
        self.assertAlmostEqual(_lag1(_series(0.0, 123)), 0.0, delta=0.08)

    def test_stationary_std_preserved(self):
        # sqrt(1-rho^2) scaling keeps the marginal std ~ sigma regardless of rho.
        self.assertAlmostEqual(statistics.pstdev(_series(0.65, 99)), 0.08, delta=0.02)

    def test_antithetic_pairs_are_exact_mirrors(self):
        def run(sign):
            w = make_world_from_csv(STATE_CSV, max_agents=2, base_year=2000)
            w.params = build_params()
            w.global_state._temperature_variability_sigma = 0.08
            w.global_state._temperature_variability_seed = 7
            w.global_state._temperature_variability_sign = sign
            w.global_state._temperature_variability_state = 0.0
            return [(_setattr_time(w, t), _sample_temperature_variability(w, 1.0))[1] for t in range(6)]

        a, b = run(1.0), run(-1.0)
        for x, y in zip(a, b):
            self.assertAlmostEqual(x + y, 0.0, places=15)

    def test_deterministic(self):
        self.assertEqual(_series(0.65, 42, n=20), _series(0.65, 42, n=20))


def _setattr_time(world, t):
    world.time = t
    return None


if __name__ == "__main__":
    unittest.main()
