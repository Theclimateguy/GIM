#!/usr/bin/env python3
"""S5 — does geography improve GIM's validated conflict ranking? (leverage test)

The border-geography diagnostic showed GIM's conflict block ignores a strong geographic signal. This
script tests whether that signal has LEVERAGE on the metric we actually report (the conflict AUC vs the
UCDP/PRIO record): it augments `conflict_proneness` with a spatial lag of neighbour conflict-proneness
(spatial contagion; Gleditsch 2007; Buhaug & Gleditsch 2008) and re-scores the ranking.

Honest framing: the gain is modest and on a small (geo-matched) country set; the grid-searched blend is
an upper bound. The untuned standalone exposure AUC is the clean "geography carries signal" number.
Writes results/calibration/conflict_geography.json.

Run: python3 scripts/run_s5_conflict_geography.py
"""
from __future__ import annotations

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (REPO, os.path.join(REPO, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from gim.geography import build_geography                              # noqa: E402
from gim.conflict_geography import auc, blended_auc_scan, spatial_exposure  # noqa: E402
from conflict_backtest import load_gim_conflict_proneness, load_ucdp_labels  # noqa: E402

WINDOW = (1990, 2023)


def main() -> int:
    geo = build_geography()
    cp = load_gim_conflict_proneness()
    labels = load_ucdp_labels(WINDOW)
    if labels is None:
        print("UCDP file absent — cannot score. See data/external/SOURCES.md.")
        return 0

    names = [n for n in geo.matched if n in cp]
    y = [labels.get(n, 0) for n in names]
    exposure = spatial_exposure(names, {n: cp[n] for n in names}, geo.adjacency)

    base_auc = auc([cp[n] for n in names], y)
    exp_auc = auc([exposure[n] for n in names], y)
    best_auc, best_w, _ = blended_auc_scan([cp[n] for n in names], [exposure[n] for n in names], y)

    print("S5 — geography leverage on the conflict ranking (spatial contagion)\n")
    print(f"geo-matched countries scored: {len(names)}  base rate {sum(y) / len(y):.3f}")
    print(f"AUC conflict_proneness alone        : {base_auc:.3f}  (baseline)")
    print(f"AUC neighbour-exposure alone (untuned): {exp_auc:.3f}  (geography carries standalone signal)")
    print(f"AUC blended (best w={best_w:.2f})           : {best_auc:.3f}  (delta {best_auc - base_auc:+.3f}, optimistic)")

    helps = exp_auc > 0.5 and best_auc > base_auc
    print("\nRESULT:", "GEOGRAPHY HELPS — neighbour conflict-risk improves the ranking; a switchable "
          "spatial-contagion term is justified." if helps else "no leverage — geography does not improve the metric.")

    out = os.path.join(REPO, "results", "calibration", "conflict_geography.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump({
            "experiment": "S5 geography leverage: conflict_proneness + spatial-lag(neighbour conflict) vs UCDP",
            "window": list(WINDOW), "n_countries": len(names),
            "auc_conflict_proneness": round(base_auc, 3),
            "auc_neighbour_exposure_alone": round(exp_auc, 3),
            "auc_blended": round(best_auc, 3), "blend_weight": round(best_w, 2),
            "auc_gain": round(best_auc - base_auc, 3),
            "note": "Modest gain on a small geo-matched set; blended best is grid-search-optimistic. "
                    "Spatial contagion of conflict: Gleditsch 2007; Buhaug & Gleditsch 2008.",
        }, fh, indent=2)
        fh.write("\n")
    print(f"ledger -> {os.path.relpath(out, REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
