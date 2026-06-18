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
        self.assertGreater(observed_point.global_co2_rmse_gtco2, active_point.global_co2_rmse_gtco2)
        self.assertEqual(recommended.label, "active")
        self.assertAlmostEqual(recommended.decarb_rate, active_point.decarb_rate, places=6)


if __name__ == "__main__":
    unittest.main()
