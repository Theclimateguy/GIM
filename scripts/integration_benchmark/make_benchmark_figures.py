#!/usr/bin/env python3
"""Integration-benchmark figures (reproducible, committed). House style matches
paper/figures/make_figures.py.

Reads:  results/integration_benchmark/latest.json
Writes: paper/figures/fig6_integration_carbon, fig7_integration_oil,
        fig8_integration_crop, fig9_integration_summary  (each .pdf + .png)

Run:    python3 -m scripts.integration_benchmark.make_benchmark_figures
"""
from __future__ import annotations

import json
import os
import textwrap

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIGDIR = os.path.join(REPO, "paper", "figures")
DATA = os.path.join(REPO, "results", "integration_benchmark", "latest.json")

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
INK = "#1a1a1a"
GIM = "#2166ac"        # GIM / integrated (blue)
SECT = "#b2182b"       # sectoral model (red)
MUTED = "#9aa0a6"
SOCIAL = "#762a83"     # social-block highlight (purple)
GOOD = "#2e7d32"       # first-order effect GIM shares with the sectoral model


def _finish(fig, name, suptitle, caption, top=0.90, bottom=0.27, width=150):
    """Lay out, add a wrapped figure caption + suptitle, save (no tight bbox -- the bbox
    would otherwise expand to fit the wide caption and squash the axes). '$' is escaped
    so it renders literally instead of opening a mathtext span."""
    esc = lambda t: t.replace("$", r"\$")
    fig.tight_layout(rect=(0.0, bottom, 1.0, top))
    fig.suptitle(esc(suptitle), fontsize=11.5, color=INK, y=0.975)
    fig.text(0.5, bottom * 0.42, esc(textwrap.fill(caption, width=width)),
             ha="center", va="center", fontsize=7.8, style="italic", color=INK,
             bbox=dict(boxstyle="round,pad=0.55", fc="#f5f5f2", ec="#d9d9d4", lw=0.8))
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(FIGDIR, f"{name}.{ext}"))
    plt.close(fig)
    print(f"  wrote {name}.pdf / .png")


def _time_axis(ax, n):
    ax.set_xlim(0, n - 1)
    ax.set_xticks(range(0, n, 2))


def _get(scn, sid):
    return [s for s in scn if s["id"] == sid][0]


# ----------------------------------------------------------------------------------
def fig_carbon(sc):
    s = sc["series"]; sw = sc["sweep"]; h = sc["headline"]
    yrs = np.arange(len(s["emissions_base"]))
    fig, ax = plt.subplots(1, 3, figsize=(11.2, 3.7))

    # P1 -- what DICE models: emissions fall (GIM agrees)
    ax[0].plot(yrs, s["emissions_base"], color=MUTED, lw=2, label="no policy")
    ax[0].plot(yrs, s["emissions_shock"], color=GOOD, lw=2.4, label="carbon $50/t")
    ax[0].fill_between(yrs, s["emissions_shock"], s["emissions_base"],
                       color=GOOD, alpha=0.12)
    ax[0].set_title("What DICE models — and GIM reproduces", color=INK)
    ax[0].set_xlabel("year"); ax[0].set_ylabel("global emissions")
    ax[0].legend(loc="lower left")
    _time_axis(ax[0], len(yrs))
    ax[0].text(0.96, 0.92, f"−{h['emissions_cut_pct_10y']:.1f}% @10y",
               transform=ax[0].transAxes, ha="right", va="top", color=GOOD, fontsize=9.5)

    # P2 -- what DICE cannot see: tension up, trust down
    ax2 = ax[1]
    ax2.plot(yrs, s["tension_base"], color=MUTED, lw=2, label="tension (no policy)")
    ax2.plot(yrs, s["tension_shock"], color=SOCIAL, lw=2.4, label="tension (carbon $50/t)")
    ax2.fill_between(yrs, s["tension_base"], s["tension_shock"],
                     color=SOCIAL, alpha=0.15)
    ax2.set_title("What DICE structurally cannot see", color=INK)
    ax2.set_xlabel("year"); ax2.set_ylabel("social tension")
    ax2.legend(loc="upper left")
    _time_axis(ax2, len(yrs))
    ax2.text(0.96, 0.08,
             f"@10y:  tension +{h['tension_delta_10y']*1000:.1f}×10⁻³\n"
             f"          trust {h['trust_delta_10y']*1000:.1f}×10⁻³",
             transform=ax2.transAxes, ha="right", va="bottom", color=SOCIAL, fontsize=8)

    # P3 -- dose-response: carbon -> tension; DICE slope = 0
    ax3 = ax[2]
    ax3.axhline(0, color=SECT, lw=2.0, ls="--", label="DICE (no society block): 0")
    ax3.plot(sw["carbon"], sw["tension_delta"], color=GIM, lw=2.4,
             marker="o", ms=4, label="GIM: tension response")
    ax3.scatter([50], [h["tension_delta_10y"]], color=SOCIAL, zorder=5, s=42)
    ax3.set_title("Dose–response: a channel DICE lacks", color=INK)
    ax3.set_xlabel("carbon price ($/tCO2)"); ax3.set_ylabel("terminal tension delta")
    ax3.legend(loc="upper left")

    _finish(fig, "fig6_integration_carbon",
            "Scenario A — Carbon tax $50/tCO2:  GIM agrees on emissions, adds the political-economy cost",
            "Anchor: Nordhaus, DICE-2016R (PNAS 2017) — optimal carbon price welfare-optimal, emissions "
            "decline; no unemployment / inflation / politics.  Real reversals: France 2018 (gilets jaunes), "
            "Australia 2014.  GIM adds the economy→society→policy path that determines whether the tax survives.")


# ----------------------------------------------------------------------------------
def fig_oil(sc):
    s = sc["series"]; sw = sc["sweep"]; h = sc["headline"]
    yrs = np.arange(len(s["dca_base"]))
    fig, ax = plt.subplots(1, 2, figsize=(8.4, 3.8))

    # P1 -- importer debt-crisis years: severe shock above baseline
    ax[0].plot(yrs, s["dca_base"], color=MUTED, lw=2, label="no oil shock")
    ax[0].plot(yrs, s["dca_shock"], color=GIM, lw=2.4, label="severe oil shock (~15% GDP bill)")
    ax[0].fill_between(yrs, s["dca_base"], s["dca_shock"], color=GIM, alpha=0.14)
    ax[0].set_title("Sovereign-debt cascade in importers", color=INK)
    ax[0].set_xlabel("year"); ax[0].set_ylabel("mean debt-crisis years (importers)")
    ax[0].legend(loc="upper left")
    _time_axis(ax[0], len(yrs))

    # P2 -- dose-response: burden -> extra importers in crisis; energy model = 0.
    # Mark BOTH the realistic (-20% supply ~3% GDP, marginal) and severe (~15%, headline) points.
    ax2 = ax[1]
    x = [b * 100 for b in sw["burden_gdp"]]
    ax2.axhline(0, color=SECT, lw=2.0, ls="--", label="energy model (no finance block): 0")
    ax2.plot(x, sw["extra_in_crisis"], color=GIM, lw=2.4, marker="o", ms=4,
             label="GIM: extra importers in crisis")
    ax2.axvline(3.3, color=MUTED, lw=1.1, ls=":", alpha=0.9)
    ax2.annotate("realistic\n−20% supply\n(~3% GDP)", xy=(3.3, 0.0), xytext=(0.5, 2.6),
                 fontsize=7.2, color="#5F5E5A",
                 arrowprops=dict(arrowstyle="->", color=MUTED, lw=0.8))
    ax2.axvline(15, color=SOCIAL, lw=1.3, ls=":", alpha=0.9)
    ax2.annotate("severe\n(~15% GDP)", xy=(15, 3.0), xytext=(8.5, 3.6),
                 fontsize=7.6, color=SOCIAL,
                 arrowprops=dict(arrowstyle="->", color=SOCIAL, lw=0.9))
    ax2.set_title("Dose–response: threshold-shaped cascade", color=INK)
    ax2.set_xlabel("oil-import burden (% of GDP / yr)")
    ax2.set_ylabel("extra importers in sovereign crisis")
    ax2.legend(loc="upper left")

    _finish(fig, "fig7_integration_oil",
            "Scenario B — Oil price shock:  an energy model sees price; GIM sees the sovereign-debt cascade",
            "Anchor: IMF GFSR Oct-2025 ch.3; BU GDP Center 2026.  Energy-system models (MESSAGEix) stop at "
            "price / demand adjustment — no sovereign-finance block.  Real case: Sri Lanka 2022 ($1.9B reserves "
            "vs $6B debt service → default).  The cascade is threshold-shaped; the energy model is flat-zero everywhere.",
            width=108)


# ----------------------------------------------------------------------------------
def fig_crop(sc):
    s = sc["series"]; sw = sc["sweep"]; h = sc["headline"]
    yrs = np.arange(len(s["food_base"]))
    fig, ax = plt.subplots(1, 2, figsize=(8.4, 3.8))

    # P1 -- food affordability + protest, base vs shock (vulnerable subset)
    ax[0].plot(yrs, s["food_base"], color=MUTED, lw=2, label="food stress (no shock)")
    ax[0].plot(yrs, s["food_shock"], color=GOOD, lw=2.4, label="food stress (yield -50%)")
    ax[0].plot(yrs, s["protest_base"], color=MUTED, lw=1.4, ls="--", alpha=0.8)
    ax[0].plot(yrs, s["protest_shock"], color=SOCIAL, lw=2.0, ls="--",
               label="protest pressure (yield -50%)")
    ax[0].fill_between(yrs, s["food_base"], s["food_shock"], color=GOOD, alpha=0.12)
    ax[0].set_title("Food stress (AgMIP) → protest (GIM)", color=INK)
    ax[0].set_xlabel("year"); ax[0].set_ylabel("metric level (vulnerable subset)")
    ax[0].legend(loc="center right", fontsize=7.6)
    _time_axis(ax[0], len(yrs))

    # P2 -- dose-response: yield cut -> food/protest; convex; AgMIP protest slope = 0
    ax2 = ax[1]
    x = [c * 100 for c in sw["yield_cut"]]
    ax2.axhline(0, color=SECT, lw=2.0, ls="--", label="AgMIP (no politics): protest 0")
    ax2.plot(x, sw["food_delta"], color=GOOD, lw=2.2, marker="o", ms=4,
             label="GIM: food-stress delta")
    ax2.plot(x, sw["protest_delta"], color=SOCIAL, lw=2.4, marker="s", ms=4,
             label="GIM: protest delta")
    ax2.axvline(50, color=SOCIAL, lw=1.2, ls=":", alpha=0.8)
    ax2.annotate("severe (−50%)", xy=(50, 0.09), xytext=(26, 0.15),
                 fontsize=7.6, color=SOCIAL,
                 arrowprops=dict(arrowstyle="->", color=SOCIAL, lw=0.9))
    ax2.set_title("Dose–response: convex escalation", color=INK)
    ax2.set_xlabel("vulnerable-region yield loss (%)")
    ax2.set_ylabel("terminal delta")
    ax2.legend(loc="upper left", fontsize=7.6)

    _finish(fig, "fig8_integration_crop",
            "Scenario C — severe crop yield shock:  AgMIP stops at hunger; GIM carries it to protest pressure",
            "Anchor: AgMIP / IPCC AR6 (yield→hunger endpoint).  Lagi, Bertrand & Bar-Yam 2011 "
            "(arXiv:1108.2455): food riots above FAO index 210 (p<1e-7), coinciding with the Arab Spring 2011.  "
            "GIM adds food→affordability→protest in vulnerable importers, with convex (accelerating) escalation.",
            width=108)


# ----------------------------------------------------------------------------------
def fig_summary(scn):
    """Thesis figure: three cross-sector channels. GIM has a positive, quantified slope;
    every sectoral model is structurally flat-zero on its cross-sector axis."""
    A = _get(scn, "A_carbon_tax"); B = _get(scn, "B_oil_shock"); C = _get(scn, "C_crop_shock")
    fig, ax = plt.subplots(1, 3, figsize=(11.2, 3.9))

    def norm(v):
        v = np.array(v, float); m = np.max(np.abs(v))
        return v / m if m > 0 else v

    # A
    ax[0].axhline(0, color=SECT, lw=2.0, ls="--")
    ax[0].plot(norm(A["sweep"]["carbon"]), norm(A["sweep"]["tension_delta"]),
               color=GIM, lw=2.6, marker="o", ms=4)
    ax[0].set_title("A · economy → society", color=INK)
    ax[0].set_xlabel("carbon price (normalized)")
    ax[0].set_ylabel("cross-sector response (normalized)")
    ax[0].text(0.04, 0.90, "GIM: social tension", color=GIM, fontsize=8.5, transform=ax[0].transAxes)
    ax[0].text(0.04, 0.06, "DICE: zero", color=SECT, fontsize=8.5, transform=ax[0].transAxes)

    # B
    ax[1].axhline(0, color=SECT, lw=2.0, ls="--")
    ax[1].plot(norm(B["sweep"]["burden_gdp"]), norm(B["sweep"]["dca_delta"]),
               color=GIM, lw=2.6, marker="o", ms=4)
    ax[1].set_title("B · resources → finance", color=INK)
    ax[1].set_xlabel("oil-import burden (normalized)")
    ax[1].text(0.04, 0.90, "GIM: sovereign crises", color=GIM, fontsize=8.5, transform=ax[1].transAxes)
    ax[1].text(0.04, 0.06, "MESSAGEix: zero", color=SECT, fontsize=8.5, transform=ax[1].transAxes)

    # C
    ax[2].axhline(0, color=SECT, lw=2.0, ls="--")
    ax[2].plot(norm(C["sweep"]["yield_cut"]), norm(C["sweep"]["protest_delta"]),
               color=GIM, lw=2.6, marker="o", ms=4)
    ax[2].set_title("C · climate/food → society", color=INK)
    ax[2].set_xlabel("yield loss (normalized)")
    ax[2].text(0.04, 0.90, "GIM: protest pressure", color=GIM, fontsize=8.5, transform=ax[2].transAxes)
    ax[2].text(0.04, 0.06, "AgMIP: zero", color=SECT, fontsize=8.5, transform=ax[2].transAxes)

    for a in ax:
        a.set_ylim(-0.12, 1.08)
        a.set_xlim(-0.02, 1.05)

    ha = A["headline"]; hb = B["headline"]; hc = C["headline"]
    cap = (f"Each curve is one cross-sector channel, normalized to its own peak; the dashed red line is "
           f"every sectoral model's structural zero on that axis.  Headline effects (10y): "
           f"A carbon $50/t → emissions −{ha['emissions_cut_pct_10y']:.1f}%, tension +{ha['tension_delta_10y']*1e3:.1f}×10⁻³;  "
           f"B severe oil shock (~15% GDP) → +{hb['extra_importers_in_crisis_peak']:.0f} importers in sovereign crisis, debt-crisis-years ×{hb['dca_ratio_peak']:.1f};  "
           f"C severe yield −50% → food-stress +{hc['food_delta_10y']:.3f}, protest +{hc['protest_delta_10y']:.3f}.  "
           f"Shapes differ honestly: B threshold-stepped, C convex, A weak-but-robust.")
    _finish(fig, "fig9_integration_summary",
            "The integration dividend — three cross-sector channels with a non-zero GIM slope where sectoral models are flat",
            cap, bottom=0.30, width=158)


def main():
    with open(DATA) as fh:
        data = json.load(fh)
    scn = data["scenarios"]
    print("rendering integration-benchmark figures:")
    fig_carbon(_get(scn, "A_carbon_tax"))
    fig_oil(_get(scn, "B_oil_shock"))
    fig_crop(_get(scn, "C_crop_shock"))
    fig_summary(scn)


if __name__ == "__main__":
    main()
