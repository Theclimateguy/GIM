#!/usr/bin/env python3
"""Temporal hold-out validation (reviewer major-revision items 1/2).

Design: history matching is rerun with the implausibility computed ONLY on
2015-2019 (data "available through 2019"; HM convention: world-aggregate series
against the standard tolerances, gim/calibration_hm.py); the resulting NROY region
is frozen; 2020-2023 is then scored strictly out-of-sample. Because 2020 is the
COVID year (which no structural model of this class anticipates endogenously),
out-of-sample errors are reported both for the raw 2020-2023 segment and with 2020
excluded (2021-2023).

Reported errors use the SAME metrics as the golden backtest / paper Table 3:
  GDP          -- RMSE over country-year pairs (20 fixture countries), trillion USD;
  CO2          -- RMSE of the global emission series, Gt;
  temperature  -- RMSE of the global anomaly series, deg C.

Naive benchmarks on the held-out segment, built from observed data through 2019 only
(per-country for GDP, global for CO2/temperature):
  persistence -- hold the 2019 observed value flat;
  linear      -- OLS trend fitted on observed 2015-2019, extrapolated.
Skill = 1 - RMSE_model / RMSE_benchmark (positive = model better).

All model runs are deterministic single members (internal temperature variability
off), the same convention as the history-matching pipeline. Model errors are
reported for the NROY median and for the default (headline) configuration.

Writes results/calibration/holdout_validation.json and prints a summary.
"""
from __future__ import annotations

import json
import os
import random
import sys
from statistics import median

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.calibration_hm import DEFAULT_CALIBRATION_PARAMS, DEFAULT_TOLERANCES
from gim.core.priors import key_priors
from gim.historical_backtest import (
    load_historical_observed_fixture,
    run_historical_backtest,
)

CONSTRAIN_YEARS = list(range(2015, 2020))
HOLDOUT_YEARS = list(range(2020, 2024))
HOLDOUT_EXCOVID = list(range(2021, 2024))
N_SAMPLES = 60
THRESHOLD = 3.0
SEED = 2026
OUT = os.path.join(REPO, "results", "calibration", "holdout_validation.json")


def rmse_pairs(pairs) -> float:
    pairs = list(pairs)
    return (sum((p - a) ** 2 for p, a in pairs) / len(pairs)) ** 0.5


def gdp_rmse_window(pred_by_year, act_by_year, years) -> float:
    """Golden metric: RMSE over country-year pairs."""
    pairs = []
    for y in years:
        act = act_by_year[y]
        for c, a in act.items():
            pairs.append((pred_by_year[y].get(c, 0.0), a))
    return rmse_pairs(pairs)


def series_rmse_window(pred, act, years) -> float:
    return rmse_pairs((pred[y], act[y]) for y in years)


def world_aggregates(res) -> dict:
    return {
        "world_gdp": {y: sum(v.values()) for y, v in res.predicted_gdp_trillions.items()},
        "global_co2": dict(res.predicted_global_co2_gtco2),
        "temperature": dict(res.predicted_temperature_c),
    }


def linear_forecast(base: dict, years) -> dict:
    xs = list(base.keys())
    ys = [base[y] for y in xs]
    n = len(xs)
    xbar, ybar = sum(xs) / n, sum(ys) / n
    slope = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys)) / sum((x - xbar) ** 2 for x in xs)
    return {y: ybar + slope * (y - xbar) for y in years}


def main() -> int:
    obs = load_historical_observed_fixture()
    obs_world = {
        "world_gdp": {int(y): float(sum(v.values())) for y, v in obs["gdp_trillions_by_year"].items()},
        "global_co2": {int(y): float(v) for y, v in obs["global_co2_gtco2"].items()},
        "temperature": {int(y): float(v) for y, v in obs["temperature_c_preindustrial"].items()},
    }

    priors = key_priors()
    rng = random.Random(SEED)

    members = []
    for i in range(N_SAMPLES):
        draw = {n: priors[n].sample(rng) for n in DEFAULT_CALIBRATION_PARAMS}
        res = run_historical_backtest(
            params_override=draw, temperature_variability_sigma_override=0.0
        )
        agg = world_aggregates(res)
        act = res.actual_gdp_trillions
        insample_world = {v: series_rmse_window(agg[v], obs_world[v], CONSTRAIN_YEARS) for v in agg}
        imp = max(insample_world[v] / DEFAULT_TOLERANCES[v] for v in insample_world)
        m = {
            "draw": draw,
            "implausibility_max_2015_2019": imp,
            "nroy": imp <= THRESHOLD,
            "golden_metric": {
                "gdp_insample": gdp_rmse_window(res.predicted_gdp_trillions, act, CONSTRAIN_YEARS),
                "gdp_oos": gdp_rmse_window(res.predicted_gdp_trillions, act, HOLDOUT_YEARS),
                "gdp_oos_ex2020": gdp_rmse_window(res.predicted_gdp_trillions, act, HOLDOUT_EXCOVID),
                "co2_insample": series_rmse_window(agg["global_co2"], obs_world["global_co2"], CONSTRAIN_YEARS),
                "co2_oos": series_rmse_window(agg["global_co2"], obs_world["global_co2"], HOLDOUT_YEARS),
                "co2_oos_ex2020": series_rmse_window(agg["global_co2"], obs_world["global_co2"], HOLDOUT_EXCOVID),
                "temp_insample": series_rmse_window(agg["temperature"], obs_world["temperature"], CONSTRAIN_YEARS),
                "temp_oos": series_rmse_window(agg["temperature"], obs_world["temperature"], HOLDOUT_YEARS),
                "temp_oos_ex2020": series_rmse_window(agg["temperature"], obs_world["temperature"], HOLDOUT_EXCOVID),
            },
        }
        members.append(m)
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{N_SAMPLES} draws")

    nroy = [m for m in members if m["nroy"]]
    print(f"NROY: {len(nroy)}/{N_SAMPLES} retained (threshold {THRESHOLD}, constraints 2015-2019)")

    # default (headline) configuration
    res0 = run_historical_backtest(temperature_variability_sigma_override=0.0)
    agg0 = world_aggregates(res0)
    act0 = res0.actual_gdp_trillions

    # naive benchmarks from data through 2019
    # GDP: per-country persistence / linear
    act_by_year = {int(y): v for y, v in obs["gdp_trillions_by_year"].items()}
    countries = list(act_by_year[2019].keys())
    gdp_persist = {y: {c: act_by_year[2019][c] for c in countries} for y in HOLDOUT_YEARS}
    gdp_linear = {y: {} for y in HOLDOUT_YEARS}
    for c in countries:
        base = {y: act_by_year[y][c] for y in CONSTRAIN_YEARS}
        fc = linear_forecast(base, HOLDOUT_YEARS)
        for y in HOLDOUT_YEARS:
            gdp_linear[y][c] = fc[y]
    bench = {
        "gdp": {"persistence": gdp_persist, "linear": gdp_linear},
        "co2": {
            "persistence": {y: obs_world["global_co2"][2019] for y in HOLDOUT_YEARS},
            "linear": linear_forecast({y: obs_world["global_co2"][y] for y in CONSTRAIN_YEARS}, HOLDOUT_YEARS),
        },
        "temp": {
            "persistence": {y: obs_world["temperature"][2019] for y in HOLDOUT_YEARS},
            "linear": linear_forecast({y: obs_world["temperature"][y] for y in CONSTRAIN_YEARS}, HOLDOUT_YEARS),
        },
    }

    def med(var):
        return median(m["golden_metric"][var] for m in nroy)

    summary = {
        "n_samples": N_SAMPLES, "n_nroy": len(nroy), "threshold": THRESHOLD,
        "constrain_years": CONSTRAIN_YEARS, "holdout_years": HOLDOUT_YEARS,
        "metric_note": "GDP = country-year RMSE (golden metric); CO2/temp = global series RMSE; deterministic runs",
        "variables": {},
    }
    specs = [
        ("gdp", lambda pred_res, yrs: gdp_rmse_window(pred_res.predicted_gdp_trillions, act0, yrs),
         lambda b, yrs: gdp_rmse_window(b, act_by_year, yrs)),
        ("co2", lambda pred_res, yrs: series_rmse_window(agg0["global_co2"], obs_world["global_co2"], yrs),
         lambda b, yrs: rmse_pairs((b[y], obs_world["global_co2"][y]) for y in yrs)),
        ("temp", lambda pred_res, yrs: series_rmse_window(agg0["temperature"], obs_world["temperature"], yrs),
         lambda b, yrs: rmse_pairs((b[y], obs_world["temperature"][y]) for y in yrs)),
    ]
    for var, default_fn, bench_fn in specs:
        row = {
            "nroy_median_insample_2015_2019": med(f"{var}_insample"),
            "nroy_median_oos_2020_2023": med(f"{var}_oos"),
            "nroy_median_oos_2021_2023": med(f"{var}_oos_ex2020"),
            "default_insample_2015_2019": default_fn(res0, CONSTRAIN_YEARS),
            "default_oos_2020_2023": default_fn(res0, HOLDOUT_YEARS),
            "default_oos_2021_2023": default_fn(res0, HOLDOUT_EXCOVID),
        }
        for bname in ("persistence", "linear"):
            for tag, yrs in (("2020_2023", HOLDOUT_YEARS), ("2021_2023", HOLDOUT_EXCOVID)):
                b = bench[var][bname]
                b_rmse = bench_fn(b, yrs)
                row[f"{bname}_oos_{tag}"] = b_rmse
                row[f"skill_default_vs_{bname}_{tag}"] = 1.0 - row[f"default_oos_{tag.replace('_', '_')}"] / b_rmse
        summary["variables"][var] = row

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump({"summary": summary, "members": members}, fh, indent=1)
    print("wrote", OUT)

    for var, row in summary["variables"].items():
        print(f"\n[{var}]")
        for k, v in row.items():
            print(f"  {k:40s} {v: .4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
