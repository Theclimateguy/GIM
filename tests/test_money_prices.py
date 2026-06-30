"""E4.1: quantity-theory money->price transmission (headline-active at the calibrated pass-through)."""
import contextlib
import io
import unittest

from gim.core import calibration_params as cal
from gim.historical_backtest import run_historical_backtest


class MoneyPricesTests(unittest.TestCase):
    def test_headline_value_is_calibrated(self):
        # [E4.1] activated in the headline at the data-calibrated dynamic-panel pass-through.
        self.assertEqual(cal.MONEY_INFLATION_PASS, 0.027)

    def test_headline_matches_golden(self):
        # Headline now includes the money->price channel; golden re-anchored (unchanged at 2 places).
        with contextlib.redirect_stdout(io.StringIO()):
            g = run_historical_backtest()
        self.assertAlmostEqual(g.gdp_rmse_trillions, 0.621, places=2)
        self.assertAlmostEqual(g.global_co2_rmse_gtco2, 0.933, places=2)

    def test_channel_responds_to_lambda(self):
        # Independent of the headline default: turning the channel OFF vs a strong pass-through must
        # move the realized path (inflation -> Taylor rule -> cost of capital -> investment -> GDP).
        with contextlib.redirect_stdout(io.StringIO()):
            off = run_historical_backtest(params_override={"MONEY_INFLATION_PASS": 0.0})
            strong = run_historical_backtest(params_override={"MONEY_INFLATION_PASS": 1.0})
        self.assertNotAlmostEqual(off.gdp_rmse_trillions, strong.gdp_rmse_trillions, places=4)


if __name__ == "__main__":
    unittest.main()
