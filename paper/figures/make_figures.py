#!/usr/bin/env python3
"""Regenerate the paper figures (fig2-fig5) from result artifacts -- reproducible & committed.

Run from the repo root after the experiments have produced their artifacts:
    python3 paper/figures/make_figures.py
Produces, in paper/figures/: fig2_validation, fig3_sensitivity, fig4_ensemble,
fig5_social_channel -- each as .pdf (for LaTeX) and .png (preview).

Data sources (latest matching artifact is picked automatically):
  fig2  results/calibration/conflict_backtest.json + conflict_auc_inference.json; backtest RMSE
        are the verified headline numbers (docs/CALIBRATION_REFERENCE.md / paper Table 3).
  fig3  results/sensitivity-*/sensitivity.json   (4 metrics, max_agents=57)
  fig4  results/ensemble-*/ensemble.json         (N=500, max_agents=57)
  fig5  results/social_channel/social_channel.json
"""
from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIGDIR = os.path.join(REPO, "paper", "figures")
sys.path.insert(0, REPO)

# ---- consistent, simple house style -------------------------------------------------
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
ACCENT = "#2166ac"      # primary (model / current)
ACCENT2 = "#b2182b"     # contrast (baseline / climate)
MUTED = "#9aa0a6"
SOCIAL = "#762a83"      # social-block highlight


def _save(fig, name):
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(FIGDIR, f"{name}.{ext}"), bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {name}.pdf / .png")


def _latest_sensitivity(metric, agents=100):
    best = None
    for d in glob.glob(os.path.join(REPO, "results", "sensitivity-*")):
        try:
            j = json.load(open(os.path.join(d, "sensitivity.json")))
            m = json.load(open(os.path.join(d, "run_manifest.json")))
        except Exception:
            continue
        if j.get("metric") == metric and m["inputs"].get("max_agents") == agents:
            ts = os.path.basename(d)
            if best is None or ts > best[0]:
                best = (ts, j)
    return best[1] if best else None


def _latest_ensemble(agents=100, n_members=500):
    best = None
    for d in glob.glob(os.path.join(REPO, "results", "ensemble-*")):
        try:
            j = json.load(open(os.path.join(d, "ensemble.json")))
        except Exception:
            continue
        cfg = j.get("config", {})
        if cfg.get("max_agents") == agents and cfg.get("n_members") == n_members:
            ts = os.path.basename(d)
            if best is None or ts > best[0]:
                best = (ts, j)
    return best[1] if best else None


# ---- fig2: validation (backtest skill + conflict ROC with CI & permutation null) ----
def fig2():
    from scripts.conflict_backtest import auc, load_gim_conflict_proneness, load_ucdp_labels
    inf = json.load(open(os.path.join(REPO, "results", "calibration", "conflict_auc_inference.json")))

    # verified headline backtest RMSE (paper Table 3)
    labels = ["Мировой\nпродукт", "Выбросы\nCO$_2$", "Температура"]
    current = [0.59, 1.15, 0.135]
    baseline = [1.03, 1.61, 0.134]

    gim = load_gim_conflict_proneness()
    lab = load_ucdp_labels((1990, 2023))
    names = [n for n in gim if n in lab] + [n for n in gim if n not in lab]
    scores = np.array([gim[n] for n in names]); y = np.array([lab.get(n, 0) for n in names])
    auc_obs = auc(list(scores), list(y))

    def roc(sc, yy):
        thr = np.unique(sc)[::-1]
        P, N = (yy == 1).sum(), (yy == 0).sum()
        tpr, fpr = [0.0], [0.0]
        for t in thr:
            pred = sc >= t
            tpr.append(((pred) & (yy == 1)).sum() / max(P, 1))
            fpr.append(((pred) & (yy == 0)).sum() / max(N, 1))
        return np.array(fpr), np.array(tpr)

    fpr, tpr = roc(scores, y)
    # bootstrap ROC band: TPR at a common FPR grid
    rng = np.random.default_rng(2026)
    grid = np.linspace(0, 1, 41)
    boot = []
    for _ in range(2000):
        idx = rng.integers(0, len(names), len(names))
        if (y[idx] == 1).sum() == 0 or (y[idx] == 0).sum() == 0:
            continue
        f, t = roc(scores[idx], y[idx])
        boot.append(np.interp(grid, f, t))
    boot = np.array(boot)
    band_lo, band_hi = np.percentile(boot, 5, axis=0), np.percentile(boot, 95, axis=0)

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(9.2, 3.7))

    x = np.arange(len(labels)); w = 0.38
    axA.bar(x - w / 2, current, w, label="Замкнутое ядро (CES)", color=ACCENT)
    axA.bar(x + w / 2, baseline, w, label="Эталон: Кобб—Дуглас", color=MUTED)
    for xi, (c, b) in enumerate(zip(current, baseline)):
        axA.text(xi - w / 2, c, f"{c:g}", ha="center", va="bottom", fontsize=8)
        axA.text(xi + w / 2, b, f"{b:g}", ha="center", va="bottom", fontsize=8)
    axA.set_xticks(x); axA.set_xticklabels(labels)
    axA.set_ylabel("RMSE ретропроверки 2015—2023")
    axA.set_title("(a) Точность ядра: меньше — лучше", pad=10)
    axA.legend(loc="upper left")
    axA.set_ylim(0, 2.0)

    axB.fill_between(grid, band_lo, band_hi, color=ACCENT, alpha=0.18,
                     label="бутстреп 90% полоса")
    axB.plot(fpr, tpr, color=ACCENT, lw=2,
             label=f"GIM: AUC={auc_obs:.3f} [{inf['bootstrap']['ci95'][0]:.2f}; {inf['bootstrap']['ci95'][1]:.2f}]")
    axB.plot([0, 1], [0, 1], "--", color=MUTED, lw=1, label="случайное (0.5)")
    axB.set_xlabel("Доля ложных тревог (FPR)"); axB.set_ylabel("Доля попаданий (TPR)")
    axB.set_title("(b) Ранжирование риска конфликта (57 стран)", pad=10)
    axB.legend(loc="lower right")
    axB.set_xlim(0, 1); axB.set_ylim(0, 1)
    axB.text(0.045, 0.93, f"перестановочный тест: $p\\approx${inf['permutation']['p_value']:.3f}",
             fontsize=8.5, color=ACCENT2)
    _save(fig, "fig2_validation")


# ---- fig3: Morris screening, top-7 per metric (4 panels), at 57 countries ----------
def fig3():
    specs = [("temperature", "Температура, $^\\circ$C", ACCENT2),
             ("world_gdp", "Мировой продукт (57 стран)", ACCENT),
             ("co2", "Выбросы CO$_2$", "#5aae61"),
             ("mean_social_tension", "Социальное напряжение", SOCIAL)]
    pretty = {
        "ECS_DEFAULT": "чувствит. климата", "OCEAN_EXCHANGE": "обмен с океаном",
        "HEAT_CAP_SURFACE": "теплоёмк. поверхн.", "HEAT_CAP_DEEP": "теплоёмк. глубин",
        "EMISSIONS_SCALE": "масштаб эмиссий", "DECARB_RATE_STRUCTURAL": "темп декарбониз.",
        "LAND_USE_CO2_GTCO2_YR": "землепользование", "GAMMA_ENERGY": "энергоёмкость",
        "CAPITAL_DEPRECIATION": "аморт. капитала", "DAMAGE_QUAD_COEFF": "коэф. ущерба",
        "CES_SIGMA_KE": "замещение K–E", "TFP_RD_SHARE_SENS": "ПФП от НИОКР",
        "ALPHA_CAPITAL": "доля капитала", "BETA_LABOR": "доля труда",
        "BASE_DEATH_RATE": "смертность", "BASE_BIRTH_RATE": "рождаемость",
        "BASE_INTEREST_RATE": "ставка", "DAMAGE_BENEFIT_MAX": "выгода ущерба",
        "DAMAGE_RISK_ADJ": "риск-корр. ущерба", "PURE_TIME_PREFERENCE": "врем. предпочт.",
        "MARKET_DEMAND_ELASTICITY": "эласт. спроса",
    }
    fig, axes = plt.subplots(2, 2, figsize=(9.2, 6.0))
    for ax, (metric, title, col) in zip(axes.flat, specs):
        j = _latest_sensitivity(metric)
        rk = j["ranking"][:7][::-1]
        names = [pretty.get(n, n.lower()) for n, _ in rk]
        vals = np.array([v for _, v in rk])
        vmax = float(vals.max())
        norm = vals / vmax if vmax > 0 else vals
        ax.barh(range(len(names)), norm, color=col, alpha=0.85)
        ax.set_yticks(range(len(names))); ax.set_yticklabels(names, fontsize=8)
        ax.set_xlim(0, 1.08); ax.set_title(title, fontsize=10)
        ax.set_xlabel("$\\mu^*$ (норм. на макс. в панели)", fontsize=8.5)
        ax.grid(axis="y", visible=False)
        for i, v in enumerate(norm):
            ax.text(v + 0.02, i, f"{v:.2f}", va="center", fontsize=7, color=INK)
        # absolute scale -- so the cross-metric magnitude is not hidden by per-panel normalisation
        note = f"абс. макс. $\\mu^*$ = {vmax:.3g}"
        if metric == "mean_social_tension":
            note += "\n(≈ шумовой порог; см. рис. 5)"
        ax.text(0.97, 0.06, note, transform=ax.transAxes, ha="right", va="bottom",
                fontsize=7.5, color=INK,
                bbox=dict(boxstyle="round,pad=0.25", fc="#f5f5f5", ec="#cccccc", lw=0.5))
    fig.suptitle("Скрининг чувствительности (Моррис, 26 приоров): семь ведущих параметров",
                 fontsize=11, y=1.0)
    _save(fig, "fig3_sensitivity")


# ---- fig4: ensemble fan charts (GDP + temperature), N=500, 57 countries ------------
def fig4():
    j = _latest_ensemble()
    yrs = np.array(j["years"])
    def band(ax, m, ylab, title, col):
        b = j["metrics"][m]
        ax.fill_between(yrs, b["p5"], b["p95"], color=col, alpha=0.15, label="5—95 перцентиль")
        ax.fill_between(yrs, b["p25"], b["p75"], color=col, alpha=0.30, label="25—75 перцентиль")
        ax.plot(yrs, b["p50"], color=col, lw=2, label="медиана")
        ax.set_xlabel("год прогноза"); ax.set_ylabel(ylab); ax.set_title(title)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.legend(loc="upper left")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.2, 3.7))
    band(a1, "world_gdp", "трлн долл.", "(a) Мировой продукт (57 стран)", ACCENT)
    band(a2, "temperature", "$^\\circ$C над доинд.", "(b) Аномалия температуры", ACCENT2)
    _save(fig, "fig4_ensemble")


# ---- fig5: social-tension channel (impulse response + localization) -----------------
def fig5():
    j = json.load(open(os.path.join(REPO, "results", "social_channel", "social_channel.json")))
    irf = j["impulse_response"]
    lags = np.array(irf["lag_years"]); mean = np.array(irf["mean"])
    lo = np.array(irf["p5"]); hi = np.array(irf["p95"])
    H = 15
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.2, 3.7))

    a1.axhline(0, color=MUTED, lw=0.8)
    a1.fill_between(lags[:H + 1], lo[:H + 1], hi[:H + 1], color=SOCIAL, alpha=0.15,
                    label="5—95% (приоры)")
    a1.plot(lags[:H + 1], mean[:H + 1], color=SOCIAL, lw=2, marker="o", ms=3, label="средний отклик")
    sh = j["config"]["shock"]["years"]
    a1.axvspan(0, sh[-1] - sh[0], color=MUTED, alpha=0.12)
    a1.text((sh[-1] - sh[0]) / 2, hi[:H + 1].max() * 0.93, "шок", ha="center", fontsize=8, color=INK)
    a1.set_xlabel("лет после шока"); a1.set_ylabel("$\\Delta$ напряжения")
    a1.set_title("(a) Отклик на стагфляц. шок\n(безработица+инфляция, 3 года)")
    a1.legend(loc="lower right")

    loc = j["localization_spearman_top"][:7][::-1]
    social_set = {"SOCIAL_STRESS_UNEMPLOYMENT_SENS", "SOCIAL_STRESS_INFLATION_SENS",
                  "INEQUALITY_EFFECT_SENS", "SOCIAL_TRUST_ANCHOR_SENS"}
    pretty = {"SOCIAL_TRUST_ANCHOR_SENS": "якорь доверия*", "INEQUALITY_EFFECT_SENS": "эффект неравенства*",
              "SOCIAL_STRESS_UNEMPLOYMENT_SENS": "стресс: безработица*",
              "SOCIAL_STRESS_INFLATION_SENS": "стресс: инфляция*",
              "OCEAN_EXCHANGE": "обмен с океаном", "DAMAGE_BENEFIT_MAX": "выгода ущерба",
              "CES_SIGMA_KE": "замещение K–E", "MARKET_DEMAND_ELASTICITY": "эласт. спроса",
              "ECS_DEFAULT": "чувствит. климата", "TFP_RD_SHARE_SENS": "ПФП от НИОКР",
              "CAPITAL_DEPRECIATION": "аморт. капитала", "GAMMA_ENERGY": "энергоёмкость",
              "BASE_INTEREST_RATE": "ставка", "DAMAGE_QUAD_COEFF": "коэф. ущерба"}
    names = [pretty.get(d["prior"], d["prior"].lower()) for d in loc]
    rhos = [d["rho"] for d in loc]
    cols = [SOCIAL if d["prior"] in social_set else MUTED for d in loc]
    a2.barh(range(len(names)), rhos, color=cols, alpha=0.85)
    a2.axvline(0, color=INK, lw=0.7)
    a2.set_yticks(range(len(names))); a2.set_yticklabels(names, fontsize=8)
    a2.set_xlabel("ранговая корр. с напряжением (Спирмен)")
    a2.set_title("(b) Что управляет напряжением\n(* — приоры соц-блока)")
    a2.grid(axis="y", visible=False)
    _save(fig, "fig5_social_channel")


def main():
    print("Regenerating paper figures from artifacts:")
    fig2(); fig3(); fig4(); fig5()
    print("Done.")


if __name__ == "__main__":
    main()
