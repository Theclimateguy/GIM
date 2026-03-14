from __future__ import annotations

from dataclasses import dataclass

from .core.state_artifact import ACTIVE_STATE_ARTIFACT
from .historical_backtest import run_historical_backtest


IEA_OBSERVED_DECARB_RATE = 0.022
DEFAULT_DECARB_CANDIDATES = (
    ACTIVE_STATE_ARTIFACT.decarb_rate,
    0.040,
    0.030,
    IEA_OBSERVED_DECARB_RATE,
    0.018,
)


@dataclass(frozen=True)
class DecarbSensitivityPoint:
    label: str
    decarb_rate: float
    gdp_rmse_trillions: float
    global_co2_rmse_gtco2: float
    temperature_rmse_c: float


def evaluate_decarb_sensitivity(
    candidates: tuple[float, ...] = DEFAULT_DECARB_CANDIDATES,
) -> list[DecarbSensitivityPoint]:
    points: list[DecarbSensitivityPoint] = []
    active_rate = float(ACTIVE_STATE_ARTIFACT.decarb_rate)
    for rate in candidates:
        result = run_historical_backtest(decarb_rate_override=rate)
        if abs(rate - active_rate) < 1e-12:
            label = "active"
        elif abs(rate - IEA_OBSERVED_DECARB_RATE) < 1e-12:
            label = "observed_iea"
        else:
            label = f"candidate_{rate:.3f}"
        points.append(
            DecarbSensitivityPoint(
                label=label,
                decarb_rate=float(rate),
                gdp_rmse_trillions=result.gdp_rmse_trillions,
                global_co2_rmse_gtco2=result.global_co2_rmse_gtco2,
                temperature_rmse_c=result.temperature_rmse_c,
            )
        )
    return points


def recommend_decarb_rate(
    points: list[DecarbSensitivityPoint],
) -> DecarbSensitivityPoint:
    if not points:
        raise ValueError("No decarb sensitivity points provided")
    return min(
        points,
        key=lambda point: (
            point.global_co2_rmse_gtco2,
            point.temperature_rmse_c,
            point.gdp_rmse_trillions,
        ),
    )


def format_decarb_sensitivity(points: list[DecarbSensitivityPoint]) -> str:
    recommended = recommend_decarb_rate(points)
    lines = ["Decarb sensitivity backtest"]
    for point in points:
        marker = "*" if point == recommended else "-"
        lines.append(
            f"{marker} {point.label}: rate={point.decarb_rate:.3f}, "
            f"GDP={point.gdp_rmse_trillions:.3f}, CO2={point.global_co2_rmse_gtco2:.3f}, "
            f"Temp={point.temperature_rmse_c:.3f}"
        )
    lines.append(f"Recommended rate: {recommended.decarb_rate:.3f} ({recommended.label})")
    return "\n".join(lines)
