"""#17 Climate damage function calibrated to Howard & Sterner (2017) + Burke et al. (2015).

Guards: no double-count at the 2023 baseline, Howard-Sterner-consistent magnitude at +3 degC,
warming "benefit" disabled, coefficient inside the literature range, and the Burke growth channel
present-but-off by default.
"""

import unittest

from gim.core import calibration_params as cp
from gim.core.climate import climate_damage_multiplier, TGLOBAL_2023_C
from gim.core.params import default_params


class DamageFunctionCalibrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.p = default_params()

    def test_zero_damage_at_2023_baseline(self) -> None:
        # Normalised to 2023 -> no double-count of damage already embedded in the anchored GDP.
        self.assertAlmostEqual(climate_damage_multiplier(TGLOBAL_2023_C, self.p), 1.0, places=9)

    def test_three_degree_damage_matches_howard_sterner(self) -> None:
        # Total loss vs pre-industrial = incremental (modelled) + base-year embedded (~1.4%).
        incremental = 1.0 - climate_damage_multiplier(3.0, self.p)
        base_embedded = cp.DAMAGE_QUAD_COEFF * TGLOBAL_2023_C**2
        total_vs_preindustrial = incremental + base_embedded
        # Howard-Sterner preferred central ~7% GDP at +3C.
        self.assertGreater(total_vs_preindustrial, 0.06)
        self.assertLess(total_vs_preindustrial, 0.08)

    def test_coeff_in_literature_range(self) -> None:
        # DICE-2016R2 ~0.0026 (lower) .. Howard-Sterner incl-catastrophic ~0.0115 (upper).
        self.assertGreaterEqual(cp.DAMAGE_QUAD_COEFF, 0.0026)
        self.assertLessEqual(cp.DAMAGE_QUAD_COEFF, 0.0115)

    def test_no_warming_benefit(self) -> None:
        self.assertEqual(cp.DAMAGE_BENEFIT_MAX, 0.0)
        # Monotone damage: warmer than 2023 is never a net gain.
        self.assertLessEqual(climate_damage_multiplier(2.5, self.p), 1.0)
        self.assertLessEqual(climate_damage_multiplier(4.0, self.p), climate_damage_multiplier(3.0, self.p))

    def test_growth_channel_present_but_off(self) -> None:
        self.assertEqual(cp.GROWTH_DAMAGE_TFP_COEFF, 0.0)  # off by default (golden-safe)
        self.assertIn("GROWTH_DAMAGE_TFP_COEFF", default_params())


if __name__ == "__main__":
    unittest.main()
