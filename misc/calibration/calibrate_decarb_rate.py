from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gim.core import calibration_params as cal  # noqa: E402
from gim.historical_backtest import (  # noqa: E402
    compute_observed_global_co2_intensity,
    estimate_observed_decarb_rate,
    run_historical_backtest,
)


def main() -> None:
    observed_mean = estimate_observed_decarb_rate(method="mean_pairwise")
    observed_end_to_end = estimate_observed_decarb_rate(method="end_to_end")
    intensity = compute_observed_global_co2_intensity()
    active_rate = float(cal.DECARB_RATE_STRUCTURAL)

    candidates: list[float] = []
    for value in (
        observed_mean,
        observed_end_to_end,
        0.040,
        0.045,
        active_rate,
        0.052,
        0.055,
        0.056,
    ):
        rounded = round(float(value), 6)
        if rounded not in candidates:
            candidates.append(rounded)

    print("Observed global CO2 intensity (GtCO2 / T$)")
    for year in sorted(intensity):
        print(f"{year}: {intensity[year]:.6f}")
    print()
    print(f"Observed structural decarb rate (mean pairwise): {observed_mean:.6f}")
    print(f"Observed structural decarb rate (end-to-end):  {observed_end_to_end:.6f}")
    print(f"Active artifact decarb rate:                    {active_rate:.6f}")
    print()
    print("Backtest comparison")

    best = None
    for rate in candidates:
        result = run_historical_backtest(decarb_rate_override=rate)
        print(
            f"rate={rate:.6f}  GDP_RMSE={result.gdp_rmse_trillions:.3f}  "
            f"CO2_RMSE={result.global_co2_rmse_gtco2:.3f}  TEMP_RMSE={result.temperature_rmse_c:.3f}"
        )
        key = (result.global_co2_rmse_gtco2, result.gdp_rmse_trillions, result.temperature_rmse_c)
        if best is None or key < best[0]:
            best = (key, rate)

    assert best is not None
    print()
    print(f"Recommended active DECARB_RATE_STRUCTURAL: {best[1]:.6f}")
    print(
        "Observed reference to stamp in the manifest: "
        f"{observed_mean:.6f} (source=observed, years=2015-2023)"
    )


if __name__ == "__main__":
    main()
