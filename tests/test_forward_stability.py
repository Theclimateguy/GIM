"""Forward-projection stability (guards the E3 headline against runaway dynamics).

A baseline forward projection must not collapse or explode: world GDP and energy use should grow at
sane secular rates. This catches the kind of compounding instability that the 2015-2023 backtest
(too short, prices near reference) does not surface.
"""
import unittest

from gim.core.policy import make_policy_map
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv

STATE = "data/agent_states_operational_2026_calibrated.csv"


def _annualized(start, end, years):
    return (end / start) ** (1.0 / years) - 1.0 if start > 0 and end > 0 else -1.0


class ForwardStabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        world = make_world_from_csv(STATE, max_agents=40, base_year=2026)
        pol = make_policy_map(world.agents.keys(), mode="simple")
        cls.g0 = sum(a.economy.gdp for a in world.agents.values())
        cls.e0 = sum(a.resources["energy"].consumption for a in world.agents.values() if a.resources.get("energy"))
        for _ in range(20):
            step_world(world, pol)
        cls.g1 = sum(a.economy.gdp for a in world.agents.values())
        cls.e1 = sum(a.resources["energy"].consumption for a in world.agents.values() if a.resources.get("energy"))
        cls.years = 20

    def test_world_gdp_grows_at_sane_rate(self):
        g = _annualized(self.g0, self.g1, self.years)
        self.assertTrue(-0.01 < g < 0.06, f"forward world GDP growth {g:.3%}/yr out of sane range")

    def test_energy_use_does_not_collapse_or_explode(self):
        e = _annualized(self.e0, self.e1, self.years)
        self.assertTrue(-0.10 < e < 0.10, f"forward energy growth {e:.3%}/yr out of sane range")


if __name__ == "__main__":
    unittest.main()
