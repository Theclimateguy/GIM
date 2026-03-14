import unittest

from gim.core import calibration_params as cal
from misc.calibration.calibrate_gamma_cross_section import estimate_gamma_cross_section, load_gamma_cross_section


class GammaCrossSectionTests(unittest.TestCase):
    def test_cross_section_fit_stays_in_literature_band(self) -> None:
        rows = load_gamma_cross_section()
        fit = estimate_gamma_cross_section(rows=rows)

        self.assertEqual(fit.sample_size, 20)
        self.assertGreaterEqual(fit.bounded_gamma, 0.04)
        self.assertLessEqual(fit.bounded_gamma, 0.07)
        self.assertGreater(fit.unconstrained_gamma, fit.bounded_gamma)
        self.assertAlmostEqual(fit.bounded_gamma, 0.07, places=6)

    def test_active_gamma_matches_cross_section_recommendation(self) -> None:
        fit = estimate_gamma_cross_section()
        self.assertAlmostEqual(cal.GAMMA_ENERGY, fit.bounded_gamma, places=6)


if __name__ == "__main__":
    unittest.main()
