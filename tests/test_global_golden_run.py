"""Golden snapshot of the GLOBAL forward run — the public reference.

Pins the first ten years (2024–2033) of the 57-agent world: aggregates, the resource
prices and the crisis counts. Deterministic — seeded world, extreme events off, simple
background policy, forward_init — so the bands are tight and any drift is a real change.

This is the reference the public release is built and expanded against. It deliberately
does NOT use the intra-country block layer (BLOCK_LAYER_AGENTS stays empty), so Russia is
one consolidated country agent like the other 56, which is the model the paper describes
and the only configuration that ships publicly. The block-layer golden lives separately in
test_integrated_golden_run.py, which is excluded from the public build.

Crisis counts are pinned with a band of 1: they are small integers, and the point is to
catch a channel dying or firing everywhere, not to freeze the exact agent set. The fx
counts being non-zero here is itself the guard — that channel produced zero crises in
every configuration until it was repaired.

Golden values fixed 2026-08-24. Update them as a conscious, reviewed decision, the same
convention test_integrated_golden_run.py follows, and say in the commit what moved and why.
"""

import unittest

import numpy as np

from gim.core.policy import make_policy_map
from gim.core.simulation import step_world
from gim.runtime import load_world

YEARS = 10


GOLDEN = {
    2024: {
        "world_gdp": (106.801, 0.5), "temperature": (1.1741, 0.01), "global_co2": (37.491, 0.4),
        "mean_trust": (0.5709, 0.02), "mean_tension": (0.3958, 0.02), "price_energy": (0.9622, 0.05),
        "price_food": (1.0000, 0.05), "price_metals": (0.8610, 0.05),
        "n_debt": (1, 1), "n_fx": (3, 1), "n_regime": (0, 1)},
    2025: {
        "world_gdp": (108.093, 0.5), "temperature": (1.0782, 0.01), "global_co2": (36.567, 0.4),
        "mean_trust": (0.5643, 0.02), "mean_tension": (0.3935, 0.02), "price_energy": (0.9417, 0.05),
        "price_food": (1.0000, 0.05), "price_metals": (0.7849, 0.05),
        "n_debt": (2, 1), "n_fx": (2, 1), "n_regime": (1, 1)},
    2026: {
        "world_gdp": (110.324, 0.5), "temperature": (1.0372, 0.01), "global_co2": (36.172, 0.4),
        "mean_trust": (0.5545, 0.02), "mean_tension": (0.3984, 0.02), "price_energy": (0.9337, 0.05),
        "price_food": (1.0004, 0.05), "price_metals": (0.7442, 0.05),
        "n_debt": (3, 1), "n_fx": (3, 1), "n_regime": (0, 1)},
    2027: {
        "world_gdp": (113.461, 0.5), "temperature": (1.2091, 0.01), "global_co2": (36.220, 0.4),
        "mean_trust": (0.5497, 0.02), "mean_tension": (0.3990, 0.02), "price_energy": (0.9347, 0.05),
        "price_food": (1.0026, 0.05), "price_metals": (0.7257, 0.05),
        "n_debt": (2, 1), "n_fx": (2, 1), "n_regime": (0, 1)},
    2028: {
        "world_gdp": (117.015, 0.5), "temperature": (1.3641, 0.01), "global_co2": (36.495, 0.4),
        "mean_trust": (0.5457, 0.02), "mean_tension": (0.3998, 0.02), "price_energy": (0.9410, 0.05),
        "price_food": (1.0081, 0.05), "price_metals": (0.7217, 0.05),
        "n_debt": (2, 1), "n_fx": (2, 1), "n_regime": (1, 1)},
    2029: {
        "world_gdp": (120.868, 0.5), "temperature": (1.3753, 0.01), "global_co2": (36.849, 0.4),
        "mean_trust": (0.5405, 0.02), "mean_tension": (0.4020, 0.02), "price_energy": (0.9492, 0.05),
        "price_food": (1.0185, 0.05), "price_metals": (0.7274, 0.05),
        "n_debt": (2, 1), "n_fx": (3, 1), "n_regime": (1, 1)},
    2030: {
        "world_gdp": (125.536, 0.5), "temperature": (1.3904, 0.01), "global_co2": (37.241, 0.4),
        "mean_trust": (0.5383, 0.02), "mean_tension": (0.4006, 0.02), "price_energy": (0.9568, 0.05),
        "price_food": (1.0340, 0.05), "price_metals": (0.7393, 0.05),
        "n_debt": (2, 1), "n_fx": (4, 1), "n_regime": (1, 1)},
    2031: {
        "world_gdp": (128.354, 0.5), "temperature": (1.4073, 0.01), "global_co2": (37.823, 0.4),
        "mean_trust": (0.5334, 0.02), "mean_tension": (0.4045, 0.02), "price_energy": (0.9668, 0.05),
        "price_food": (1.0562, 0.05), "price_metals": (0.7565, 0.05),
        "n_debt": (3, 1), "n_fx": (4, 1), "n_regime": (1, 1)},
    2032: {
        "world_gdp": (133.468, 0.5), "temperature": (1.4038, 0.01), "global_co2": (38.266, 0.4),
        "mean_trust": (0.5288, 0.02), "mean_tension": (0.4076, 0.02), "price_energy": (0.9799, 0.05),
        "price_food": (1.0828, 0.05), "price_metals": (0.7747, 0.05),
        "n_debt": (3, 1), "n_fx": (4, 1), "n_regime": (1, 1)},
    2033: {
        "world_gdp": (138.168, 0.5), "temperature": (1.4987, 0.01), "global_co2": (38.887, 0.4),
        "mean_trust": (0.5271, 0.02), "mean_tension": (0.4087, 0.02), "price_energy": (0.9994, 0.05),
        "price_food": (1.1113, 0.05), "price_metals": (0.7958, 0.05),
        "n_debt": (3, 1), "n_fx": (2, 1), "n_regime": (1, 1)},
}


class GlobalGoldenRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        world = load_world(forward_init=True)
        ids = sorted(world.agents.keys())
        policies = make_policy_map(list(world.agents.keys()), mode="simple")
        cls.n_agents = len(ids)
        cls.traj = {}
        for t in range(YEARS):
            world = step_world(world, policies, enable_extreme_events=False)
            g = world.global_state
            cls.traj[2024 + t] = {
                "world_gdp": float(sum(world.agents[a].economy.gdp for a in ids)),
                "temperature": float(g.temperature_global),
                "global_co2": float(sum(world.agents[a].climate.co2_annual_emissions
                                        for a in ids)),
                "mean_trust": float(np.mean([world.agents[a].society.trust_gov for a in ids])),
                "mean_tension": float(np.mean([world.agents[a].society.social_tension
                                               for a in ids])),
                "price_energy": float(g.prices["energy"]),
                "price_food": float(g.prices["food"]),
                "price_metals": float(g.prices["metals"]),
                "n_debt": int(sum(world.agents[a].risk.debt_crisis_active_years > 0
                                  for a in ids)),
                "n_fx": int(sum(world.agents[a].risk.fx_crisis_active_years > 0 for a in ids)),
                "n_regime": int(sum(world.agents[a].risk.regime_crisis_active_years > 0
                                    for a in ids)),
            }

    def test_world_is_the_consolidated_57_agent_set(self):
        self.assertEqual(self.n_agents, 57)

    def test_trajectory_within_golden_bands(self):
        for year, fields in GOLDEN.items():
            for field, (golden, band) in fields.items():
                got = self.traj[year][field]
                self.assertLessEqual(
                    abs(got - golden), band,
                    f"{year} {field}: {got} left the golden band {golden}+/-{band}")

    def test_every_crisis_channel_fires_at_least_once(self):
        """Guards against a channel going structurally dead, as fx once was."""
        for field in ("n_debt", "n_fx", "n_regime"):
            total = sum(self.traj[y][field] for y in self.traj)
            self.assertGreater(total, 0, f"{field} never fires across {YEARS} years")


if __name__ == "__main__":
    unittest.main()
