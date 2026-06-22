"""F2.5 (D5): limited-foresight investment (switchable, default adaptive)."""
import contextlib
import io
import unittest

from gim.core import calibration_params as cal
from gim.historical_backtest import run_historical_backtest


class ExpectationsTests(unittest.TestCase):
    def test_default_is_adaptive(self):
        self.assertEqual(cal.EXPECTATIONS_FORESIGHT, 0.0)

    def test_default_golden_preserved(self):
        with contextlib.redirect_stdout(io.StringIO()):
            g = run_historical_backtest()
        self.assertAlmostEqual(g.gdp_rmse_trillions, 1.026, places=2)
        self.assertAlmostEqual(g.global_co2_rmse_gtco2, 1.606, places=2)

    def test_foresight_changes_trajectory(self):
        with contextlib.redirect_stdout(io.StringIO()):
            base = run_historical_backtest()
            fore = run_historical_backtest(params_override={"EXPECTATIONS_FORESIGHT": 0.5})
        # a forward-looking tilt should move the GDP path (not necessarily improve it)
        self.assertNotAlmostEqual(base.gdp_rmse_trillions, fore.gdp_rmse_trillions, places=4)


if __name__ == "__main__":
    unittest.main()
