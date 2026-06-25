#!/usr/bin/env python3
"""S4 — conflict forecast-skill benchmark (social-domain analogue of D6, Tier-B).

Upgrades the conflict backtest from "skill vs base rate" to a reproducible benchmark: it reports
discrimination (AUC), Brier-skill vs base rate (BSS), the Murphy CALIBRATION decomposition
(reliability/resolution), and places GIM's number against the PUBLISHED skill of the standard
conflict-forecasting models (PITF, ViEWS).

Reuses the exact live scoring set from scripts/conflict_backtest.py (GIM conflict_proneness vs UCDP/PRIO
involvement, 1990-2023). If the UCDP file is absent it falls back to the stored result ledger.

HONEST SCOPE: Tier-B forecast-skill benchmark, not D6 engine-reproduction; the references score different
targets/units (caveat in gim/conflict_benchmark.py). The substantive point: GIM's skill comes from an
UNFITTED mechanistic input. A same-test-set bake-off vs ViEWS needs their replication data (deferred).

Run: python3 scripts/run_s4_conflict_benchmark.py
"""
from __future__ import annotations

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (REPO, os.path.join(REPO, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from gim.conflict_benchmark import (                       # noqa: E402
    PUBLISHED_BENCHMARKS,
    brier_decomposition,
    calibration_curve,
    compare_to_benchmarks,
)


def _live_scoring_set():
    """(probs, labels) over the 57 GIM countries, or None if the UCDP file is absent."""
    from conflict_backtest import load_gim_conflict_proneness, load_ucdp_labels  # noqa: E402
    gim = load_gim_conflict_proneness()
    labels_map = load_ucdp_labels((1990, 2023))
    if labels_map is None:
        return None
    names = [n for n in gim if n in labels_map] + [n for n in gim if n not in labels_map]
    return [gim[n] for n in names], [labels_map.get(n, 0) for n in names]


def main() -> int:
    print("S4 — conflict forecast-skill benchmark (social-domain analogue of D6, Tier-B)\n")
    scoring = _live_scoring_set()
    if scoring is None:
        stored = json.load(open(os.path.join(REPO, "results", "calibration", "conflict_backtest.json")))
        auc_v, bss = stored["auc"], stored["brier_skill_score"]
        print(f"(UCDP file absent — using stored ledger) AUC={auc_v:.3f}  BSS={bss:+.3f}")
        decomp = None
    else:
        from conflict_backtest import auc as auc_fn, brier
        probs, labels = scoring
        n = len(labels)
        base = sum(labels) / n
        auc_v = auc_fn(probs, labels)
        bss = 1.0 - brier(probs, labels) / brier([base] * n, labels)
        decomp = brier_decomposition(probs, labels)
        print(f"scored {n} countries; base rate {base:.3f}")
        print(f"discrimination : AUC = {auc_v:.3f}   BSS = {bss:+.3f}")
        print(f"calibration    : Brier = {decomp['brier']:.4f}  reliability = {decomp['reliability']:.4f} "
              f"(lower better)  resolution = {decomp['resolution']:.4f} (higher better)  "
              f"cal.err = {decomp['calibration_error']:.3f}")
        cal = calibration_curve(probs, labels)
        print("reliability diagram (forecast -> observed, n):")
        for p_bar, o_bar, nk in cal:
            print(f"    {p_bar:.2f} -> {o_bar:.2f}  (n={nk})")

    print("\npublished reference models (different targets/units — reference points, not a common set):")
    for b in PUBLISHED_BENCHMARKS:
        print(f"    {b['model']}: {b['skill']}  [{b['target']}]")

    cmp = compare_to_benchmarks(auc_v, bss)
    print(f"\nGIM AUC {cmp['gim_auc']:.3f} / BSS {cmp['gim_bss']:+.3f} vs reference AUC band "
          f"{cmp['reference_auc_band'][0]:.2f}-{cmp['reference_auc_band'][1]:.2f}")
    print("RESULT:", "BENCHMARKED — " + str(cmp["verdict"]) if cmp["above_chance"]
          else "CHECK FAILED — " + str(cmp["verdict"]))
    return 0 if cmp["above_chance"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
