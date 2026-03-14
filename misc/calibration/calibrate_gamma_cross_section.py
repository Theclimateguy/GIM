from __future__ import annotations

from dataclasses import dataclass
import csv
import json
import math
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gim.core import calibration_params as cal  # noqa: E402
from gim.historical_backtest import DEFAULT_INITIAL_STATE_CSV, DEFAULT_OBSERVED_FIXTURE, GDP_BACKTEST_ACTORS  # noqa: E402


LITERATURE_MIN = 0.04
LITERATURE_MAX = 0.07
GRID_STEP = 0.001
TARGET_YEAR = "2015"


@dataclass(frozen=True)
class GammaCrossSectionRow:
    country: str
    log_capital: float
    log_labor: float
    log_energy: float
    log_gdp: float


@dataclass(frozen=True)
class GammaCrossSectionFit:
    sample_size: int
    alpha_capital: float
    beta_labor: float
    unconstrained_gamma: float
    unconstrained_intercept: float
    unconstrained_log_rmse: float
    unconstrained_level_rmse: float
    bounded_gamma: float
    bounded_intercept: float
    bounded_log_rmse: float
    bounded_level_rmse: float
    bounded_r_squared: float


def _load_observed_2015_gdp(path: Path) -> dict[str, float]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        name: float(value)
        for name, value in raw["gdp_trillions_by_year"][TARGET_YEAR].items()
        if name in GDP_BACKTEST_ACTORS
    }


def load_gamma_cross_section(
    *,
    state_csv: Path = DEFAULT_INITIAL_STATE_CSV,
    observed_fixture: Path = DEFAULT_OBSERVED_FIXTURE,
) -> list[GammaCrossSectionRow]:
    observed_gdp = _load_observed_2015_gdp(Path(observed_fixture))
    rows: list[GammaCrossSectionRow] = []
    with Path(state_csv).open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            country = row["name"]
            if country not in observed_gdp:
                continue
            capital = max(float(row["capital"]), 1e-9)
            labor = max(float(row["population"]) / 1e9, 1e-9)
            energy_input = max(float(row["energy_consumption"]) / 1000.0, 1e-9)
            gdp = max(observed_gdp[country], 1e-9)
            rows.append(
                GammaCrossSectionRow(
                    country=country,
                    log_capital=math.log(capital),
                    log_labor=math.log(labor),
                    log_energy=math.log(energy_input),
                    log_gdp=math.log(gdp),
                )
            )
    return rows


def _fit_intercept_and_errors(
    rows: list[GammaCrossSectionRow],
    *,
    alpha: float,
    beta: float,
    gamma: float,
) -> tuple[float, float, float, float]:
    residual_targets = [
        row.log_gdp - alpha * row.log_capital - beta * row.log_labor
        for row in rows
    ]
    mean_log_energy = sum(row.log_energy for row in rows) / len(rows)
    mean_residual = sum(residual_targets) / len(residual_targets)
    intercept = mean_residual - gamma * mean_log_energy

    squared_log_errors = []
    squared_level_errors = []
    fitted_logs = []
    for row in rows:
        fitted_log = intercept + alpha * row.log_capital + beta * row.log_labor + gamma * row.log_energy
        fitted_logs.append(fitted_log)
        squared_log_errors.append((fitted_log - row.log_gdp) ** 2)
        squared_level_errors.append((math.exp(fitted_log) - math.exp(row.log_gdp)) ** 2)

    log_rmse = math.sqrt(sum(squared_log_errors) / len(squared_log_errors))
    level_rmse = math.sqrt(sum(squared_level_errors) / len(squared_level_errors))
    mean_log_gdp = sum(row.log_gdp for row in rows) / len(rows)
    total_ss = sum((row.log_gdp - mean_log_gdp) ** 2 for row in rows)
    residual_ss = sum((fitted_log - row.log_gdp) ** 2 for fitted_log, row in zip(fitted_logs, rows))
    r_squared = 1.0 - residual_ss / total_ss if total_ss > 0.0 else 0.0
    return intercept, log_rmse, level_rmse, r_squared


def estimate_gamma_cross_section(
    *,
    rows: list[GammaCrossSectionRow] | None = None,
    alpha: float = cal.ALPHA_CAPITAL,
    beta: float = cal.BETA_LABOR,
    lower: float = LITERATURE_MIN,
    upper: float = LITERATURE_MAX,
    step: float = GRID_STEP,
) -> GammaCrossSectionFit:
    if rows is None:
        rows = load_gamma_cross_section()
    if not rows:
        raise ValueError("No cross-sectional rows available for GAMMA_ENERGY estimation")

    x_values = [row.log_energy for row in rows]
    y_values = [row.log_gdp - alpha * row.log_capital - beta * row.log_labor for row in rows]
    mean_x = sum(x_values) / len(x_values)
    mean_y = sum(y_values) / len(y_values)
    var_x = sum((value - mean_x) ** 2 for value in x_values)
    cov_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values))
    unconstrained_gamma = cov_xy / var_x if var_x > 0.0 else 0.0
    unconstrained_intercept, unconstrained_log_rmse, unconstrained_level_rmse, _ = _fit_intercept_and_errors(
        rows,
        alpha=alpha,
        beta=beta,
        gamma=unconstrained_gamma,
    )

    grid_count = int(round((upper - lower) / step))
    candidates = [lower + index * step for index in range(grid_count + 1)]
    best_gamma = lower
    best_intercept = 0.0
    best_log_rmse = math.inf
    best_level_rmse = math.inf
    best_r_squared = float("-inf")
    for gamma in candidates:
        intercept, log_rmse, level_rmse, r_squared = _fit_intercept_and_errors(
            rows,
            alpha=alpha,
            beta=beta,
            gamma=gamma,
        )
        key = (log_rmse, level_rmse, -r_squared)
        best_key = (best_log_rmse, best_level_rmse, -best_r_squared)
        if key < best_key:
            best_gamma = gamma
            best_intercept = intercept
            best_log_rmse = log_rmse
            best_level_rmse = level_rmse
            best_r_squared = r_squared

    return GammaCrossSectionFit(
        sample_size=len(rows),
        alpha_capital=alpha,
        beta_labor=beta,
        unconstrained_gamma=unconstrained_gamma,
        unconstrained_intercept=unconstrained_intercept,
        unconstrained_log_rmse=unconstrained_log_rmse,
        unconstrained_level_rmse=unconstrained_level_rmse,
        bounded_gamma=best_gamma,
        bounded_intercept=best_intercept,
        bounded_log_rmse=best_log_rmse,
        bounded_level_rmse=best_level_rmse,
        bounded_r_squared=best_r_squared,
    )


def main() -> None:
    rows = load_gamma_cross_section()
    fit = estimate_gamma_cross_section(rows=rows)

    print("GAMMA_ENERGY cross-section identification (2015)")
    print(f"Sample size: {fit.sample_size}")
    print(
        f"Fixed exponents: alpha={fit.alpha_capital:.2f}, beta={fit.beta_labor:.2f}"
    )
    print(
        "Unconstrained OLS: "
        f"gamma={fit.unconstrained_gamma:.6f}, "
        f"log_RMSE={fit.unconstrained_log_rmse:.6f}, "
        f"level_RMSE={fit.unconstrained_level_rmse:.6f}"
    )
    print(
        "Literature-bounded fit: "
        f"gamma={fit.bounded_gamma:.3f}, "
        f"log_RMSE={fit.bounded_log_rmse:.6f}, "
        f"level_RMSE={fit.bounded_level_rmse:.6f}, "
        f"R^2={fit.bounded_r_squared:.4f}"
    )
    print(
        "Recommended active GAMMA_ENERGY: "
        f"{fit.bounded_gamma:.2f} "
        f"(bounded to literature range {LITERATURE_MIN:.2f}-{LITERATURE_MAX:.2f})"
    )


if __name__ == "__main__":
    main()
