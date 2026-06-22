"""E3.1: cost-minimizing (price-responsive) energy demand."""
import unittest

from gim.core import calibration_params as cal
from gim.core.params import default_params
from gim.core.resources import update_resource_stocks
from gim.core.world_factory import make_world_from_csv

STATE = "data/agent_states_operational_2026_calibrated.csv"


def _energy_consumption_after_price_change(p0, p1, on):
    """Establish baseline price p0 (one step), then change to p1 and return demand before/after."""
    world = make_world_from_csv(STATE, max_agents=6, base_year=2026)
    world.params = default_params().with_overrides({"ENERGY_DEMAND_PRICE_RESPONSE": bool(on)})
    world.global_state.prices["energy"] = p0
    update_resource_stocks(world)  # anchors the previous price at p0
    a = next(iter(world.agents.values()))
    before = a.resources["energy"].consumption
    world.global_state.prices["energy"] = p1
    update_resource_stocks(world)
    return before, a.resources["energy"].consumption


class EnergyDemandTests(unittest.TestCase):
    def test_default_is_on(self):
        # [E3.1 re-anchor] cost-minimizing energy demand is part of the objective headline core.
        self.assertTrue(cal.ENERGY_DEMAND_PRICE_RESPONSE)

    def test_constant_price_no_response(self):
        # a CONSTANT price leaves demand unchanged (non-compounding) -- the key fix.
        b, c = _energy_consumption_after_price_change(1.5, 1.5, True)
        self.assertAlmostEqual(b, c, places=6)

    def test_demand_falls_on_price_rise_at_sigma_elasticity(self):
        # doubling the price cuts demand by 2^(-sigma) -- the cost-min response to a price change.
        b, c = _energy_consumption_after_price_change(1.0, 2.0, True)
        self.assertAlmostEqual(c / b, 2.0 ** (-cal.CES_SIGMA_KE), places=3)

    def test_off_means_no_response(self):
        b, c = _energy_consumption_after_price_change(1.0, 2.0, False)
        self.assertAlmostEqual(b, c, places=6)


if __name__ == "__main__":
    unittest.main()
