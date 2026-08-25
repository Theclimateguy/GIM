#!/usr/bin/env python3
"""E8 -- does the conflict composite beat its own single best component?

Section 5 reports the conflict-proneness score ranking the 57 agents against UCDP/PRIO at
AUC 0.739, with chance (0.5) as the reference and a base-rate Brier skill of +0.123. The
missing benchmark is the one a reviewer will ask for first: the score is a FIXED-WEIGHT
composite, so the relevant null is not chance, it is **the best single component**. If one
input scores as well as the blend, the composite is decoration and should be replaced in
the paper by that input.

Expanding the two construction steps (`scripts/build_gim13_agent_states.py:1172, 1372`):

  conflict_proneness = 0.35*(1-regime_stability) + 0.25*social_tension
                     + 0.20*climate_risk + 0.20*minmax(military_gdp_ratio)
  social_tension     = 0.35*(1-trust_gov) + 0.25*gini_norm + 0.15*water_stress
                     + 0.10*climate_risk + 0.15*(1-regime_stability)

so in reduced form the weights on the primitives are

  0.3875*(1-regime_stability) + 0.2250*climate_risk + 0.2000*military
  + 0.0875*(1-trust_gov) + 0.0625*gini_norm + 0.0375*water_stress

i.e. it is dominated by (1 - regime_stability).

Reports AUC with a bootstrap CI for the composite and for every component, and the paired
bootstrap distribution of the DIFFERENCE composite - component, which is the statistic
that decides whether the blend adds anything.

Writes Paper/revision/results/e8_conflict_composite_vs_components.json
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
for p in (REPO, os.path.join(REPO, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from conflict_backtest import load_ucdp_labels  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                   "e8_conflict_composite_vs_components.json")
STATE = os.path.join(REPO, "data", "agent_states_operational.csv")
N_BOOT = 20000
SEED = 20260824
WINDOW = (1990, 2023)

# name -> (column, orientation). orientation +1 means "higher raises conflict risk".
COMPONENTS = {
    "one_minus_regime_stability": ("regime_stability", -1),
    "climate_risk": ("climate_risk", +1),
    "one_minus_trust_gov": ("trust_gov", -1),
    "inequality_gini": ("inequality_gini", +1),
    "water_stress": ("water_stress", +1),
    "social_tension": ("social_tension", +1),
    "military_power": ("military_power", +1),
}
REDUCED_FORM_WEIGHTS = {
    "one_minus_regime_stability": 0.3875,
    "climate_risk": 0.2250,
    "military(minmax mil/gdp)": 0.2000,
    "one_minus_trust_gov": 0.0875,
    "gini_norm": 0.0625,
    "water_stress": 0.0375,
}


def auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Mann-Whitney AUC with ties handled by midranks."""
    pos, neg = labels == 1, labels == 0
    n1, n0 = pos.sum(), neg.sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(scores.size, dtype=float)
    s = scores[order]
    i = 0
    while i < s.size:
        j = i
        while j + 1 < s.size and s[j + 1] == s[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def main() -> int:
    rows = list(csv.DictReader(open(STATE)))
    labels_map = load_ucdp_labels(WINDOW)
    if labels_map is None:
        print("UCDP labels unavailable; cannot run E8")
        return 1

    names, y = [], []
    cols = {k: [] for k in COMPONENTS}
    comp = []
    for r in rows:
        nm = r.get("name") or r.get("id")
        try:
            vals = {k: float(r[c]) * sign for k, (c, sign) in COMPONENTS.items()}
            cp = float(r["conflict_proneness"])
        except (KeyError, ValueError, TypeError):
            continue
        names.append(nm)
        y.append(int(labels_map.get(nm, 0)))
        comp.append(cp)
        for k, v in vals.items():
            cols[k].append(v)

    y = np.array(y)
    comp = np.array(comp)
    n = y.size
    print(f"n = {n} agents, positives = {int(y.sum())}, base rate = {y.mean():.3f}")

    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, n, size=(N_BOOT, n))

    def boot_auc(v):
        return np.array([auc(v[i], y[i]) for i in idx])

    base_boot = boot_auc(comp)
    results = {
        "composite_conflict_proneness": {
            "auc": auc(comp, y),
            "ci95": [float(np.nanquantile(base_boot, 0.025)),
                     float(np.nanquantile(base_boot, 0.975))],
        }
    }

    print(f"\ncomposite conflict_proneness  AUC {results['composite_conflict_proneness']['auc']:.4f} "
          f"CI {results['composite_conflict_proneness']['ci95'][0]:.3f}-"
          f"{results['composite_conflict_proneness']['ci95'][1]:.3f}\n")
    print(f"{'component':32s} {'AUC':>7s} {'95% CI':>17s} {'delta vs composite':>20s} {'P(composite>comp)':>18s}")

    per = {}
    for k in COMPONENTS:
        v = np.array(cols[k])
        a = auc(v, y)
        vb = boot_auc(v)
        d = base_boot - vb                      # paired: same resamples
        per[k] = {
            "auc": a,
            "ci95": [float(np.nanquantile(vb, 0.025)), float(np.nanquantile(vb, 0.975))],
            "delta_composite_minus_component": float(np.nanmean(d)),
            "delta_ci95": [float(np.nanquantile(d, 0.025)), float(np.nanquantile(d, 0.975))],
            "prob_composite_better": float(np.nanmean(d > 0)),
        }
        print(f"{k:32s} {a:7.4f} [{per[k]['ci95'][0]:.3f},{per[k]['ci95'][1]:.3f}] "
              f"{per[k]['delta_composite_minus_component']:+20.4f} "
              f"{per[k]['prob_composite_better']:18.3f}")

    best = max(per, key=lambda k: per[k]["auc"])
    verdict = ("composite adds nothing detectable"
               if per[best]["delta_ci95"][0] <= 0 <= per[best]["delta_ci95"][1]
               else "composite differs from its best component")
    print(f"\nbest single component: {best} (AUC {per[best]['auc']:.4f}); "
          f"composite - best = {per[best]['delta_composite_minus_component']:+.4f} "
          f"[{per[best]['delta_ci95'][0]:+.4f}, {per[best]['delta_ci95'][1]:+.4f}] -> {verdict}")

    payload = {
        "experiment": "E8",
        "question": "Does the fixed-weight conflict composite beat its best single component?",
        "config": {"n_bootstrap": N_BOOT, "seed": SEED, "ucdp_window": list(WINDOW),
                   "n_agents": int(n), "n_positive": int(y.sum()),
                   "state_csv": os.path.relpath(STATE, REPO)},
        "reduced_form_weights": REDUCED_FORM_WEIGHTS,
        "composite": results["composite_conflict_proneness"],
        "components": per,
        "best_single_component": best,
        "verdict": verdict,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(os.path.abspath(OUT), "w") as fh:
        json.dump(payload, fh, indent=1)
    print("wrote", os.path.abspath(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
