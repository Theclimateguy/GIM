"""Canonical chart-ready JSON shapes for the v2 line (THE-65 / THE-67).

Every deterministic mode projects into one of these stable shapes so the Swift
chart components (E5) have a single contract and the CLI and the HTTP engine emit
*identical* JSON (the parity guarantee). No model math here — pure reshaping.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

# The validated ensemble (`gim.ensemble._collect_metrics`) tracks exactly these.
# Inflation / debt *levels* are deliberately absent — the validated metric set
# carries debt/regime stress as crisis *counts*, not levels (honest scoping).
DEFAULT_FAN_METRICS: tuple[str, ...] = (
    "world_gdp",
    "temperature",
    "co2",
    "mean_social_tension",
    "n_debt_crises",
    "n_wars",
)

_BAND_KEYS = ("p5", "p25", "p50", "p75", "p95", "mean")


def fan_series(bands: Dict[str, Dict[str, List[float]]], metric: str, years: Sequence[int]) -> Dict[str, Any]:
    """One metric's fan: median + IQR + 5–95 bands over the horizon (Fig. 4)."""
    b = bands.get(metric, {})
    out: Dict[str, Any] = {"metric": metric, "years": list(years)}
    for key in _BAND_KEYS:
        out[key] = [float(v) for v in b.get(key, [])]
    return out


def ensemble_projection(
    bands: Dict[str, Dict[str, List[float]]],
    years: Sequence[int],
    n_members: int,
    metrics: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    metrics = list(metrics or DEFAULT_FAN_METRICS)
    return {
        "kind": "ensemble",
        "n_members": int(n_members),
        "years": list(years),
        "metrics": [fan_series(bands, m, years) for m in metrics],
    }


def delta_projection(
    delta_bands: Dict[str, Dict[str, List[float]]],
    base_bands: Dict[str, Dict[str, List[float]]],
    scen_bands: Dict[str, Dict[str, List[float]]],
    years: Sequence[int],
    n_members: int,
    metrics: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Scenario − baseline as a *paired* delta fan with a zero reference line, plus
    the baseline and scenario medians for context (Fig. 6–9 / E6)."""
    metrics = list(metrics or DEFAULT_FAN_METRICS)
    out_metrics: List[Dict[str, Any]] = []
    for m in metrics:
        out_metrics.append(
            {
                "metric": m,
                "delta": fan_series(delta_bands, m, years),
                "baseline_p50": [float(v) for v in base_bands.get(m, {}).get("p50", [])],
                "scenario_p50": [float(v) for v in scen_bands.get(m, {}).get("p50", [])],
            }
        )
    return {
        "kind": "scenario_delta",
        "n_members": int(n_members),
        "years": list(years),
        "zero_line": True,
        "metrics": out_metrics,
    }


def dose_projection(
    metric: str,
    grid: Sequence[float],
    terminal_delta: Sequence[float],
    terminal_scenario: Sequence[float],
    terminal_baseline: float,
) -> Dict[str, Any]:
    """Terminal delta vs lever magnitude (Fig. 6–9): the model's non-zero slope
    where sectoral models are flat."""
    return {
        "kind": "dose_response",
        "metric": metric,
        "x": [float(g) for g in grid],
        "delta": [float(v) for v in terminal_delta],
        "scenario": [float(v) for v in terminal_scenario],
        "baseline": float(terminal_baseline),
        "x_label": "lever magnitude",
        "y_label": f"terminal Δ {metric}",
    }


def tornado_projection(metric: str, morris: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
    """Morris ranking (Fig. 3): which parameters drive the output."""
    ranked = sorted(morris.items(), key=lambda kv: kv[1].get("mu_star", 0.0), reverse=True)
    return {
        "kind": "tornado",
        "metric": metric,
        "params": [
            {
                "name": name,
                "mu_star": float(d.get("mu_star", 0.0)),
                "mu": float(d.get("mu", 0.0)),
                "sigma": float(d.get("sigma", 0.0)),
            }
            for name, d in ranked
        ],
    }


def roc_projection(auc: float, ci: Sequence[float], p_value: float, comparison: Dict[str, Any]) -> Dict[str, Any]:
    """Conflict relative-risk AUC (Fig. 2b) for the About panel."""
    return {
        "kind": "conflict_auc",
        "auc": float(auc),
        "ci95": [float(ci[0]), float(ci[1])],
        "p_value": float(p_value),
        "comparison": comparison,
    }


__all__ = [
    "DEFAULT_FAN_METRICS",
    "fan_series",
    "ensemble_projection",
    "delta_projection",
    "dose_projection",
    "tornado_projection",
    "roc_projection",
]
