from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gim.historical_backtest import run_historical_backtest  # noqa: E402


GRID = (0.0, 0.04, 0.06, 0.08, 0.10)
ENSEMBLE_SIZE = 8


@dataclass(frozen=True)
class TemperatureVariabilityPoint:
    sigma: float
    temperature_rmse_c: float
    temperature_bias_c: float
    temperature_predicted_std_c: float
    gdp_rmse_trillions: float
    global_co2_rmse_gtco2: float


def main() -> None:
    points: list[TemperatureVariabilityPoint] = []
    for sigma in GRID:
        result = run_historical_backtest(
            temperature_variability_sigma_override=sigma,
            temperature_ensemble_size=ENSEMBLE_SIZE if sigma > 0.0 else 1,
        )
        points.append(
            TemperatureVariabilityPoint(
                sigma=sigma,
                temperature_rmse_c=result.temperature_rmse_c,
                temperature_bias_c=result.temperature_bias_c,
                temperature_predicted_std_c=result.temperature_predicted_std_c,
                gdp_rmse_trillions=result.gdp_rmse_trillions,
                global_co2_rmse_gtco2=result.global_co2_rmse_gtco2,
            )
        )

    print("TEMP_NATURAL_VARIABILITY_SIGMA grid search")
    for point in points:
        print(
            f"sigma={point.sigma:.2f}  "
            f"Temp_RMSE={point.temperature_rmse_c:.4f}  "
            f"Temp_bias={point.temperature_bias_c:+.4f}  "
            f"Temp_std={point.temperature_predicted_std_c:.4f}  "
            f"GDP_RMSE={point.gdp_rmse_trillions:.3f}  "
            f"CO2_RMSE={point.global_co2_rmse_gtco2:.3f}"
        )

    recommended = min(
        points,
        key=lambda point: (
            abs(point.temperature_predicted_std_c - 0.103),
            point.temperature_rmse_c,
            abs(point.temperature_bias_c),
        ),
    )
    print(
        "\nRecommended TEMP_NATURAL_VARIABILITY_SIGMA: "
        f"{recommended.sigma:.2f}"
    )


if __name__ == "__main__":
    main()
