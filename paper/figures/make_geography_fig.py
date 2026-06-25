#!/usr/bin/env python3
"""Regenerate fig10_geography (the conflict-geography finding) -- reproducible & committed.

    python3 paper/figures/make_geography_fig.py
Produces paper/figures/fig10_geography.{pdf,png}.

Panel (a): conflict locality (adjacency relative to chance), real interstate conflict vs GIM with the
  geography contagion off and on -- from scripts/diagnose_border_geography.py.
Panel (b): the leverage on the conflict ranking AUC -- conflict_proneness alone, with the neighbour
  spatial-lag blended in, and the neighbour exposure alone -- from scripts/run_s5_conflict_geography.py
  (read from results/calibration/conflict_geography.json when present).
"""
from __future__ import annotations

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIGDIR = os.path.join(REPO, "paper", "figures")
LEDGER = os.path.join(REPO, "results", "calibration", "conflict_geography.json")

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["DejaVu Serif"], "font.size": 10,
    "axes.titlesize": 11, "axes.labelsize": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.8, "axes.axisbelow": True,
})

# Locality lifts (× chance) and median distances (km) — scripts/diagnose_border_geography.py.
LOCALITY = [("Real\ninterstate", 45.6, 863), ("GIM\n(geo off)", 2.7, 6906), ("GIM\n(geo on)", 9.6, 3364)]

# AUC leverage — read the ledger if present, else the documented S5 values.
AUC = {"auc_conflict_proneness": 0.772, "auc_blended": 0.805, "auc_neighbour_exposure_alone": 0.690}
if os.path.exists(LEDGER):
    AUC.update({k: v for k, v in json.load(open(LEDGER)).items() if k in AUC})


def main() -> None:
    fig, (axa, axb) = plt.subplots(1, 2, figsize=(7.2, 3.2))

    # (a) locality
    labels = [t[0] for t in LOCALITY]
    lifts = [t[1] for t in LOCALITY]
    colors = ["#444444", "#c0392b", "#2e7d32"]
    bars = axa.bar(labels, lifts, color=colors, width=0.62)
    axa.axhline(1.0, ls="--", lw=1.0, color="#888888")
    axa.text(2.55, 1.4, "chance", color="#888888", fontsize=8, ha="right")
    axa.set_ylabel("neighbour adjacency (× chance)")
    axa.set_title("(a) conflict locality")
    axa.set_ylim(0, 52)
    for bar, (_, lift, km) in zip(bars, LOCALITY):
        axa.text(bar.get_x() + bar.get_width() / 2, lift + 1.0, f"{lift:.1f}×",
                 ha="center", va="bottom", fontsize=9)
        axa.text(bar.get_x() + bar.get_width() / 2, min(lift, 50) / 2, f"{km:,} km",
                 ha="center", va="center", fontsize=7.5, color="white", rotation=90)

    # (b) AUC leverage
    blab = ["conflict\nproneness", "+ neighbour\nexposure", "exposure\nalone"]
    bvals = [AUC["auc_conflict_proneness"], AUC["auc_blended"], AUC["auc_neighbour_exposure_alone"]]
    bars2 = axb.bar(blab, bvals, color=["#444444", "#2e7d32", "#7f8c8d"], width=0.62)
    axb.axhline(0.5, ls="--", lw=1.0, color="#888888")
    axb.text(2.45, 0.515, "chance (0.5)", color="#888888", fontsize=8, ha="right")
    axb.set_ylabel("conflict ranking AUC (vs UCDP)")
    axb.set_title("(b) leverage on conflict skill")
    axb.set_ylim(0.45, 0.86)
    for bar, v in zip(bars2, bvals):
        axb.text(bar.get_x() + bar.get_width() / 2, v + 0.006, f"{v:.3f}",
                 ha="center", va="bottom", fontsize=9)
    gain = AUC["auc_blended"] - AUC["auc_conflict_proneness"]
    axb.annotate(f"+{gain:.3f}", xy=(1, AUC["auc_blended"]), xytext=(0.5, 0.84),
                 fontsize=8.5, color="#2e7d32", ha="center")

    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(FIGDIR, f"fig10_geography.{ext}"), dpi=150, bbox_inches="tight")
    print("wrote fig10_geography.{pdf,png}")


if __name__ == "__main__":
    main()
