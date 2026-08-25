#!/usr/bin/env python3
"""Vintage-clean conflict-ranking test (reviewer major-revision item 3).

Reverse-causation concern: regime stability and the military-expenditure share are
themselves affected by armed conflict, so inputs measured within or after the
evaluation window partly encode the outcome they rank. Bound: rebuild the
conflict-proneness score using ONLY data available up to 1999 (WGI 1996/1998
vintages, WB Gini and military-expenditure share at their latest pre-2000 value),
then evaluate the ranking against UCDP/PRIO conflict incidence over 2000-2023.

Construction mirrors scripts/build_gim13_agent_states.py (weights unchanged), with
two terms REMOVED because no pre-2000 source exists (water stress ER.H2O.FWST.ZS
and ND-GAIN climate vulnerability); the remaining weights are renormalized:

  tension_v  = [0.35*(1-trust) + 0.25*gini_norm + 0.15*(1-regime_stab)] / 0.75
  conflict_v = [0.35*(1-regime_stab) + 0.25*tension_v + 0.20*milex_norm] / 0.80

Coverage: the 49 direct country agents with a pre-2000 WGI vintage (Taiwan is not
in the WB panels; the 7 regional aggregates are excluded). For apples-to-apples,
the CURRENT (2023-vintage) score is also evaluated on the same 49-country subset
and the same 2000-2023 labels.

Inference mirrors conflict_auc_inference.py: bootstrap 95% CI (20,000 resamples),
one-sided label-permutation p (50,000), seed 2026.

Writes results/calibration/conflict_vintage_test.json.
"""
from __future__ import annotations

import csv
import json
import os
import random
import sys
from statistics import median

import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

import importlib.util

spec = importlib.util.spec_from_file_location(
    "conflict_backtest", os.path.join(REPO, "scripts", "conflict_backtest.py")
)
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)

CUTOFF = 1999
WINDOW = (2000, 2023)
WGI_CSV = os.path.join(REPO, "data", "external", "worldbank_wgi_1990_2024.csv")
WDI_CSV = os.path.join(REPO, "data", "external", "worldbank_wdi_1990_2024.csv")
STATE = os.path.join(REPO, "data", "agent_states_operational.csv")
OUT = os.path.join(REPO, "results", "calibration", "conflict_vintage_test.json")

BOOT_N = int(os.getenv("BOOT_N", "20000"))
PERM_N = int(os.getenv("PERM_N", "50000"))
SEED = int(os.getenv("AUC_SEED", "2026"))


def latest_leq(panel: pd.DataFrame, variable: str, cutoff: int) -> pd.Series:
    sub = panel[(panel["variable"] == variable) & (panel["year"] <= cutoff)].dropna(subset=["value"])
    sub = sub.sort_values("year").groupby("iso3").last()
    return sub["value"]


def unit(x):
    """WGI point scale +-2.5 -> [0,1]."""
    return ((x + 2.5) / 5.0).clip(0.0, 1.0)


def robust_minmax(s: pd.Series, lower_q=0.05, upper_q=0.95, default=0.5) -> pd.Series:
    if s.dropna().empty:
        return pd.Series(default, index=s.index)
    lo, hi = s.quantile(lower_q), s.quantile(upper_q)
    if pd.isna(lo) or pd.isna(hi) or hi <= lo:
        return pd.Series(default, index=s.index)
    return ((s.clip(lo, hi) - lo) / (hi - lo)).fillna(default)


def main() -> int:
    wgi = pd.read_csv(WGI_CSV)
    wdi = pd.read_csv(WDI_CSV)

    pv = unit(latest_leq(wgi, "wgi_political_stability", CUTOFF))
    ge = unit(latest_leq(wgi, "wgi_gov_effectiveness", CUTOFF))
    rl = unit(latest_leq(wgi, "wgi_rule_of_law", CUTOFF))
    va = unit(latest_leq(wgi, "wgi_voice_accountability", CUTOFF))
    gini = latest_leq(wdi, "gini_wb", CUTOFF)
    milex = latest_leq(wdi, "milex_pct_gdp", CUTOFF)

    df = pd.DataFrame({"pv": pv, "ge": ge, "rl": rl, "va": va, "gini": gini, "milex": milex})
    df = df.dropna(subset=["pv", "ge", "rl", "va"])  # require full WGI vintage
    n_gini_imputed = int(df["gini"].isna().sum())
    df["gini"] = df["gini"].fillna(df["gini"].median())
    gini_norm = (df["gini"] / 100.0).clip(0.0, 1.0)

    regime_stab = 0.55 * df["pv"] + 0.25 * df["rl"] + 0.20 * df["ge"]
    trust = (0.42 * df["ge"] + 0.23 * df["va"] + 0.20 * regime_stab + 0.15 * (1.0 - gini_norm)).clip(0.0, 1.0)
    tension_v = ((0.35 * (1.0 - trust) + 0.25 * gini_norm + 0.15 * (1.0 - regime_stab)) / 0.75).clip(0.0, 1.0)
    milex_norm = robust_minmax(df["milex"])
    conflict_v = ((0.35 * (1.0 - regime_stab) + 0.25 * tension_v + 0.20 * milex_norm) / 0.80).clip(0.0, 1.0)

    # iso3 -> GIM name, restrict to the 50 direct country agents present in the state file
    iso_to_name = {}
    with open(STATE, newline="") as fh:
        for row in csv.DictReader(fh):
            if not row["id"].startswith("AG_"):
                iso_to_name[row["id"]] = row["name"]
    scores_v = {iso_to_name[i]: float(conflict_v[i]) for i in conflict_v.index if i in iso_to_name}

    labels_all = cb.load_ucdp_labels(WINDOW)
    names = sorted(scores_v)
    y = [labels_all.get(n, 0) for n in names]
    s_vint = [scores_v[n] for n in names]

    # current (2023-vintage) score on the SAME subset and SAME window
    cur = cb.load_gim_conflict_proneness()
    s_cur = [cur[n] for n in names]

    def boot_ci(scores, labels):
        rng = random.Random(SEED)
        idx = list(range(len(labels)))
        vals = []
        while len(vals) < BOOT_N:
            take = [idx[rng.randrange(len(idx))] for _ in idx]
            lb = [labels[i] for i in take]
            if len(set(lb)) < 2:
                continue
            vals.append(cb.auc([scores[i] for i in take], lb))
        vals.sort()
        return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals))]

    def perm_p(scores, labels, observed):
        rng = random.Random(SEED + 1)
        hits = 0
        lb = list(labels)
        for _ in range(PERM_N):
            rng.shuffle(lb)
            if cb.auc(scores, lb) >= observed:
                hits += 1
        return (1 + hits) / (1 + PERM_N)

    results = {}
    for tag, s in (("vintage_leq1999", s_vint), ("current_2023_same_subset", s_cur)):
        a = cb.auc(s, y)
        lo, hi = boot_ci(s, y)
        p = perm_p(s, y, a)
        results[tag] = {"auc": a, "ci95": [lo, hi], "perm_p": p}
        print(f"{tag}: AUC={a:.3f}  95% CI [{lo:.2f}, {hi:.2f}]  perm p={p:.4g}")

    payload = {
        "design": {
            "cutoff_year": CUTOFF, "eval_window": list(WINDOW),
            "n_countries": len(names), "n_positive": sum(y),
            "excluded": "Taiwan (no WB/WGI panel) + 7 regional aggregates",
            "dropped_terms": "water_stress, climate_risk (no pre-2000 source); weights renormalized",
            "n_gini_imputed_median": n_gini_imputed,
            "boot_n": BOOT_N, "perm_n": PERM_N, "seed": SEED,
        },
        "results": results,
        "scores_vintage": {n: scores_v[n] for n in names},
        "labels_2000_2023": dict(zip(names, y)),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(payload, fh, indent=1)
    print(f"n={len(names)} countries, positives={sum(y)}, gini imputed={n_gini_imputed}")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
