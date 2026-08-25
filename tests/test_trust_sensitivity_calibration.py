"""#16 Trust-erosion sensitivities anchored to the cross-country trust/wellbeing literature.

Guards: the misery-index 2:1 unemployment:inflation weighting, sign correctness, the switchable
Gini x unemployment interaction (off by default), and golden-safety of the macro backtest.
"""

import unittest

from gim.core import calibration_params as cp
from gim.historical_backtest import run_historical_backtest


class TrustSensitivityCalibrationTests(unittest.TestCase):
    def test_unemployment_inflation_ratio_is_two_to_one(self) -> None:
        # Di Tella et al. 2001 / Stevenson-Wolfers: unemployment ~2x inflation in welfare/trust cost.
        ratio = cp.TRUST_UNEMPLOYMENT_SENS / cp.TRUST_INFLATION_SENS
        self.assertAlmostEqual(ratio, 2.0, delta=0.25)

    def test_signs_are_correct(self) -> None:
        self.assertLess(cp.TRUST_UNEMPLOYMENT_SENS, 0)
        self.assertLess(cp.TRUST_INFLATION_SENS, 0)
        self.assertLess(cp.TRUST_GINI_SENS, 0)
        self.assertLess(cp.TRUST_TENSION_SENS, 0)

    def test_average_flow_magnitude_preserved(self) -> None:
        # Rebalancing the ratio preserves the calibrated average flow magnitude (~0.0225).
        avg = (abs(cp.TRUST_UNEMPLOYMENT_SENS) + abs(cp.TRUST_INFLATION_SENS)) / 2.0
        self.assertAlmostEqual(avg, 0.0225, delta=0.003)

    def test_interaction_off_by_default(self) -> None:
        self.assertEqual(cp.TRUST_GINI_UNEMP_INTERACT, 0.0)

    def test_macro_backtest_golden_safe(self) -> None:
        r = run_historical_backtest()
        self.assertAlmostEqual(r.gdp_rmse_trillions, 0.598, delta=0.01)
        self.assertAlmostEqual(r.global_co2_rmse_gtco2, 0.939, delta=0.01)


if __name__ == "__main__":
    unittest.main()
