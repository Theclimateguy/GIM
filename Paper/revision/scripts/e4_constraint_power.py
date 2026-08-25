#!/usr/bin/env python3
"""E4 -- how much does history matching actually constrain?

Section 5 says the 2015-2019 window "rules out none of the sampled draws at the
three-sigma cut, so the frozen region coincides with the prior box". That is stated as
an aside. It is in fact the central fact about the calibration step, and it needs to be
quantified rather than mentioned: if no draw is ever ruled out, the history-matching
stage is decorative and the "constraint hold-out" cannot be a hold-out in any sense.

Tolerances (gim/calibration_hm.py:29) are world_gdp 6.0 T$, global_co2 2.0 Gt,
temperature 0.15 C, with NROY defined by max_o RMSE_o/tol_o <= 3.0. A draw therefore
survives unless world output is off by 18 T$ (about 18% of world product), emissions by
6 Gt, or temperature by 0.45 C.

This script measures three things over a large prior sample:

  1. the implausibility distribution, and the threshold that would actually bind;
  2. how much of each parameter's prior range the NROY region retains;
  3. whether implausibility carries information about OUT-OF-SAMPLE error even when the
     cut does not bind -- i.e. whether the ranking is informative although the filter is
     not. This is the part that decides whether the calibration stage can be defended as
     something other than decoration.

Writes Paper/revision/results/e4_constraint_power.json
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

from gim.calibration_hm import DEFAULT_CALIBRATION_PARAMS, DEFAULT_TOLERANCES  # noqa: E402
from gim.core.priors import key_priors                                          # noqa: E402
from gim.historical_backtest import (                                           # noqa: E402
    load_historical_observed_fixture,
    run_historical_backtest,
)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                   "e4_constraint_power.json")
N_SAMPLES = 600
SEED = 2026
THRESHOLD = 3.0
CONSTRAIN_YEARS = list(range(2015, 2020))
FULL_YEARS = list(range(2015, 2024))
HOLDOUT_YEARS = list(range(2020, 2024))
OUTPUTS = ("world_gdp", "global_co2", "temperature")


def rmse_pairs(pairs) -> float:
    pairs = list(pairs)
    return (sum((p - a) ** 2 for p, a in pairs) / len(pairs)) ** 0.5


def series_rmse(pred, act, years) -> float:
    return rmse_pairs((pred[y], act[y]) for y in years)


def gdp_country_rmse(pred_by_year, act_by_year, years) -> float:
    pairs = []
    for y in years:
        for c, a in act_by_year[y].items():
            pairs.append((pred_by_year[y].get(c, 0.0), a))
    return rmse_pairs(pairs)


def world_aggregates(res) -> dict:
    return {
        "world_gdp": {y: sum(v.values()) for y, v in res.predicted_gdp_trillions.items()},
        "global_co2": dict(res.predicted_global_co2_gtco2),
        "temperature": dict(res.predicted_temperature_c),
    }


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
        agg = world_aggregates(res)
        act = res.actual_gdp_trillions
        rms_c = {o: series_rmse(agg[o], obs_world[o], CONSTRAIN_YEARS) for o in OUTPUTS}
        rms_f = {o: series_rmse(agg[o], obs_world[o], FULL_YEARS) for o in OUTPUTS}
        imp_c = {o: rms_c[o] / DEFAULT_TOLERANCES[o] for o in OUTPUTS}
        imp_f = {o: rms_f[o] / DEFAULT_TOLERANCES[o] for o in OUTPUTS}
        members.append({
            "draw": draw,
            "imp_2015_2019": imp_c,
            "imp_2015_2019_max": max(imp_c.values()),
            "imp_2015_2023_max": max(imp_f.values()),
            "gdp_country_rmse_oos": gdp_country_rmse(res.predicted_gdp_trillions, act, HOLDOUT_YEARS),
            "co2_rmse_oos": series_rmse(agg["global_co2"], obs_world["global_co2"], HOLDOUT_YEARS),
            "temp_rmse_oos": series_rmse(agg["temperature"], obs_world["temperature"], HOLDOUT_YEARS),
        })
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{N_SAMPLES}")

    imp_max = np.array([m["imp_2015_2019_max"] for m in members])
    per_output = {o: np.array([m["imp_2015_2019"][o] for m in members]) for o in OUTPUTS}

    # 1. does the cut bind?
    n_ruled_out = int((imp_max > THRESHOLD).sum())
    binding = {
        "threshold_used": THRESHOLD,
        "n_samples": N_SAMPLES,
        "n_ruled_out_at_3sigma": n_ruled_out,
        "fraction_ruled_out_at_3sigma": n_ruled_out / N_SAMPLES,
        "implausibility_max_over_all_draws": float(imp_max.max()),
        "implausibility_quantiles": {q: float(np.quantile(imp_max, float(q)))
                                     for q in ("0.5", "0.9", "0.95", "0.99", "1.0")},
        "threshold_that_would_rule_out_5pct": float(np.quantile(imp_max, 0.95)),
        "threshold_that_would_rule_out_50pct": float(np.quantile(imp_max, 0.50)),
        "headroom_factor_at_median": THRESHOLD / float(np.quantile(imp_max, 0.50)),
        "tolerance_that_would_bind_at_3sigma": {
            o: float(np.quantile(per_output[o] * DEFAULT_TOLERANCES[o], 0.50) / THRESHOLD)
            for o in OUTPUTS
        },
        "current_tolerances": dict(DEFAULT_TOLERANCES),
        "per_output_implausibility_median": {o: float(np.median(per_output[o])) for o in OUTPUTS},
        "per_output_implausibility_max": {o: float(per_output[o].max()) for o in OUTPUTS},
        "binding_output": max(OUTPUTS, key=lambda o: float(np.median(per_output[o]))),
    }

    # 2. does NROY narrow any prior?
    nroy = [m for m in members if m["imp_2015_2019_max"] <= THRESHOLD]
    retained = {}
    for n in DEFAULT_CALIBRATION_PARAMS:
        pv = np.array([m["draw"][n] for m in members])
        span = float(pv.max() - pv.min()) or 1e-12
        if nroy:
            nv = np.array([m["draw"][n] for m in nroy])
            retained[n] = {
                "prior_min": float(pv.min()), "prior_max": float(pv.max()),
                "nroy_min": float(nv.min()), "nroy_max": float(nv.max()),
                "retained_fraction": float((nv.max() - nv.min()) / span),
            }

    # 3. is implausibility informative about out-of-sample error even when it does not bind?
    def spearman(a, b):
        ra = np.argsort(np.argsort(a)).astype(float)
        rb = np.argsort(np.argsort(b)).astype(float)
        return float(np.corrcoef(ra, rb)[0, 1])

    oos = {
        "gdp_country_rmse_oos": np.array([m["gdp_country_rmse_oos"] for m in members]),
        "co2_rmse_oos": np.array([m["co2_rmse_oos"] for m in members]),
        "temp_rmse_oos": np.array([m["temp_rmse_oos"] for m in members]),
    }
    informative = {k: {"spearman_vs_implausibility": spearman(imp_max, v)} for k, v in oos.items()}
    # per-output: does each in-sample implausibility rank its own out-of-sample error?
    pairing = {"global_co2": "co2_rmse_oos", "temperature": "temp_rmse_oos",
               "world_gdp": "gdp_country_rmse_oos"}
    for o, key in pairing.items():
        informative[key]["spearman_vs_own_output_implausibility"] = spearman(per_output[o], oos[key])

    # decile lift: mean out-of-sample error of the best vs worst implausibility decile
    order = np.argsort(imp_max)
    k = max(1, N_SAMPLES // 10)
    for key, v in oos.items():
        best, worst = v[order[:k]], v[order[-k:]]
        informative[key]["best_decile_mean"] = float(best.mean())
        informative[key]["worst_decile_mean"] = float(worst.mean())
        informative[key]["decile_lift"] = float(worst.mean() / best.mean()) if best.mean() > 0 else float("nan")

    print(f"\nruled out at 3-sigma: {n_ruled_out}/{N_SAMPLES}")
    print(f"max implausibility over all draws: {imp_max.max():.3f} (cut is at {THRESHOLD})")
    print(f"median implausibility: {np.median(imp_max):.3f} -> headroom factor "
          f"{binding['headroom_factor_at_median']:.1f}x")
    print(f"binding output: {binding['binding_output']}")
    for o in OUTPUTS:
        print(f"  {o:12s} median I {np.median(per_output[o]):.3f}  max I {per_output[o].max():.3f}"
              f"  tol that would bind: {binding['tolerance_that_would_bind_at_3sigma'][o]:.3f}"
              f" (current {DEFAULT_TOLERANCES[o]})")
    print("\nimplausibility vs out-of-sample error (Spearman):")
    for k_, v in informative.items():
        print(f"  {k_:24s} rho={v['spearman_vs_implausibility']:+.3f}  "
              f"own-output rho={v.get('spearman_vs_own_output_implausibility', float('nan')):+.3f}  "
              f"decile lift {v['decile_lift']:.2f}x")

    payload = {
        "experiment": "E4",
        "question": "Does the 3-sigma history-matching cut constrain anything, and is "
                    "implausibility informative about out-of-sample error?",
        "config": {"n_samples": N_SAMPLES, "seed": SEED, "threshold": THRESHOLD,
                   "constrain_years": CONSTRAIN_YEARS, "holdout_years": HOLDOUT_YEARS,
                   "params": DEFAULT_CALIBRATION_PARAMS,
                   "tolerances": DEFAULT_TOLERANCES},
        "binding": binding,
        "prior_retention": retained,
        "informativeness": informative,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(os.path.abspath(OUT), "w") as fh:
        json.dump(payload, fh, indent=1)
    print("wrote", os.path.abspath(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
