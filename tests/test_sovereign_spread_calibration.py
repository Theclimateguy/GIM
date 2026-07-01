"""#14 Sovereign-spread block anchored to Hilscher-Nosbusch / Arora-Cerisola / Reinhart-Rogoff."""

import unittest

from gim.core import calibration_params as cp
from gim.historical_backtest import run_historical_backtest


class SovereignSpreadCalibrationTests(unittest.TestCase):
    def test_neutral_marginal_matches_hilscher_nosbusch(self) -> None:
        # Neutral factor = RISK_BASE * FRAG_BASE; marginal at threshold in bp/pp.
        neutral = cp.DEBT_SPREAD_RISK_BASE * cp.DEBT_SPREAD_FRAGILITY_BASE
        bp_per_pp = cp.DEBT_SPREAD_LINEAR * neutral * 100
        self.assertAlmostEqual(bp_per_pp, 2.1, delta=0.6)  # Hilscher-Nosbusch ~2.1 bp/pp

    def test_threshold_at_maastricht_reference(self) -> None:
        self.assertAlmostEqual(cp.DEBT_SPREAD_THRESHOLD, 0.60, places=2)

    def test_linear_within_published_90pct_range(self) -> None:
        self.assertGreaterEqual(cp.DEBT_SPREAD_LINEAR, 0.043)
        self.assertLessEqual(cp.DEBT_SPREAD_LINEAR, 0.086)

    def test_quadratic_acceleration_present(self) -> None:
        self.assertGreater(cp.DEBT_SPREAD_QUADRATIC, 0.0)

    def test_macro_backtest_golden_safe(self) -> None:
        r = run_historical_backtest()
        self.assertAlmostEqual(r.gdp_rmse_trillions, 0.598, delta=0.01)
        self.assertAlmostEqual(r.global_co2_rmse_gtco2, 0.939, delta=0.01)


if __name__ == "__main__":
    unittest.main()
