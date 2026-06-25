"""Switchable gravity trade initialisation (off by default).

Skipped without shapely + geojson. Golden-identical-when-off is covered by the rest of the suite and by
the 2015-2023 backtest (OFF reproduces 0.5903/1.1482/0.1349 exactly); here we check that turning it ON
preserves the average trade level while imposing a realistic distance gradient.
"""

import os
import statistics
import unittest

try:
    import shapely  # noqa: F401
    from gim.geography import GEOJSON
    _HAVE = os.path.exists(GEOJSON)
except Exception:  # pragma: no cover
    _HAVE = False

if _HAVE:
    from gim.core.params import default_params
    from gim.core.political_dynamics import _apply_trade_gravity_once
    from gim.core.world_factory import make_world_from_csv

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(_REPO, "data", "agent_states_operational_2026_calibrated.csv")


@unittest.skipUnless(_HAVE, "shapely + world_countries.geojson required")
class TradeGravityTests(unittest.TestCase):
    def _gravity_world(self):
        w = make_world_from_csv(STATE, base_year=2026)
        w.params = default_params().with_overrides({"TRADE_GRAVITY_INIT": True})
        _apply_trade_gravity_once(w, w.params)
        return w

    def _all_ti(self, w):
        return [r.trade_intensity for rels in w.relations.values() for r in rels.values()]

    def test_level_preserved_but_structure_added(self):
        w = self._gravity_world()
        vals = self._all_ti(w)
        self.assertAlmostEqual(statistics.fmean(vals), 0.5, delta=0.05)   # mean ~ flat baseline
        self.assertGreater(statistics.pstdev(vals), 0.05)                 # flat had sd=0; gravity has spread

    def test_trade_decays_with_distance(self):
        w = self._gravity_world()
        idx = {a.name: aid for aid, a in w.agents.items()}

        def ti(n1, n2):
            return w.relations[idx[n1]][idx[n2]].trade_intensity
        # near, high-GDP pair beats a far pair
        self.assertGreater(ti("United States", "Canada"), ti("United States", "Australia"))

    def test_application_is_idempotent(self):
        w = self._gravity_world()
        snap = {(i, j): r.trade_intensity for i, rels in w.relations.items() for j, r in rels.items()}
        _apply_trade_gravity_once(w, w.params)   # second call no-ops via the marker
        snap2 = {(i, j): r.trade_intensity for i, rels in w.relations.items() for j, r in rels.items()}
        self.assertEqual(snap, snap2)


if __name__ == "__main__":
    unittest.main()
