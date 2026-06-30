#!/usr/bin/env python3
"""Calibrate the two development-structured engine terms from World Bank data (2026-06).

Both terms make per-country dynamics a function of development level (GDP per capita), and are
mirror images of each other:

  * TFP conditional convergence (gim/core/metrics.py `update_tfp_endogenous`):
        d(ln TFP)/dt += TFP_CONVERGENCE_SENS * ln(gdp_pc_frontier / gdp_pc_i)
    Poorer countries catch up faster. Slope from the real-PPP-GDP growth cross-section.

  * Development-dependent structural decarbonisation (gim/core/climate.py
    `update_emissions_from_economy`):
        decarb_i = DECARB_DEV_BASE + DECARB_DEV_SLOPE * ln(gdp_pc_i)
    Richer / post-industrial countries decarbonise faster (renewables, offshoring of heavy
    industry). Fit from the per-country CO2/real-PPP-GDP intensity-decline cross-section.

Inputs (committed, so the fit is reproducible offline):
  * data/worldbank_growth_decarb_2015_2023.csv  -- WB real PPP GDP (NY.GDP.MKTP.PP.KD, constant
    2021 intl $) and CO2 (EN.GHG.CO2.MT.CE.AR5, MtCO2) for the 20 GDP_BACKTEST_ACTORS, 2015-2023.
  * tests/fixtures/historical_backtest_state_2015.csv -- the model's 2015 base GDP/population,
    used for the GDP-per-capita the engine sees at t0.

Run ``python calibration/growth_decarb_calibration.py`` to recompute and rewrite
``calibration/growth_decarb_calibration.json`` and print the fitted constants (which must match
TFP_CONVERGENCE_SENS / DECARB_DEV_BASE / DECARB_DEV_SLOPE in gim/core/calibration_params.py).
Pass ``--refresh`` to re-pull the raw series from the World Bank API first (needs network).
"""

from __future__ import annotations

import csv
import json
import math
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WB_CSV = REPO_ROOT / "data" / "worldbank_growth_decarb_2015_2023.csv"
STATE_2015 = REPO_ROOT / "tests" / "fixtures" / "historical_backtest_state_2015.csv"
OUT_JSON = REPO_ROOT / "calibration" / "growth_decarb_calibration.json"

START_YEAR, END_YEAR = 2015, 2023

# country -> World Bank ISO3 (the 20-actor backtest surface).
ACTORS = {
    "United States": "USA", "China": "CHN", "Japan": "JPN", "Germany": "DEU", "India": "IND",
    "United Kingdom": "GBR", "France": "FRA", "Italy": "ITA", "Brazil": "BRA", "Canada": "CAN",
    "South Korea": "KOR", "Russia": "RUS", "Australia": "AUS", "Spain": "ESP", "Mexico": "MEX",
    "Indonesia": "IDN", "Netherlands": "NLD", "Saudi Arabia": "SAU", "Turkey": "TUR",
    "Switzerland": "CHE",
}
PPP_GDP_INDICATOR = "NY.GDP.MKTP.PP.KD"   # real PPP GDP, constant 2021 international $
CO2_INDICATOR = "EN.GHG.CO2.MT.CE.AR5"    # CO2 emissions, MtCO2 (AR5 GWP)


def _ols(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Plain OLS y = a + b*x. Returns (a, b, r2)."""
    n = len(xs)
    sx, sy = sum(xs), sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    b = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    a = (sy - b * sx) / n
    ybar = sy / n
    ss_tot = sum((y - ybar) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    return a, b, (1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"))


def _refresh_from_worldbank() -> None:
    """Re-pull the raw PPP GDP + CO2 series from the World Bank API (needs network)."""
    codes = ";".join(ACTORS.values())
    rows: dict[tuple[str, int], dict] = {}
    for indicator, col in ((PPP_GDP_INDICATOR, "ppp_gdp_const2021intl_usd"), (CO2_INDICATOR, "co2_mtco2_ar5")):
        for batch_start in range(0, len(ACTORS), 4):  # batch to avoid API timeouts
            batch = list(ACTORS.values())[batch_start:batch_start + 4]
            url = (f"https://api.worldbank.org/v2/country/{';'.join(batch)}/indicator/{indicator}"
                   f"?date={START_YEAR}:{END_YEAR}&format=json&per_page=400")
            with urllib.request.urlopen(url, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            iso2name = {v: k for k, v in ACTORS.items()}
            for rec in (payload[1] or []):
                iso = rec["countryiso3code"]
                if iso in iso2name and rec["value"] is not None:
                    key = (iso2name[iso], int(rec["date"]))
                    rows.setdefault(key, {"country": iso2name[iso], "iso3": iso, "year": int(rec["date"])})[col] = rec["value"]
    out = sorted(rows.values(), key=lambda r: (list(ACTORS).index(r["country"]), r["year"]))
    with WB_CSV.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["country", "iso3", "year", "ppp_gdp_const2021intl_usd", "co2_mtco2_ar5"])
        w.writeheader()
        for r in out:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})
    print(f"refreshed {WB_CSV} ({len(out)} rows)")


def _load_wb() -> tuple[dict, dict]:
    ppp: dict[str, dict[int, float]] = {}
    co2: dict[str, dict[int, float]] = {}
    with WB_CSV.open() as fh:
        for row in csv.DictReader(fh):
            c, y = row["country"], int(row["year"])
            if row["ppp_gdp_const2021intl_usd"]:
                ppp.setdefault(c, {})[y] = float(row["ppp_gdp_const2021intl_usd"])
            if row["co2_mtco2_ar5"]:
                co2.setdefault(c, {})[y] = float(row["co2_mtco2_ar5"])
    return ppp, co2


def _load_gdp_pc_2015() -> dict[str, float]:
    """GDP per capita ($) the engine sees at the 2015 base, from the model state."""
    pc: dict[str, float] = {}
    with STATE_2015.open() as fh:
        for row in csv.DictReader(fh):
            gdp = float(row["gdp"]) * 1e12          # trillions USD -> USD
            pop = float(row["population"])
            if pop > 0:
                pc[row["name"]] = gdp / pop
    return pc


def calibrate() -> dict:
    ppp, co2 = _load_wb()
    gdp_pc = _load_gdp_pc_2015()
    yrs = END_YEAR - START_YEAR

    frontier_pc = max(gdp_pc[c] for c in ACTORS if c in gdp_pc)

    conv_x, conv_y, dec_x, dec_y, per_country = [], [], [], [], []
    for c in ACTORS:
        if c not in ppp or c not in co2 or c not in gdp_pc:
            continue
        if START_YEAR not in ppp[c] or END_YEAR not in ppp[c]:
            continue
        real_growth = (ppp[c][END_YEAR] / ppp[c][START_YEAR]) ** (1.0 / yrs) - 1.0
        loggap = math.log(frontier_pc / gdp_pc[c])
        conv_x.append(loggap)
        conv_y.append(real_growth)
        row = {"country": c, "real_ppp_growth": real_growth, "loggap_to_frontier": loggap,
               "gdp_pc_usd": gdp_pc[c]}
        if START_YEAR in co2[c] and END_YEAR in co2[c]:
            i0 = co2[c][START_YEAR] / ppp[c][START_YEAR]
            i1 = co2[c][END_YEAR] / ppp[c][END_YEAR]
            decarb = -math.log(i1 / i0) / yrs
            dec_x.append(math.log(gdp_pc[c]))
            dec_y.append(decarb)
            row["decarb_rate"] = decarb
        per_country.append(row)

    c_a, c_b, c_r2 = _ols(conv_x, conv_y)            # real_growth = a + b*loggap
    d_a, d_b, d_r2 = _ols(dec_x, dec_y)              # decarb = a + b*ln(gdp_pc)

    return {
        "generated_by": "calibration/growth_decarb_calibration.py",
        "window": {"start_year": START_YEAR, "end_year": END_YEAR},
        "sources": {
            "real_ppp_gdp": f"World Bank {PPP_GDP_INDICATOR} (constant 2021 international $)",
            "co2": f"World Bank {CO2_INDICATOR} (MtCO2, AR5 GWP)",
            "gdp_per_capita": "model 2015 base state (tests/fixtures/historical_backtest_state_2015.csv)",
        },
        "tfp_convergence": {
            "form": "d(ln TFP)/dt += slope * ln(gdp_pc_frontier / gdp_pc_i)",
            "intercept_frontier_growth": c_a, "slope": c_b, "r2": c_r2,
            "n": len(conv_x), "maps_to": {"TFP_CONVERGENCE_SENS": round(c_b, 4)},
        },
        "development_decarb": {
            "form": "decarb_i = base + slope * ln(gdp_pc_i)",
            "base": d_a, "slope": d_b, "r2": d_r2,
            "n": len(dec_x), "median_country_decarb": sorted(dec_y)[len(dec_y) // 2],
            "maps_to": {"DECARB_DEV_BASE": round(d_a, 4), "DECARB_DEV_SLOPE": round(d_b, 4)},
        },
        "per_country": per_country,
    }


def main() -> None:
    if "--refresh" in sys.argv:
        _refresh_from_worldbank()
    result = calibrate()
    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    conv = result["tfp_convergence"]
    dec = result["development_decarb"]
    print(f"TFP convergence: slope={conv['slope']:.4f} (R2={conv['r2']:.2f}, n={conv['n']}) "
          f"-> TFP_CONVERGENCE_SENS")
    print(f"Dev decarb:      decarb = {dec['base']:.4f} + {dec['slope']:.4f}*ln(gdp_pc) "
          f"(R2={dec['r2']:.2f}, n={dec['n']}) -> DECARB_DEV_BASE / DECARB_DEV_SLOPE")
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
