"""Weak-signal detection (analyst-tier): Mahalanobis anomaly + structural-break change-point.

Validates the detectors on synthetic ground-truth (stationary -> quiet; injected anomaly / mean-shift
-> detected at the right place) and confirms the combined scan detrends trending GIM-style series so it
flags departures from the dynamics rather than the secular trend. numpy-only, no scipy.
"""
import unittest

try:
    import numpy as np
    _HAVE_NUMPY = True
except ImportError:  # pragma: no cover
    _HAVE_NUMPY = False


@unittest.skipUnless(_HAVE_NUMPY, "weak_signal is analysis-tier (needs numpy)")
class WeakSignalTests(unittest.TestCase):
    def test_chi2_ppf_matches_known_quantiles(self):
        from gim.weak_signal import _chi2_ppf
        # Known chi-square 0.99 quantiles: df1=6.63, df5=15.09, df10=23.21.
        self.assertAlmostEqual(_chi2_ppf(0.99, 1), 6.63, delta=0.2)
        self.assertAlmostEqual(_chi2_ppf(0.99, 5), 15.09, delta=0.3)
        self.assertAlmostEqual(_chi2_ppf(0.99, 10), 23.21, delta=0.4)

    def test_mahalanobis_flags_injected_anomalies_not_baseline(self):
        from gim.weak_signal import mahalanobis_scores
        rng = np.random.default_rng(0)
        base = rng.normal(0, 1, (40, 3))
        anom = rng.normal(6, 1, (5, 3))  # far from baseline distribution
        X = np.vstack([base, anom])
        m = mahalanobis_scores(X, ref_rows=40, alpha=0.99)
        self.assertEqual(sum(m["anomaly"][-5:]), 5)          # all injected anomalies flagged
        self.assertLessEqual(sum(m["anomaly"][:40]), 2)       # ~chi-square false-positive rate

    def test_structural_break_detects_mean_shift_at_location(self):
        from gim.weak_signal import structural_break
        rng = np.random.default_rng(1)
        series = np.concatenate([rng.normal(0, 0.3, 20), rng.normal(2.0, 0.3, 20)])
        sb = structural_break(series)
        self.assertGreater(sb["break_prob"], 0.9)
        self.assertAlmostEqual(sb["location"], 20, delta=2)

    def test_structural_break_shift_scores_above_noise(self):
        from gim.weak_signal import structural_break
        rng = np.random.default_rng(2)
        shift = np.concatenate([rng.normal(0, 0.3, 20), rng.normal(2.0, 0.3, 20)])
        noise = rng.normal(0, 0.3, 40)
        self.assertGreater(structural_break(shift)["break_prob"],
                           structural_break(noise)["break_prob"])

    def test_scan_detrends_trending_series(self):
        # A pure linear trend has no anomalies in its *dynamics*; detrended scan should be near-silent,
        # whereas scanning raw levels re-detects the trend as one long anomaly.
        from gim.weak_signal import weak_signal_scan
        trend = [float(t) for t in range(40)]
        flat = [1.0] * 40
        det = weak_signal_scan({"a": trend, "b": flat}, detrend=True)
        raw = weak_signal_scan({"a": trend, "b": flat}, detrend=False)
        self.assertLess(det["mahalanobis"]["n_anomalies"], raw["mahalanobis"]["n_anomalies"])

    def test_scan_detects_injected_shock(self):
        from gim.weak_signal import weak_signal_scan
        rng = np.random.default_rng(3)
        gdp = list(100.0 * np.cumprod(1 + rng.normal(0.02, 0.005, 30)))  # smooth growth
        gdp = [g * (0.85 if i >= 20 else 1.0) for i, g in enumerate(gdp)]  # -15% shock at t=20
        rep = weak_signal_scan({"gdp": gdp})
        self.assertGreater(rep["structural_breaks"]["gdp"]["break_prob"], 0.9)
        self.assertAlmostEqual(rep["structural_breaks"]["gdp"]["location"], 19, delta=2)

    def test_scan_returns_expected_structure(self):
        from gim.weak_signal import weak_signal_scan
        rep = weak_signal_scan({"x": list(range(10)), "y": [i * 0.5 for i in range(10)]})
        self.assertEqual(set(rep) >= {"mahalanobis", "structural_breaks", "early_warning",
                                       "dimensions"}, True)
        self.assertEqual(set(rep["dimensions"]), {"x", "y"})


if __name__ == "__main__":
    unittest.main()
