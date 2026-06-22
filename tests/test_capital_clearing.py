"""E3.2: capital-market clearing (investment responds to the price of capital)."""
import contextlib
import io
import unittest

from gim.core import calibration_params as cal
from gim.core.params import default_params
from gim.core.economy import update_economy_output
from gim.core.world_factory import make_world_from_csv
from gim.historical_backtest import run_historical_backtest

STATE = "data/agent_states_operational_2026_calibrated.csv"


def _capital_after_transient_rate(bump):
    world = make_world_from_csv(STATE, max_agents=6, base_year=2026)
    world.params = default_params().with_overrides({"CAPITAL_MARKET_CLEARING": True})
    a = next(iter(world.agents.values()))
    update_economy_output(a, world)            # anchors the baseline return-cost gap
    world.params = world.params.with_overrides({"BASE_INTEREST_RATE": 0.02 + bump})  # transient cost shock
    update_economy_output(a, world)
    return a.economy.capital


class CapitalClearingTests(unittest.TestCase):
    def test_default_is_on(self):
        # [E3 full-closure base] capital-market clearing is headline.
        self.assertTrue(cal.CAPITAL_MARKET_CLEARING)

    def test_default_golden(self):
        with contextlib.redirect_stdout(io.StringIO()):
            g = run_historical_backtest()
        self.assertAlmostEqual(g.gdp_rmse_trillions, 0.590, places=2)
        self.assertAlmostEqual(g.global_co2_rmse_gtco2, 1.146, places=2)

    def test_transient_cost_of_capital_shock_lowers_capital(self):
        # baseline-anchored: a transient rise in the cost of capital (rate) cuts investment -> capital.
        no_shock = _capital_after_transient_rate(0.0)
        shock = _capital_after_transient_rate(0.08)
        self.assertLess(shock, no_shock)


if __name__ == "__main__":
    unittest.main()
