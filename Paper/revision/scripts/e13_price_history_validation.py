#!/usr/bin/env python3
"""E13 -- fix 3: validate the model's resource prices against observed history.

E6 showed the retrospective backtest runs in the configuration where the resource-price
subsystem is degenerate: over the actual 2015-2023 window the energy price is exactly 1.0
at every step and metals reaches its 0.30 floor in 2022. Nothing in Section 5 tests the
price subsystem, and the observed-data fixture carries no price series at all, so the
degeneracy is invisible to every existing check.

This adds the missing target: World Bank Pink Sheet annual indices for energy, food and
metals & minerals (see data/external/README_commodity_prices.md), renormalised to the
model's base year so both sides are indices starting at 1.0.

**Scope caveat, carried into the output as well as here.** The Pink Sheet series are market
price indices for traded commodity baskets. GIM's prices are clearing indices for three
aggregate resources, with a reserve buffer and no storage, futures or financialisation.
These are related but not identical constructs, so the fair test is DIRECTION and MULTI-YEAR
MAGNITUDE, not year-by-year timing. A model that gets the sign and rough size of the
2015-2023 move right is doing what can reasonably be asked of it; one whose price does not
move at all is not.

Reports, per resource and per configuration: total move, correlation, RMSE against the
observed index, and the RMSE of a flat-at-1.0 null. A model price with zero variance has an
undefined correlation and an RMSE equal to the observed series' own dispersion -- that is
the finding, not an error.

Writes Paper/revision/results/e13_price_history_validation.json
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import gim.historical_backtest as hb                 # noqa: E402
from gim.core.policy import make_policy_map          # noqa: E402
from gim.core.simulation import step_world           # noqa: E402
from gim.runtime import load_world                   # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                   "e13_price_history_validation.json")
OBS = os.path.join(REPO, "data", "external",
                   "worldbank_commodity_price_indices_annual.csv")
RESOURCES = ("energy", "food", "metals")
OBS_COL = {"energy": "energy_index_2010_100",
           "food": "food_index_2010_100",
           "metals": "metals_minerals_index_2010_100"}


def observed(base_year: int, years) -> dict:
    raw = {}
    with open(OBS, newline="") as fh:
        for row in csv.DictReader(fh):
            raw[int(row["year"])] = {r: float(row[OBS_COL[r]]) for r in RESOURCES}
    return {r: {y: raw[y][r] / raw[base_year][r] for y in years if y in raw}
            for r in RESOURCES}


def model_prices_backtest():
    """Instrument the actual historical backtest -- where Section 5's numbers come from."""
    captured = []
    orig = hb.step_world

    def spy(world, policies, **kw):
        w = orig(world, policies, **kw)
        w2 = w if w is not None else world
        captured.append({k: float(v) for k, v in w2.global_state.prices.items()})
        return w

    hb.step_world = spy
    try:
        res = hb.run_historical_backtest(temperature_variability_sigma_override=0.0)
    finally:
        hb.step_world = orig
    start = int(res.start_year)
    series = {r: {start: 1.0} for r in RESOURCES}
    for i, snap in enumerate(captured):
        for r in RESOURCES:
            series[r][start + 1 + i] = snap[r]
    return start, int(res.end_year), series


def model_prices_forward(base_year: int, n_years: int):
    """Same window length under forward_init=True, the configuration E6 found non-degenerate."""
    world = load_world(forward_init=True)
    pol = make_policy_map(list(world.agents.keys()), mode="simple")
    series = {r: {base_year: float(world.global_state.prices[r])} for r in RESOURCES}
    for i in range(n_years):
        world = step_world(world, pol, enable_extreme_events=False)
        for r in RESOURCES:
            series[r][base_year + 1 + i] = float(world.global_state.prices[r])
    return series


def score(model: dict, obs: dict, years) -> dict:
    m = np.array([model[y] for y in years], dtype=float)
    o = np.array([obs[y] for y in years], dtype=float)
    flat = np.ones_like(o)
    const = bool(m.std() < 1e-12)
    rmse_m = float(np.sqrt(np.mean((m - o) ** 2)))
    rmse_f = float(np.sqrt(np.mean((flat - o) ** 2)))
    return {
        "years": list(years),
        "model": [float(v) for v in m],
        "observed": [float(v) for v in o],
        "model_total_move_pct": float(100.0 * (m[-1] - m[0]) / max(abs(m[0]), 1e-9)),
        "observed_total_move_pct": float(100.0 * (o[-1] - o[0]) / max(abs(o[0]), 1e-9)),
        "same_direction": bool(np.sign(m[-1] - m[0]) == np.sign(o[-1] - o[0])),
        "model_sd": float(m.std()),
        "observed_sd": float(o.std()),
        "model_is_constant": const,
        "correlation": (None if const or o.std() < 1e-12
                        else float(np.corrcoef(m, o)[0, 1])),
        "rmse_model_vs_observed": rmse_m,
        "rmse_flat_null_vs_observed": rmse_f,
        "skill_vs_flat_null": float(1.0 - rmse_m / rmse_f) if rmse_f > 0 else float("nan"),
    }


def main() -> int:
    start, end, bt = model_prices_backtest()
    years = list(range(start, end + 1))
    obs = observed(start, years)
    fwd = model_prices_forward(start, len(years) - 1)

    results = {}
    for label, series in (("backtest_config_section5", bt),
                          ("forward_init_same_window", fwd)):
        results[label] = {r: score(series[r], obs[r], years) for r in RESOURCES}

    for label, block in results.items():
        print(f"\n--- {label} ---")
        print(f"{'resource':9s} {'model move':>11s} {'observed':>10s} {'dir':>5s} "
              f"{'corr':>7s} {'RMSE':>7s} {'flat null':>10s} {'skill':>7s}")
        for r in RESOURCES:
            s = block[r]
            corr = "n/a" if s["correlation"] is None else f"{s['correlation']:+.3f}"
            print(f"{r:9s} {s['model_total_move_pct']:+10.1f}% "
                  f"{s['observed_total_move_pct']:+9.1f}% "
                  f"{'yes' if s['same_direction'] else 'NO':>5s} {corr:>7s} "
                  f"{s['rmse_model_vs_observed']:7.3f} {s['rmse_flat_null_vs_observed']:10.3f} "
                  f"{s['skill_vs_flat_null']:+7.3f}")

    payload = {
        "experiment": "E13",
        "question": "Do the model's resource prices track observed history, and does the "
                    "startup configuration change the answer?",
        "scope_caveat": ("World Bank Pink Sheet series are MARKET price indices for traded "
                         "commodity baskets; GIM prices are CLEARING indices for three "
                         "aggregate resources with a reserve buffer and no storage, futures "
                         "or financialisation. The fair test is direction and multi-year "
                         "magnitude, not year-by-year timing."),
        "observed_source": "data/external/worldbank_commodity_price_indices_annual.csv "
                           "(World Bank CMO Pink Sheet, annual nominal indices, 2010=100, "
                           "renormalised to the model base year)",
        "config": {"window": [start, end], "n_years": len(years)},
        "results": results,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(os.path.abspath(OUT), "w") as fh:
        json.dump(payload, fh, indent=1)
    print("\nwrote", os.path.abspath(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
