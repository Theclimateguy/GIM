"""CINC-style national-capability grounding for military_power (F3)."""

import unittest

from gim.capability import (
    capability_ranking,
    composite_capability_index,
    ground_military_power,
)
from gim.core.world_factory import make_world_from_csv

STATE_CSV = "data/agent_states_operational.csv"


class CapabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = make_world_from_csv(STATE_CSV, max_agents=57, base_year=2023)
        cls.cinc = composite_capability_index(cls.world)

    def test_shares_sum_to_one(self):
        self.assertAlmostEqual(sum(self.cinc.values()), 1.0, places=6)

    def test_reproduces_published_cinc_ordering(self):
        # GIM's CINC-style index should match the real Correlates-of-War CINC ranking:
        # China > US > India, with China ~0.2 and the US ~0.15.
        names = {a.name: v for a, v in ((self.world.agents[k], v) for k, v in self.cinc.items())}
        self.assertGreater(names["China"], names["United States"])
        self.assertGreater(names["United States"], names["India"])
        self.assertTrue(0.15 < names["China"] < 0.28, names["China"])
        self.assertTrue(0.10 < names["United States"] < 0.20, names["United States"])

    def test_ground_military_power_is_mean_one_and_data_ordered(self):
        ground_military_power(self.world)
        mp = {a.name: a.technology.military_power for a in self.world.agents.values()}
        # rescaled to mean ~1, but China now outranks the US (data-grounded), unlike the
        # ungrounded scalar where the US led.
        n = len(mp)
        self.assertAlmostEqual(sum(mp.values()) / n, 1.0, places=6)
        self.assertGreater(mp["China"], mp["United States"])

    def test_ranking_helper(self):
        top = capability_ranking(self.world, top=3)
        self.assertEqual(top[0][0], "China")


if __name__ == "__main__":
    unittest.main()
