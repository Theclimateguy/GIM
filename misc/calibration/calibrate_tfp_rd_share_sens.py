from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gim.core import calibration_params as cal  # noqa: E402
from gim.historical_backtest import run_historical_backtest  # noqa: E402


GRID = (0.5, 0.8, 1.0, 1.2, 1.5, 2.0)


def main() -> None:
    original = cal.TFP_RD_SHARE_SENS
    rows: list[tuple[float, float, float, float]] = []
    try:
        for sens in GRID:
            cal.TFP_RD_SHARE_SENS = sens
            result = run_historical_backtest()
            rows.append(
                (
                    sens,
                    result.gdp_rmse_trillions,
                    result.global_co2_rmse_gtco2,
                    result.temperature_rmse_c,
                )
            )
    finally:
        cal.TFP_RD_SHARE_SENS = original

    print("TFP_RD_SHARE_SENS grid search")
    for sens, gdp_rmse, co2_rmse, temp_rmse in rows:
        print(
            f"tfp_rd_share_sens={sens:.1f}  GDP_RMSE={gdp_rmse:.3f}  "
            f"CO2_RMSE={co2_rmse:.3f}  TEMP_RMSE={temp_rmse:.3f}"
        )

    best = min(rows, key=lambda row: (row[1], row[2], row[3]))
    print()
    print(f"Recommended TFP_RD_SHARE_SENS: {best[0]:.1f}")
    if abs(best[0] - GRID[0]) < 1e-9 or abs(best[0] - GRID[-1]) < 1e-9:
        print("Warning: optimum is on the grid boundary; consider an expanded search in the next pass.")


if __name__ == "__main__":
    main()
