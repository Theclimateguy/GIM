from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gim.core import calibration_params as cal  # noqa: E402
from gim.historical_backtest import run_historical_backtest  # noqa: E402


GRID = (0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.12)


def main() -> None:
    original = cal.GAMMA_ENERGY
    rows: list[tuple[float, float, float, float]] = []
    try:
        for gamma in GRID:
            cal.GAMMA_ENERGY = gamma
            result = run_historical_backtest()
            rows.append(
                (
                    gamma,
                    result.gdp_rmse_trillions,
                    result.global_co2_rmse_gtco2,
                    result.temperature_rmse_c,
                )
            )
    finally:
        cal.GAMMA_ENERGY = original

    print("GAMMA_ENERGY grid search")
    for gamma, gdp_rmse, co2_rmse, temp_rmse in rows:
        print(
            f"gamma={gamma:.2f}  GDP_RMSE={gdp_rmse:.3f}  "
            f"CO2_RMSE={co2_rmse:.3f}  TEMP_RMSE={temp_rmse:.3f}"
        )

    best = min(rows, key=lambda row: (row[1], row[2], row[3]))
    gdp_values = [row[1] for row in rows]
    co2_values = [row[2] for row in rows]
    print()
    if max(gdp_values) - min(gdp_values) < 1e-6 and max(co2_values) - min(co2_values) < 1e-6:
        print(
            "Surface is flat on the current historical backtest; "
            "GAMMA_ENERGY is not identified by this harness and should stay unchanged for now."
        )
    else:
        print(f"Recommended GAMMA_ENERGY: {best[0]:.2f}")


if __name__ == "__main__":
    main()
