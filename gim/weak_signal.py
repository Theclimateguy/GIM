"""Weak-signal detection over GIM's multivariate state space (analyst-tier diagnostic).

Crisis *detection* in GIM is threshold-based (a debt/regime/FX crisis fires when conditions cross a
line). **Weak-signal** analysis is the complement: spotting the subtle, multivariate build-up that
*precedes* a regime shift, before any threshold trips. This module provides two standard, validated
detectors, applied post-hoc to a trajectory or ensemble (zero simulation-core / golden impact):

1. **Mahalanobis anomaly** — how far the current multidimensional state sits from its recent baseline
   distribution, accounting for the covariance between dimensions. A spike means the system has moved
   into an unusual joint region of state space (a weak signal of stress). Flagged against a chi-square
   quantile (the null distribution of the squared Mahalanobis distance for Gaussian state).

2. **Bayesian-flavoured structural break** — a Gaussian mean-shift change-point on a single series,
   scored by a BIC-penalised log-likelihood ratio (single mean vs two segments) turned into a
   posterior-style break probability, with the most likely break location.

These complement the critical-slowing-down early-warning primitives in `gim.criticality`
(rising lag-1 autocorrelation + variance). `weak_signal_scan` combines all three.

Analyst-tier: requires numpy (the GIM core is standard-library only; this is a diagnostic tool, like
`gim.sensitivity`). No scipy dependency — the chi-square quantile uses the Wilson-Hilferty
approximation.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover - analysis-tier dependency
    raise ImportError(
        "gim.weak_signal needs numpy (analysis extra): pip install -e '.[analysis]'"
    ) from exc


def _chi2_ppf(p: float, df: int) -> float:
    """Chi-square quantile via the Wilson-Hilferty approximation (no scipy dependency)."""
    # standard-normal quantile (Acklam-style rational approximation, adequate for thresholds)
    z = _norm_ppf(p)
    t = 1.0 - 2.0 / (9.0 * df) + z * math.sqrt(2.0 / (9.0 * df))
    return df * (t ** 3)


def _norm_ppf(p: float) -> float:
    """Inverse standard-normal CDF (Acklam's rational approximation)."""
    p = min(max(p, 1e-9), 1 - 1e-9)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def mahalanobis_scores(
    states: Sequence[Sequence[float]],
    ref_rows: Optional[int] = None,
    *,
    shrinkage: float = 0.15,
    alpha: float = 0.99,
) -> Dict[str, object]:
    """Squared Mahalanobis distance of each state row from a reference distribution + anomaly flags.

    `states` is a T x D array (rows = time steps, columns = state dimensions). The reference mean and
    covariance are estimated from the first `ref_rows` rows (default: all rows). Covariance is
    shrunk toward its diagonal for stability when D is large or T is small. Rows whose squared
    distance exceeds the chi-square(df=D) `alpha` quantile are flagged as anomalies (weak signals).
    """
    X = np.asarray(states, dtype=float)
    if X.ndim != 2:
        X = X.reshape(len(X), -1)
    n, d = X.shape
    ref = X[: (ref_rows or n)]
    mu = ref.mean(axis=0)
    if ref.shape[0] > 1:
        cov = np.cov(ref, rowvar=False)
    else:
        cov = np.eye(d)
    cov = np.atleast_2d(cov)
    diag = np.diag(np.clip(np.diag(cov), 1e-12, None))
    cov = (1.0 - shrinkage) * cov + shrinkage * diag + 1e-12 * np.eye(d)
    inv = np.linalg.pinv(cov)
    delta = X - mu
    d2 = np.einsum("ij,jk,ik->i", delta, inv, delta)
    threshold = _chi2_ppf(alpha, d)
    flags = d2 > threshold
    return {
        "distance_sq": d2.tolist(),
        "anomaly": flags.tolist(),
        "threshold": float(threshold),
        "n_anomalies": int(flags.sum()),
        "dims": d,
    }


def structural_break(series: Sequence[float], *, min_seg: int = 4) -> Dict[str, object]:
    """Gaussian mean-shift change-point: BIC-penalised log-LR -> posterior-style break probability."""
    x = np.asarray(series, dtype=float)
    n = x.size
    if n < 2 * min_seg:
        return {"break_prob": 0.0, "location": None, "score": 0.0}

    def _ll(seg: np.ndarray) -> float:
        v = max(float(seg.var()), 1e-9)
        return -0.5 * seg.size * (math.log(2 * math.pi * v) + 1.0)

    base = _ll(x)
    best_ll, best_t = -math.inf, None
    for t in range(min_seg, n - min_seg):
        s = _ll(x[:t]) + _ll(x[t:])
        if s > best_ll:
            best_ll, best_t = s, t
    lr = best_ll - base                 # log-likelihood ratio for one break
    score = lr - 0.5 * math.log(n)      # BIC penalty for the extra (mean) parameter
    prob = 1.0 / (1.0 + math.exp(-score))
    return {"break_prob": float(prob), "location": int(best_t) if best_t is not None else None,
            "score": float(score)}


def _to_stationary(values: Sequence[float]) -> List[float]:
    """First-difference a series to remove a secular trend (reuse criticality.to_stationary if present)."""
    try:
        from .criticality import to_stationary
        return list(to_stationary(list(values)))
    except Exception:  # pragma: no cover - fallback to plain first differences
        x = list(values)
        return [x[i] - x[i - 1] for i in range(1, len(x))]


def weak_signal_scan(
    series_by_name: Dict[str, Sequence[float]],
    *,
    ref_frac: float = 0.5,
    alpha: float = 0.99,
    detrend: bool = True,
) -> Dict[str, object]:
    """Combined weak-signal report over a multivariate state trajectory.

    `series_by_name` maps each state dimension to its values over time (equal length). GIM state
    series are typically trending, and anomaly/break detection on raw *levels* just re-detects the
    trend; so by default (`detrend=True`) every series is first-differenced to its stationary
    increment before scanning — weak signals then mean departures from the system's *normal
    dynamics*, which is what we want. Set `detrend=False` to scan raw levels. Returns:

    - `mahalanobis`: joint-state anomaly scores/flags (which time steps are multivariate-anomalous);
    - `structural_breaks`: per-series break probability + location (a regime shift in the dynamics);
    - `early_warning`: per-series critical-slowing-down score (from gim.criticality), when available.
    """
    names = [k for k, v in series_by_name.items() if len(v) >= 4]
    if not names:
        return {"mahalanobis": None, "structural_breaks": {}, "early_warning": {}, "dimensions": []}
    T = min(len(series_by_name[k]) for k in names)
    proc = {k: (_to_stationary(series_by_name[k][:T]) if detrend else list(series_by_name[k][:T]))
            for k in names}
    Tp = min(len(proc[k]) for k in names)
    matrix = [[float(proc[k][t]) for k in names] for t in range(Tp)]
    ref_rows = max(2, int(ref_frac * Tp))

    maha = mahalanobis_scores(matrix, ref_rows=ref_rows, alpha=alpha)
    breaks = {k: structural_break(proc[k]) for k in names}
    ews: Dict[str, object] = {}
    try:
        from .criticality import early_warning_score
        ews = {k: early_warning_score(series_by_name[k][:T]) for k in names}
    except Exception:  # pragma: no cover - criticality optional / short series
        ews = {}
    return {"mahalanobis": maha, "structural_breaks": breaks, "early_warning": ews,
            "dimensions": names, "detrended": detrend}


__all__ = ["mahalanobis_scores", "structural_break", "weak_signal_scan"]
