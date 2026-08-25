"""S6 reproduction benchmark — emergent spatial autocorrelation of conflict / tension / climate.

Two layers: (1) the Moran's I / lag-correlation math is verified on toy graphs (no shapely needed);
(2) gated on shapely + geojson, the GIM run reproduces positive neighbour clustering — node Moran's I
for the country-scalar variables (tension, climate) and the dyadic neighbour-premium for the
edge-level variable (conflict).
"""

import os
import sys
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from run_s6_geo_autocorrelation import (  # noqa: E402
    morans_i, morans_p, neighbour_lag_corr, dyadic_conflict_premium,
)

try:
    import shapely  # noqa: F401
    from gim.geography import GEOJSON, build_geography
    _HAVE = os.path.exists(GEOJSON)
except Exception:  # pragma: no cover
    _HAVE = False


class MoranMathTests(unittest.TestCase):
    """Two clusters {A,B}=+1, {C,D}=-1 with within-cluster edges => perfect positive autocorrelation."""

    NAMES = ["A", "B", "C", "D"]
    EDGES = [("A", "B"), ("C", "D")]

    def test_perfect_clustering_gives_I_one(self):
        val = {"A": 1.0, "B": 1.0, "C": -1.0, "D": -1.0}
        self.assertAlmostEqual(morans_i(self.NAMES, val, self.EDGES), 1.0, places=6)
        self.assertGreater(neighbour_lag_corr(self.NAMES, val, self.EDGES), 0.99)

    def test_perfect_dispersion_gives_negative_I(self):
        val = {"A": 1.0, "B": -1.0, "C": 1.0, "D": -1.0}
        self.assertAlmostEqual(morans_i(self.NAMES, val, self.EDGES), -1.0, places=6)

    def test_permutation_p_small_when_clustered(self):
        # 10-node path with monotone values => strong positive autocorrelation; random relabellings
        # rarely match, so the one-sided permutation p is small. (4 nodes is too small: true p ~ 0.33.)
        names = [f"n{k}" for k in range(10)]
        edges = [(f"n{k}", f"n{k + 1}") for k in range(9)]
        val = {f"n{k}": float(k) for k in range(10)}
        i, p = morans_p(names, val, edges, n_perm=499, seed=1)
        self.assertGreater(i, 0.5)
        self.assertLess(p, 0.05)


@unittest.skipUnless(_HAVE, "shapely + world_countries.geojson required")
class GeoReproductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from run_s6_geo_autocorrelation import run_world, _edges
        cls.geo = build_geography()
        cls.on = run_world(6, geo_on=True)
        cls.off = run_world(6, geo_on=False)
        cls.names = [n for n in cls.geo.matched if n in cls.on["conflict"]]
        cls.edges = _edges(cls.names, cls.geo.adjacency)
        cls.exp_null = -1.0 / (len(cls.names) - 1)

    def test_tension_and_climate_cluster_positively(self):
        for var in ("tension", "climate"):
            i_on = morans_i(self.names, self.on[var], self.edges)
            self.assertGreater(i_on, self.exp_null, f"{var}: no positive node autocorrelation")
            self.assertGreater(neighbour_lag_corr(self.names, self.on[var], self.edges), 0.0)

    def test_conflict_dyadic_premium_rises_with_coupling(self):
        _a_on, _n_on, r_on = dyadic_conflict_premium(self.on["dyads"], self.geo)
        _a_off, _n_off, r_off = dyadic_conflict_premium(self.off["dyads"], self.geo)
        self.assertGreater(r_on, 1.0, "neighbours should be more conflictual than non-neighbours")
        self.assertGreater(r_on, r_off, "coupling ON should raise the neighbour-conflict premium")


if __name__ == "__main__":
    unittest.main()
