"""Nested-CES (KLE) production core (F2.1).

Guards that the default stays Cobb-Douglas (golden-preserving), that the CES core reduces to
Cobb-Douglas at sigma_ke=1, and that sigma_ke<1 makes capital and energy gross complements.
"""
import unittest

from gim.core import calibration_params as cal
from gim.core.economy import _nested_ces_core


class NestedCesTests(unittest.TestCase):
    def test_default_is_nested_ces(self):
        # [E3.1 re-anchor] the calibrated nested-CES core is the objective headline default.
        self.assertTrue(cal.NESTED_CES)

    def test_ces_reduces_to_cobb_douglas_at_sigma_one(self):
        a, b, g = 0.30, 0.60, 0.042
        for K, L, E in [(5.0, 1.2, 2.0), (10.0, 0.8, 0.5), (3.0, 2.0, 4.0)]:
            cd = (K ** a) * (L ** b) * (E ** g)
            ces = _nested_ces_core(K, L, E, a, b, g, 1.0)
            self.assertAlmostEqual(cd, ces, places=9)

    def test_calibrated_ces_equals_cobb_douglas_at_base_point(self):
        # [E3.1] With base normalization, the CES equals Cobb-Douglas at the base point for ANY sigma
        # (this is what makes activation golden-preserving). Off-base it diverges (substitution).
        a, b, g = 0.30, 0.60, 0.042
        K0, L, E0 = 7.0, 1.0, 1.5
        for sigma in (0.3, 0.4, 0.7):
            cd_base = (K0 ** a) * (L ** b) * (E0 ** g)
            ces_base = _nested_ces_core(K0, L, E0, a, b, g, sigma, base_capital=K0, base_energy=E0)
            self.assertAlmostEqual(cd_base, ces_base, places=9)
            # off the base point the calibrated CES differs (genuine substitution)
            ces_off = _nested_ces_core(K0 * 1.5, L, E0 * 0.7, a, b, g, sigma, base_capital=K0, base_energy=E0)
            cd_off = (K0 * 1.5) ** a * (L ** b) * (E0 * 0.7) ** g
            self.assertNotAlmostEqual(ces_off, cd_off, places=6)

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
