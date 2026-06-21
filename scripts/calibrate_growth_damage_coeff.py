#!/usr/bin/env python3
"""Stage-2 (F4) calibration: growth-effect climate-damage coefficient.

Self-contained, golden-preserving. Reproduces the level-vs-growth SCC "catastrophic
spread" at modern (RFF-SP / EPA-2023) 2% Ramsey discounting and records the calibrated
production stance. Run from the GIM17 repo root:

    python3 scripts/calibrate_growth_damage_coeff.py

Outputs a JSON ledger to results/calibration/growth_damage_coeff.json and prints a table.
"""
import contextlib
import dataclasses
import io
import json
import os
import sys

from gim.core.params import default_params
from gim.scc import social_cost_of_carbon
from gim.benchmark_alignment import MODERN_RHO, MODERN_ETA
from gim.historical_backtest import run_historical_backtest

# Literature SCC anchors at modern 2% discounting, 200-yr horizon ($/tCO2).
# coeff -> (target SCC, interpretation). Targets from docs/GROWTH_DAMAGE.md / parameter_priors.csv.
TARGETS = {
    0.0:    (184.0, "level-effect only (DICE / RFF-GIVE) ~ EPA/RFF central $185-190"),
    0.0002: (None,  "prior mode (Burke/Kotz/Moore-Diaz, conservative)"),
    0.0003: (314.0, "moderate growth-effect"),
    0.0007: (490.0, "strong growth-effect (Burke 2015 upper tail)"),
    0.001:  (None,  "illustrative-upper (Kotz)"),
}

HORIZON = 200


def scc_at(coeff: float, horizon: int = HORIZON) -> float:
    p = default_params().with_overrides({
        "PURE_TIME_PREFERENCE": MODERN_RHO,
        "ELASTICITY_MARGINAL_UTILITY": MODERN_ETA,
        "GROWTH_DAMAGE_TFP_COEFF": float(coeff),
    })
    return social_cost_of_carbon(years=horizon, params=p)["scc_usd_per_tco2"]


def main() -> int:
    os.makedirs("results/calibration", exist_ok=True)

    # 1) Golden invariant: default config (coeff=0, native discounting) must be unchanged.
    with contextlib.redirect_stdout(io.StringIO()):
        gold = run_historical_backtest()
    golden = {
        "gdp_rmse": round(gold.gdp_rmse_trillions, 4),
        "co2_rmse": round(gold.global_co2_rmse_gtco2, 4),
        "temp_rmse": round(gold.temperature_rmse_c, 4),
    }

    # 2) SCC vs growth-damage coefficient at modern 2% / 200-yr.
    rows = []
    print(f"{'coeff':>8} | {'SCC_200y':>9} | {'target':>7} | interpretation")
    print("-" * 78)
    for coeff, (target, note) in TARGETS.items():
        scc = scc_at(coeff)
        rows.append({"coeff": coeff, "scc_200y_modern2pct": round(scc, 1),
                     "target": target, "note": note})
        tcol = f"${target:.0f}" if target else "  -  "
        print(f"{coeff:8.4f} | ${scc:8.1f} | {tcol:>7} | {note}")

    ledger = {
        "experiment": "growth-effect damage coefficient calibration (Stage-2 / F4)",
        "discounting": {"scheme": "modern RFF-SP/EPA-2023 2% Ramsey",
                        "rho": MODERN_RHO, "eta": MODERN_ETA},
        "horizon_years": HORIZON,
        "golden_backtest_at_default": golden,
        "golden_target": {"gdp_rmse": 1.026, "co2_rmse": 1.606, "temp_rmse": 0.134},
        "scc_map": rows,
        "production_stance": {
            "GROWTH_DAMAGE_TFP_COEFF_default": 0.0,
            "rationale": "headline stays level-effect-only (golden-preserving, ~EPA/RFF central); "
                         "the prior (triangular mode 0.0002, [0,0.001]) lets the ensemble/SCC "
                         "distribution span the Burke/Kotz growth-effect upside as explicit "
                         "sampled uncertainty.",
        },
    }
    with open("results/calibration/growth_damage_coeff.json", "w") as fh:
        json.dump(ledger, fh, indent=2)
        fh.write("\n")
    print("\nGolden at default:", golden, "(target 1.026/1.606/0.134)")
    print("Ledger -> results/calibration/growth_damage_coeff.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
