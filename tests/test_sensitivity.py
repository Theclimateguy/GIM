"""Tests for global sensitivity analysis (Phase 1-D).

Correctness is checked against the analytical Ishigami benchmark, whose Sobol indices are
known in closed form (a=7, b=0.1): S1=[0.314, 0.442, 0.0], ST=[0.557, 0.442, 0.244].
"""

import math
import unittest

import numpy as np

from gim.core.priors import key_priors
from gim.sensitivity import bounds_for, make_output_fn, morris, rank, sobol

NAMES = ["x1", "x2", "x3"]
BOUNDS = [(-math.pi, math.pi)] * 3


def _ishigami(d):
    return math.sin(d["x1"]) + 7.0 * math.sin(d["x2"]) ** 2 + 0.1 * (d["x3"] ** 4) * math.sin(d["x1"])


class SobolIshigamiTests(unittest.TestCase):
    def setUp(self):
        self.s = sobol(NAMES, BOUNDS, _ishigami, n_base=16000, seed=1)

    def test_first_order_matches_analytic(self):
        self.assertAlmostEqual(self.s["x1"]["S1"], 0.314, delta=0.04)
        self.assertAlmostEqual(self.s["x2"]["S1"], 0.442, delta=0.04)
        self.assertAlmostEqual(self.s["x3"]["S1"], 0.0, delta=0.04)

    def test_total_order_matches_analytic(self):
        self.assertAlmostEqual(self.s["x1"]["ST"], 0.557, delta=0.05)
        self.assertAlmostEqual(self.s["x2"]["ST"], 0.442, delta=0.05)
        self.assertAlmostEqual(self.s["x3"]["ST"], 0.244, delta=0.05)

    def test_x3_is_pure_interaction(self):
        # x3 has ~zero first-order but substantial total-order (interaction with x1).
        self.assertGreater(self.s["x3"]["ST"], self.s["x3"]["S1"] + 0.15)


class MorrisIshigamiTests(unittest.TestCase):
    def setUp(self):
        self.m = morris(NAMES, BOUNDS, _ishigami, r=150, levels=8, seed=1)

    def test_x1_is_most_influential(self):
        self.assertEqual(rank(self.m, "mu_star")[0][0], "x1")

    def test_interaction_shows_as_sigma(self):
        # x2 has no interaction (low sigma); x3 interacts strongly (high sigma).
        self.assertLess(self.m["x2"]["sigma"], self.m["x3"]["sigma"])


class ModelSensitivityTests(unittest.TestCase):
    def test_climate_response_params_dominate_temperature(self):
        kp = key_priors()
        names = ["ECS_DEFAULT", "HEAT_CAP_SURFACE", "EMISSIONS_SCALE", "GAMMA_ENERGY"]
        fn = make_output_fn(
            "temperature",
            "data/agent_states_operational_2026_calibrated.csv",
            years=5,
            max_agents=8,
            seed=2026,
        )
        res = morris(names, bounds_for(kp, names), fn, r=5, levels=4, seed=1)
        top2 = {n for n, _ in rank(res, "mu_star")[:2]}
        # The two climate-response parameters must dominate temperature sensitivity.
        self.assertEqual(top2, {"ECS_DEFAULT", "HEAT_CAP_SURFACE"})


if __name__ == "__main__":
    unittest.main()
