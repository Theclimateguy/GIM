#!/usr/bin/env python3
"""E14 -- fix 4: what does the calibration stage do once the cut actually binds?

E4 established that the published tolerances never rule out a draw (0/600, maximum
implausibility 1.689 against a cut at 3.0) and that per-output implausibility ranks
out-of-sample error at Spearman 0.90-0.95 while the `max_o` aggregate destroys that for
GDP. Two things follow that need measuring rather than asserting:

  1. With TIGHTENED_TOLERANCES the cut does bind -- but does the surviving NROY region
     actually constrain the parameters, or does it just shrink the sample? Reported as the
     retained fraction of each parameter's prior range.
  2. Does surviving the tightened cut BUY anything out of sample? Reported as the
     out-of-sample error of NROY members against all draws, which is the question a
     reviewer will ask about any calibration stage.

Also reports the per-output ranking as an alternative to filtering: what does taking the
best decile ON THE RIGHT OUTPUT buy, compared with the max-aggregated cut?

Writes Paper/revision/results/e14_tightened_tolerances.json
"""
from __future__ import annotations

import json
import os
import random
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.calibration_hm import (                     # noqa: E402
    DEFAULT_CALIBRATION_PARAMS,
    DEFAULT_TOLERANCES,
    TIGHTENED_TOLERANCES,
)
from gim.core.priors import key_priors               # noqa: E402
from gim.historical_backtest import (                # noqa: E402
    load_historical_observed_fixture,
    run_historical_backtest,
)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                   "e14_tightened_tolerances.json")
N_SAMPLES = 600
SEED = 2026
THRESHOLD = 3.0
CONSTRAIN_YEARS = list(range(2015, 2020))
HOLDOUT_YEARS = list(range(2020, 2024))
OUTPUTS = ("world_gdp", "global_co2", "temperature")
PAIRING = {"world_gdp": "gdp_country_rmse_oos", "global_co2": "co2_rmse_oos",
           "temperature": "temp_rmse_oos"}


def rmse_pairs(pairs):
    pairs = list(pairs)
    return (sum((p - a) ** 2 for p, a in pairs) / len(pairs)) ** 0.5


def series_rmse(pred, act, years):
    return rmse_pairs((pred[y], act[y]) for y in years)


def gdp_country_rmse(pred_by_year, act_by_year, years):
    pairs = []
    for y in years:
        for c, a in act_by_year[y].items():
            pairs.append((pred_by_year[y].get(c, 0.0), a))
    return rmse_pairs(pairs)


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
        res = run_historical_backtest(params_override=draw,
                                      temperature_variability_sigma_override=0.0)
        agg = {"world_gdp": {y: sum(v.values()) for y, v in res.predicted_gdp_trillions.items()},
               "global_co2": dict(res.predicted_global_co2_gtco2),
               "temperature": dict(res.predicted_temperature_c)}
        rms = {o: series_rmse(agg[o], obs_world[o], CONSTRAIN_YEARS) for o in OUTPUTS}
        members.append({
            "draw": draw,
            "rmse_constrain": rms,
            "gdp_country_rmse_oos": gdp_country_rmse(res.predicted_gdp_trillions,
                                                     res.actual_gdp_trillions, HOLDOUT_YEARS),
            "co2_rmse_oos": series_rmse(agg["global_co2"], obs_world["global_co2"], HOLDOUT_YEARS),
            "temp_rmse_oos": series_rmse(agg["temperature"], obs_world["temperature"], HOLDOUT_YEARS),
        })
        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{N_SAMPLES}")

    oos = {k: np.array([m[k] for m in members])
           for k in ("gdp_country_rmse_oos", "co2_rmse_oos", "temp_rmse_oos")}

    def block(tols, label):
        imp = {o: np.array([m["rmse_constrain"][o] / tols[o] for m in members]) for o in OUTPUTS}
        imax = np.max(np.vstack([imp[o] for o in OUTPUTS]), axis=0)
        nroy = imax <= THRESHOLD
        retained = {}
        for n in DEFAULT_CALIBRATION_PARAMS:
            pv = np.array([m["draw"][n] for m in members])
            span = float(pv.max() - pv.min()) or 1e-12
            if nroy.any():
                nv = pv[nroy]
                retained[n] = float((nv.max() - nv.min()) / span)
        buys = {}
        for k, v in oos.items():
            buys[k] = {
                "all_draws_mean": float(v.mean()),
                "nroy_mean": float(v[nroy].mean()) if nroy.any() else float("nan"),
                "improvement_pct": (float(100.0 * (1.0 - v[nroy].mean() / v.mean()))
                                    if nroy.any() and v.mean() > 0 else float("nan")),
            }
        out = {
            "tolerances": dict(tols),
            "n_nroy": int(nroy.sum()),
            "fraction_retained": float(nroy.mean()),
            "max_implausibility": float(imax.max()),
            "median_implausibility": float(np.median(imax)),
            "prior_range_retained_per_param": retained,
            "mean_prior_range_retained": (float(np.mean(list(retained.values())))
                                          if retained else float("nan")),
            "out_of_sample_gain_from_filtering": buys,
        }
        print(f"\n[{label}] NROY {out['n_nroy']}/{N_SAMPLES} ({out['fraction_retained']*100:.1f}%)  "
              f"median I {out['median_implausibility']:.3f}  max I {out['max_implausibility']:.3f}")
        if retained:
            print(f"  mean prior range retained: {out['mean_prior_range_retained']*100:.1f}%")
            for n, v in sorted(retained.items(), key=lambda kv: kv[1]):
                print(f"     {n:26s} {v*100:5.1f}%")
        print("  out-of-sample gain from filtering:")
        for k, b in buys.items():
            print(f"     {k:24s} all {b['all_draws_mean']:.4f} -> NROY {b['nroy_mean']:.4f} "
                  f"({b['improvement_pct']:+.2f}%)")
        return out

    results = {"published_tolerances": block(DEFAULT_TOLERANCES, "published"),
               "tightened_tolerances": block(TIGHTENED_TOLERANCES, "tightened")}

    # the alternative to filtering: rank on the RIGHT output and take the best decile
    print("\n[per-output ranking, best decile on the matching output]")
    ranking = {}
    k10 = max(1, N_SAMPLES // 10)
    for o, key in PAIRING.items():
        imp_o = np.array([m["rmse_constrain"][o] for m in members])
        order = np.argsort(imp_o)
        v = oos[key]
        best = float(v[order[:k10]].mean())
        allm = float(v.mean())
        ranking[key] = {"ranked_on": o, "all_draws_mean": allm, "best_decile_mean": best,
                        "improvement_pct": float(100.0 * (1.0 - best / allm)) if allm > 0 else float("nan")}
        print(f"   {key:24s} ranked on {o:12s} all {allm:.4f} -> best decile {best:.4f} "
              f"({ranking[key]['improvement_pct']:+.2f}%)")

    payload = {
        "experiment": "E14",
        "question": "Once the cut binds, does it constrain the parameters and buy "
                    "out-of-sample skill -- and how does that compare with per-output ranking?",
        "config": {"n_samples": N_SAMPLES, "seed": SEED, "threshold": THRESHOLD,
                   "constrain_years": CONSTRAIN_YEARS, "holdout_years": HOLDOUT_YEARS},
        "filtering": results,
        "per_output_ranking": ranking,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(os.path.abspath(OUT), "w") as fh:
        json.dump(payload, fh, indent=1)
    print("\nwrote", os.path.abspath(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
