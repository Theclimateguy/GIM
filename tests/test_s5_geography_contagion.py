"""S5b — switchable geography contagion in the conflict dynamics.

Skipped without shapely + geojson (the optional 'geo' extra). Default-off golden-safety is covered by
the rest of the suite (this feature adds 0.0 to conflict_push when GEOGRAPHY_CONFLICT_LINKS is off);
here we check that turning it ON populates adjacency and makes geographic neighbours more conflictual.
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
    from gim.core.params import default_params
    from gim.core.policy import simple_rule_based_policy
    from gim.core.political_dynamics import _geo_adjacency
    from gim.core.simulation import step_world
    from gim.core.world_factory import make_world_from_csv

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(_REPO, "data", "agent_states_operational_2026_calibrated.csv")


def _mean_adjacent_conflict(world):
    vals = []
    for aid, neigh in _geo_adjacency(world).items():
        own = world.relations.get(aid, {})
        vals += [own[nb].conflict_level for nb in neigh if nb in own]
    return sum(vals) / len(vals) if vals else 0.0


@unittest.skipUnless(_HAVE, "shapely + world_countries.geojson required")
class GeoContagionTests(unittest.TestCase):
    def test_adjacency_populates_real_neighbours(self):
        world = make_world_from_csv(STATE, base_year=2026)
        adj = _geo_adjacency(world)
        self.assertTrue(any(neigh for neigh in adj.values()), "no adjacency built")

    def test_flag_on_raises_adjacent_conflict(self):
        def run(geo_on):
            world = make_world_from_csv(STATE, base_year=2026)
            # override explicitly for both cases — the headline default is now ON, so "off" must be forced
            world.params = default_params().with_overrides({"GEOGRAPHY_CONFLICT_LINKS": geo_on})
            pol = {aid: simple_rule_based_policy for aid in world.agents}
            mem: dict = {}
            for _ in range(8):
                world = step_world(world, pol, memory=mem, enable_extreme_events=False)
            return world

        self.assertGreater(_mean_adjacent_conflict(run(True)), _mean_adjacent_conflict(run(False)))


if __name__ == "__main__":
    unittest.main()
