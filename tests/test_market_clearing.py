"""F2.2 (D2): partial market clearing for resource prices (switchable, default off)."""
import unittest

from gim.core import calibration_params as cal
from gim.core.params import default_params
from gim.core.resources import update_global_resource_prices
from gim.core.world_factory import make_world_from_csv

STATE = "data/agent_states_operational_2026_calibrated.csv"


def _prices_after(overrides):
    world = make_world_from_csv(STATE, max_agents=12, base_year=2026)
    if overrides:
        world.params = default_params().with_overrides(overrides)
    update_global_resource_prices(world)
    return dict(world.global_state.prices)


class MarketClearingTests(unittest.TestCase):
    def test_default_is_off(self):
        self.assertFalse(cal.MARKET_CLEARING)

    def test_default_matches_sluggish_rule(self):
        # default (no override) and explicit MARKET_CLEARING=False must be identical.
        self.assertEqual(_prices_after(None), _prices_after({"MARKET_CLEARING": False}))

    def test_clearing_changes_prices_vs_sluggish(self):
        sluggish = _prices_after({"MARKET_CLEARING": False})
        clearing = _prices_after({"MARKET_CLEARING": True, "MARKET_DEMAND_ELASTICITY": 0.4})
        # at least one resource price should differ (clearing jumps further than the alpha step)
        self.assertTrue(any(abs(clearing[k] - sluggish[k]) > 1e-9 for k in sluggish))

    def test_clearing_raises_price_under_excess_demand(self):
        # build a world with global excess demand for energy, then clear
        world = make_world_from_csv(STATE, max_agents=12, base_year=2026)
        world.params = default_params().with_overrides({"MARKET_CLEARING": True})
        for a in world.agents.values():
            e = a.resources.get("energy")
            if e:
                e.consumption = e.production * 2.0 + 1.0  # demand > supply
        p0 = world.global_state.prices.get("energy", 1.0)
        update_global_resource_prices(world)
        self.assertGreater(world.global_state.prices["energy"], p0)


if __name__ == "__main__":
    unittest.main()
