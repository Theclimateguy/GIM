#!/usr/bin/env python3
"""D1 validation: GIM's emergent carbon-price -> CO2 emission elasticity.

The D1 channel (gim/core/climate.update_emissions_from_economy, ENERGY_PRICE_SUBSTITUTION) makes a
carbon price reduce emissions via the inner-CES capital-energy substitution (elasticity sigma_KE),
derived from producer cost-minimization rather than imposed. This script sweeps the carbon price on
the 2015-2023 backtest and records the % emission reduction + semi-elasticity, vs the empirical
benchmark, and writes a ledger.

Empirical benchmark (ex-post ETS/carbon-tax studies): carbon pricing reduced emissions ~1-2.5% on
average; significant schemes -5% to -21% (-4% to -15% bias-corrected); semi-elasticity ~0.05%/$1.
(Sources: RFF/Cambridge "Carbon pricing and the elasticity of CO2 emissions" 2021/2025; Nature
Communications meta-analysis 2024.)

    python3 scripts/measure_carbon_price_elasticity.py
"""
import contextlib
import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.historical_backtest import run_historical_backtest  # noqa: E402


def _sum_co2(overrides):
    with contextlib.redirect_stdout(io.StringIO()):
        r = run_historical_backtest(params_override=overrides)
    s = r.predicted_global_co2_gtco2
    return (sum(s.values()) if isinstance(s, dict) else sum(s)), r.global_co2_rmse_gtco2


def main() -> int:
    base, base_rmse = _sum_co2({"ENERGY_PRICE_SUBSTITUTION": True})  # carbon = 0
    rows = []
    for cp in (10, 25, 50, 100, 200):
        tot, _ = _sum_co2({"ENERGY_PRICE_SUBSTITUTION": True, "CARBON_PRICE_USD_PER_TCO2": float(cp)})
        red = 100.0 * (base - tot) / base
        rows.append({"carbon_usd_per_tco2": cp, "emission_reduction_pct": round(red, 2),
                     "semi_elasticity_pct_per_usd": round(red / cp, 4)})

    ledger = {
        "experiment": "D1 emergent carbon-price -> CO2 emission elasticity (2015-2023 backtest)",
        "mechanism": "inner-CES K-E substitution (sigma_KE) on a carbon-price energy markup; "
                     "factor = (1 + passthrough*carbon)^(-sigma_KE)",
        "golden_safe_at_zero_carbon": abs(base_rmse - 1.6058) < 0.01,
        "sweep": rows,
        "empirical_benchmark": {
            "average_intro_effect_pct": "1.0 to 2.5",
            "significant_schemes_pct": "-5 to -21 (-4 to -15 bias-corrected)",
            "semi_elasticity_pct_per_usd": "~0.05",
            "sources": ["RFF/Cambridge 2021/2025", "Nature Communications meta-analysis 2024"],
        },
        "finding": ("GIM's structural channel gives the LONG-RUN, frictionless equilibrium response "
                    "(~5-6% at $50/tCO2 with sigma_KE=0.4), ABOVE the observed SHORT-RUN ETS effect "
                    "(~1-2.5% average). The gap is the adjustment-friction wedge: real-world "
                    "incomplete pass-through, capital inertia and exemptions that GIM's equilibrium "
                    "substitution omits. Lower CARBON_PRICE_PASSTHROUGH or sigma_KE for a short-run "
                    "calibration; the structural value is the policy-relevant long-run elasticity."),
    }
    os.makedirs(os.path.join(REPO, "results", "calibration"), exist_ok=True)
    out = os.path.join(REPO, "results", "calibration", "carbon_price_elasticity.json")
    with open(out, "w") as fh:
        json.dump(ledger, fh, indent=2)
        fh.write("\n")

    print(f"baseline (carbon=0) sum CO2 = {base:.1f} GtCO2; golden-safe: {ledger['golden_safe_at_zero_carbon']}")
    for r in rows:
        print(f"  ${r['carbon_usd_per_tco2']:>4}/tCO2 -> {r['emission_reduction_pct']:>5.2f}% cut "
              f"(semi-elast {r['semi_elasticity_pct_per_usd']:.4f}%/$)")
    print(f"ledger -> {os.path.relpath(out, REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
