"""Criticality / self-organized-criticality risk layer (F5).

Real systemic risks - wars, financial crises, regime collapses, cascades - are **fat-tailed**
(power-law / self-organized-criticality), not Gaussian, and they are preceded by generic
**early-warning signals** (critical slowing down). GIM currently models crises with fixed
thresholds and fixed-magnitude shocks, which is thin-tailed and structurally understates tail
risk. This module adds the criticality toolkit, starting with the lowest-risk, highest-value
piece: a Scheffer-style early-warning diagnostic computed post-hoc from a trajectory (no change
to the simulation core, so no calibration/golden risk).

References:
- Scheffer et al. 2009, Nature 461:53 - early-warning signals for critical transitions:
  critical slowing down => rising lag-1 autocorrelation and variance before a bifurcation.
- Richardson 1948 / Clauset 2018 / Cederman 2003 - power-law (SOC) distribution of war sizes.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence


def _lag1_autocorr(x: Sequence[float]) -> float:
    n = len(x)
    if n < 3:
        return float("nan")
    m = sum(x) / n
    denom = sum((v - m) ** 2 for v in x)
    if denom <= 1e-15:
        return 0.0
    num = sum((x[i] - m) * (x[i + 1] - m) for i in range(n - 1))
    return num / denom


def _variance(x: Sequence[float]) -> float:
    n = len(x)
    if n < 2:
        return float("nan")
    m = sum(x) / n
    return sum((v - m) ** 2 for v in x) / n


def _kendall_tau(y: Sequence[float]) -> float:
    """Kendall rank correlation of y vs its index - the standard trend test for EWS.

    +1 = monotonically rising, -1 = falling. Rising AR(1)/variance => approaching criticality.
    """
    n = len(y)
    if n < 3:
        return float("nan")
    concord = discord = 0
    for i in range(n):
        for j in range(i + 1, n):
            s = (y[j] - y[i])
            if s > 0:
                concord += 1
            elif s < 0:
                discord += 1
    total = concord + discord
    return (concord - discord) / total if total else 0.0


def truncated_pareto_mean(alpha: float, a: float, b: float) -> float:
    """Mean of a truncated power law (pdf proportional to x^-alpha on [a, b])."""
    if abs(alpha - 1.0) < 1e-9 or abs(alpha - 2.0) < 1e-9:
        alpha += 1e-6  # avoid the degenerate exponents
    num = (b ** (2.0 - alpha) - a ** (2.0 - alpha)) / (2.0 - alpha)
    den = (b ** (1.0 - alpha) - a ** (1.0 - alpha)) / (1.0 - alpha)
    return num / den if den != 0 else a


def powerlaw_severity(rng, alpha: float = 1.5, a: float = 1.0, b: float = 20.0) -> float:
    """A fat-tailed, **mean-1** event-severity multiplier (self-organized-criticality / Richardson).

    Draws from a truncated power law `Pr(x) ~ x^-alpha` on `[a, b]` (Richardson war-size exponent
    ~1.5-1.6) via inverse-CDF, then divides by the distribution's mean so E[severity] == 1. The
    result is a multiplier whose *average* equals the model's existing fixed shock size, but whose
    upper tail is heavy: most events are near-baseline, a few are catastrophic. Used to make crisis
    / conflict severity fat-tailed instead of fixed.
    """
    if abs(alpha - 1.0) < 1e-9:
        alpha += 1e-6
    u = rng.random()
    a1 = a ** (1.0 - alpha)
    b1 = b ** (1.0 - alpha)
    x = (a1 + u * (b1 - a1)) ** (1.0 / (1.0 - alpha))
    mean = truncated_pareto_mean(alpha, a, b)
    return x / mean if mean > 0 else 1.0


def to_stationary(series: Sequence[float]) -> List[float]:
    """Relative first-difference transform for trending series (e.g. GDP).

    Critical-slowing-down indicators are only meaningful on stationary (non-trending) series; a
    growing level like GDP must first be turned into its growth rate, or it produces spurious
    rising autocorrelation/variance (Scheffer 2009 detrends for the same reason).
    """
    x = [float(v) for v in series]
    return [(x[i] - x[i - 1]) / (abs(x[i - 1]) + 1e-9) for i in range(1, len(x))]


def rolling_indicators(series: Sequence[float], window: int = 8) -> Dict[str, List[float]]:
    """Rolling lag-1 autocorrelation and variance over a sliding window."""
    x = [float(v) for v in series]
    ac, var = [], []
    for end in range(window, len(x) + 1):
        w = x[end - window:end]
        ac.append(_lag1_autocorr(w))
        var.append(_variance(w))
    return {"autocorrelation": ac, "variance": var}


def early_warning_score(series: Sequence[float], window: int = 8) -> Dict[str, float]:
    """Critical-slowing-down early-warning summary for one series.

    Returns the trend (Kendall tau) of rolling autocorrelation and variance. A positive
    `combined` score means the system is showing critical slowing down - a leading indicator
    that it is approaching a tipping point (regime collapse, debt crisis, conflict).
    """
    roll = rolling_indicators(series, window)
    ac = [v for v in roll["autocorrelation"] if not math.isnan(v)]
    var = [v for v in roll["variance"] if not math.isnan(v)]
    tau_ac = _kendall_tau(ac) if len(ac) >= 3 else float("nan")
    tau_var = _kendall_tau(var) if len(var) >= 3 else float("nan")
    parts = [t for t in (tau_ac, tau_var) if not math.isnan(t)]
    combined = sum(parts) / len(parts) if parts else float("nan")
    return {
        "autocorr_trend": tau_ac,
        "variance_trend": tau_var,
        "combined": combined,
        # A combined Kendall-tau trend > 0.25 across both indicators = both autocorrelation and
        # variance trending up = critical-slowing-down warning.
        "warning": bool(not math.isnan(combined) and combined > 0.25),
    }


def early_warning_scan(series_by_name: Dict[str, Sequence[float]], window: int = 8) -> Dict[str, Dict[str, float]]:
    """Early-warning scores for several state series (e.g. trust, tension, debt, conflict)."""
    return {name: early_warning_score(s, window) for name, s in series_by_name.items()}


# NOTE on a live early-warning monitor: critical-slowing-down indicators are only valid on
# *stochastic* series (they measure slowing recovery from noise). GIM's baseline projection is
# smooth and near-deterministic unless the stochastic ensemble / temperature variability is on, so
# scanning a single smooth trajectory yields spurious warnings from the trend, not genuine critical
# slowing down. A correct live monitor therefore operates on the stochastic ENSEMBLE - either on a
# noisy member's de-trended residuals, or on the rising cross-member spread over time - and is left
# as a follow-up (it needs the ensemble harness, not a single deterministic run). The primitives
# above (early_warning_score / scan / rolling_indicators / to_stationary) are the validated tools.
