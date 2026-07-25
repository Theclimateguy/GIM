#!/usr/bin/env python3
"""fig11: 30-year ensemble fans + fan-width growth (convergence evidence).

Reads the latest 30-year results/ensemble-*/ensemble.json (years=30, n=500).
Run from repo root: python3 Paper/figures/make_ensemble30_figure.py
"""
from __future__ import annotations

import glob
import json
import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["DejaVu Serif"], "font.size": 10,
    "axes.titlesize": 11, "axes.labelsize": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.8,
    "axes.axisbelow": True, "legend.frameon": False, "legend.fontsize": 8.5,
    "figure.dpi": 150,
})
ACCENT, ACCENT2, INK = "#2166ac", "#b2182b", "#1a1a1a"


def latest_30y():
    for path in sorted(glob.glob(os.path.join(REPO, "results", "ensemble-*", "ensemble.json")), reverse=True):
        d = json.load(open(path))
        if d.get("config", {}).get("years") == 30 and d.get("n_members", 0) >= 500:
            return d, path
    raise SystemExit("no 30-year ensemble found")


def main() -> int:
    d, path = latest_30y()
    print("using", path)
    m = d["metrics"]
    yrs = np.arange(0, 31)

    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.2))

    for ax, var, color, ylab, title in (
        (axes[0], "world_gdp", ACCENT, "trillion USD", "(a) World product, 30-year fan"),
        (axes[1], "temperature", ACCENT2, "$^\\circ$C above pre-ind.", "(b) Temperature anomaly"),
    ):
        v = m[var]
        ax.fill_between(yrs, v["p5"], v["p95"], color=color, alpha=0.15, label="5–95th")
        ax.fill_between(yrs, v["p25"], v["p75"], color=color, alpha=0.30, label="25–75th")
        ax.plot(yrs, v["p50"], color=color, lw=1.8, label="median")
        ax.set_xlabel("projection year")
        ax.set_ylabel(ylab)
        ax.set_title(title)
        ax.legend(loc="upper left")

    ax = axes[2]
    g = m["world_gdp"]
    hw = [(g["p95"][h] - g["p5"][h]) / 2.0 / g["p50"][h] * 100 for h in yrs]
    ax.plot(yrs, hw, color=INK, lw=1.8, label="5–95th half-width, % of median")
    ref = hw[10] * (yrs / 10.0)  # linear reference through the 10-year point
    ax.plot(yrs[1:], ref[1:], color="#9aa0a6", lw=1.2, ls="--", label="linear growth reference")
    ax.set_xlabel("projection year")
    ax.set_ylabel("relative fan half-width, %")
    ax.set_title("(c) Fan growth: near-linear, not exponential")
    ax.legend(loc="upper left")

    fig.tight_layout()
    for ext in ("pdf", "png"):
        out = os.path.join(HERE, f"fig11_ensemble30.{ext}")
        fig.savefig(out, bbox_inches="tight")
    print("wrote fig11_ensemble30.pdf / .png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
