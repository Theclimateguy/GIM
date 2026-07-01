"""Damage-function cross-validation against the empirical literature (T1.4).

The climate-damage coefficient is the single most consequential - and most disputed -
parameter in any integrated assessment model; it is the main driver of the "catastrophic
spread" across published Social-Cost-of-Carbon estimates. This module pins GIM's damage
function to the world empirical literature so its position is explicit, auditable and
guarded by a test, rather than an unexamined choice.

GIM uses a **level-effect** quadratic damage on annual output:

    output multiplier = 1 - DAMAGE_QUAD_COEFF * T^2        (T = warming above pre-industrial)

so the fractional GDP loss at warming ``T`` is ``DAMAGE_QUAD_COEFF * T^2``. The relevant
comparison is therefore the *level-effect* damage literature (DICE, Howard-Sterner
meta-analysis), reported below as the implied quadratic coefficient ``a`` in
``loss = a * T^2``. Two influential *growth-effect* studies (Burke 2015, Kotz 2024) are
included for context but are NOT directly comparable as a level coefficient and are not
used in the numeric envelope (see notes; Kotz 2024 was retracted).

All figures are from the cited primary sources (validated June 2026).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .core import calibration_params as cal_module
from .core.params import default_params


@dataclass(frozen=True)
class DamageEstimate:
    key: str
    citation: str
    form: str                         # "level" (quadratic in T) or "growth" (affects growth rate)
    loss_pct_at_3C: Optional[float]   # % GDP loss at +3 C (level studies); None for growth studies
    implied_quadratic_coeff: Optional[float]  # a in loss = a*T^2 (fraction), level studies only
    note: str


# --- Empirical evidence table (level-effect quadratic coefficient a in loss = a*T^2) ----
EMPIRICAL_DAMAGE_ESTIMATES: List[DamageEstimate] = [
    DamageEstimate(
        "dice_2016r2", "Nordhaus & Moffat 2017; DICE-2016R2 (Nordhaus 2017, Cowles d2057)",
        "level", 2.1, 0.00236,
        "One-parameter quadratic, no linear term; incl. +25% omitted-sector premium. "
        "8.5% at 6 C. Widely criticised as a lower bound on true damages.",
    ),
    DamageEstimate(
        "dice_2013r", "Nordhaus 2013; DICE-2013R",
        "level", 2.4, 0.00267,
        "Predecessor coefficient (0.267%/C^2); revised down in 2016 after Tol-survey corrections.",
    ),
    DamageEstimate(
        "gim", "GIM17 (this model)",
        "level", 7.0, 0.0078,
        "[#17] DAMAGE_QUAD_COEFF=0.0078 -> 7.0%/3C; re-anchored to the Howard & Sterner 2017 preferred "
        "central. ~3x DICE-2016R2. Engine applies it normalised to the 2023 baseline (incremental "
        "damages, no double-count); this absolute-T figure is for literature comparison.",
    ),
    DamageEstimate(
        "howard_sterner_noncat", "Howard & Sterner 2017, Env. Resource Econ. 68:197 (preferred)",
        "level", 7.5, 0.00833,
        "Meta-analysis preferred non-catastrophic damages 7-8%/3C; ~3-4x the 2015 SCC vs DICE.",
    ),
    DamageEstimate(
        "howard_sterner_cat", "Howard & Sterner 2017 (incl. catastrophic risk)",
        "level", 9.5, 0.01056,
        "9-10%/3C with catastrophic risk; ~4-5x the SCC vs DICE.",
    ),
    DamageEstimate(
        "meta_low", "Howard & Sterner 2017, survey of prior meta-analyses (low end)",
        "level", 1.9, 0.00211,
        "Lowest prior meta-analysis estimate at 3C.",
    ),
    DamageEstimate(
        "meta_high", "Howard & Sterner 2017, survey of prior meta-analyses (high end)",
        "level", 17.3, 0.01922,
        "Highest prior meta-analysis estimate at 3C.",
    ),
    DamageEstimate(
        "burke_2015", "Burke, Hsiang & Miguel 2015, Nature 527:235",
        "growth", None, None,
        "Growth-effect: ~23% lower global income by 2100 under RCP8.5 (SSP5); roughly linear, "
        "slightly concave in T; 2.5-100x prior IAM costs at 2C. Not a level coefficient.",
    ),
    DamageEstimate(
        "kotz_2024", "Kotz, Levermann & Wenz 2024, Nature 628:551 (RETRACTED)",
        "growth", None, None,
        "Growth-effect: ~19% committed income reduction by ~2049 (likely 11-29%). "
        "ARTICLE RETRACTED - reported for context only, not used as a calibration anchor.",
    ),
]

# Level-effect empirical envelope for the cross-validation guard: the full span of the
# level-effect estimates, from the low end of prior meta-analyses (1.9%/3C) to the high
# end (17.3%/3C) per the Howard & Sterner 2017 survey. GIM should sit strictly inside this
# band at policy-relevant warming. (DICE-2016R2 sits near the low end at 2.1%/3C.)
ENVELOPE_LOW_COEFF = 0.00211   # prior meta-analysis low end (1.9%/3C)
ENVELOPE_HIGH_COEFF = 0.01922  # prior meta-analysis high end (17.3%/3C)


def gim_damage_coeff(params=None) -> float:
    cal = params if params is not None else default_params()
    return float(cal.DAMAGE_QUAD_COEFF)


def gim_loss_fraction(warming_c: float, params=None) -> float:
    """GIM fractional GDP loss at ``warming_c`` degrees above pre-industrial."""
    return gim_damage_coeff(params) * (float(warming_c) ** 2)


def empirical_envelope(warming_c: float) -> Tuple[float, float]:
    """(low, high) fractional GDP loss at ``warming_c`` from the level-effect envelope."""
    t2 = float(warming_c) ** 2
    return ENVELOPE_LOW_COEFF * t2, ENVELOPE_HIGH_COEFF * t2


def gim_within_envelope(params=None, warmings: Tuple[float, ...] = (2.0, 3.0, 4.0)) -> bool:
    """True iff GIM's loss is inside the empirical level-effect envelope at each warming."""
    for w in warmings:
        lo, hi = empirical_envelope(w)
        loss = gim_loss_fraction(w, params)
        if not (lo <= loss <= hi):
            return False
    return True


def level_estimates() -> List[DamageEstimate]:
    return [e for e in EMPIRICAL_DAMAGE_ESTIMATES if e.form == "level"]


def comparison_table(params=None) -> List[Dict[str, object]]:
    """Tabular GIM-vs-literature comparison at +3 C (level studies), sorted by severity."""
    rows: List[Dict[str, object]] = []
    for e in sorted(level_estimates(), key=lambda x: x.implied_quadratic_coeff or 0.0):
        rows.append({
            "key": e.key,
            "loss_pct_at_3C": e.loss_pct_at_3C,
            "coeff": e.implied_quadratic_coeff,
            "citation": e.citation,
        })
    return rows
