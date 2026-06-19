"""Tests for the Social Cost of Carbon pulse experiment (Phase 3-B/C)."""

import unittest

from gim.scc import scc_distribution, scc_multi_horizon, social_cost_of_carbon

CSV = "data/agent_states_operational_2026_calibrated.csv"


class SCCTests(unittest.TestCase):
    def test_scc_positive_and_in_plausible_range(self):
        r = social_cost_of_carbon(CSV, years=20, pulse_gtco2=10.0, max_agents=15, seed=2026)
        scc = r["scc_usd_per_tco2"]
        self.assertGreater(scc, 0.0)            # a CO2 pulse causes net damage
        self.assertLess(scc, 1000.0)            # plausible order of magnitude ($/tCO2)

    def test_marginality_pulse_size_invariant(self):
        a = social_cost_of_carbon(CSV, years=20, pulse_gtco2=10.0, max_agents=15, seed=2026)
        b = social_cost_of_carbon(CSV, years=20, pulse_gtco2=5.0, max_agents=15, seed=2026)
        # Per-ton SCC must be ~invariant to (small) pulse size — confirms marginality/linearity.
        self.assertAlmostEqual(a["scc_usd_per_tco2"], b["scc_usd_per_tco2"], delta=0.05 * a["scc_usd_per_tco2"])

    def test_deterministic(self):
        a = social_cost_of_carbon(CSV, years=15, max_agents=12, seed=2026)
        b = social_cost_of_carbon(CSV, years=15, max_agents=12, seed=2026)
        self.assertEqual(a["scc_usd_per_tco2"], b["scc_usd_per_tco2"])


class SCCHorizonTests(unittest.TestCase):
    def test_scc_rises_with_horizon(self):
        # T1.4: longer horizons capture more of the long-run damage tail -> higher SCC.
        h = scc_multi_horizon(CSV, horizons=(15, 60), max_agents=12, seed=2026)
        self.assertEqual(set(h), {15, 60})
        self.assertGreater(h[60], h[15])
        self.assertGreater(h[60], 0.0)


class SCCDistributionTests(unittest.TestCase):
    def test_distribution_shape(self):
        d = scc_distribution(CSV, n_samples=8, years=15, max_agents=12, master_seed=2026)
        self.assertEqual(d["n_samples"], 8)
        p = d["percentiles"]
        self.assertLessEqual(p["p5"], p["p50"])
        self.assertLessEqual(p["p50"], p["p95"])
        self.assertGreater(p["p50"], 0.0)


if __name__ == "__main__":
    unittest.main()
