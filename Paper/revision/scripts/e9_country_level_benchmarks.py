#!/usr/bin/env python3
"""E9 -- naive benchmarks at country level, where the model claims to be useful.

Section 5 compares the model against persistence and linear extrapolation on the WORLD
aggregates only, and reports honestly that output loses to both. But the paper's own
argument is that the useful resolution is the country: "at country level -- where the
crisis triggers live". No naive benchmark is reported there, so the one place the model
claims an advantage is the one place it is not benchmarked.

This runs the same two naive benchmarks per country on the 2020-2023 window, both built
from observed data through 2019 only:
  persistence -- hold the country's 2019 observed GDP flat;
  linear      -- OLS trend on that country's observed 2015-2019, extrapolated.
Skill = 1 - RMSE_model / RMSE_benchmark; positive means the model wins.

It also reports the win rate across countries, which is the statistic the
forecast-evaluation literature uses when a mean skill is dominated by a few large levels
(Celasun et al. 2021 report exactly this shape for professional growth forecasts).

Writes Paper/revision/results/e9_country_level_benchmarks.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.historical_backtest import (           # noqa: E402
    load_historical_observed_fixture,
    run_historical_backtest,
)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                   "e9_country_level_benchmarks.json")
FIT_YEARS = list(range(2015, 2020))
HOLDOUT = list(range(2020, 2024))
HOLDOUT_EX2020 = list(range(2021, 2024))


def rmse(pred: dict, act: dict, years) -> float:
    v = [(pred[y] - act[y]) ** 2 for y in years if y in pred and y in act]
    return float(np.sqrt(np.mean(v))) if v else float("nan")


def linear_extrapolate(obs: dict, fit_years, target_years) -> dict:
    xs = [y for y in fit_years if y in obs]
    ys = [obs[y] for y in xs]
    if len(xs) < 2:
        return {y: obs[xs[-1]] for y in target_years} if xs else {}
    slope, intercept = np.polyfit(xs, ys, 1)
    return {y: float(intercept + slope * y) for y in target_years}


def main() -> int:
    obs = load_historical_observed_fixture()
    gdp_obs = {int(y): {c: float(v) for c, v in d.items()}
               for y, d in obs["gdp_trillions_by_year"].items()}

    res = run_historical_backtest(temperature_variability_sigma_override=0.0)
    pred = {int(y): {c: float(v) for c, v in d.items()}
            for y, d in res.predicted_gdp_trillions.items()}

    countries = sorted(set(gdp_obs[HOLDOUT[0]]) & set(pred.get(HOLDOUT[0], {})))
    print(f"countries scored: {len(countries)}")

    rows = []
    for c in countries:
        act = {y: gdp_obs[y][c] for y in gdp_obs if c in gdp_obs[y]}
        mod = {y: pred[y][c] for y in pred if c in pred[y]}
        if 2019 not in act:
            continue
        persist = {y: act[2019] for y in HOLDOUT}
        linear = linear_extrapolate(act, FIT_YEARS, HOLDOUT)

        entry = {"country": c, "level_2019": act[2019]}

        # Levels RMSE is dominated by scale: a 1% error on China outweighs a 30% error on
        # the Netherlands. Forecast evaluation scores growth rates for exactly this reason,
        # so the same three forecasts are also scored as annual log-growth.
        def to_growth(series):
            g = {}
            for y in HOLDOUT:
                prev = series.get(y - 1)
                cur = series.get(y)
                if prev and cur and prev > 0 and cur > 0:
                    g[y] = float(np.log(cur / prev))
            return g

        act_g = to_growth(act)
        mod_g = to_growth(mod)
        # naive growth benchmarks: zero growth (persistence) and the mean 2015-2019 growth
        hist_g = [float(np.log(act[y] / act[y - 1]))
                  for y in FIT_YEARS[1:] if y in act and (y - 1) in act and act[y - 1] > 0]
        mean_g = float(np.mean(hist_g)) if hist_g else 0.0
        persist_g = {y: 0.0 for y in HOLDOUT}
        trend_g = {y: mean_g for y in HOLDOUT}
        entry["growth"] = {
            "mean_growth_2015_2019": mean_g,
            "rmse_model": rmse(mod_g, act_g, HOLDOUT),
            "rmse_zero_growth": rmse(persist_g, act_g, HOLDOUT),
            "rmse_mean_growth": rmse(trend_g, act_g, HOLDOUT),
        }
        gm = entry["growth"]
        gm["skill_vs_zero_growth"] = (float(1.0 - gm["rmse_model"] / gm["rmse_zero_growth"])
                                      if gm["rmse_zero_growth"] > 0 else float("nan"))
        gm["skill_vs_mean_growth"] = (float(1.0 - gm["rmse_model"] / gm["rmse_mean_growth"])
                                      if gm["rmse_mean_growth"] > 0 else float("nan"))
        gm["beats_zero_growth"] = bool(gm["rmse_model"] < gm["rmse_zero_growth"])
        gm["beats_mean_growth"] = bool(gm["rmse_model"] < gm["rmse_mean_growth"])

        for tag, years in (("oos", HOLDOUT), ("oos_ex2020", HOLDOUT_EX2020)):
            rm, rp, rl = rmse(mod, act, years), rmse(persist, act, years), rmse(linear, act, years)
            entry[tag] = {
                "rmse_model": rm, "rmse_persistence": rp, "rmse_linear": rl,
                "skill_vs_persistence": float(1.0 - rm / rp) if rp > 0 else float("nan"),
                "skill_vs_linear": float(1.0 - rm / rl) if rl > 0 else float("nan"),
                "beats_persistence": bool(rm < rp), "beats_linear": bool(rm < rl),
                "beats_both": bool(rm < rp and rm < rl),
            }
        rows.append(entry)

    def summarise(tag):
        sp = np.array([r[tag]["skill_vs_persistence"] for r in rows])
        sl = np.array([r[tag]["skill_vs_linear"] for r in rows])
        bp = np.array([r[tag]["beats_persistence"] for r in rows])
        bl = np.array([r[tag]["beats_linear"] for r in rows])
        bb = np.array([r[tag]["beats_both"] for r in rows])
        pooled_m = float(np.sqrt(np.mean([r[tag]["rmse_model"] ** 2 for r in rows])))
        pooled_p = float(np.sqrt(np.mean([r[tag]["rmse_persistence"] ** 2 for r in rows])))
        pooled_l = float(np.sqrt(np.mean([r[tag]["rmse_linear"] ** 2 for r in rows])))
        return {
            "n_countries": len(rows),
            "win_rate_vs_persistence": float(bp.mean()),
            "win_rate_vs_linear": float(bl.mean()),
            "win_rate_vs_both": float(bb.mean()),
            "median_skill_vs_persistence": float(np.nanmedian(sp)),
            "median_skill_vs_linear": float(np.nanmedian(sl)),
            "pooled_rmse_model": pooled_m,
            "pooled_rmse_persistence": pooled_p,
            "pooled_rmse_linear": pooled_l,
            "pooled_skill_vs_persistence": float(1.0 - pooled_m / pooled_p),
            "pooled_skill_vs_linear": float(1.0 - pooled_m / pooled_l),
        }

    def summarise_growth():
        bz = np.array([r["growth"]["beats_zero_growth"] for r in rows])
        bm = np.array([r["growth"]["beats_mean_growth"] for r in rows])
        sz = np.array([r["growth"]["skill_vs_zero_growth"] for r in rows])
        sm = np.array([r["growth"]["skill_vs_mean_growth"] for r in rows])
        pm = float(np.sqrt(np.mean([r["growth"]["rmse_model"] ** 2 for r in rows])))
        pz = float(np.sqrt(np.mean([r["growth"]["rmse_zero_growth"] ** 2 for r in rows])))
        pmg = float(np.sqrt(np.mean([r["growth"]["rmse_mean_growth"] ** 2 for r in rows])))
        return {
            "n_countries": len(rows),
            "win_rate_vs_zero_growth": float(bz.mean()),
            "win_rate_vs_mean_growth": float(bm.mean()),
            "median_skill_vs_zero_growth": float(np.nanmedian(sz)),
            "median_skill_vs_mean_growth": float(np.nanmedian(sm)),
            "pooled_rmse_model": pm, "pooled_rmse_zero_growth": pz,
            "pooled_rmse_mean_growth": pmg,
            "pooled_skill_vs_zero_growth": float(1.0 - pm / pz),
            "pooled_skill_vs_mean_growth": float(1.0 - pm / pmg),
        }

    summary = {tag: summarise(tag) for tag in ("oos", "oos_ex2020")}
    summary["growth_2020_2023"] = summarise_growth()

    for tag in ("oos", "oos_ex2020"):
        s = summary[tag]
        print(f"\n[{tag}] n={s['n_countries']}")
        print(f"  win rate vs persistence {s['win_rate_vs_persistence']*100:5.1f}%   "
              f"vs linear {s['win_rate_vs_linear']*100:5.1f}%   "
              f"vs both {s['win_rate_vs_both']*100:5.1f}%")
        print(f"  median skill  persistence {s['median_skill_vs_persistence']:+.3f}   "
              f"linear {s['median_skill_vs_linear']:+.3f}")
        print(f"  pooled RMSE   model {s['pooled_rmse_model']:.4f}  "
              f"persistence {s['pooled_rmse_persistence']:.4f}  linear {s['pooled_rmse_linear']:.4f}"
              f"  -> skill {s['pooled_skill_vs_persistence']:+.3f} / {s['pooled_skill_vs_linear']:+.3f}")

    g = summary["growth_2020_2023"]
    print(f"\n[growth 2020-2023, annual log-growth] n={g['n_countries']}")
    print(f"  win rate vs zero-growth {g['win_rate_vs_zero_growth']*100:5.1f}%   "
          f"vs mean-growth {g['win_rate_vs_mean_growth']*100:5.1f}%")
    print(f"  median skill  zero {g['median_skill_vs_zero_growth']:+.3f}   "
          f"mean {g['median_skill_vs_mean_growth']:+.3f}")
    print(f"  pooled RMSE   model {g['pooled_rmse_model']:.4f}  zero {g['pooled_rmse_zero_growth']:.4f}"
          f"  mean {g['pooled_rmse_mean_growth']:.4f}  -> skill "
          f"{g['pooled_skill_vs_zero_growth']:+.3f} / {g['pooled_skill_vs_mean_growth']:+.3f}")

    print(f"\n{'country':28s} {'model':>8s} {'persist':>8s} {'linear':>8s}  verdict")
    for r in sorted(rows, key=lambda r: -r["level_2019"]):
        o = r["oos"]
        verdict = "wins both" if o["beats_both"] else (
            "loses both" if not (o["beats_persistence"] or o["beats_linear"]) else "split")
        print(f"{r['country'][:28]:28s} {o['rmse_model']:8.4f} {o['rmse_persistence']:8.4f} "
              f"{o['rmse_linear']:8.4f}  {verdict}")

    payload = {
        "experiment": "E9",
        "question": "Does the model beat naive benchmarks at COUNTRY level on 2020-2023, "
                    "where the paper says the crisis triggers live?",
        "config": {"fit_years": FIT_YEARS, "holdout": HOLDOUT,
                   "holdout_ex2020": HOLDOUT_EX2020,
                   "benchmarks": ["persistence (hold 2019)",
                                  "linear OLS on observed 2015-2019"]},
        "summary": summary,
        "per_country": rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(os.path.abspath(OUT), "w") as fh:
        json.dump(payload, fh, indent=1)
    print("wrote", os.path.abspath(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
