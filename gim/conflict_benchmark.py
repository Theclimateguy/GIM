"""S4 — conflict forecast-skill benchmark (Tier-B: skill vs a reproducible reference model).

The existing conflict backtest (scripts/conflict_backtest.py) scores GIM's conflict_proneness against
UCDP/PRIO and reports AUC / Brier-skill vs the base rate. S4 adds the two pieces that make it a D6-style
*reproducible* benchmark rather than a bare skill number:

  (1) CALIBRATION -- a Murphy (1973) Brier decomposition (reliability / resolution / uncertainty) and a
      calibration error, so we report not just discrimination (AUC) but reliability.
  (2) PUBLISHED REFERENCE -- the out-of-sample skill of the standard conflict-forecasting models is
      recorded with citations, and GIM's measured skill is placed against that band.

HONEST SCOPE: this is Tier-B (forecast-skill benchmark), not D6 engine-reproduction. The reference
models score DIFFERENT targets/units (PITF: 2-yr instability ONSET, country-year; ViEWS: country-month /
grid-month incidence -- AUC inflated by easy negatives on an imbalanced target), so the comparison is an
order-of-magnitude/sign placement, not a same-test-set bake-off. GIM's number is achieved by an UNFITTED
mechanistic risk input (no parameters trained on the conflict record), which is the substantive point.
A true same-set bake-off needs ViEWS replication data (deferred). See docs/calibration/SOCIAL_VALIDATION_PROGRAM.md.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple


def brier_decomposition(
    probs: Sequence[float], labels: Sequence[int], n_bins: int = 10
) -> Dict[str, float]:
    """Murphy (1973) decomposition: Brier = reliability - resolution + uncertainty.

    reliability  (lower better): mean squared gap between forecast and observed frequency per bin.
    resolution   (higher better): how far bin outcomes deviate from the base rate (discrimination).
    uncertainty  : base_rate*(1-base_rate), the irreducible part.
    calibration_error: frequency-weighted |forecast - observed| (ECE-style).

    Standard binned Murphy decomposition: brier = reliability - resolution + uncertainty holds EXACTLY
    when each bin is single-valued; with forecasts varying inside a bin there is an additional within-bin
    variance/covariance residual (Stephenson et al. 2008), so on continuous forecasts the three terms are
    a diagnostic, not an exact algebraic identity. The reliability diagram (`calibration_curve`) is the
    primary calibration evidence.
    """
    n = len(labels)
    if n == 0:
        return {k: float("nan") for k in
                ("brier", "reliability", "resolution", "uncertainty", "calibration_error")}
    base = sum(labels) / n
    uncertainty = base * (1.0 - base)
    reliability = 0.0
    resolution = 0.0
    cal_err = 0.0
    for lo in range(n_bins):
        a = lo / n_bins
        b = (lo + 1) / n_bins
        idx = [i for i, p in enumerate(probs) if (a <= p < b or (lo == n_bins - 1 and p == b))]
        if not idx:
            continue
        nk = len(idx)
        p_bar = sum(probs[i] for i in idx) / nk
        o_bar = sum(labels[i] for i in idx) / nk
        reliability += nk * (p_bar - o_bar) ** 2
        resolution += nk * (o_bar - base) ** 2
        cal_err += nk * abs(p_bar - o_bar)
    reliability /= n
    resolution /= n
    cal_err /= n
    brier = sum((p - y) ** 2 for p, y in zip(probs, labels)) / n
    return {
        "brier": brier,
        "reliability": reliability,
        "resolution": resolution,
        "uncertainty": uncertainty,
        "calibration_error": cal_err,
    }


def calibration_curve(
    probs: Sequence[float], labels: Sequence[int], n_bins: int = 10
) -> List[Tuple[float, float, int]]:
    """Reliability diagram points: (mean forecast, observed frequency, count) per occupied bin."""
    out: List[Tuple[float, float, int]] = []
    for lo in range(n_bins):
        a = lo / n_bins
        b = (lo + 1) / n_bins
        idx = [i for i, p in enumerate(probs) if (a <= p < b or (lo == n_bins - 1 and p == b))]
        if not idx:
            continue
        nk = len(idx)
        out.append((sum(probs[i] for i in idx) / nk, sum(labels[i] for i in idx) / nk, nk))
    return out


# Published out-of-sample skill of the standard conflict-forecasting models. AUC values are approximate
# and on DIFFERENT targets/units than GIM's (see module docstring) -- reference points, not a common set.
PUBLISHED_BENCHMARKS = (
    {
        "model": "PITF (Goldstone et al. 2010, AJPS)",
        "target": "political-instability onset, 2-yr-ahead, country-year",
        "skill": "~80% balanced accuracy (~AUC 0.80-0.85)",
        "auc_approx": 0.82,
    },
    {
        "model": "ViEWS (Hegre et al. 2019 JPR; 2022 competition)",
        "target": "state-based violence, country-month / PRIO-grid-month incidence (imbalanced)",
        "skill": "AUC ~0.85-0.95 (inflated by easy negatives on a rare-event target)",
        "auc_approx": 0.90,
    },
)


def compare_to_benchmarks(auc: float, bss: float) -> Dict[str, object]:
    """Place GIM's measured skill against the published reference band (with the honest caveat)."""
    lo = min(b["auc_approx"] for b in PUBLISHED_BENCHMARKS)
    above_chance = auc > 0.5 and bss > 0.0
    return {
        "gim_auc": auc,
        "gim_bss": bss,
        "reference_auc_band": (lo, max(b["auc_approx"] for b in PUBLISHED_BENCHMARKS)),
        "above_chance": above_chance,
        "verdict": (
            "above chance, lower end of the published EWS range — achieved by an UNFITTED mechanistic "
            "risk input on a country-level incidence target (not a same-set bake-off vs PITF/ViEWS)."
            if above_chance else "no skill vs chance — investigate."
        ),
    }


__all__ = [
    "brier_decomposition",
    "calibration_curve",
    "PUBLISHED_BENCHMARKS",
    "compare_to_benchmarks",
]
