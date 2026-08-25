#!/usr/bin/env python3
"""fig12: Jacobian eigenvalue spectrum + twin-run perturbation decay.

Reads results/calibration/stability_analysis.json
(produced by scripts/run_stability_analysis.py).
Run from repo root: python3 Paper/figures/make_stability_figure.py
"""
from __future__ import annotations

import json
import os

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO, "results", "calibration", "stability_analysis.json")

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["DejaVu Serif"], "font.size": 10,
    "axes.titlesize": 11, "axes.labelsize": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.8,
    "axes.axisbelow": True, "legend.frameon": False, "legend.fontsize": 8.5,
    "figure.dpi": 150,
})
INK = "#1a1a1a"
YEAR_COLOR = {"2026": "#2166ac", "2036": "#e08214", "2046": "#b2182b"}


def main() -> int:
    d = json.load(open(SRC))
    spec = d["spectral_radius"]
    twins = d["twin_runs"]

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.6))

    # (a) eigenvalue cloud with unit circle
    ax = axes[0]
    th = np.linspace(0, 2 * np.pi, 400)
    ax.plot(np.cos(th), np.sin(th), color="#9aa0a6", lw=1.0, ls="--",
            label="unit circle", zorder=1)
    for year, s in sorted(spec.items()):
        eig = np.array(s["eigs_re_im"])
        ax.scatter(eig[:, 0], eig[:, 1], s=9, alpha=0.55,
                   color=YEAR_COLOR.get(year, INK), label=f"{year} ($\\rho$={s['rho']:.3f})",
                   linewidths=0, zorder=2)
    ax.set_xlabel("Re $\\lambda$")
    ax.set_ylabel("Im $\\lambda$")
    ax.set_title("(a) Spectrum of the one-year map")
    ax.set_aspect("equal")
    ax.set_xlim(-1.25, 1.25)
    ax.set_ylim(-1.25, 1.25)
    ax.legend(loc="upper left", fontsize=7.5, markerscale=1.6)
    # annotate the growth cluster
    ax.annotate("slow socio-fiscal modes\n(trust, tension, debt)\n$|\\lambda|\\approx1.07$--$1.09$",
                xy=(1.07, 0.05), xytext=(0.16, 0.62), fontsize=7.5, color=INK,
                arrowprops=dict(arrowstyle="->", color=INK, lw=0.8))

    # (b) twin-run divergence: relative world-product gap over time
    ax = axes[1]
    styles = {
        "gdp_usa_+0.1pct": ("USA output $+0.1\\%$", "#2166ac", "-"),
        "temperature_+0.01C": ("temperature $+0.01\\,^{\\circ}$C", "#b2182b", "-"),
        "tension_all_+0.01": ("social tension $+0.01$ (all)", "#762a83", "-"),
    }
    yrs = np.arange(1, 31)
    for key, (label, color, ls) in styles.items():
        series = np.array(twins[key]["series_rel_gdp_gap"])
        series = np.maximum(series, 1e-12)
        ax.semilogy(yrs, series, color=color, ls=ls, lw=1.8, label=label)
    ax.set_xlabel("years after perturbation")
    ax.set_ylabel("relative world-product gap")
    ax.set_title("(b) Perturbations: contraction vs. slow social memory")
    ax.legend(loc="lower right", fontsize=8)

    fig.tight_layout()
    for ext in ("pdf", "png"):
        out = os.path.join(HERE, f"fig12_stability.{ext}")
        fig.savefig(out, bbox_inches="tight")
    print("wrote fig12_stability.pdf / .png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
