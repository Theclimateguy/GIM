"""E3.1: cost-minimizing (price-responsive) energy demand."""
import unittest

from gim.core import calibration_params as cal
from gim.core.params import default_params
from gim.core.resources import update_resource_stocks
from gim.core.world_factory import make_world_from_csv

STATE = "data/agent_states_operational_2026_calibrated.csv"


def _energy_consumption_after(price, on):
    world = make_world_from_csv(STATE, max_agents=6, base_year=2026)
    world.params = default_params().with_overrides({"ENERGY_DEMAND_PRICE_RESPONSE": bool(on)})
    world.global_state.prices["energy"] = price
    a = next(iter(world.agents.values()))
    before = a.resources["energy"].consumption
    update_resource_stocks(world)
    return before, a.resources["energy"].consumption


class EnergyDemandTests(unittest.TestCase):
    def test_default_is_on(self):
        # [E3.1 re-anchor] cost-minimizing energy demand is part of the objective headline core.
        self.assertTrue(cal.ENERGY_DEMAND_PRICE_RESPONSE)

    def test_no_response_at_reference_price(self):
        # at the reference price (1.0) demand is unchanged whether the channel is on or off.
        b_on, c_on = _energy_consumption_after(1.0, True)
        self.assertAlmostEqual(b_on, c_on, places=6)

    def test_demand_falls_with_price_at_sigma_elasticity(self):
        b, c = _energy_consumption_after(2.0, True)
        ratio = c / b
        sigma = cal.CES_SIGMA_KE
        self.assertAlmostEqual(ratio, 2.0 ** (-sigma), places=3)  # E ∝ p^(-sigma)

    def test_off_means_no_response(self):
        b, c = _energy_consumption_after(2.0, False)
        self.assertAlmostEqual(b, c, places=6)


if __name__ == "__main__":
    unittest.main()
