#!/usr/bin/env python3
"""Charts for the El Niño 2026-27 scenario run (scripts/run_elnino_2026.py)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "elnino2026"

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.25,
                     "figure.facecolor": "white"})

rows = list(csv.DictReader(open(OUT / "fans.csv")))
IDX = {(r["run"], r["metric"], int(r["year"])): r for r in rows}
YEARS = list(range(2026, 2034))


def d(run, metric, year, key="d_p50"):
    r = IDX.get((run, metric, year))
    if not r or r.get(key, "") == "":
        return float("nan")
    return float(r[key]) * 100.0


def series(run, metric, key="d_p50"):
    return [d(run, metric, y, key) for y in YEARS]


LBL = {
    "elnino_strong": "Эль-Ниньо сильное (ONI ~ +1,5)",
    "elnino_vstrong": "Эль-Ниньо очень сильное (ONI ≥ +2,0)",
    "elnino_historic": "Хвост: историческое (RONI +2,5…+3,0)",
    "hormuz_only": "Только Ормуз (геополитика)",
    "elnino_hormuz": "Наложение: Эль-Ниньо + Ормуз",
}
COL = {"elnino_strong": "#7ea6d8", "elnino_vstrong": "#1f5fa8",
       "elnino_historic": "#0b2f5e", "hormuz_only": "#c9601a",
       "elnino_hormuz": "#8c1d40"}


# --------------------------------------------------------------- Fig 1: dose
fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
panels = [("food_supply", "Мировое предложение продовольствия, Δ%"),
          ("food_price", "Мировая цена продовольствия, Δ%"),
          ("energy_price", "Мировая цена энергии, Δ%")]
for ax, (m, title) in zip(axes, panels):
    for run in ("elnino_strong", "elnino_vstrong", "elnino_historic"):
        ax.plot(YEARS, series(run, m), "o-", ms=3, color=COL[run], label=LBL[run])
        ax.fill_between(YEARS, series(run, m, "d_p5"), series(run, m, "d_p95"),
                        color=COL[run], alpha=0.12, lw=0)
    ax.axhline(0, color="k", lw=0.7)
    ax.set_title(title, fontsize=9)
axes[0].legend(fontsize=7, loc="lower right")
fig.suptitle("Рис. A. Отклик на амплитуду события (медиана и 5–95% ансамбля, 300 членов; "
             "отклонение от базового прогона)", fontsize=9)
fig.tight_layout(rect=(0, 0, 1, 0.93))
fig.savefig(OUT / "fig_a_dose.png", dpi=160)

# ------------------------------------------------- Fig 2: compound arithmetic
fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
for ax, (m, title, unit) in zip(axes, [
        ("energy_price", "Цена энергии", "Δ%"),
        ("world_inflation", "Мировая инфляция (взвеш. по ВВП)", "Δ п.п."),
        ("world_gdp", "Мировой ВВП", "Δ%")]):
    for run in ("elnino_vstrong", "hormuz_only", "elnino_hormuz"):
        ax.plot(YEARS, series(run, m), "o-", ms=3, color=COL[run], label=LBL[run])
    ax.plot(YEARS, [a + b for a, b in zip(series("elnino_vstrong", m),
                                          series("hormuz_only", m))],
            "k--", lw=1.1, label="Арифметическая сумма частей")
    ax.axhline(0, color="k", lw=0.7)
    ax.set_title(f"{title}, {unit}", fontsize=9)
axes[0].legend(fontsize=7)
fig.suptitle("Рис. B. Наложение шоков: сложение или усиление? Пунктир — сумма отдельных "
             "эффектов, бордовая — совместный прогон", fontsize=9)
fig.tight_layout(rect=(0, 0, 1, 0.93))
fig.savefig(OUT / "fig_b_compound.png", dpi=160)

# ---------------------------------------------------- Fig 3: who pays, and how long
FOCUS = ["IND", "PAK", "EGY", "CHN", "IDN", "BRA", "AUS", "ZAF", "NGA", "USA", "RUS", "DEU"]
NAMES = {"IND": "Индия", "PAK": "Пакистан", "EGY": "Египет", "CHN": "Китай",
         "IDN": "Индонезия", "BRA": "Бразилия", "AUS": "Австралия", "ZAF": "ЮАР",
         "NGA": "Нигерия", "USA": "США", "RUS": "Россия", "DEU": "Германия"}
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
run = "elnino_vstrong"
for ax, (pre, title) in zip(axes, [("gdp", "ВВП, Δ% к базовому прогону"),
                                   ("pop", "Население, Δ% к базовому прогону")]):
    vals = [(a, d(run, f"{pre}_{a}", 2033)) for a in FOCUS if f"{pre}_{a}" in
            {r["metric"] for r in rows}]
    vals.sort(key=lambda x: x[1])
    ax.barh([NAMES.get(a, a) for a, _ in vals], [v for _, v in vals],
            color=["#8c1d40" if v < -0.01 else "#9aa4ad" for _, v in vals])
    ax.axvline(0, color="k", lw=0.7)
    ax.set_title(f"{title}  (2033, через 6 лет после пика)", fontsize=9)
fig.suptitle("Рис. C. След события через 6 лет: устойчивый ущерб сконцентрирован там, где "
             "продовольственный баланс уже дефицитен", fontsize=9)
fig.tight_layout(rect=(0, 0, 1, 0.92))
fig.savefig(OUT / "fig_c_distribution.png", dpi=160)

# ---------------------------------------------- Fig 4: inflation with food overlay
fig, ax = plt.subplots(figsize=(6.5, 3.8))
for run, lbl, c, ls in [
        ("elnino_vstrong", "Эль-Ниньо, ядро (только энергия в cost-push)", "#1f5fa8", "-"),
        ("elnino_vstrong_foodcpi", "Эль-Ниньо + продовольствие в ИПЦ (расширение)", "#1f5fa8", "--"),
        ("elnino_hormuz", "Эль-Ниньо + Ормуз, ядро", "#8c1d40", "-"),
        ("elnino_hormuz_foodcpi", "Эль-Ниньо + Ормуз + продовольствие в ИПЦ", "#8c1d40", "--")]:
    ax.plot(YEARS, series(run, "world_inflation"), ls, color=c, lw=1.4, label=lbl)
ax.axhline(0, color="k", lw=0.7)
ax.set_title("Рис. D. Мировая инфляция, Δ п.п.: чего не видит ядро", fontsize=9)
ax.legend(fontsize=7)
fig.tight_layout()
fig.savefig(OUT / "fig_d_inflation.png", dpi=160)

print("saved:", *[p.name for p in sorted(OUT.glob("fig_*.png"))])
