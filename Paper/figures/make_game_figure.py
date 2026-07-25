#!/usr/bin/env python3
"""Regenerate fig10 (game-outcome distributions) from the committed game artifacts.

Data: Paper/figures/game_data/{outcome_summary.json, difficulty_tuning.json},
copied from the GODMODE prototype's headless batch harnesses
(scripts/outcome_batch.py, scripts/tune_difficulty.py in the game repository).

Run from the repo root:
    python3 Paper/figures/make_game_figure.py
"""
from __future__ import annotations

import json
import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "game_data")

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["DejaVu Serif"],
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": "#e6e6e6",
    "grid.linewidth": 0.8,
    "axes.axisbelow": True,
    "legend.frameon": False,
    "legend.fontsize": 8.5,
    "figure.dpi": 150,
})

CAUSE_ORDER = ["win", "temp", "economic", "geopolitics", "avg_stability", "energy_price",
               "planet_health", "food_price"]
CAUSE_LABEL = {
    "win": "survived to 2050",
    "temp": "climate (temperature)",
    "economic": "economic strain",
    "geopolitics": "geopolitical strain",
    "avg_stability": "social stability",
    "energy_price": "energy price",
    "planet_health": "biosphere",
    "food_price": "food price",
}
CAUSE_COLOR = {
    "win": "#2166ac",
    "temp": "#b2182b",
    "economic": "#e08214",
    "geopolitics": "#762a83",
    "avg_stability": "#9aa0a6",
    "energy_price": "#5aae61",
    "planet_health": "#1b7837",
    "food_price": "#c51b7d",
}
# production leaderboard uses its own cause keys
PROD_KEY = {"temp": "temp", "economic": "economic_strain", "geopolitics": "geopolitical_strain",
            "avg_stability": "avg_stability", "energy_price": "energy_price",
            "planet_health": "planet_health", "food_price": "food_price"}


def main() -> int:
    with open(os.path.join(DATA, "outcome_summary.json")) as fh:
        summ = json.load(fh)
    with open(os.path.join(DATA, "prod_telemetry_summary.json")) as fh:
        prod = json.load(fh)

    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.4))

    # (a) outcome composition per scripted archetype
    ax = axes[0]
    pols = ["green", "growth", "random", "humans"]
    pol_label = {"green": "green bot\n(decarbonise)", "growth": "growth bot\n(output first)",
                 "random": "mixed bot\n(random)", "humans": "humans\n(production)"}
    y = np.arange(len(pols))
    left = np.zeros(len(pols))
    for cause in CAUSE_ORDER:
        vals = []
        for p in pols:
            if p == "humans":
                n = prod["n"]
                if cause == "win":
                    vals.append(100.0 * prod["wins"] / n)
                else:
                    vals.append(100.0 * prod["loss_reasons"].get(PROD_KEY[cause], 0) / n)
            else:
                block = summ[p]
                n = block["runs"]
                if cause == "win":
                    vals.append(block["win_pct"])
                else:
                    vals.append(100.0 * block["loss_reasons"].get(cause, 0) / n)
        vals = np.array(vals)
        ax.barh(y, vals, left=left, height=0.62, color=CAUSE_COLOR[cause],
                label=CAUSE_LABEL[cause])
        left += vals
    ax.set_yticks(y, [pol_label[p] for p in pols])
    ax.set_xlabel("share of runs, %")
    ax.set_xlim(0, 100)
    ax.set_title(f"(a) Outcomes: {summ['all']['runs']} bot runs + {prod['n']} human runs")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncols=4, fontsize=7.0,
              columnspacing=0.8, handlelength=1.1)
    ax.invert_yaxis()

    # (b) loss-year histogram, all runs
    ax = axes[1]
    hist = summ["all"]["loss_year_hist"]
    years = sorted(hist, key=int)
    n_loss = sum(hist.values())
    vals = [100.0 * hist[yr] / n_loss for yr in years]
    ph = prod["loss_year_hist"]
    n_ploss = sum(ph.values())
    # both histograms use floor bins: 5*(final_year//5) -> direct alignment
    pvals = [100.0 * ph.get(str(yr), 0) / n_ploss for yr in years]
    x = np.arange(len(years))
    ax.bar(x - 0.19, vals, width=0.36, color="#b2182b", label="scripted bots")
    ax.bar(x + 0.19, pvals, width=0.36, color="#9aa0a6", label="humans (production)")
    ax.set_xticks(x, [f"{yr}\u2013{int(yr)%100+4}" if int(yr) < 2050 else "2050" for yr in years], fontsize=8.5)
    ax.set_ylabel("share of losses, %")
    ax.set_title("(b) When losing runs fail")
    ax.legend(loc="upper left", fontsize=7.5)
    for i, v in enumerate(vals):
        ax.text(i - 0.19, v + 0.8, f"{v:.0f}", ha="center", fontsize=7, color="#1a1a1a")
    for i, v in enumerate(pvals):
        ax.text(i + 0.19, v + 0.8, f"{v:.0f}", ha="center", fontsize=7, color="#5f6368")

    fig.tight_layout()
    for ext in ("pdf", "png"):
        out = os.path.join(HERE, f"fig10_game_outcomes.{ext}")
        fig.savefig(out, bbox_inches="tight")
    print("wrote fig10_game_outcomes.pdf / .png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
