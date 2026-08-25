"""Forecast skill scoring for validation (Phase 2-A).

Proper scoring rules and reference baselines so model quality can be judged against
"do nothing" forecasts rather than in the abstract:

- **RMSE / MAE** — deterministic point-forecast error.
- **CRPS** (Continuous Ranked Probability Score) — proper score for probabilistic
  (ensemble) forecasts; reduces to MAE for a single-member forecast.
- **interval coverage** — does the model's X% band contain the truth ~X% of the time?
- **baselines** — persistence (carry the anchor value forward) and naive linear trend.
- **skill score** — ``1 - err_model / err_baseline`` (>0 means the model beats the baseline).

Series are dicts ``{year: value}``.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence

Series = Dict[int, float]


def _common_years(a: Series, b: Series) -> List[int]:
    return sorted(set(a) & set(b))


def rmse(predicted: Series, observed: Series) -> float:
    years = _common_years(predicted, observed)
    if not years:
        return float("nan")
    return math.sqrt(sum((predicted[y] - observed[y]) ** 2 for y in years) / len(years))


def mae(predicted: Series, observed: Series) -> float:
    years = _common_years(predicted, observed)
    if not years:
        return float("nan")
    return sum(abs(predicted[y] - observed[y]) for y in years) / len(years)


def crps_ensemble(observation: float, samples: Sequence[float]) -> float:
    """Empirical CRPS for an ensemble forecast (energy-form estimator).

    CRPS = mean|x_i - y| - 0.5 * mean_{i,j}|x_i - x_j|. For one sample this is |x - y| (MAE).
    """
    m = len(samples)
    if m == 0:
        return float("nan")
    term1 = sum(abs(s - observation) for s in samples) / m
    if m == 1:
        return term1
    term2 = sum(abs(si - sj) for si in samples for sj in samples) / (m * m)
    return term1 - 0.5 * term2


def mean_crps(observed: Series, ensemble_by_year: Dict[int, Sequence[float]]) -> float:
    years = [y for y in observed if y in ensemble_by_year]
    if not years:
        return float("nan")
    return sum(crps_ensemble(observed[y], ensemble_by_year[y]) for y in years) / len(years)


def interval_coverage(observed: Series, lower: Series, upper: Series) -> float:
    years = [y for y in observed if y in lower and y in upper]
    if not years:
        return float("nan")
    inside = sum(1 for y in years if lower[y] <= observed[y] <= upper[y])
    return inside / len(years)


def persistence_forecast(observed: Series, anchor_year: int) -> Series:
    """Carry the anchor-year observation forward (the canonical no-skill baseline)."""
    if anchor_year not in observed:
        anchor_year = min(observed)
    value = observed[anchor_year]
    return {y: value for y in observed if y >= anchor_year}


def trend_forecast(observed: Series, train_years: Sequence[int]) -> Series:
    """Ordinary-least-squares linear trend fit on train_years, extrapolated over all years."""
    ty = sorted(train_years)
    n = len(ty)
    if n < 2:
        return persistence_forecast(observed, ty[0] if ty else min(observed))
    xbar = sum(ty) / n
    ybar = sum(observed[y] for y in ty) / n
    sxx = sum((y - xbar) ** 2 for y in ty)
    sxy = sum((y - xbar) * (observed[y] - ybar) for y in ty)
    slope = sxy / sxx if sxx else 0.0
    intercept = ybar - slope * xbar
    return {y: intercept + slope * y for y in observed}


def skill_score(err_model: float, err_baseline: float) -> float:
    """1 - err_model/err_baseline. >0 beats the baseline; 1.0 is perfect; <0 is worse."""
    if err_baseline == 0 or math.isnan(err_baseline):
        return float("nan")
    return 1.0 - err_model / err_baseline


def score_series(
    predicted: Series,
    observed: Series,
    *,
    anchor_year: int | None = None,
    train_years: Sequence[int] | None = None,
) -> Dict[str, float]:
    """Score a model series vs observed, with persistence and trend baselines."""
    anchor_year = anchor_year if anchor_year is not None else min(observed)
    train_years = train_years if train_years is not None else [anchor_year, anchor_year + 1]
    # Forecast horizon: years strictly after the anchor (out-of-sample relative to anchor).
    horizon = {y: observed[y] for y in observed if y > anchor_year}
    pred_h = {y: predicted[y] for y in horizon if y in predicted}

    model_rmse = rmse(pred_h, horizon)
    pers = persistence_forecast(observed, anchor_year)
    trend = trend_forecast(observed, train_years)
    pers_rmse = rmse({y: pers[y] for y in horizon if y in pers}, horizon)
    trend_rmse = rmse({y: trend[y] for y in horizon if y in trend}, horizon)
    return {
        "model_rmse": model_rmse,
        "persistence_rmse": pers_rmse,
        "trend_rmse": trend_rmse,
        "skill_vs_persistence": skill_score(model_rmse, pers_rmse),
        "skill_vs_trend": skill_score(model_rmse, trend_rmse),
    }


__all__ = [
    "rmse", "mae", "crps_ensemble", "mean_crps", "interval_coverage",
    "persistence_forecast", "trend_forecast", "skill_score", "score_series",
]
