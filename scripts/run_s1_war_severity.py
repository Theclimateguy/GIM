#!/usr/bin/env python3
"""S1 — war-size power-law exponent (the social-domain analogue of the D6 keystone check).

Anchor GIM's crisis/war severity tail exponent (CRISIS_SEVERITY_ALPHA) to the most robust empirical
regularity in conflict studies: war severity follows a power law Pr(x) ~ x^-alpha with alpha ~ 1.5
(Richardson 1948; reconfirmed by Clauset 2018, Science Advances, with modern MLE+KS; reproduced by
Cederman's 2003 self-organized-criticality model of war). This published exponent is the "DICE number"
of S1.

Two parts, mirroring D6:
  (A) ANCHOR  -- the prior CRISIS_SEVERITY_ALPHA = 1.5 sits inside the published 1.5-1.8 envelope and is
                 a sourced key prior in data/parameter_priors.csv.
  (B) ENGINE  -- feed the prior into GIM's OWN severity sampler (gim/criticality.powerlaw_severity),
                 then RECOVER the exponent with an independent truncated-Pareto MLE and check the KS
                 goodness-of-fit. If the sampler is a correct truncated power law, alpha_hat ~ 1.5 and
                 KS does not reject.

HONEST SCOPE: alpha is an imposed sampler input, so (B) validates the *sampler*, not an *emergent*
exponent. Endogenous emergence (alpha arising from an SOC conflict dynamic) is the deferred research
branch in docs/CRITICALITY_RISK.md. S1 delivers the anchoring half of D6 + sampler validation, not the
engine-reproduction half. See docs/calibration/SOCIAL_VALIDATION_PROGRAM.md.

Run: python3 scripts/run_s1_war_severity.py
"""
from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gim.core.params import default_params       # noqa: E402
from gim.core.priors import key_priors            # noqa: E402
from gim.criticality import (                      # noqa: E402
    fit_truncated_pareto_alpha,
    ks_distance,
    powerlaw_severity,
    truncated_pareto_mean,
)

LIT_LOW, LIT_HIGH = 1.5, 1.8   # published war-size exponent envelope (Richardson / Clauset / Cederman)
N = 40000
SEED = 2026


def main() -> int:
    p = default_params()
    alpha = float(p.get("CRISIS_SEVERITY_ALPHA"))
    b = float(p.get("CRISIS_SEVERITY_MAX"))
    a = 1.0

    print("S1 — war-size power-law exponent (social-domain analogue of D6)")
    print(f"prior CRISIS_SEVERITY_ALPHA = {alpha}  (published war-size envelope {LIT_LOW}-{LIT_HIGH})")

    # (A) ANCHOR: prior inside the published envelope, and a sourced key prior.
    kp = key_priors()
    sourced = "CRISIS_SEVERITY_ALPHA" in kp and bool(kp["CRISIS_SEVERITY_ALPHA"].source.strip())
    in_env = LIT_LOW <= alpha <= LIT_HIGH
    print(f"\n(A) anchor: prior in literature envelope [{LIT_LOW},{LIT_HIGH}]: {in_env}; "
          f"sourced key-prior: {sourced}")

    # (B) ENGINE: draw from GIM's sampler, undo the mean-normalisation to get the raw truncated-Pareto
    #     draws, then refit the exponent independently and check the goodness-of-fit.
    rng = random.Random(SEED)
    mean = truncated_pareto_mean(alpha, a, b)
    raw = [powerlaw_severity(rng, alpha=alpha, a=a, b=b) * mean for _ in range(N)]
    alpha_hat = fit_truncated_pareto_alpha(raw, a=a, b=b)
    ks = ks_distance(raw, alpha_hat, a=a, b=b)
    sample_mean = (sum(raw) / N) / mean   # mean of the (normalised) severity multiplier; target ~1.0

    print(f"(B) engine: N={N} draws; MLE alpha_hat = {alpha_hat:.3f} (input {alpha}); "
          f"KS distance = {ks:.4f}; mean severity = {sample_mean:.3f} (target ~1.0)")

    recovered = abs(alpha_hat - alpha) <= 0.05
    ks_ok = ks <= 0.02
    mean_ok = abs(sample_mean - 1.0) <= 0.05
    ok = in_env and sourced and recovered and ks_ok and mean_ok
    print("\nRESULT:", "ANCHORED & SAMPLER VALID — the prior matches the war-size power law and GIM's "
          "severity engine reproduces it." if ok else "CHECK FAILED — investigate.")
    print("Interpretation: S1 anchors CRISIS_SEVERITY_ALPHA to Richardson/Clauset and validates the "
          "truncated-Pareto sampler; it does NOT claim an emergent exponent (deferred SOC branch).")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
