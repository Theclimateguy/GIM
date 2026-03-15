from __future__ import annotations

import csv
import io
import json
import math
from datetime import datetime, UTC
from pathlib import Path
import sys
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gim.core import calibration_params as cal  # noqa: E402
from gim.historical_backtest import run_historical_backtest  # noqa: E402


INPUT_PATH = Path(__file__).resolve().with_name("decarb_rate_input.json")
OUTPUT_PATH = Path(__file__).resolve().with_name("decarb_rate_calibration.json")
START_YEAR = 2000
END_YEAR = 2023
EXCLUDED_YEARS = (2020, 2021)
PPP_GDP_INDICATOR = "NY.GDP.MKTP.PP.KD"
WORLD_BANK_API = "https://api.worldbank.org/v2/country/{code}/indicator/{indicator}?format=json&per_page=80"
GCB_EMISSIONS_URL = "https://zenodo.org/records/17417124/files/GCB2025v15_MtCO2_flat.csv?download=1"
USER_AGENT = "GIM14 decarb calibration/1.0"
TCRIT_95 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.080,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.060,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
}
OECD_ISO3 = {
    "AUS",
    "AUT",
    "BEL",
    "CAN",
    "CHL",
    "COL",
    "CRI",
    "CZE",
    "DNK",
    "EST",
    "FIN",
    "FRA",
    "DEU",
    "GRC",
    "HUN",
    "ISL",
    "IRL",
    "ISR",
    "ITA",
    "JPN",
    "KOR",
    "LVA",
    "LTU",
    "LUX",
    "MEX",
    "NLD",
    "NZL",
    "NOR",
    "POL",
    "PRT",
    "SVK",
    "SVN",
    "ESP",
    "SWE",
    "CHE",
    "TUR",
    "GBR",
    "USA",
}


def _download_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def _fetch_world_bank_gdp_series(code: str, indicator: str) -> dict[int, float]:
    payload = json.loads(_download_text(WORLD_BANK_API.format(code=code, indicator=indicator)))
    if len(payload) < 2 or payload[1] is None:
        raise RuntimeError(f"World Bank API returned no data for {code} / {indicator}")
    series: dict[int, float] = {}
    for row in payload[1]:
        value = row.get("value")
        if value is None:
            continue
        year = int(row["date"])
        if START_YEAR <= year <= END_YEAR:
            series[year] = float(value) / 1e12
    return series


def _fetch_gcb_emissions_series() -> dict[str, dict[int, float]]:
    reader = csv.DictReader(io.StringIO(_download_text(GCB_EMISSIONS_URL)))
    global_emissions: dict[int, float] = {}
    oecd_emissions: dict[int, float] = {}
    for row in reader:
        year = int(row["Year"])
        if year < START_YEAR or year > END_YEAR:
            continue
        raw_total = row.get("Total")
        if not raw_total:
            continue
        total = float(raw_total)
        global_emissions[year] = global_emissions.get(year, 0.0) + total
        if row.get("ISO 3166-1 alpha-3") in OECD_ISO3:
            oecd_emissions[year] = oecd_emissions.get(year, 0.0) + total
    non_oecd_emissions = {
        year: global_emissions[year] - oecd_emissions.get(year, 0.0)
        for year in global_emissions
    }
    return {
        "global": global_emissions,
        "oecd": oecd_emissions,
        "non_oecd": non_oecd_emissions,
    }


def _build_input_snapshot() -> dict[str, Any]:
    global_gdp = _fetch_world_bank_gdp_series("WLD", PPP_GDP_INDICATOR)
    oecd_gdp = _fetch_world_bank_gdp_series("OED", PPP_GDP_INDICATOR)
    non_oecd_gdp = {year: global_gdp[year] - oecd_gdp[year] for year in global_gdp}
    emissions = _fetch_gcb_emissions_series()
    series: dict[str, dict[str, dict[str, float]]] = {}
    for group, group_emissions in emissions.items():
        if group == "global":
            group_gdp = global_gdp
        elif group == "oecd":
            group_gdp = oecd_gdp
        else:
            group_gdp = non_oecd_gdp
        group_series: dict[str, dict[str, float]] = {}
        for year in range(START_YEAR, END_YEAR + 1):
            if year not in group_emissions or year not in group_gdp:
                continue
            emissions_mtco2 = float(group_emissions[year])
            gdp_ppp_trillion_usd = float(group_gdp[year])
            group_series[str(year)] = {
                "emissions_mtco2": emissions_mtco2,
                "gdp_ppp_trillion_usd": gdp_ppp_trillion_usd,
                "intensity_mtco2_per_trillion_usd": emissions_mtco2 / max(gdp_ppp_trillion_usd, 1e-9),
            }
        series[group] = group_series
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "methodology": {
            "start_year": START_YEAR,
            "end_year": END_YEAR,
            "excluded_years": list(EXCLUDED_YEARS),
            "fit": "log_linear_ols",
            "dependent_variable": "ln(CO2 / GDP_PPP)",
            "gdp_indicator": PPP_GDP_INDICATOR,
            "grouping": "current_oecd_membership_vs_non_oecd",
        },
        "sources": {
            "emissions": {
                "label": "Global Carbon Project / Global Carbon Budget 2025 flat country dataset",
                "url": GCB_EMISSIONS_URL,
                "unit": "MtCO2",
            },
            "gdp": {
                "label": "World Bank GDP, PPP (constant 2021 international $)",
                "indicator": PPP_GDP_INDICATOR,
                "aggregate_codes": {"global": "WLD", "oecd": "OED"},
                "unit": "trillion PPP dollars",
            },
        },
        "series": series,
    }


def _load_input_snapshot() -> tuple[dict[str, Any], str]:
    if INPUT_PATH.exists():
        return json.loads(INPUT_PATH.read_text(encoding="utf-8")), "local_snapshot"
    snapshot = _build_input_snapshot()
    INPUT_PATH.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    return snapshot, "fetched_and_cached"


def _t_critical_95(df: int) -> float:
    if df <= 0:
        return 1.96
    return TCRIT_95.get(df, 1.96)


def _fit_log_linear(series: dict[str, dict[str, float]]) -> dict[str, Any]:
    usable_years = sorted(
        year
        for year in (int(raw_year) for raw_year in series)
        if year not in EXCLUDED_YEARS
    )
    x_values = [float(year - usable_years[0]) for year in usable_years]
    y_values = [
        math.log(max(float(series[str(year)]["intensity_mtco2_per_trillion_usd"]), 1e-12))
        for year in usable_years
    ]
    n = len(x_values)
    if n < 3:
        raise RuntimeError("Need at least three annual observations for decarb regression")
    mean_x = sum(x_values) / n
    mean_y = sum(y_values) / n
    sxx = sum((x - mean_x) ** 2 for x in x_values)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values))
    slope = sxy / max(sxx, 1e-12)
    intercept = mean_y - slope * mean_x
    fitted = [intercept + slope * x for x in x_values]
    residuals = [actual - expected for actual, expected in zip(y_values, fitted)]
    ss_res = sum(residual ** 2 for residual in residuals)
    ss_tot = sum((y - mean_y) ** 2 for y in y_values)
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0.0 else 1.0
    sigma2 = ss_res / max(n - 2, 1)
    slope_se = math.sqrt(sigma2 / max(sxx, 1e-12))
    tcrit = _t_critical_95(n - 2)
    rate = -slope
    rate_margin = tcrit * slope_se
    return {
        "estimate": float(rate),
        "ci_95": [float(rate - rate_margin), float(rate + rate_margin)],
        "r2": float(r2),
        "n": n,
        "start_year": usable_years[0],
        "end_year": usable_years[-1],
        "excluded_years": list(EXCLUDED_YEARS),
    }


def _compare_backtests(observed_rate: float, active_rate: float) -> dict[str, Any]:
    candidates = []
    for rate in (round(observed_rate, 6), round(active_rate, 6)):
        if rate not in candidates:
            candidates.append(rate)
    comparisons: list[dict[str, float | str]] = []
    best_key: tuple[float, float, float] | None = None
    recommended_rate = candidates[0]
    for rate in candidates:
        result = run_historical_backtest(decarb_rate_override=rate)
        key = (
            float(result.global_co2_rmse_gtco2),
            float(result.gdp_rmse_trillions),
            float(result.temperature_rmse_c),
        )
        if best_key is None or key < best_key:
            best_key = key
            recommended_rate = rate
        comparisons.append(
            {
                "rate": rate,
                "label": "active_artifact" if abs(rate - active_rate) < 1e-12 else "observed_data_fit",
                "gdp_rmse_trillions": float(result.gdp_rmse_trillions),
                "global_co2_rmse_gtco2": float(result.global_co2_rmse_gtco2),
                "temperature_rmse_c": float(result.temperature_rmse_c),
            }
        )
    return {
        "active_artifact_rate": float(active_rate),
        "observed_data_rate": float(observed_rate),
        "recommended_active_rate": float(recommended_rate),
        "comparisons": comparisons,
    }


def build_calibration_artifact(snapshot: dict[str, Any], *, input_source: str) -> dict[str, Any]:
    fits = {
        group: _fit_log_linear(group_series)
        for group, group_series in snapshot["series"].items()
    }
    global_estimate = fits["global"]["estimate"]
    active_rate = float(cal.DECARB_RATE_STRUCTURAL)
    artifact = {
        "input_source": input_source,
        "generated_at": datetime.now(UTC).isoformat(),
        "methodology": snapshot["methodology"],
        "sources": snapshot["sources"],
        "global": fits["global"],
        "oecd": fits["oecd"],
        "non_oecd": fits["non_oecd"],
        "active_rate_backtest": _compare_backtests(global_estimate, active_rate),
        "recommendation": {
            "observed_reference_rate": float(global_estimate),
            "active_structural_rate": active_rate,
            "notes": (
                "Use the observed global fit as the manifest reference prior. "
                "Keep the active structural rate manifest-bound until the historical backtest "
                "stops preferring the compiled-state artifact value."
            ),
        },
    }
    return artifact


def main() -> None:
    try:
        snapshot, input_source = _load_input_snapshot()
    except URLError as exc:
        raise SystemExit(f"Unable to fetch decarb calibration inputs: {exc}") from exc

    artifact = build_calibration_artifact(snapshot, input_source=input_source)
    OUTPUT_PATH.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    print("Structural decarbonization fit (CO2 / GDP_PPP, log-linear OLS)")
    print(f"Input source: {input_source}")
    print(f"Snapshot: {INPUT_PATH.relative_to(REPO_ROOT)}")
    for group in ("global", "oecd", "non_oecd"):
        result = artifact[group]
        print(
            f"{group:9s} rate={result['estimate']:.6f}  "
            f"CI95=({result['ci_95'][0]:.6f}, {result['ci_95'][1]:.6f})  "
            f"R2={result['r2']:.3f}  n={result['n']}"
        )
    comparison = artifact["active_rate_backtest"]
    print()
    print(
        f"Observed reference rate: {comparison['observed_data_rate']:.6f} | "
        f"Active artifact rate: {comparison['active_artifact_rate']:.6f}"
    )
    for row in comparison["comparisons"]:
        print(
            f"{row['label']:17s} rate={row['rate']:.6f}  "
            f"GDP_RMSE={row['gdp_rmse_trillions']:.3f}  "
            f"CO2_RMSE={row['global_co2_rmse_gtco2']:.3f}  "
            f"TEMP_RMSE={row['temperature_rmse_c']:.3f}"
        )
    print(f"Recommended active rate: {comparison['recommended_active_rate']:.6f}")
    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
