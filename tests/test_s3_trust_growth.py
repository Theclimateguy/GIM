"""S3 — trust -> growth channel: structural finding + regime-collapse anchor.

GIM has no marginal trust->growth channel (the effective rate is invariant to trust_gov); its only
trust->growth pathway is the nonlinear regime-collapse output hit, whose magnitude is anchored to the
macroeconomic-disaster literature (Barro & Ursua 2008; ~10-30% peak-to-trough).
"""

import unittest

from gim.core.params import default_params
from gim.core.priors import key_priors
from gim.trust_growth_validation import (
    interest_rate_trust_sensitivity,
    regime_collapse_gdp_drop,
)

COLLAPSE_PRIORS = ("REGIME_COLLAPSE_GDP_MULT", "REGIME_COLLAPSE_CAPITAL_MULT")
DISASTER_BAND = (0.10, 0.30)


class S3TrustGrowthTests(unittest.TestCase):
    def test_no_marginal_trust_growth_channel(self):
        # the structural finding: the effective interest rate does not respond to trust at all
        s = interest_rate_trust_sensitivity()
        self.assertLess(s["rate_span"], 1e-9)

    def test_regime_collapse_drop_matches_disaster_band(self):
        c = regime_collapse_gdp_drop()
        self.assertTrue(DISASTER_BAND[0] <= c["gdp_drop_frac"] <= DISASTER_BAND[1], c["gdp_drop_frac"])
        self.assertEqual(c["regime_crisis_active_years"], 1.0)
        # the realised drop equals 1 - REGIME_COLLAPSE_GDP_MULT
        expected = 1.0 - float(default_params().get("REGIME_COLLAPSE_GDP_MULT"))
        self.assertAlmostEqual(c["gdp_drop_frac"], expected, places=6)

    def test_collapse_priors_sourced_and_real(self):
        kp = key_priors()
        base = default_params()
        for name in COLLAPSE_PRIORS:
            self.assertIn(name, kp, f"{name} missing from priors CSV")
            self.assertTrue(kp[name].source.strip(), f"{name} needs a source citation")
            self.assertIn(name, base, f"{name} is not a real model parameter")
            self.assertAlmostEqual(kp[name].p1, float(base.get(name)), places=6)
        # the 0.7-0.9 GDP-multiplier band maps to a 10-30% loss (the disaster band)
        gdp_prior = kp["REGIME_COLLAPSE_GDP_MULT"]
        self.assertAlmostEqual(1.0 - gdp_prior.high, DISASTER_BAND[0], places=6)
        self.assertAlmostEqual(1.0 - gdp_prior.low, DISASTER_BAND[1], places=6)


if __name__ == "__main__":
    unittest.main()
