import unittest

from gim.decarb_sensitivity import (
    OBSERVED_FIXTURE_DECARB_RATE,
    evaluate_decarb_sensitivity,
    format_decarb_sensitivity,
    recommend_decarb_rate,
)


class DecarbSensitivityTests(unittest.TestCase):
    def test_observed_fixture_decarb_rate_is_evaluated_and_rejected_by_current_backtest(self) -> None:
        points = evaluate_decarb_sensitivity()
        print(format_decarb_sensitivity(points))

        observed_point = next(point for point in points if point.label == "observed_fixture")
        active_point = next(point for point in points if point.label == "active")
        recommended = recommend_decarb_rate(points)

        self.assertAlmostEqual(observed_point.decarb_rate, OBSERVED_FIXTURE_DECARB_RATE, places=6)
        # the observed-fixture decarb rate is still clearly rejected (much worse CO2 than active).
        self.assertGreater(observed_point.global_co2_rmse_gtco2, active_point.global_co2_rmse_gtco2)
        # [E3 full-closure base] the artifact-bound active rate (0.052) stays near-optimal: the
        # recommended rate is within one grid step and its CO2 within a small tolerance of the active.
        self.assertLess(abs(recommended.decarb_rate - active_point.decarb_rate), 0.005)
        self.assertLess(active_point.global_co2_rmse_gtco2 - recommended.global_co2_rmse_gtco2, 0.15)


if __name__ == "__main__":
    unittest.main()
