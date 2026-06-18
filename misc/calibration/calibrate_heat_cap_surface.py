from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gim.core import calibration_params as cal  # noqa: E402
from gim.historical_backtest import run_historical_backtest  # noqa: E402


GRID = (8.0, 10.0, 12.0, 15.0, 20.0, 30.0, 40.0, 50.0)


@dataclass(frozen=True)
class HeatCapPoint:
    heat_cap_surface: float
    temperature_rmse_c: float
    temperature_bias_c: float
    temperature_predicted_std_c: float
    gdp_rmse_trillions: float
    global_co2_rmse_gtco2: float


def main() -> None:
    original = cal.HEAT_CAP_SURFACE
    try:
        points: list[HeatCapPoint] = []
        for heat_cap_surface in GRID:
            cal.HEAT_CAP_SURFACE = heat_cap_surface
            result = run_historical_backtest(
                temperature_variability_sigma_override=0.0,
                temperature_ensemble_size=1,
            )
            points.append(
                HeatCapPoint(
                    heat_cap_surface=heat_cap_surface,
                    temperature_rmse_c=result.temperature_rmse_c,
                    temperature_bias_c=result.temperature_bias_c,
                    temperature_predicted_std_c=result.temperature_predicted_std_c,
                    gdp_rmse_trillions=result.gdp_rmse_trillions,
                    global_co2_rmse_gtco2=result.global_co2_rmse_gtco2,
                )
            )
    finally:
        cal.HEAT_CAP_SURFACE = original

    print("HEAT_CAP_SURFACE grid search (deterministic temperature backtest)")
    for point in points:
        print(
            f"C_s={point.heat_cap_surface:5.1f}  "
            f"Temp_RMSE={point.temperature_rmse_c:.4f}  "
            f"Temp_bias={point.temperature_bias_c:+.4f}  "
            f"Temp_std={point.temperature_predicted_std_c:.4f}  "
            f"GDP_RMSE={point.gdp_rmse_trillions:.3f}  "
            f"CO2_RMSE={point.global_co2_rmse_gtco2:.3f}"
        )

    recommended = min(
        points,
        key=lambda point: (
            point.temperature_rmse_c,
            abs(point.temperature_bias_c),
            abs(point.temperature_predicted_std_c - 0.103),
        ),
    )
    print(
        "\nRecommended HEAT_CAP_SURFACE: "
        f"{recommended.heat_cap_surface:.1f}"
    )


if __name__ == "__main__":
    main()
