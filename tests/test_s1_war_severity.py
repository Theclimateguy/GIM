"""S1 — war-size power-law exponent: prior anchoring + severity-sampler validation.

The social-domain analogue of the D6 keystone check: the prior CRISIS_SEVERITY_ALPHA must sit inside
the published war-size exponent envelope (Richardson 1948 / Clauset 2018 / Cederman 2003), and GIM's
own truncated-Pareto severity sampler must reproduce that exponent (MLE recovery + KS goodness-of-fit).
"""

import random
import unittest

from gim.core.params import default_params
from gim.core.priors import key_priors
from gim.criticality import (
    fit_truncated_pareto_alpha,
    ks_distance,
    powerlaw_severity,
    truncated_pareto_mean,
)

LIT_LOW, LIT_HIGH = 1.5, 1.8  # Richardson 1948 / Clauset 2018 / Cederman 2003 war-size envelope


class S1WarSeverityTests(unittest.TestCase):
    def test_prior_is_sourced_and_in_literature_envelope(self):
        kp = key_priors()
        self.assertIn("CRISIS_SEVERITY_ALPHA", kp)
        prior = kp["CRISIS_SEVERITY_ALPHA"]
        self.assertTrue(prior.source.strip(), "CRISIS_SEVERITY_ALPHA needs a source citation")
        self.assertTrue(LIT_LOW <= prior.p1 <= LIT_HIGH, "prior mode outside the war-size envelope")
        # heavy-tailed but a proper power law: 1 < alpha <= 2
        self.assertGreater(prior.low, 1.0)
        self.assertLessEqual(prior.high, 2.0)

    def test_prior_central_matches_default_param(self):
        self.assertAlmostEqual(
            key_priors()["CRISIS_SEVERITY_ALPHA"].p1,
            float(default_params().get("CRISIS_SEVERITY_ALPHA")),
            places=6,
        )

    def test_sampler_recovers_exponent_and_passes_ks(self):
        p = default_params()
        alpha = float(p.get("CRISIS_SEVERITY_ALPHA"))
        b = float(p.get("CRISIS_SEVERITY_MAX"))
        a = 1.0
        rng = random.Random(2026)
        mean = truncated_pareto_mean(alpha, a, b)
        raw = [powerlaw_severity(rng, alpha=alpha, a=a, b=b) * mean for _ in range(8000)]
        alpha_hat = fit_truncated_pareto_alpha(raw, a=a, b=b)
        self.assertAlmostEqual(alpha_hat, alpha, delta=0.1)
        self.assertLess(ks_distance(raw, alpha_hat, a=a, b=b), 0.03)

    def test_severity_multiplier_is_mean_one(self):
        rng = random.Random(7)
        vals = [powerlaw_severity(rng, alpha=1.5, a=1.0, b=20.0) for _ in range(20000)]
        self.assertAlmostEqual(sum(vals) / len(vals), 1.0, delta=0.05)


if __name__ == "__main__":
    unittest.main()
