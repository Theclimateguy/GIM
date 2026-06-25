#!/usr/bin/env python3
"""S2 — migration gravity elasticities (social-domain analogue of the D6 keystone check).

Exercise GIM's SHIPPED migration engine (gim.core.social.update_migration_flows) on a controlled
synthetic world and recover its gravity elasticities, comparing to the international-migration gravity
literature (Beine, Bertoli & Fernandez-Huertas Moraga 2016; Ramos 2017).

HONEST SCOPE / functional form: GIM has no bilateral distance field, so trade linkage plays the role of
the gravity proximity/contiguity term (a positive linkage elasticity, NOT a -1 distance elasticity). The
engine is linear in the income gap, not log-linear, so the income-LEVEL elasticity is operating-point
dependent (reported, not hidden). What is cleanly reproduced: the canonical unit population-mass
elasticity and a positive, order-1 income elasticity inside the empirical band. This anchors the
MIGRATION_* priors and documents the trade-linkage-as-proximity structural choice.
See docs/calibration/SOCIAL_VALIDATION_PROGRAM.md.

Run: python3 scripts/run_s2_migration_gravity.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gim.core.priors import key_priors                 # noqa: E402
from gim.migration_validation import gravity_elasticities  # noqa: E402

# Gravity income elasticity is typically positive and order ~1 (commonly ~0.5-1.5 across studies).
INCOME_BAND = (0.5, 2.0)
MIGRATION_PRIORS = (
    "MIGRATION_BASE_RATE",
    "MIGRATION_MAX_SHARE",
    "MIGRATION_INCOME_PUSH_W",
    "MIGRATION_CONFLICT_PUSH_W",
)


def main() -> int:
    e = gravity_elasticities()
    print("S2 — migration gravity elasticities (social-domain analogue of D6)")
    print(f"controlled grid: 1 poor origin + {int(e['n_destinations'])} richer destinations "
          "(no back-migration); flows read off the shipped engine via population deltas.\n")
    print(f"  mass (origin-population) elasticity : {e['mass_elasticity']:.3f}  (gravity expects 1)")
    print(f"  income-GAP elasticity               : {e['gap_elasticity']:.3f}  (engine is gap-linear -> 1)")
    print(f"  trade-linkage elasticity            : {e['linkage_elasticity']:.3f}  (proximity term -> 1)")
    print(f"  income-LEVEL elasticity             : {e['income_level_elasticity']:.3f}  "
          f"(gravity band {INCOME_BAND[0]}-{INCOME_BAND[1]})")

    kp = key_priors()
    sourced = all(p in kp and bool(kp[p].source.strip()) for p in MIGRATION_PRIORS)
    print(f"\nanchor: all MIGRATION_* priors sourced key-priors: {sourced}")

    mass_ok = abs(e["mass_elasticity"] - 1.0) < 0.02
    gap_ok = abs(e["gap_elasticity"] - 1.0) < 0.02 and abs(e["linkage_elasticity"] - 1.0) < 0.02
    income_ok = INCOME_BAND[0] <= e["income_level_elasticity"] <= INCOME_BAND[1]
    ok = sourced and mass_ok and gap_ok and income_ok
    print("\nRESULT:", "GRAVITY-CONSISTENT & ANCHORED — unit mass-elasticity, positive order-1 income "
          "elasticity; MIGRATION_* priors sourced." if ok else "CHECK FAILED — investigate.")
    print("Interpretation: GIM migration reproduces the gravity mass/income structure with trade linkage "
          "as the proximity term; the gap-linear form (vs log-linear) is a documented limitation.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
