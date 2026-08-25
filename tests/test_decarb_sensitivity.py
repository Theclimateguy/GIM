import unittest

from gim.decarb_sensitivity import (
    OBSERVED_FIXTURE_DECARB_RATE,
    evaluate_decarb_sensitivity,
    format_decarb_sensitivity,
    recommend_decarb_rate,
)


class DecarbSensitivityTests(unittest.TestCase):
    def test_data_grounded_decarb_rates_now_beat_the_legacy_fudge_rates(self) -> None:
        points = evaluate_decarb_sensitivity()
        print(format_decarb_sensitivity(points))

        observed_point = next(point for point in points if point.label == "observed_fixture")
        active_point = next(point for point in points if point.label == "active")
        recommended = recommend_decarb_rate(points)

        self.assertAlmostEqual(observed_point.decarb_rate, OBSERVED_FIXTURE_DECARB_RATE, places=6)
        # [RECAL 2026-06] After fixing the 2015-state capital (cap/GDP 0.23x -> 3.0x) and adding TFP
        # convergence, the finding inverts: the data-derived low rates (~0.016-0.021) give the BEST CO2
        # fit, while the legacy high "fudge" rates (>=0.045, once near-optimal because they cancelled the
        # broken capital ramp) are now clearly rejected.
        legacy_high = [p for p in points if p.decarb_rate >= 0.045]
        self.assertTrue(legacy_high)
        for p in legacy_high:
            self.assertGreater(p.global_co2_rmse_gtco2, active_point.global_co2_rmse_gtco2)
        # the recommended rate is low and data-grounded (inside the honest prior band).
        self.assertLessEqual(recommended.decarb_rate, 0.025)
        self.assertLessEqual(recommended.global_co2_rmse_gtco2, active_point.global_co2_rmse_gtco2 + 1e-9)


if __name__ == "__main__":
    unittest.main()
