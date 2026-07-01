#!/usr/bin/env python3
"""S3 — trust -> growth channel (social-domain analogue of the D6 keystone check).

A clean Knack-Keefer (1997) marginal trust->growth elasticity cannot be reproduced because GIM has no
marginal trust->growth channel: trust_gov feeds only the diagnostic credit rating, not the effective
interest rate (-> cost of capital -> investment). This script demonstrates that absence, then validates
and anchors the channel that DOES exist -- the nonlinear regime-collapse output hit -- against the
macroeconomic-disaster / cost-of-instability literature (Barro & Ursua 2008; Aisen & Veiga 2013;
civil-war / state-collapse output losses ~10-30%).

HONEST SCOPE: S3 delivers (1) a structural FINDING (no marginal trust->growth channel; a candidate
model extension, not papered over), and (2) a Tier-A anchor for REGIME_COLLAPSE_GDP_MULT. The collapse
THRESHOLDS remain Tier-C expert priors (no canonical number; sensitivity-disciplined).
See docs/calibration/SOCIAL_VALIDATION_PROGRAM.md.

Run: python3 scripts/run_s3_trust_growth.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gim.core.priors import key_priors                                   # noqa: E402
from gim.trust_growth_validation import (                                # noqa: E402
    interest_rate_trust_sensitivity,
    regime_collapse_gdp_drop,
)

DISASTER_BAND = (0.10, 0.30)   # macroeconomic-disaster peak-to-trough GDP losses (Barro & Ursua 2008)


def main() -> int:
    print("S3 — trust -> growth channel (social-domain analogue of D6)")

    # (1) STRUCTURAL FINDING: the effective rate (-> investment -> growth) is invariant to trust.
    s = interest_rate_trust_sensitivity()
    no_marginal = s["rate_span"] < 1e-9
    print(f"\n(1) marginal channel: effective rate over trust in [0.05,0.95] spans {s['rate_span']:.2e} "
          f"-> {'NO marginal trust->growth channel (as found)' if no_marginal else 'UNEXPECTED channel'}")

    # (2) VALIDATED ANCHOR: the regime-collapse output hit vs the disaster literature.
    c = regime_collapse_gdp_drop()
    drop = c["gdp_drop_frac"]
    in_band = DISASTER_BAND[0] <= drop <= DISASTER_BAND[1]
    print(f"(2) collapse channel: trust<0.20 & tension>0.80 -> one-off GDP drop {drop:.1%} "
          f"(capital {c['capital_drop_frac']:.1%}); disaster band {DISASTER_BAND[0]:.0%}-{DISASTER_BAND[1]:.0%}: {in_band}")

    kp = key_priors()
    sourced = "REGIME_COLLAPSE_GDP_MULT" in kp and bool(kp["REGIME_COLLAPSE_GDP_MULT"].source.strip())
    print(f"\nanchor: REGIME_COLLAPSE_GDP_MULT sourced key-prior: {sourced}")

    ok = no_marginal and in_band and sourced
    print("\nRESULT:", "FINDING + ANCHORED — no marginal trust->growth channel (flagged); the "
          "regime-collapse output hit (~20%) matches the disaster literature and is anchored."
          if ok else "CHECK FAILED — investigate.")
    print("Interpretation: GIM's trust->growth is a nonlinear instability-collapse threshold, not a "
          "marginal social-capital elasticity; a trust->TFP channel is a candidate extension.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
