"""S4 — conflict forecast-skill benchmark: Brier decomposition + calibration + reference comparison.

Unit-tested on synthetic deterministic data (no dependency on the UCDP file): the Murphy identity
Brier = reliability - resolution + uncertainty must hold; a perfectly-calibrated forecast must have
~zero reliability error; and the published-reference comparator must place above-chance skill correctly.
"""

import unittest

from gim.conflict_benchmark import (
    PUBLISHED_BENCHMARKS,
    brier_decomposition,
    calibration_curve,
    compare_to_benchmarks,
)


class S4ConflictBenchmarkTests(unittest.TestCase):
    def test_murphy_identity_exact_for_single_valued_bins(self):
        # one distinct forecast per 0.1-wide bin -> the binned Murphy identity holds exactly
        probs = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95] * 4
        labels = [0, 0, 0, 1, 0, 1, 1, 1, 1, 1] * 4
        d = brier_decomposition(probs, labels, n_bins=10)
        identity = d["reliability"] - d["resolution"] + d["uncertainty"]
        self.assertAlmostEqual(d["brier"], identity, places=9)

    def test_uncertainty_is_base_rate_variance(self):
        labels = [1, 1, 1, 0, 0, 0, 0, 0, 0, 0]  # base rate 0.3
        d = brier_decomposition([0.5] * 10, labels, n_bins=10)
        self.assertAlmostEqual(d["uncertainty"], 0.3 * 0.7, places=9)

    def test_perfect_calibration_has_low_reliability_error(self):
        # bins whose forecast equals the in-bin frequency -> reliability ~ 0
        probs, labels = [], []
        for p, n_pos, n_tot in [(0.2, 2, 10), (0.5, 5, 10), (0.8, 8, 10)]:
            probs += [p] * n_tot
            labels += [1] * n_pos + [0] * (n_tot - n_pos)
        d = brier_decomposition(probs, labels, n_bins=10)
        self.assertLess(d["reliability"], 1e-9)
        self.assertLess(d["calibration_error"], 1e-9)
        self.assertGreater(d["resolution"], 0.0)

    def test_calibration_curve_bins(self):
        probs = [0.1, 0.1, 0.9, 0.9]
        labels = [0, 0, 1, 1]
        curve = calibration_curve(probs, labels, n_bins=10)
        self.assertEqual(len(curve), 2)
        # perfectly separated -> observed freq is 0 in the low bin, 1 in the high bin
        self.assertEqual(curve[0][1], 0.0)
        self.assertEqual(curve[1][1], 1.0)

    def test_benchmark_comparator_places_gim_skill(self):
        cmp = compare_to_benchmarks(auc=0.736, bss=0.143)
        self.assertTrue(cmp["above_chance"])
        self.assertLessEqual(cmp["reference_auc_band"][0], cmp["reference_auc_band"][1])
        self.assertTrue(all("model" in b and b["auc_approx"] > 0.5 for b in PUBLISHED_BENCHMARKS))

    def test_no_skill_flagged(self):
        cmp = compare_to_benchmarks(auc=0.5, bss=-0.01)
        self.assertFalse(cmp["above_chance"])


if __name__ == "__main__":
    unittest.main()
