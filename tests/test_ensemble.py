"""Tests for the Monte-Carlo ensemble runtime (Phase 1-C)."""

import math
import unittest

from gim.ensemble import DEFAULT_PERCENTILES, METRICS, EnsembleConfig, run_ensemble

STATE_CSV = "data/agent_states_operational_2026_calibrated.csv"


def _cfg(**kw):
    base = dict(
        state_csv=STATE_CSV,
        n_members=12,
        years=3,
        max_agents=8,
        master_seed=2026,
        prior_set="key",
        n_jobs=1,
    )
    base.update(kw)
    return EnsembleConfig(**base)


class EnsembleShapeTests(unittest.TestCase):
    def setUp(self):
        self.res = run_ensemble(_cfg())

    def test_bands_present_for_all_metrics(self):
        self.assertEqual(self.res.n_members, 12)
        self.assertEqual(len(self.res.years), 4)  # years + 1 (incl. initial)
        for m in METRICS:
            self.assertIn(m, self.res.bands)
            for key in ("p5", "p25", "p50", "p75", "p95", "mean"):
                self.assertEqual(len(self.res.bands[m][key]), 4)

    def test_percentiles_are_monotone(self):
        for m in METRICS:
            b = self.res.bands[m]
            for t in range(len(self.res.years)):
                self.assertLessEqual(b["p5"][t], b["p50"][t] + 1e-9, m)
                self.assertLessEqual(b["p50"][t], b["p95"][t] + 1e-9, m)

    def test_uncertainty_is_propagated(self):
        # Temperature spread must be > 0 by the final year (ECS/heat-capacity priors propagate).
        temp = self.res.bands["temperature"]
        self.assertGreater(temp["p95"][-1] - temp["p5"][-1], 0.0)

    def test_to_dict_shape(self):
        d = self.res.to_dict()
        self.assertEqual(set(d), {"config", "years", "n_members", "metrics", "percentiles"})
        self.assertEqual(d["percentiles"], list(DEFAULT_PERCENTILES))


class EnsembleDeterminismTests(unittest.TestCase):
    def test_two_runs_identical(self):
        a = run_ensemble(_cfg())
        b = run_ensemble(_cfg())
        for m in METRICS:
            self.assertEqual(a.bands[m]["p50"], b.bands[m]["p50"], m)

    def test_serial_equals_parallel(self):
        ser = run_ensemble(_cfg(n_members=8, n_jobs=1))
        par = run_ensemble(_cfg(n_members=8, n_jobs=2))
        for m in METRICS:
            for key in ("p5", "p50", "p95", "mean"):
                for x, y in zip(ser.bands[m][key], par.bands[m][key]):
                    self.assertTrue(math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-12), m)

    def test_different_seed_differs(self):
        a = run_ensemble(_cfg(master_seed=1))
        b = run_ensemble(_cfg(master_seed=2))
        self.assertNotEqual(a.bands["temperature"]["p50"], b.bands["temperature"]["p50"])


if __name__ == "__main__":
    unittest.main()
