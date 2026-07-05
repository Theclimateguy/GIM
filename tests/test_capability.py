"""CINC-style national-capability grounding for military_power (F3 / F3+ milex component).

Two validated configurations:
  * proxy CINC (MILEX_CINC_COMPONENT off): pop/energy/GDP shares — anchored to the published
    Correlates-of-War CINC ordering (China > US > India, China ~0.2, US ~0.15).
  * milex-augmented CINC (headline default): + SIPRI 2023 military expenditure share. The US
    (~37% of world milex) overtakes China — an intentional, documented departure from the
    steel-and-personnel-era COW component mix (see calibration_params MILEX_CINC_COMPONENT).
"""

import unittest

from gim.capability import (
    capability_ranking,
    composite_capability_index,
    ground_military_power,
    load_military_spending,
)
from gim.core import calibration_params as cal
from gim.core.world_factory import make_world_from_csv

STATE_CSV = "data/agent_states_operational.csv"


def _build_world(milex_component: bool):
    prev = cal.MILEX_CINC_COMPONENT
    cal.MILEX_CINC_COMPONENT = milex_component
    try:
        return make_world_from_csv(STATE_CSV, max_agents=57, base_year=2023)
    finally:
        cal.MILEX_CINC_COMPONENT = prev


class ProxyCapabilityTests(unittest.TestCase):
    """3-component proxy CINC — preserved published-COW anchor (flag off)."""

    @classmethod
    def setUpClass(cls):
        cls.world = _build_world(milex_component=False)
        cls.cinc = composite_capability_index(cls.world)

    def test_shares_sum_to_one(self):
        self.assertAlmostEqual(sum(self.cinc.values()), 1.0, places=6)

    def test_reproduces_published_cinc_ordering(self):
        # The proxy index should match the real Correlates-of-War CINC ranking:
        # China > US > India, with China ~0.2 and the US ~0.15.
        names = {a.name: v for a, v in ((self.world.agents[k], v) for k, v in self.cinc.items())}
        self.assertGreater(names["China"], names["United States"])
        self.assertGreater(names["United States"], names["India"])
        self.assertTrue(0.15 < names["China"] < 0.28, names["China"])
        self.assertTrue(0.10 < names["United States"] < 0.20, names["United States"])


class MilexCapabilityTests(unittest.TestCase):
    """4-component milex-augmented CINC — headline default (flag on)."""

    @classmethod
    def setUpClass(cls):
        cls.world = _build_world(milex_component=True)
        cls.cinc = composite_capability_index(cls.world)

    def test_shares_sum_to_one(self):
        self.assertAlmostEqual(sum(self.cinc.values()), 1.0, places=6)

    def test_milex_populated_from_grounding_file(self):
        populated = sum(
            1 for a in self.world.agents.values() if a.economy.military_spending > 0.0
        )
        # 57 actors minus HKG (no separate military in SIPRI; folded into CHN) and any
        # future coverage gaps — require the overwhelming majority populated.
        self.assertGreaterEqual(populated, 50, populated)

    def test_milex_weighted_ordering(self):
        # With the SIPRI milex share included the US (~37% of world milex) overtakes China;
        # India stays the third-ranked COUNTRY (aggregates like "Rest of Global South" are
        # not countries). Documented re-anchor vs the published COW mix.
        names = {a.name: v for a, v in ((self.world.agents[k], v) for k, v in self.cinc.items())}
        self.assertGreater(names["United States"], names["China"])
        self.assertGreater(names["China"], names["India"])
        self.assertTrue(0.15 < names["United States"] < 0.28, names["United States"])
        self.assertTrue(0.12 < names["China"] < 0.25, names["China"])
        self.assertGreater(names["Russia"], names["Germany"])  # milex signal: RUS above DEU

    def test_ground_military_power_is_mean_one_and_data_ordered(self):
        ground_military_power(self.world)
        mp = {a.name: a.technology.military_power for a in self.world.agents.values()}
        n = len(mp)
        self.assertAlmostEqual(sum(mp.values()) / n, 1.0, places=6)
        self.assertGreater(mp["United States"], mp["China"])

    def test_ranking_helper(self):
        top = capability_ranking(self.world, top=3)
        self.assertEqual(top[0][0], "United States")
        self.assertEqual(top[1][0], "China")

    def test_loader_missing_file_is_noop(self):
        world = _build_world(milex_component=False)
        n = load_military_spending(world, csv_path="/nonexistent/path.csv")
        self.assertEqual(n, 0)
        self.assertTrue(all(a.economy.military_spending == 0.0 for a in world.agents.values()))


if __name__ == "__main__":
    unittest.main()
