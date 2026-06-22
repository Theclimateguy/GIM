"""Nested-CES (KLE) production core (F2.1).

Guards that the default stays Cobb-Douglas (golden-preserving), that the CES core reduces to
Cobb-Douglas at sigma_ke=1, and that sigma_ke<1 makes capital and energy gross complements.
"""
import unittest

from gim.core import calibration_params as cal
from gim.core.economy import _nested_ces_core


class NestedCesTests(unittest.TestCase):
    def test_default_is_cobb_douglas(self):
        self.assertFalse(cal.NESTED_CES)

    def test_ces_reduces_to_cobb_douglas_at_sigma_one(self):
        a, b, g = 0.30, 0.60, 0.042
        for K, L, E in [(5.0, 1.2, 2.0), (10.0, 0.8, 0.5), (3.0, 2.0, 4.0)]:
            cd = (K ** a) * (L ** b) * (E ** g)
            ces = _nested_ces_core(K, L, E, a, b, g, 1.0)
            self.assertAlmostEqual(cd, ces, places=9)

    def test_sigma_below_one_makes_K_E_complements(self):
        # With gross complements (sigma<1), raising energy alone while capital is scarce yields
        # less extra output than the unit-elastic (Cobb-Douglas) case.
        a, b, g = 0.30, 0.60, 0.042
        K, L = 1.0, 1.0
        base_cd = _nested_ces_core(K, L, 1.0, a, b, g, 1.0)
        hi_cd = _nested_ces_core(K, L, 4.0, a, b, g, 1.0)
        base_ces = _nested_ces_core(K, L, 1.0, a, b, g, 0.4)
        hi_ces = _nested_ces_core(K, L, 4.0, a, b, g, 0.4)
        # both increase with energy, but the CES (complements) gains proportionally less
        self.assertGreater(hi_ces, base_ces)
        self.assertLess(hi_ces / base_ces, hi_cd / base_cd)


if __name__ == "__main__":
    unittest.main()
