"""Damage-function cross-validation tests (T1.4)."""

import unittest

from gim.damage_validation import (
    EMPIRICAL_DAMAGE_ESTIMATES,
    ENVELOPE_HIGH_COEFF,
    ENVELOPE_LOW_COEFF,
    empirical_envelope,
    gim_damage_coeff,
    gim_loss_fraction,
    gim_within_envelope,
    level_estimates,
)


class EvidenceTableTests(unittest.TestCase):
    def test_level_coefficients_match_reported_loss_at_3c(self):
        # Each level study's implied quadratic coefficient must reproduce its reported
        # %GDP loss at 3 C (a*9 == loss fraction), within rounding.
        for e in level_estimates():
            self.assertAlmostEqual(
                e.implied_quadratic_coeff * 9.0, e.loss_pct_at_3C / 100.0, places=3, msg=e.key
            )

    def test_retracted_study_is_flagged(self):
        kotz = next(e for e in EMPIRICAL_DAMAGE_ESTIMATES if e.key == "kotz_2024")
        self.assertIn("RETRACTED", kotz.note.upper())
        self.assertEqual(kotz.form, "growth")  # excluded from the numeric envelope

    def test_dice_is_lower_bound_and_meta_high_is_upper(self):
        coeffs = [e.implied_quadratic_coeff for e in level_estimates()]
        self.assertEqual(min(coeffs), ENVELOPE_LOW_COEFF)        # DICE-2016R2
        self.assertEqual(max(coeffs), ENVELOPE_HIGH_COEFF)       # meta-analysis high end


class GimPositioningTests(unittest.TestCase):
    def test_gim_default_is_7_0_pct_at_3c(self):
        # [#17] re-anchored to Howard-Sterner preferred central (~7%/3C).
        self.assertAlmostEqual(gim_loss_fraction(3.0), 0.070, places=2)

    def test_gim_at_howard_sterner_preferred_above_dice(self):
        # [#17] The defensible academic position: re-anchored to the Howard-Sterner preferred
        # central (7-8%/3C), comfortably above DICE and below the catastrophic-inclusive estimate.
        gim = gim_damage_coeff()
        self.assertGreater(gim, 0.00236)   # well above DICE-2016R2
        self.assertGreaterEqual(gim, 0.0070)  # at Howard-Sterner preferred central
        self.assertLess(gim, 0.01056)      # below Howard-Sterner incl-catastrophic

    def test_gim_within_empirical_envelope(self):
        self.assertTrue(gim_within_envelope())

    def test_envelope_brackets_gim_at_each_warming(self):
        for w in (2.0, 3.0, 4.0):
            lo, hi = empirical_envelope(w)
            loss = gim_loss_fraction(w)
            self.assertLessEqual(lo, loss)
            self.assertLessEqual(loss, hi)


if __name__ == "__main__":
    unittest.main()
