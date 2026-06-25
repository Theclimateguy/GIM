"""Geography asset (gim/geography.py) — coverage + known-neighbour sanity.

Skipped when shapely (an optional 'geo' dependency) or the geojson is unavailable, so the core suite
never depends on it. The module is golden-safe: it is not imported by the simulation core.
"""

import os
import unittest

try:
    import shapely  # noqa: F401
    from gim.geography import build_geography, great_circle_km, GEOJSON
    _HAVE = os.path.exists(GEOJSON)
except Exception:  # pragma: no cover - environment without shapely
    _HAVE = False


@unittest.skipUnless(_HAVE, "shapely + world_countries.geojson required")
class GeographyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = build_geography()

    def test_coverage_matches_most_agents(self):
        total = len(self.g.matched) + len(self.g.unmatched)
        self.assertGreaterEqual(len(self.g.matched), 0.8 * total)  # aggregates/city-states excluded

    def test_known_neighbours(self):
        self.assertTrue(self.g.is_adjacent("United States", "Canada"))
        self.assertTrue(self.g.is_adjacent("France", "Germany"))
        self.assertTrue(self.g.is_adjacent("Russia", "China"))

    def test_known_non_neighbours(self):
        self.assertFalse(self.g.is_adjacent("United States", "Australia"))
        self.assertFalse(self.g.is_adjacent("Japan", "Brazil"))

    def test_distance_ordering_and_symmetry(self):
        self.assertLess(self.g.distance_km("France", "Germany"),
                        self.g.distance_km("France", "Japan"))
        self.assertAlmostEqual(self.g.distance_km("China", "India"),
                               self.g.distance_km("India", "China"), places=6)

    def test_base_rate_is_a_small_fraction(self):
        br = self.g.adjacency_base_rate()
        self.assertTrue(0.0 < br < 0.25, br)  # most country pairs are not neighbours

    def test_great_circle_zero_distance(self):
        self.assertAlmostEqual(great_circle_km(40.0, -3.0, 40.0, -3.0), 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
