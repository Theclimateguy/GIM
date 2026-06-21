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
