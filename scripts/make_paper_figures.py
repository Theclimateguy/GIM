#!/usr/bin/env python3
"""Regenerate the paper's figures from committed model output.

Before this script only the three integration-benchmark figures had a generator; the rest
were produced outside the repository, which meant a reader could not reproduce them and a
model change could not propagate into them. Several had gone stale: fig12 still showed the
pre-repair spectral radius, and fig5 showed a social-channel result that reverses on the
repaired model.

Each figure reads a committed artefact rather than re-running the model, so the numbers in
the paper, the JSON results and the plots cannot drift apart:

  fig12_stability          results/calibration/stability_analysis.json
                           (scripts/run_stability_analysis.py)
  fig5_social_channel      Paper/revision/results/e5_social_channel_level_vs_response.json
                           (Paper/revision/scripts/e5_...py)
  fig1_architecture        drawn here; the model's channel map, kept in sync by hand
  fig9_integration_summary results/integration_benchmark/<latest>/benchmark.json

Usage:  python3 scripts/make_paper_figures.py [--only fig12,fig5]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

REPO = Path(__file__).resolve().parent.parent
FIGS = REPO / "Paper" / "figures"

plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
    "legend.fontsize": 7, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.4,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 200, "savefig.bbox": "tight", "pdf.fonttype": 42,
})
PURPLE, BLUE, RED, GREY = "#7B3FA0", "#1f6fb4", "#b42121", "#666666"


def _save(fig, name):
    FIGS.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(FIGS / f"{name}.{ext}")
    plt.close(fig)
    print(f"  wrote Paper/figures/{name}.pdf")


# ----------------------------------------------------------------- fig12: stability
def fig12_stability():
    src = REPO / "results" / "calibration" / "stability_analysis.json"
    d = json.loads(src.read_text())
    spec = d["spectral_radius"]
    years = sorted(spec, key=int)

    fig, ax = plt.subplots(1, 2, figsize=(7.0, 2.9))
    th = np.linspace(0, 2 * np.pi, 400)
    ax[0].plot(np.cos(th), np.sin(th), ls="--", lw=0.8, color=GREY, label="unit circle")
    colors = [BLUE, PURPLE, RED]
    for c, y in zip(colors, years):
        e = np.array(spec[y]["eigs_re_im"])
        ax[0].scatter(e[:, 0], e[:, 1], s=5, alpha=0.55, color=c,
                      label=rf"{y} ($\rho$={spec[y]['rho']:.3f})")
    n_above = [spec[y]["n_eigs_above_1"] for y in years]
    ax[0].text(-1.22, 1.22, f"{min(n_above)}–{max(n_above)} modes above unity; their mass\n"
               "sits on debt, unemployment and inflation\n"
               "— the climate subspace carries none",
               fontsize=6.0, ha="left", va="top", linespacing=1.35)
    ax[0].set_ylim(-1.32, 1.55)
    ax[0].set_xlabel(r"Re $\lambda$"); ax[0].set_ylabel(r"Im $\lambda$")
    ax[0].set_title("(a) Spectrum of the one-year map")
    ax[0].set_aspect("equal"); ax[0].legend(loc="lower left", framealpha=0.9)
    ax[0].set_xlim(-1.30, 1.30)

    tw = d["twin_runs"]
    lbl = {"gdp_usa_+0.1pct": ("USA output +0.1%", BLUE),
           "temperature_+0.01C": (r"temperature +0.01 $^\circ$C", RED),
           "tension_all_+0.01": ("social tension +0.01 (all)", PURPLE)}
    for k, (name, c) in lbl.items():
        if k not in tw:
            continue
        s = np.array(tw[k]["series_rel_gdp_gap"])
        ax[1].plot(np.arange(1, s.size + 1), np.maximum(s, 1e-12), color=c, lw=1.3, label=name)
    ax[1].set_yscale("log")
    ax[1].set_xlabel("years after perturbation")
    ax[1].set_ylabel("relative world-product gap")
    ax[1].set_title("(b) Perturbations: contraction vs. slow social memory")
    ax[1].legend(loc="lower right", framealpha=0.9)
    _save(fig, "fig12_stability")


# ------------------------------------------------------- fig5: social channel
def fig5_social_channel():
    src = REPO / "Paper" / "revision" / "results" / "e5_social_channel_level_vs_response.json"
    d = json.loads(src.read_text())
    per = d["per_prior"]
    top = sorted(per.items(), key=lambda kv: -abs(kv[1]["rho_vs_final_tension_level"]))[:8]

    fig, ax = plt.subplots(1, 2, figsize=(7.4, 2.9),
                           gridspec_kw={"wspace": 0.42})
    agg = d["aggregate"]
    irf = json.loads((REPO / "results" / "social_channel" / "social_channel.json").read_text())["impulse_response"]
    lag = np.array(irf["lag_years"], dtype=float)
    mean = np.array(irf["mean"], dtype=float)
    p5, p95 = np.array(irf["p5"], dtype=float), np.array(irf["p95"], dtype=float)
    ax[0].axvspan(0, 3, color="#dddddd", alpha=0.65, lw=0)
    ax[0].text(1.5, p95.max() * 0.94, "shock", ha="center", fontsize=6, color="#555555")
    ax[0].fill_between(lag, p5, p95, color=PURPLE, alpha=0.18, lw=0, label="5–95% (priors)")
    ax[0].plot(lag, mean, "o-", color=PURPLE, lw=1.3, ms=2.6, label="mean response")
    ax[0].axhline(0, color="black", lw=0.7)
    ax[0].annotate(f"peak {irf['peak_response']:+.4f}\nat lag {irf['peak_lag']}y",
                   xy=(irf["peak_lag"], irf["peak_response"]),
                   xytext=(irf["peak_lag"] + 6.0, p95.max() * 0.86), fontsize=6,
                   arrowprops=dict(arrowstyle="->", lw=0.7))
    ax[0].set_xlabel("years after shock"); ax[0].set_ylabel(r"$\Delta$ tension")
    ax[0].set_title("(a) Response to a stagflation shock\n(unemployment + inflation, 3 years)")
    ax[0].legend(loc="lower right", framealpha=0.9, fontsize=6.2)

    names = [k for k, _ in top][::-1]
    lev = [per[k]["rho_vs_final_tension_level"] for k in names]
    res = [per[k]["rho_vs_shock_response"] for k in names]
    y = np.arange(len(names))
    ax[1].barh(y + 0.19, lev, height=0.36, color=PURPLE, label="vs. final tension level")
    ax[1].barh(y - 0.19, res, height=0.36, color=BLUE, label="vs. causal shock response")
    social = {"SOCIAL_STRESS_UNEMPLOYMENT_SENS", "SOCIAL_STRESS_INFLATION_SENS",
              "INEQUALITY_EFFECT_SENS", "SOCIAL_TRUST_ANCHOR_SENS"}
    ax[1].set_yticks(y)
    ax[1].set_yticklabels([(k.lower().replace("_", " ") + ("*" if k in social else ""))
                           for k in names], fontsize=6)
    ax[1].axvline(0, color="black", lw=0.7)
    ax[1].set_xlabel(r"rank correlation (Spearman)")
    ax[1].set_title("(b) What governs tension\n(* — social-block priors)")
    ax[1].legend(loc="lower right", framealpha=0.9, fontsize=6.5)
    _save(fig, "fig5_social_channel")


# ------------------------------------------------ fig9: integration transfer functions
def fig9_integration_summary():
    """Three cross-sector transfer functions, each in its own units.

    Earlier versions normalised all three to their own maximum, which was needed only for the
    withdrawn 'integration dividend' framing (everything on one axis, against a flat zero).
    Read as transfer functions the magnitudes matter, so each panel keeps its own units and
    carries the fitted shape.
    """
    paths = sorted(glob.glob(str(REPO / "results" / "integration_benchmark" / "*" / "benchmark.json")))
    scen = {s["id"]: s for s in json.loads(Path(paths[-1]).read_text())["scenarios"]}

    def exponent(x, y):
        pts = [(u, v) for u, v in zip(x, y) if u > 0 and v > 0]
        if len(pts) < 3:
            return None
        lx = np.log([u for u, _ in pts]); ly = np.log([v for _, v in pts])
        return float(np.polyfit(lx, ly, 1)[0])

    fig, ax = plt.subplots(1, 3, figsize=(7.4, 2.6), gridspec_kw={"wspace": 0.40})

    a = scen["A_carbon_tax"]["sweep"]
    x, v = np.array(a["carbon"]), np.array(a["tension_delta"])
    ax[0].plot(x, v, "o-", color=PURPLE, lw=1.4, ms=4, mec="white", mew=0.6)
    ax[0].set_xlabel("carbon price (USD/tCO$_2$)")
    ax[0].set_ylabel(r"$\Delta$ social tension, 10 y")
    ax[0].set_title("(a) economy $\\to$ society", fontsize=8.5)
    e = exponent(x, v)
    ax[0].text(0.04, 0.93, f"power law, exponent {e:.2f}", transform=ax[0].transAxes,
               fontsize=6.3, va="top")

    b = scen["B_oil_shock"]["sweep"]
    x, v = np.array(b["burden_gdp"]) * 100, np.array(b["extra_in_crisis"])
    ax[1].step(x, v, where="post", color=RED, lw=1.3, alpha=0.85)
    ax[1].plot(x, v, "o", color=RED, ms=4, mec="white", mew=0.6, zorder=3)
    ax[1].set_xlabel(r"oil-import burden (% of GDP/yr)")
    ax[1].set_ylabel("additional importers in\nsovereign debt crisis")
    ax[1].set_title("(b) resources $\\to$ finance", fontsize=8.5)
    ax[1].set_yticks(range(0, int(v.max()) + 2, 4))
    ax[1].text(0.04, 0.93, f"threshold-stepped,\n{len(set(v))} distinct levels",
               transform=ax[1].transAxes, fontsize=6.3, va="top")

    c = scen["C_crop_shock"]["sweep"]
    x = np.array(c["yield_cut"]) * 100
    ax[2].plot(x, np.array(c["food_delta"]), "s--", color="#8a8a8a", lw=1.0, ms=3,
               mec="white", mew=0.5, label="food affordability")
    ax[2].plot(x, np.array(c["protest_delta"]), "o-", color="#1a7f4f", lw=1.4, ms=4,
               mec="white", mew=0.6, label="protest pressure")
    ax[2].set_xlabel(r"regional yield loss (%)")
    ax[2].set_ylabel(r"$\Delta$ index, 10 y")
    ax[2].set_title("(c) climate $\\to$ society", fontsize=8.5)
    ax[2].legend(loc="upper left", framealpha=0.9, fontsize=6.0)
    e2 = exponent(x, np.array(c["protest_delta"]))
    ax[2].text(0.04, 0.72, f"power law, exponent {e2:.2f}", transform=ax[2].transAxes,
               fontsize=6.3, va="top")

    for a_ in ax:
        a_.margins(x=0.06, y=0.14)
    _save(fig, "fig9_integration_summary")


# ------------------------------------------------------ fig1: architecture
def fig1_architecture():
    """The closed loop on a clean radial layout.

    Economy at the hub, the physical blocks above it and the human blocks below. Each arrow
    runs between box borders rather than centres, and its label is offset perpendicular to
    the arrow, so labels cannot land on top of one another or on a box.
    """
    fig, ax = plt.subplots(figsize=(7.2, 4.7))
    ax.set_xlim(0, 12); ax.set_ylim(0, 7.7); ax.axis("off")

    FILL = {"climate": "#f4dde1", "resource": "#f6f0cf", "economy": "#cddff3",
            "human": "#f6e3d0", "crisis": "#d8ecdd"}
    nodes = {}

    def box(key, x, y, w, h, title, sub, kind):
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                    boxstyle="round,pad=0.10,rounding_size=0.10",
                                    fc=FILL[kind], ec="#4a4a4a", lw=0.9, zorder=3))
        ax.text(x, y + (0.17 if sub else 0.0), title, ha="center", va="center",
                fontsize=8.0, weight="bold", zorder=4)
        if sub:
            ax.text(x, y - 0.21, sub, ha="center", va="center", fontsize=6.3,
                    color="#3a3a3a", linespacing=1.25, zorder=4)
        nodes[key] = (x, y, w, h)

    def edge(a, b, label, color="#333333", rad=0.0, side=1.0, off=0.30, fs=6.1, t=0.5):
        (axc, ayc, aw, ah), (bxc, byc, bw, bh) = nodes[a], nodes[b]
        dx, dy = bxc - axc, byc - ayc
        L = max((dx * dx + dy * dy) ** 0.5, 1e-9)
        ux, uy = dx / L, dy / L
        sa = min(aw / 2 / max(abs(ux), 1e-6), ah / 2 / max(abs(uy), 1e-6)) + 0.14
        sb = min(bw / 2 / max(abs(ux), 1e-6), bh / 2 / max(abs(uy), 1e-6)) + 0.14
        p0 = (axc + ux * sa, ayc + uy * sa)
        p1 = (bxc - ux * sb, byc - uy * sb)
        ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=9,
                                     lw=1.0, color=color, zorder=2,
                                     connectionstyle="arc3,rad=%s" % rad))
        # label anchored at fraction t along the chord, then pushed off the bow and
        # perpendicular to it -- t lets two arrows sharing a region separate their labels
        bow = 4.0 * t * (1.0 - t)              # 1 at the midpoint, 0 at the ends
        mx = p0[0] + (p1[0] - p0[0]) * t - uy * rad * L * 0.5 * bow
        my = p0[1] + (p1[1] - p0[1]) * t + ux * rad * L * 0.5 * bow
        ax.text(mx - uy * off * side, my + ux * off * side, label, ha="center", va="center",
                fontsize=fs, color=color, linespacing=1.2, zorder=5,
                bbox=dict(fc="white", ec="none", alpha=0.92, pad=0.9))

    box("climate", 6.0, 6.60, 2.9, 1.00, "Climate and carbon", "temperature, carbon pools", "climate")
    box("carbon",  1.9, 5.20, 2.3, 0.85, r"Carbon price", "", "climate")
    box("damage", 10.1, 5.20, 2.3, 0.85, r"Damage $\Omega(T)$", "", "climate")
    box("res",     1.9, 3.20, 2.6, 1.00, "Resources", "energy, food, metals", "resource")
    box("econ",    6.0, 3.20, 3.0, 1.10, "Economy", "output, capital, prices,\nemployment", "economy")
    box("geo",    10.1, 3.20, 2.6, 1.00, "Geopolitics", "trade, sanctions,\nconflict", "human")
    box("crisis",  3.4, 1.15, 2.9, 1.05, "Crises and finance", "debt, currency, regime", "crisis")
    box("soc",     8.6, 1.15, 2.9, 1.05, "Society and politics", "trust, tension,\ninequality", "human")

    edge("econ", "climate", "emissions", side=-1.0)
    edge("climate", "damage", r"warming $T$", color="#8a8a8a", rad=-0.18, side=-1.0)
    edge("damage", "econ", "output loss", color=RED, rad=-0.16, side=-1.0)
    edge("carbon", "econ", "energy\nsubstitution", color=RED, rad=0.14, side=1.0,
         off=0.32, t=0.68)
    edge("climate", "res", "yield loss\nper $^\\circ$C", color=RED, rad=0.30, side=-1.0,
         off=0.34, fs=5.9, t=0.74)
    edge("res", "econ", "prices, demand", side=1.0)
    edge("econ", "geo", "trade, sanctions", side=1.0)
    edge("econ", "crisis", "thresholds,\nshocks", rad=0.12, side=1.0)
    edge("econ", "soc", "inflation,\nunemployment", rad=-0.10, side=-1.0, off=0.36)
    edge("soc", "econ", "savings, risk", color=RED, rad=-0.34, side=1.0, off=0.44)
    edge("res", "crisis", "trade balance,\nreserves", color=RED, rad=0.14, side=-1.0, fs=5.9)
    edge("crisis", "soc", r"crisis $\to$ tension", color="#8a8a8a", side=-1.0)

    ax.add_patch(FancyBboxPatch((0.45, 0.02), 11.1, 0.42,
                                boxstyle="round,pad=0.06,rounding_size=0.08",
                                fc="#efefef", ec="#666666", lw=0.8, ls="--", zorder=1))
    ax.text(6.0, 0.23, "Weak signals: joint-state monitoring "
                       "(Mahalanobis distance, change-point, critical slowing down)",
            ha="center", va="center", fontsize=6.8, zorder=2)
    _save(fig, "fig1_architecture")


# ------------------------------------------------------ fig2: retrospective anchor
def fig2_validation():
    """(a) in-sample errors incl. the resource prices that are newly scored;
    (b) the conflict ROC against the benchmark that matters -- its best single covariate."""
    sys.path.insert(0, str(REPO))
    from gim.calibration_hm import PRICE_TOLERANCES
    from gim.historical_backtest import run_historical_backtest

    r = run_historical_backtest(temperature_variability_sigma_override=0.0)
    e8 = json.loads((REPO / "Paper" / "revision" / "results" /
                     "e8_conflict_composite_vs_components.json").read_text())

    fig, ax = plt.subplots(1, 2, figsize=(7.0, 2.9))

    names = ["World\nproduct", "CO$_2$\nemissions", "Temperature",
             "energy\nprice", "food\nprice", "metals\nprice"]
    vals = [r.gdp_rmse_trillions, r.global_co2_rmse_gtco2, r.temperature_rmse_c * 10,
            r.resource_price_rmse["energy"] / PRICE_TOLERANCES["price_energy"],
            r.resource_price_rmse["food"] / PRICE_TOLERANCES["price_food"],
            r.resource_price_rmse["metals"] / PRICE_TOLERANCES["price_metals"]]
    cols = [BLUE] * 3 + ["#1a7f4f"] * 3
    b = ax[0].bar(range(6), vals, color=cols, width=0.62)
    ax[0].bar_label(b, fmt="%.2f", fontsize=6, padding=1.5)
    ax[0].axhline(1.0, color=GREY, ls="--", lw=0.8)
    ax[0].text(5.45, 1.03, "flat-price null", fontsize=5.8, color=GREY, ha="right")
    ax[0].set_xticks(range(6)); ax[0].set_xticklabels(names, fontsize=5.6)
    ax[0].axvline(2.5, color=GREY, lw=0.7, ls=":")
    ax[0].set_ylabel("RMSE, or price error vs. a flat null", fontsize=7)
    ax[0].set_title("(a) Retrospective accuracy, 2015–2023")
    ax[0].tick_params(axis="x", pad=1)
    ax[0].set_ylim(0, max(vals) * 1.30)

    comp, best_key = e8["composite"], e8["best_single_component"]
    best = e8["components"][best_key]
    ax[1].bar([0, 1], [comp["auc"], best["auc"]], color=[BLUE, PURPLE], width=0.5)
    for i, d in enumerate((comp, best)):
        ax[1].errorbar(i, d["auc"], yerr=[[d["auc"] - d["ci95"][0]], [d["ci95"][1] - d["auc"]]],
                       fmt="none", ecolor="black", capsize=3, lw=0.9)
        ax[1].text(i, d["ci95"][1] + 0.02, f"{d['auc']:.3f}", ha="center", fontsize=7)
    ax[1].axhline(0.5, color=GREY, ls="--", lw=0.8)
    ax[1].text(1.45, 0.512, "chance", fontsize=6, color=GREY, ha="right")
    ax[1].set_xticks([0, 1])
    ax[1].set_xticklabels(["composite\nconflict score",
                           "best single covariate\n(1 $-$ regime stability)"], fontsize=6.5)
    ax[1].set_ylim(0.40, 1.10); ax[1].set_ylabel("AUC (95% CI)")
    ax[1].set_title("(b) Conflict ranking against its own best covariate")
    d = best["delta_composite_minus_component"]
    lo, hi = best["delta_ci95"]
    ax[1].text(0.02, 0.97,
               f"paired $\\Delta$ = {d:+.3f}  [{lo:+.3f}, {hi:+.3f}]\n"
               f"P(composite better) = {best['prob_composite_better']:.2f}",
               transform=ax[1].transAxes, ha="left", va="top", fontsize=6.0)
    _save(fig, "fig2_validation")


# ------------------------------------------------ fig11: 30-year parametric ensemble
def fig11_ensemble30():
    runs = sorted(glob.glob(str(REPO / "results" / "ensemble-*" / "ensemble.json")))
    d = None
    for r in reversed(runs):                    # newest run with a 30-year horizon
        cand = json.loads(Path(r).read_text())
        if int(cand["config"]["years"]) >= 30:
            d = cand; break
    if d is None:
        print("  no 30-year ensemble found; run ENS_MEMBERS=500 ENS_YEARS=30 "
              "python3 scripts/run_ensemble.py")
        return
    t = np.arange(len(d["years"]))
    fig, ax = plt.subplots(1, 3, figsize=(7.6, 2.5), gridspec_kw={"wspace": 0.40})

    def fan(a, key, color, ylab, title):
        m = d["metrics"][key]
        a.fill_between(t, m["p5"], m["p95"], color=color, alpha=0.16, lw=0, label="5–95th")
        a.fill_between(t, m["p25"], m["p75"], color=color, alpha=0.32, lw=0, label="25–75th")
        a.plot(t, m["p50"], color=color, lw=1.4, label="median")
        a.set_xlabel("projection year"); a.set_ylabel(ylab); a.set_title(title, fontsize=8)
        a.legend(loc="upper left", framealpha=0.9, fontsize=6)

    fan(ax[0], "world_gdp", BLUE, "trillion USD", "(a) World product, 30-year fan")
    fan(ax[1], "temperature", RED, r"$^\circ$C above pre-ind.", "(b) Temperature anomaly")

    m = d["metrics"]["world_gdp"]
    half = [(hi - lo) / 2.0 / max(md, 1e-9) * 100.0
            for lo, hi, md in zip(m["p5"], m["p95"], m["p50"])]
    ax[2].plot(t, half, color="black", lw=1.3, label="5–95th half-width, % of median")
    ax[2].plot(t, np.linspace(half[0], half[-1], len(t)), ls="--", lw=0.9, color=GREY,
               label="linear growth reference")
    ax[2].set_xlabel("projection year"); ax[2].set_ylabel("relative fan half-width, %")
    ax[2].set_title("(c) Fan growth: near-linear", fontsize=8)
    ax[2].legend(loc="upper left", framealpha=0.9, fontsize=6)
    print(f"  final fan half-width: {half[-1]:.1f}% of median "
          f"(n={d['config']['n_members']}, {d['config']['years']}y)")
    _save(fig, "fig11_ensemble30")


FIGURES = {"fig11": fig11_ensemble30, "fig12": fig12_stability, "fig5": fig5_social_channel,
           "fig9": fig9_integration_summary, "fig1": fig1_architecture,
           "fig2": fig2_validation}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma-separated subset, e.g. fig12,fig5")
    args = ap.parse_args()
    want = [w.strip() for w in args.only.split(",") if w.strip()] or list(FIGURES)
    for w in want:
        if w not in FIGURES:
            print(f"unknown figure {w!r}; known: {', '.join(FIGURES)}")
            return 1
        print(f"{w}:")
        FIGURES[w]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
