"""Switchable social-tension spatial contagion (off by default).

Skipped without shapely + geojson. Golden-identical-when-off is covered by the rest of the suite and the
2015-2023 backtest (OFF reproduces 0.5903/1.1482/0.1349, ON: GDP -0.0001, CO2/T ±0). Here we check the
mechanism: with the channel ON, a country surrounded by high-tension neighbours gains more tension than
with it OFF.
"""

import os
import unittest

try:
    import shapely  # noqa: F401
    from gim.geography import GEOJSON
    _HAVE = os.path.exists(GEOJSON)
except Exception:  # pragma: no cover
    _HAVE = False

if _HAVE:
    from gim.core.geo_coupling import adjacency
    from gim.core.params import default_params
    from gim.core.policy import simple_rule_based_policy
    from gim.core.simulation import step_world
    from gim.core.world_factory import make_world_from_csv

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(_REPO, "data", "agent_states_operational.csv")


@unittest.skipUnless(_HAVE, "shapely + world_countries.geojson required")
class GeoTensionTests(unittest.TestCase):
    def _delta_with_hot_neighbours(self, links: bool) -> float:
        w = make_world_from_csv(STATE, base_year=2023)
        w.params = default_params().with_overrides({"GEOGRAPHY_TENSION_LINKS": links})
        adj = adjacency(w)
        target = next(aid for aid, n in adj.items() if n)   # first agent with a neighbour (deterministic)
        for nb in adj[target]:
            w.agents[nb].society.social_tension = 0.95      # surround it with unrest
        base = w.agents[target].society.social_tension
        pol = {aid: simple_rule_based_policy for aid in w.agents}
        w = step_world(w, pol, memory={}, enable_extreme_events=False)
        return w.agents[target].society.social_tension - base

    def test_hot_neighbours_raise_tension_more_when_on(self):
        self.assertGreater(self._delta_with_hot_neighbours(True),
                           self._delta_with_hot_neighbours(False))


if __name__ == "__main__":
    unittest.main()
