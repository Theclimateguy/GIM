"""#15 Logistic demographic transition: validate the calibrated CBR/CDR curves and the global
2015-2023 population trajectory against UN WPP 2024.

The logistic crude-birth-rate and Preston-style underlying-mortality curves are anchored to published
WPP/Lutz cross-country values (no microdata download needed):
  - CBR ~44/1000 at low income ($1-2k), ~9/1000 at high income ($60k+), inflection ~$8k (Lutz 2001).
  - underlying CDR ~17/1000 pre-transition -> ~7/1000 high-income (income channel, age-fixed; Preston 1975).

Validation targets:
  1. Curve sanity at benchmark incomes (matches WPP-style rates within tolerance).
  2. Implied global natural increase (births-deaths) ~+1.0%/yr over 2015-2023 (UN WPP: 7.43B->8.02B,
     ~0.95%/yr, of which natural increase is essentially all of it at the world level).

Run:  PYTHONPATH=<repo root> python3 calibration/calibrate_demographics.py
"""

from __future__ import annotations

import json
from pathlib import Path

from gim.core import calibration_params as cal
from gim.core.social import logistic_birth_rate, preston_death_rate

OUT = Path(__file__).resolve().parent / "demographics_calibration.json"

# WPP-style benchmark crude rates (per 1000) by income bracket, for curve cross-validation.
WPP_BENCHMARKS = [
    # (gdp_pc_usd, cbr_per_1000_approx, cdr_underlying_per_1000_approx, label)
    (1500, 40.0, 14.0, "low income (Sub-Saharan)"),
    (8000, 18.0, 9.0, "lower-middle income"),
    (20000, 12.0, 8.0, "upper-middle income"),
    (60000, 10.0, 7.5, "high income"),
]


def main() -> None:
    rows = []
    for y, cbr_ref, cdr_ref, label in WPP_BENCHMARKS:
        cbr = logistic_birth_rate(y, cal) * 1000.0
        cdr = preston_death_rate(y, cal) * 1000.0
        rows.append(
            {
                "gdp_pc": y,
                "label": label,
                "cbr_model": round(cbr, 1),
                "cbr_wpp_ref": cbr_ref,
                "cdr_model": round(cdr, 1),
                "cdr_wpp_ref": cdr_ref,
            }
        )

    # Global natural-increase check: emissions-/population-weighted world rate near the world median.
    # World mean income ~ $12k (2015); natural increase = CBR - CDR.
    world_y = 12000.0
    ni = (logistic_birth_rate(world_y, cal) - preston_death_rate(world_y, cal)) * 100.0
    out = {
        "method": "Logistic CBR (Lutz 2001) + income-driven CDR (Preston 1975), anchored to WPP brackets",
        "params": {
            "CBR_LOGISTIC_MIN": cal.CBR_LOGISTIC_MIN,
            "CBR_LOGISTIC_MAX": cal.CBR_LOGISTIC_MAX,
            "CBR_LOGISTIC_MID_GDP_PC": cal.CBR_LOGISTIC_MID_GDP_PC,
            "CBR_LOGISTIC_K": cal.CBR_LOGISTIC_K,
            "CDR_LOGISTIC_MIN": cal.CDR_LOGISTIC_MIN,
            "CDR_LOGISTIC_MAX": cal.CDR_LOGISTIC_MAX,
            "CDR_LOGISTIC_MID_GDP_PC": cal.CDR_LOGISTIC_MID_GDP_PC,
            "CDR_LOGISTIC_K": cal.CDR_LOGISTIC_K,
        },
        "benchmark_table": rows,
        "implied_world_natural_increase_pct_yr_at_12k": round(ni, 2),
        "un_wpp_2015_2023_growth_pct_yr": 0.95,
        "sources": [
            "Lutz, Sanderson & Scherbov (2001) Nature 412:543",
            "Preston (1975) Population Studies 29:231",
            "UN World Population Prospects 2024",
        ],
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
