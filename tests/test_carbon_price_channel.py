"""D1: CES cost-min carbon-price -> emissions substitution channel (switchable, default off)."""
import contextlib
import io
import unittest

from gim.core import calibration_params as cal
from gim.historical_backtest import run_historical_backtest


def _sum_co2(overrides):
    with contextlib.redirect_stdout(io.StringIO()):
        r = run_historical_backtest(params_override=overrides)
    s = r.predicted_global_co2_gtco2
    return (sum(s.values()) if isinstance(s, dict) else sum(s)), r.global_co2_rmse_gtco2


class CarbonPriceChannelTests(unittest.TestCase):
    def test_default_is_off(self):
        self.assertFalse(cal.ENERGY_PRICE_SUBSTITUTION)

    def test_golden_safe_at_zero_carbon(self):
        # Channel ON with no carbon price must be bit-identical to the default (markup=0 -> factor=1).
        _, rmse_on = _sum_co2({"ENERGY_PRICE_SUBSTITUTION": True})
        _, rmse_def = _sum_co2({})
        self.assertAlmostEqual(rmse_on, rmse_def, places=6)

    def test_carbon_price_reduces_emissions(self):
        base, _ = _sum_co2({"ENERGY_PRICE_SUBSTITUTION": True})
        priced, _ = _sum_co2({"ENERGY_PRICE_SUBSTITUTION": True, "CARBON_PRICE_USD_PER_TCO2": 50.0})
        self.assertLess(priced, base)
        # long-run reduction at $50 should be a few percent (structural CES response)
        red = 100.0 * (base - priced) / base
        self.assertTrue(2.0 < red < 12.0, red)

    def test_reduction_is_monotone_in_carbon_price(self):
        base, _ = _sum_co2({"ENERGY_PRICE_SUBSTITUTION": True})
        prev = base
        for cp in (25.0, 50.0, 100.0):
            tot, _ = _sum_co2({"ENERGY_PRICE_SUBSTITUTION": True, "CARBON_PRICE_USD_PER_TCO2": cp})
            self.assertLess(tot, prev)
            prev = tot

    def test_channel_requires_flag(self):
        # carbon price with the channel OFF does nothing (flag-gated).
        off, _ = _sum_co2({"CARBON_PRICE_USD_PER_TCO2": 100.0})
        default, _ = _sum_co2({})
        self.assertEqual(off, default)


if __name__ == "__main__":
    unittest.main()
