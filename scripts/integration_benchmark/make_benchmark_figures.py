#!/usr/bin/env python3
"""Integration-benchmark figures (reproducible, committed). House style matches
paper/figures/make_figures.py.

Bilingual: renders an English set (for paper/gim_paper.tex) and a Russian set with
the ``_ru`` suffix (for paper/gim_paper_ru.tex). All on-figure text is pulled from the
STR table so the two stay in lock-step.

Reads:  results/integration_benchmark/latest.json
Writes: paper/figures/fig6_integration_carbon[_ru], fig7_integration_oil[_ru],
        fig8_integration_crop[_ru], fig9_integration_summary[_ru]  (each .pdf + .png)

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
    "font.serif": ["DejaVu Serif"],   # full Cyrillic coverage -> RU text renders natively
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

# ----------------------------------------------------------------------------------
# All on-figure strings, by language. {} are runtime numbers (.format at use site).
STR = {
    "en": {
        "year": "year",
        # carbon
        "carbon_suptitle": "Scenario A — Carbon tax $50/tCO2:  GIM agrees on emissions, adds the political-economy cost",
        "carbon_p1": "What DICE models — and GIM reproduces",
        "carbon_p2": "What DICE structurally cannot see",
        "carbon_p3": "Dose–response: a channel DICE lacks",
        "yl_emissions": "global emissions",
        "yl_tension": "social tension",
        "yl_tension_delta": "terminal tension delta",
        "xl_carbon_price": "carbon price ($/tCO2)",
        "leg_no_policy": "no policy",
        "leg_carbon50": "carbon $50/t",
        "leg_tension_nopolicy": "tension (no policy)",
        "leg_tension_carbon": "tension (carbon $50/t)",
        "leg_dice_nosociety": "DICE (no society block): 0",
        "leg_gim_tension": "GIM: tension response",
        "ann_emis_cut": "−{:.1f}% @10y",
        "ann_tension_trust": "@10y:  tension +{:.1f}×10⁻³\n          trust {:.1f}×10⁻³",
        "carbon_caption": ("Anchor: Nordhaus, DICE-2016R (PNAS 2017) — optimal carbon price "
                           "welfare-optimal, emissions decline; no unemployment / inflation / politics.  "
                           "Real reversals: France 2018 (gilets jaunes), Australia 2014.  GIM adds the "
                           "economy, society and policy chain that determines whether the tax survives."),
        # oil
        "oil_suptitle": "Scenario B — Oil price shock:  an energy model sees price; GIM sees the sovereign-debt cascade",
        "oil_p1": "Sovereign-debt cascade in importers",
        "oil_p2": "Dose–response: threshold-shaped cascade",
        "yl_dca": "mean debt-crisis years (importers)",
        "yl_extra_crisis": "extra importers in sovereign crisis",
        "xl_burden": "oil-import burden (% of GDP / yr)",
        "leg_no_oil": "no oil shock",
        "leg_severe_oil": "severe oil shock (~15% GDP bill)",
        "leg_energy_nofinance": "energy model (no finance block): 0",
        "leg_gim_extra": "GIM: extra importers in crisis",
        "ann_realistic": "realistic\n(~3% GDP)",
        "ann_severe": "severe\n(~15% GDP)",
        "oil_caption": ("Anchor: IMF GFSR Oct-2025 ch.3; BU GDP Center 2026.  Energy-system models "
                        "(MESSAGEix) stop at price / demand adjustment — no sovereign-finance block.  "
                        "Real case: Sri Lanka 2022 ($1.9B reserves vs $6B debt service, ending in "
                        "default).  The cascade is threshold-shaped; the energy model is flat-zero everywhere."),
        # crop
        "crop_suptitle": "Scenario C — severe crop yield shock:  AgMIP stops at hunger; GIM carries it to protest pressure",
        "crop_p1": "Food stress (AgMIP) to protest (GIM)",
        "crop_p2": "Dose–response: convex escalation",
        "yl_metric": "metric level (vulnerable subset)",
        "yl_terminal_delta": "terminal delta",
        "xl_yield_loss": "vulnerable-region yield loss (%)",
        "leg_food_noshock": "food stress (no shock)",
        "leg_food_shock": "food stress (yield -50%)",
        "leg_protest_shock": "protest pressure (yield -50%)",
        "leg_agmip_noprotest": "AgMIP (no politics): protest 0",
        "leg_gim_food": "GIM: food-stress delta",
        "leg_gim_protest": "GIM: protest delta",
        "ann_severe50": "severe (−50%)",
        "crop_caption": ("Anchor: AgMIP / IPCC AR6 (yield decline to a hunger index).  Lagi, Bertrand "
                         "& Bar-Yam 2011 (arXiv:1108.2455): food riots above FAO index 210 (p<1e-7), "
                         "coinciding with the Arab Spring 2011.  GIM adds the food, affordability and "
                         "protest chain in vulnerable importers, with convex escalation."),
        # summary
        "sum_suptitle": "The integration dividend — three cross-sector channels with a non-zero GIM slope where sectoral models are flat",
        "sum_A": "A · economy and society",
        "sum_B": "B · resources and finance",
        "sum_C": "C · climate and society",
        "yl_xsector": "cross-sector response (normalized)",
        "xl_carbon_norm": "carbon price (normalized)",
        "xl_burden_norm": "oil-import burden (normalized)",
        "xl_yield_norm": "yield loss (normalized)",
        "lab_gim_tension": "GIM: social tension",
        "lab_dice_zero": "DICE: zero",
        "lab_gim_sovereign": "GIM: sovereign crises",
        "lab_messageix_zero": "MESSAGEix: zero",
        "lab_gim_protest": "GIM: protest pressure",
        "lab_agmip_zero": "AgMIP: zero",
        "sum_caption": ("Each curve is one cross-sector channel, normalized to its own peak; the dashed "
                        "red line is every sectoral model's structural zero on that axis.  Headline "
                        "effects (10y): A carbon $50/t: emissions −{:.1f}%, tension +{:.1f}×10⁻³;  "
                        "B severe oil shock (~15% GDP): +{:.0f} importers in sovereign crisis, "
                        "debt-crisis-years ×{:.1f};  C severe yield −50%: food-stress +{:.3f}, protest "
                        "+{:.3f}.  Shapes differ honestly: B threshold-stepped, C convex, A weak-but-robust."),
    },
    "ru": {
        "year": "год",
        # carbon
        "carbon_suptitle": "Сценарий А — Углеродный налог $50/тCO2:  GIM согласуется по выбросам и добавляет политэкономическую цену",
        "carbon_p1": "Что моделирует DICE — и воспроизводит GIM",
        "carbon_p2": "Чего DICE структурно не видит",
        "carbon_p3": "Доза–отклик: недостающий канал",
        "yl_emissions": "глобальные выбросы",
        "yl_tension": "социальное напряжение",
        "yl_tension_delta": "итоговый прирост напряжения",
        "xl_carbon_price": "цена углерода ($/тCO2)",
        "leg_no_policy": "без политики",
        "leg_carbon50": "налог $50/т",
        "leg_tension_nopolicy": "напряжение (без политики)",
        "leg_tension_carbon": "напряжение (налог $50/т)",
        "leg_dice_nosociety": "DICE (нет блока общества): 0",
        "leg_gim_tension": "GIM: отклик напряжения",
        "ann_emis_cut": "−{:.1f}% за 10 лет",
        "ann_tension_trust": "за 10 лет:  напряжение +{:.1f}×10⁻³\n          доверие {:.1f}×10⁻³",
        "carbon_caption": ("Эталон: Нордхаус, DICE-2016R (PNAS 2017) — оптимальная по благосостоянию "
                           "цена углерода, выбросы снижаются; нет безработицы, инфляции и политики.  "
                           "Реальные развороты: Франция 2018 (жёлтые жилеты), Австралия 2014.  GIM "
                           "добавляет цепочку «экономика — общество — политика», определяющую, доживёт ли налог."),
        # oil
        "oil_suptitle": "Сценарий Б — Нефтяной шок: энергомодель видит цену, GIM — долговой каскад",
        "oil_p1": "Суверенный долговой каскад у импортёров",
        "oil_p2": "Доза–отклик: пороговый каскад",
        "yl_dca": "ср. годы долгового кризиса (импортёры)",
        "yl_extra_crisis": "доп. импортёры в суверенном кризисе",
        "xl_burden": "нефтяное импортное бремя (% ВВП / год)",
        "leg_no_oil": "без шока",
        "leg_severe_oil": "тяжёлый шок (~15% ВВП)",
        "leg_energy_nofinance": "энергомодель (нет финблока): 0",
        "leg_gim_extra": "GIM: доп. импортёры в кризисе",
        "ann_realistic": "реалистичный\n(~3% ВВП)",
        "ann_severe": "тяжёлый\n(~15% ВВП)",
        "oil_caption": ("Эталон: IMF GFSR окт. 2025, гл. 3; BU GDP Center 2026.  Энергосистемные "
                        "модели (MESSAGEix) останавливаются на цене и подстройке спроса — без блока "
                        "суверенных финансов.  Реальный случай: Шри-Ланка 2022 ($1.9 млрд резервов "
                        "против $6 млрд обслуживания долга, дефолт).  Каскад пороговый; энергомодель всюду на нуле."),
        # crop
        "crop_suptitle": "Сценарий В — Урожайный шок: AgMIP видит голод, GIM — протестное давление",
        "crop_p1": "Прод. стресс (AgMIP) и протест (GIM)",
        "crop_p2": "Доза–отклик: выпуклая эскалация",
        "yl_metric": "уровень метрики (уязвимые страны)",
        "yl_terminal_delta": "итоговый прирост",
        "xl_yield_loss": "потеря урожая в уязвимых регионах (%)",
        "leg_food_noshock": "прод. стресс (без шока)",
        "leg_food_shock": "прод. стресс (урожай −50%)",
        "leg_protest_shock": "протестное давление (урожай −50%)",
        "leg_agmip_noprotest": "AgMIP (без политики): протест 0",
        "leg_gim_food": "GIM: прирост прод. стресса",
        "leg_gim_protest": "GIM: прирост протеста",
        "ann_severe50": "тяжёлый (−50%)",
        "crop_caption": ("Эталон: AgMIP / МГЭИК AR6 (снижение урожая до индекса голода).  Lagi, "
                         "Bertrand & Bar-Yam 2011 (arXiv:1108.2455): продовольственные бунты выше "
                         "индекса ФАО 210 (p<1e-7), совпадая с «Арабской весной» 2011.  GIM добавляет "
                         "цепочку «продовольствие — доступность — протест» у уязвимых импортёров, с выпуклой эскалацией."),
        # summary
        "sum_suptitle": "Выигрыш от интеграции — три межсекторных канала с ненулевым наклоном GIM там, где секторальные модели плоские",
        "sum_A": "А · экономика и общество",
        "sum_B": "Б · ресурсы и финансы",
        "sum_C": "В · климат и общество",
        "yl_xsector": "межсекторный отклик (норм.)",
        "xl_carbon_norm": "цена углерода (норм.)",
        "xl_burden_norm": "импортное бремя (норм.)",
        "xl_yield_norm": "потеря урожая (норм.)",
        "lab_gim_tension": "GIM: соц. напряжение",
        "lab_dice_zero": "DICE: ноль",
        "lab_gim_sovereign": "GIM: суверенные кризисы",
        "lab_messageix_zero": "MESSAGEix: ноль",
        "lab_gim_protest": "GIM: протестное давление",
        "lab_agmip_zero": "AgMIP: ноль",
        "sum_caption": ("Каждая кривая — один межсекторный канал, нормированный к собственному пику; "
                        "красный пунктир — структурный ноль любой секторальной модели по этой оси.  "
                        "Ключевые эффекты (10 лет): А углеродный налог $50/т: выбросы −{:.1f}%, "
                        "напряжение +{:.1f}×10⁻³;  Б тяжёлый нефтяной шок (~15% ВВП): +{:.0f} импортёра "
                        "в суверенном кризисе, годы долгового кризиса ×{:.1f};  В тяжёлая потеря урожая "
                        "−50%: прод. стресс +{:.3f}, протест +{:.3f}.  Формы честно различаются: "
                        "Б ступенчато-пороговая, В выпуклая, А слабая-но-устойчивая."),
    },
}

LANG = "en"
SUFFIX = ""


def set_lang(lang):
    global LANG, SUFFIX
    LANG = lang
    SUFFIX = "" if lang == "en" else f"_{lang}"


def L(key):
    return STR[LANG][key]


def _finish(fig, name, suptitle, caption, top=0.90, bottom=0.27, width=150):
    """Lay out, add a wrapped figure caption + suptitle, save (no tight bbox -- the bbox
    would otherwise expand to fit the wide caption and squash the axes). '$' is escaped
    so it renders literally instead of opening a mathtext span. Filename gets the
    language SUFFIX."""
    esc = lambda t: t.replace("$", r"\$")
    fig.tight_layout(rect=(0.0, bottom, 1.0, top))
    fig.suptitle(esc(suptitle), fontsize=11.5, color=INK, y=0.975)
    fig.text(0.5, bottom * 0.42, esc(textwrap.fill(caption, width=width)),
             ha="center", va="center", fontsize=7.8, style="italic", color=INK,
             bbox=dict(boxstyle="round,pad=0.55", fc="#f5f5f2", ec="#d9d9d4", lw=0.8))
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(FIGDIR, f"{name}{SUFFIX}.{ext}"))
    plt.close(fig)
    print(f"  wrote {name}{SUFFIX}.pdf / .png")


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
    ax[0].plot(yrs, s["emissions_base"], color=MUTED, lw=2, label=L("leg_no_policy"))
    ax[0].plot(yrs, s["emissions_shock"], color=GOOD, lw=2.4, label=L("leg_carbon50"))
    ax[0].fill_between(yrs, s["emissions_shock"], s["emissions_base"], color=GOOD, alpha=0.12)
    ax[0].set_title(L("carbon_p1"), color=INK)
    ax[0].set_xlabel(L("year")); ax[0].set_ylabel(L("yl_emissions"))
    ax[0].legend(loc="lower left")
    _time_axis(ax[0], len(yrs))
    ax[0].text(0.96, 0.92, L("ann_emis_cut").format(h["emissions_cut_pct_10y"]),
               transform=ax[0].transAxes, ha="right", va="top", color=GOOD, fontsize=9.5)

    # P2 -- what DICE cannot see: tension up, trust down
    ax2 = ax[1]
    ax2.plot(yrs, s["tension_base"], color=MUTED, lw=2, label=L("leg_tension_nopolicy"))
    ax2.plot(yrs, s["tension_shock"], color=SOCIAL, lw=2.4, label=L("leg_tension_carbon"))
    ax2.fill_between(yrs, s["tension_base"], s["tension_shock"], color=SOCIAL, alpha=0.15)
    ax2.set_title(L("carbon_p2"), color=INK)
    ax2.set_xlabel(L("year")); ax2.set_ylabel(L("yl_tension"))
    ax2.legend(loc="upper left")
    _time_axis(ax2, len(yrs))
    ax2.text(0.96, 0.08, L("ann_tension_trust").format(h["tension_delta_10y"] * 1000,
                                                       h["trust_delta_10y"] * 1000),
             transform=ax2.transAxes, ha="right", va="bottom", color=SOCIAL, fontsize=8)

    # P3 -- dose-response: carbon price -> tension; DICE slope = 0
    ax3 = ax[2]
    ax3.axhline(0, color=SECT, lw=2.0, ls="--", label=L("leg_dice_nosociety"))
    ax3.plot(sw["carbon"], sw["tension_delta"], color=GIM, lw=2.4,
             marker="o", ms=4, label=L("leg_gim_tension"))
    ax3.scatter([50], [h["tension_delta_10y"]], color=SOCIAL, zorder=5, s=42)
    ax3.set_title(L("carbon_p3"), color=INK)
    ax3.set_xlabel(L("xl_carbon_price")); ax3.set_ylabel(L("yl_tension_delta"))
    ax3.legend(loc="upper left")

    _finish(fig, "fig6_integration_carbon", L("carbon_suptitle"), L("carbon_caption"))


# ----------------------------------------------------------------------------------
def fig_oil(sc):
    s = sc["series"]; sw = sc["sweep"]; h = sc["headline"]
    yrs = np.arange(len(s["dca_base"]))
    fig, ax = plt.subplots(1, 2, figsize=(8.4, 3.8))

    # P1 -- importer debt-crisis years: severe shock above baseline
    ax[0].plot(yrs, s["dca_base"], color=MUTED, lw=2, label=L("leg_no_oil"))
    ax[0].plot(yrs, s["dca_shock"], color=GIM, lw=2.4, label=L("leg_severe_oil"))
    ax[0].fill_between(yrs, s["dca_base"], s["dca_shock"], color=GIM, alpha=0.14)
    ax[0].set_title(L("oil_p1"), color=INK)
    ax[0].set_xlabel(L("year")); ax[0].set_ylabel(L("yl_dca"))
    ax[0].legend(loc="upper left")
    _time_axis(ax[0], len(yrs))

    # P2 -- dose-response: burden -> extra importers in crisis; energy model = 0.
    # Mark BOTH the realistic (~3% GDP, marginal) and severe (~15%, headline) points.
    ax2 = ax[1]
    x = [b * 100 for b in sw["burden_gdp"]]
    ax2.axhline(0, color=SECT, lw=2.0, ls="--", label=L("leg_energy_nofinance"))
    ax2.plot(x, sw["extra_in_crisis"], color=GIM, lw=2.4, marker="o", ms=4, label=L("leg_gim_extra"))
    ax2.axvline(3.3, color=MUTED, lw=1.1, ls=":", alpha=0.9)
    ax2.text(3.7, 0.55, L("ann_realistic"), fontsize=7.2, color="#5F5E5A", ha="left", va="bottom")
    ax2.axvline(15, color=SOCIAL, lw=1.3, ls=":", alpha=0.9)
    ax2.text(15.4, 0.9, L("ann_severe"), fontsize=7.6, color=SOCIAL, ha="left", va="bottom")
    ax2.set_title(L("oil_p2"), color=INK)
    ax2.set_xlabel(L("xl_burden")); ax2.set_ylabel(L("yl_extra_crisis"))
    ax2.legend(loc="upper left")

    _finish(fig, "fig7_integration_oil", L("oil_suptitle"), L("oil_caption"), width=108)


# ----------------------------------------------------------------------------------
def fig_crop(sc):
    s = sc["series"]; sw = sc["sweep"]; h = sc["headline"]
    yrs = np.arange(len(s["food_base"]))
    fig, ax = plt.subplots(1, 2, figsize=(8.4, 3.8))

    # P1 -- food affordability + protest, base vs shock (vulnerable subset)
    ax[0].plot(yrs, s["food_base"], color=MUTED, lw=2, label=L("leg_food_noshock"))
    ax[0].plot(yrs, s["food_shock"], color=GOOD, lw=2.4, label=L("leg_food_shock"))
    ax[0].plot(yrs, s["protest_base"], color=MUTED, lw=1.4, ls="--", alpha=0.8)
    ax[0].plot(yrs, s["protest_shock"], color=SOCIAL, lw=2.0, ls="--", label=L("leg_protest_shock"))
    ax[0].fill_between(yrs, s["food_base"], s["food_shock"], color=GOOD, alpha=0.12)
    ax[0].set_title(L("crop_p1"), color=INK)
    ax[0].set_xlabel(L("year")); ax[0].set_ylabel(L("yl_metric"))
    ax[0].legend(loc="center right", fontsize=7.6)
    _time_axis(ax[0], len(yrs))

    # P2 -- dose-response: yield cut -> food/protest; convex; AgMIP protest slope = 0
    ax2 = ax[1]
    x = [c * 100 for c in sw["yield_cut"]]
    ax2.axhline(0, color=SECT, lw=2.0, ls="--", label=L("leg_agmip_noprotest"))
    ax2.plot(x, sw["food_delta"], color=GOOD, lw=2.2, marker="o", ms=4, label=L("leg_gim_food"))
    ax2.plot(x, sw["protest_delta"], color=SOCIAL, lw=2.4, marker="s", ms=4, label=L("leg_gim_protest"))
    ax2.axvline(50, color=SOCIAL, lw=1.2, ls=":", alpha=0.8)
    ax2.text(50, 0.19, L("ann_severe50"), fontsize=7.6, color=SOCIAL, ha="center", va="top")
    ax2.set_title(L("crop_p2"), color=INK)
    ax2.set_xlabel(L("xl_yield_loss")); ax2.set_ylabel(L("yl_terminal_delta"))
    ax2.legend(loc="upper left", fontsize=7.6)

    _finish(fig, "fig8_integration_crop", L("crop_suptitle"), L("crop_caption"), width=108)


# ----------------------------------------------------------------------------------
def fig_summary(scn):
    """Thesis figure: three cross-sector channels. GIM has a positive, quantified slope;
    every sectoral model is structurally flat-zero on its cross-sector axis."""
    A = _get(scn, "A_carbon_tax"); B = _get(scn, "B_oil_shock"); C = _get(scn, "C_crop_shock")
    fig, ax = plt.subplots(1, 3, figsize=(11.2, 3.9))

    def norm(v):
        v = np.array(v, float); m = np.max(np.abs(v))
        return v / m if m > 0 else v

    ax[0].axhline(0, color=SECT, lw=2.0, ls="--")
    ax[0].plot(norm(A["sweep"]["carbon"]), norm(A["sweep"]["tension_delta"]),
               color=GIM, lw=2.6, marker="o", ms=4)
    ax[0].set_title(L("sum_A"), color=INK)
    ax[0].set_xlabel(L("xl_carbon_norm")); ax[0].set_ylabel(L("yl_xsector"))
    ax[0].text(0.04, 0.90, L("lab_gim_tension"), color=GIM, fontsize=8.5, transform=ax[0].transAxes)
    ax[0].text(0.96, 0.20, L("lab_dice_zero"), color=SECT, fontsize=8.5, ha="right", transform=ax[0].transAxes)

    ax[1].axhline(0, color=SECT, lw=2.0, ls="--")
    ax[1].plot(norm(B["sweep"]["burden_gdp"]), norm(B["sweep"]["dca_delta"]),
               color=GIM, lw=2.6, marker="o", ms=4)
    ax[1].set_title(L("sum_B"), color=INK)
    ax[1].set_xlabel(L("xl_burden_norm"))
    ax[1].text(0.04, 0.90, L("lab_gim_sovereign"), color=GIM, fontsize=8.5, transform=ax[1].transAxes)
    ax[1].text(0.96, 0.20, L("lab_messageix_zero"), color=SECT, fontsize=8.5, ha="right", transform=ax[1].transAxes)

    ax[2].axhline(0, color=SECT, lw=2.0, ls="--")
    ax[2].plot(norm(C["sweep"]["yield_cut"]), norm(C["sweep"]["protest_delta"]),
               color=GIM, lw=2.6, marker="o", ms=4)
    ax[2].set_title(L("sum_C"), color=INK)
    ax[2].set_xlabel(L("xl_yield_norm"))
    ax[2].text(0.04, 0.90, L("lab_gim_protest"), color=GIM, fontsize=8.5, transform=ax[2].transAxes)
    ax[2].text(0.96, 0.20, L("lab_agmip_zero"), color=SECT, fontsize=8.5, ha="right", transform=ax[2].transAxes)

    for a in ax:
        a.set_ylim(-0.12, 1.08)
        a.set_xlim(-0.02, 1.05)

    ha = A["headline"]; hb = B["headline"]; hc = C["headline"]
    cap = L("sum_caption").format(
        ha["emissions_cut_pct_10y"], ha["tension_delta_10y"] * 1e3,
        hb["extra_importers_in_crisis_peak"], hb["dca_ratio_peak"],
        hc["food_delta_10y"], hc["protest_delta_10y"])
    _finish(fig, "fig9_integration_summary", L("sum_suptitle"), cap, bottom=0.30, width=158)


def main():
    with open(DATA) as fh:
        data = json.load(fh)
    scn = data["scenarios"]
    for lang in ("en", "ru"):
        set_lang(lang)
        print(f"rendering integration-benchmark figures [{lang}]:")
        fig_carbon(_get(scn, "A_carbon_tax"))
        fig_oil(_get(scn, "B_oil_shock"))
        fig_crop(_get(scn, "C_crop_shock"))
        fig_summary(scn)


if __name__ == "__main__":
    main()
