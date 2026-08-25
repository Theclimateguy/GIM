#!/usr/bin/env python3
"""Build Russian HTML and PDF reports for a GIM18 climate/energy stress-test run."""

from __future__ import annotations

import argparse
import html
import textwrap
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch
from PIL import Image


plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "pdf.fonttype": 42,
        "axes.unicode_minus": False,
    }
)

ORDER = [
    "ssp1_sustainability",
    "ssp2_middle_road",
    "ssp3_fragmentation",
    "ssp5_fossil_growth",
    "delayed_transition",
]

SCENARIO_LABELS = {
    "ssp1_sustainability": "SSP1 устойчивость",
    "ssp2_middle_road": "SSP2 средний путь",
    "ssp3_fragmentation": "SSP3 фрагментация",
    "ssp5_fossil_growth": "SSP5 ископаемый рост",
    "delayed_transition": "Отложенный переход",
}

SCENARIO_SHORT = {
    "ssp1_sustainability": "SSP1",
    "ssp2_middle_road": "SSP2",
    "ssp3_fragmentation": "SSP3",
    "ssp5_fossil_growth": "SSP5",
    "delayed_transition": "Отложенный\nпереход",
}

SCENARIO_COLORS = {
    "ssp1_sustainability": "#1f8a70",
    "ssp2_middle_road": "#4b6cb7",
    "ssp3_fragmentation": "#b65f28",
    "ssp5_fossil_growth": "#111827",
    "delayed_transition": "#b88a00",
}

REGION_RU = {
    "Oceania": "Океания",
    "Europe": "Европа",
    "South Asia": "Южная Азия",
    "Global South": "Глобальный Юг",
    "North America": "Северная Америка",
    "Middle East": "Ближний Восток",
    "East Asia": "Восточная Азия",
    "South America": "Южная Америка",
}

COUNTRY_RU = {
    "United States": "США",
    "China": "Китай",
    "Brazil": "Бразилия",
    "Turkiye": "Турция",
    "Saudi Arabia": "Саудовская Аравия",
    "Israel": "Израиль",
    "Mexico": "Мексика",
    "South Africa": "ЮАР",
    "Argentina": "Аргентина",
    "Russia": "Россия",
    "Ireland": "Ирландия",
    "Norway": "Норвегия",
    "Switzerland": "Швейцария",
    "Denmark": "Дания",
    "Finland": "Финляндия",
    "Austria": "Австрия",
    "Sweden": "Швеция",
    "Netherlands": "Нидерланды",
    "Czechia": "Чехия",
    "Belgium": "Бельгия",
    "India": "Индия",
    "Germany": "Германия",
    "Nigeria": "Нигерия",
}


def fmt(value: float, digits: int = 1) -> str:
    text = f"{float(value):,.{digits}f}"
    return text.replace(",", " ").replace(".", ",")


def pct(value: float, digits: int = 0) -> str:
    return f"{fmt(100.0 * float(value), digits)}%"


def esc(value: object) -> str:
    return html.escape(str(value))


def country_ru(name: str) -> str:
    return COUNTRY_RU.get(name, name)


def region_ru(name: str) -> str:
    return REGION_RU.get(name, name)


def table_html(df: pd.DataFrame, *, classes: str = "") -> str:
    header = "<thead><tr>" + "".join(f"<th>{esc(col)}</th>" for col in df.columns) + "</tr></thead>"
    body_rows = []
    for row in df.itertuples(index=False, name=None):
        body_rows.append("<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>")
    return f'<table class="{classes}">{header}<tbody>{"".join(body_rows)}</tbody></table>'


def prepare_data(run_dir: Path) -> dict[str, pd.DataFrame]:
    data = {
        "final": pd.read_csv(run_dir / "final_summary.csv"),
        "summary": pd.read_csv(run_dir / "trajectory_summary.csv"),
        "region": pd.read_csv(run_dir / "region_summary.csv"),
        "country": pd.read_csv(run_dir / "country_summary.csv"),
        "all_actor": pd.read_csv(run_dir / "all_actor_trajectories.csv"),
        "focus": pd.read_csv(run_dir / "focus_actor_trajectories.csv"),
    }
    for df in data.values():
        if "scenario" in df.columns:
            df["scenario_label_ru"] = df["scenario"].map(SCENARIO_LABELS).fillna(df["scenario"])
    return data


def style_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, color="#e5e7eb", linewidth=0.8)
    ax.tick_params(colors="#374151", labelsize=8)
    ax.title.set_color("#111827")
    ax.xaxis.label.set_color("#374151")
    ax.yaxis.label.set_color("#374151")


def population_exposure(all_actor: pd.DataFrame) -> pd.DataFrame:
    final_year = int(all_actor["year"].max())
    df = all_actor[all_actor["year"] == final_year].copy()
    rows = []
    for (scenario, seed), group in df.groupby(["scenario", "seed"]):
        pop = group["population"].clip(lower=0).sum()
        rows.append(
            {
                "scenario": scenario,
                "seed": seed,
                "high_social_stress_pop": group.loc[
                    (group["social_tension"] >= 0.65) | (group["trust_gov"] <= 0.25),
                    "population",
                ]
                .clip(lower=0)
                .sum()
                / max(pop, 1.0),
                "high_climate_risk_pop": group.loc[group["climate_risk"] >= 0.65, "population"]
                .clip(lower=0)
                .sum()
                / max(pop, 1.0),
                "low_food_buffer_pop": group.loc[group["food_reserve_years"] <= 0.25, "population"]
                .clip(lower=0)
                .sum()
                / max(pop, 1.0),
            }
        )
    return pd.DataFrame(rows).groupby("scenario", as_index=False).mean(numeric_only=True)


def plot_global_panel(summary: pd.DataFrame, assets_dir: Path) -> str:
    metrics = [
        ("gdp_index_mean", "Индекс ВВП, 2026=100"),
        ("temperature_mean", "Температурная аномалия, °C"),
        ("emissions_index_mean", "Индекс годовых выбросов CO₂"),
        ("avg_relation_conflict_mean", "Средний двусторонний конфликт"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 7.2), constrained_layout=False)
    axes = axes.flatten()
    for ax, (metric, title) in zip(axes, metrics):
        for scenario in ORDER:
            group = summary[summary["scenario"] == scenario].sort_values("year")
            if group.empty:
                continue
            ax.plot(
                group["year"],
                group[metric],
                color=SCENARIO_COLORS[scenario],
                linewidth=2.2,
                label=SCENARIO_LABELS[scenario],
            )
        ax.set_title(title, fontsize=10, pad=8)
        ax.set_xlabel("")
        style_axes(ax)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, fontsize=8, bbox_to_anchor=(0.5, 0.0))
    fig.suptitle("Глобальные траектории климато-энергетических режимов", fontsize=13, x=0.02, ha="left")
    fig.tight_layout(rect=[0, 0.08, 1, 0.95])
    path = assets_dir / "01_global_trajectories_ru.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path.name


def plot_tradeoff(final: pd.DataFrame, assets_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(9.4, 5.9))
    points = []
    for scenario in ORDER:
        row = final[final["scenario"] == scenario].iloc[0]
        x = float(row["temperature_mean"])
        y = float(row["gdp_index_mean"])
        points.append((x, y))
        ax.scatter(
            x,
            y,
            s=95 + 5 * row["emissions_index_mean"],
            color=SCENARIO_COLORS[scenario],
            alpha=0.9,
            edgecolor="white",
            linewidth=1.2,
        )
        offsets = {
            "ssp1_sustainability": (12, 12, "left"),
            "ssp2_middle_road": (-24, -24, "right"),
            "ssp3_fragmentation": (-8, 20, "right"),
            "ssp5_fossil_growth": (-10, 20, "right"),
            "delayed_transition": (28, 22, "left"),
        }
        dx, dy, ha = offsets[scenario]
        ax.annotate(
            SCENARIO_LABELS[scenario],
            xy=(x, y),
            xytext=(dx, dy),
            textcoords="offset points",
            ha=ha,
            va="center",
            fontsize=8,
            color="#111827",
            annotation_clip=False,
        )
    xs, ys = zip(*points)
    ax.set_xlim(min(xs) - 0.006, max(xs) + 0.006)
    ax.set_ylim(min(ys) - 4, max(ys) + 4)
    ax.set_title("Компромисс выпуск-климат в 2056 году", fontsize=12, pad=10)
    ax.set_xlabel("Температурная аномалия, °C")
    ax.set_ylabel("Глобальный индекс ВВП, 2026=100")
    style_axes(ax)
    fig.tight_layout()
    path = assets_dir / "02_tradeoff_gdp_temperature_ru.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path.name


def plot_region_heatmap(region: pd.DataFrame, assets_dir: Path) -> str:
    final_year = int(region["year"].max())
    df = region[region["year"] == final_year].copy()
    pivot = df.pivot_table(index="region", columns="scenario", values="gdp_index_mean", aggfunc="mean")
    pivot = pivot[[col for col in ORDER if col in pivot.columns]]
    pivot = pivot.sort_values("ssp5_fossil_growth", ascending=False)
    labels = [SCENARIO_SHORT[col] for col in pivot.columns]
    fig, ax = plt.subplots(figsize=(10.8, 5.8))
    im = ax.imshow(pivot.values, aspect="auto", cmap="YlGnBu")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([region_ru(name) for name in pivot.index], fontsize=8)
    ax.set_title("Региональный индекс ВВП в 2056 году", fontsize=12, pad=10)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, f"{pivot.values[i, j]:.0f}", ha="center", va="center", fontsize=7, color="#111827")
    cbar = fig.colorbar(im, ax=ax, shrink=0.82)
    cbar.set_label("Индекс ВВП, 2026=100", fontsize=8)
    fig.tight_layout()
    path = assets_dir / "03_region_gdp_heatmap_ru.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path.name


def plot_population_exposure(exposure: pd.DataFrame, assets_dir: Path) -> str:
    metrics = [
        ("high_social_stress_pop", "Социальный стресс"),
        ("high_climate_risk_pop", "Климатический риск"),
        ("low_food_buffer_pop", "Низкий прод. буфер"),
    ]
    df = exposure.set_index("scenario").loc[[s for s in ORDER if s in exposure["scenario"].values]]
    x = np.arange(len(df.index))
    width = 0.23
    fig, ax = plt.subplots(figsize=(11, 5.4))
    for idx, (col, label) in enumerate(metrics):
        ax.bar(x + (idx - 1) * width, df[col] * 100.0, width=width, label=label)
    ax.set_xticks(x)
    ax.set_xticklabels([SCENARIO_SHORT[s] for s in df.index], fontsize=8)
    ax.set_ylabel("Доля населения, %")
    ax.set_title("Экспозиция населения в 2056 году", fontsize=12, pad=10)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12), fontsize=8)
    style_axes(ax)
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    path = assets_dir / "04_population_exposure_ru.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path.name


def plot_country_outliers(country: pd.DataFrame, assets_dir: Path) -> str:
    final_year = int(country["year"].max())
    df = country[country["year"] == final_year].copy()
    fossil = df[df["scenario"] == "ssp5_fossil_growth"].sort_values("gdp_index_mean", ascending=False).head(8).copy()
    transition = df[df["scenario"] == "ssp1_sustainability"].sort_values("gdp_index_mean").head(8).copy()
    fossil["name_ru"] = fossil["agent_name"].map(country_ru)
    transition["name_ru"] = transition["agent_name"].map(country_ru)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6))
    axes[0].barh(fossil["name_ru"], fossil["gdp_index_mean"], color="#111827")
    axes[0].invert_yaxis()
    axes[0].set_title("Максимальный прирост ВВП: SSP5", fontsize=10)
    axes[0].set_xlabel("Индекс ВВП")
    style_axes(axes[0])
    axes[1].barh(transition["name_ru"], transition["gdp_index_mean"], color="#1f8a70")
    axes[1].invert_yaxis()
    axes[1].set_title("Слабые исходы ВВП: SSP1", fontsize=10)
    axes[1].set_xlabel("Индекс ВВП")
    style_axes(axes[1])
    fig.suptitle("Страновые выбросы распределения в 2056 году", fontsize=13, x=0.02, ha="left")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    path = assets_dir / "05_country_outliers_ru.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path.name


def plot_focus_heatmap(focus: pd.DataFrame, assets_dir: Path) -> str:
    final_year = int(focus["year"].max())
    df = focus[focus["year"] == final_year].copy()
    base = focus[focus["year"] == focus["year"].min()].set_index(["scenario", "seed", "agent_id"])
    df["gdp_index"] = [
        row.gdp / max(base.loc[(row.scenario, row.seed, row.agent_id), "gdp"], 1e-9) * 100.0
        for row in df.itertuples(index=False)
    ]
    summary = df.groupby(["scenario", "agent_id"])["gdp_index"].mean().reset_index()
    pivot = summary.pivot(index="agent_id", columns="scenario", values="gdp_index")
    pivot = pivot[[col for col in ORDER if col in pivot.columns]]
    fig, ax = plt.subplots(figsize=(10.5, 4.9))
    im = ax.imshow(pivot.values, aspect="auto", cmap="PuBuGn")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([SCENARIO_SHORT[s] for s in pivot.columns], fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_title("Индекс ВВП ключевых стран в 2056 году", fontsize=12, pad=10)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, f"{pivot.values[i, j]:.0f}", ha="center", va="center", fontsize=7)
    cbar = fig.colorbar(im, ax=ax, shrink=0.85)
    cbar.set_label("Индекс ВВП", fontsize=8)
    fig.tight_layout()
    path = assets_dir / "06_focus_country_heatmap_ru.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path.name


def build_tables(data: dict[str, pd.DataFrame]) -> dict[str, str | pd.DataFrame]:
    final = data["final"].copy()
    global_table = final[
        [
            "scenario",
            "gdp_index_mean",
            "temperature_mean",
            "emissions_index_mean",
            "tension_mean",
            "trust_mean",
            "energy_gap_log_mean",
            "avg_relation_conflict_mean",
            "migration_pressure_mean",
        ]
    ].copy()
    global_table["scenario"] = global_table["scenario"].map(SCENARIO_LABELS)
    global_table = global_table.rename(
        columns={
            "scenario": "Сценарий",
            "gdp_index_mean": "ВВП idx",
            "temperature_mean": "T, °C",
            "emissions_index_mean": "Выбросы idx",
            "tension_mean": "Напряж.",
            "trust_mean": "Доверие",
            "energy_gap_log_mean": "Энерг. стресс",
            "avg_relation_conflict_mean": "Конфликт",
            "migration_pressure_mean": "Миграция",
        }
    )
    for col in global_table.columns:
        if col == "Сценарий":
            continue
        digits = 3 if col in {"Напряж.", "Доверие", "Энерг. стресс", "Конфликт", "Миграция"} else 1
        if col == "T, °C":
            digits = 3
        global_table[col] = global_table[col].map(lambda x, d=digits: fmt(x, d))

    region = data["region"]
    final_year = int(region["year"].max())
    rf = region[region["year"] == final_year]
    region_rows = []
    for scenario in ["ssp5_fossil_growth", "ssp1_sustainability", "delayed_transition"]:
        top = rf[rf["scenario"] == scenario].sort_values("gdp_index_mean", ascending=False).head(3)
        stressed = rf[rf["scenario"] == scenario].sort_values("social_stress_share_mean", ascending=False).head(2)
        region_rows.append(
            {
                "Сценарий": SCENARIO_LABELS[scenario],
                "Лидеры выпуска": "; ".join(
                    f"{region_ru(r.region)} ({fmt(r.gdp_index_mean, 0)})" for r in top.itertuples(index=False)
                ),
                "Макс. соцстресс": "; ".join(
                    f"{region_ru(r.region)} ({pct(r.social_stress_share_mean, 0)})" for r in stressed.itertuples(index=False)
                ),
            }
        )

    country = data["country"]
    cf = country[country["year"] == country["year"].max()].copy()
    robust = (
        cf.groupby(["agent_id", "agent_name", "region"])
        .agg(
            mean_gdp_index=("gdp_index_mean", "mean"),
            min_gdp_index=("gdp_index_mean", "min"),
            mean_tension=("tension_mean", "mean"),
            mean_trust=("trust_mean", "mean"),
            max_climate_risk=("climate_risk_mean", "max"),
        )
        .reset_index()
    )
    robust["stress_score"] = (
        (100.0 - robust["min_gdp_index"]).clip(lower=0)
        + 60.0 * robust["mean_tension"]
        + 40.0 * (1.0 - robust["mean_trust"])
        + 25.0 * robust["max_climate_risk"]
    )
    stressed = robust.sort_values("stress_score", ascending=False).head(12)
    stressed_table = stressed[
        ["agent_id", "agent_name", "region", "min_gdp_index", "mean_tension", "mean_trust", "max_climate_risk"]
    ].copy()
    stressed_table["agent_name"] = stressed_table["agent_name"].map(country_ru)
    stressed_table["region"] = stressed_table["region"].map(region_ru)
    stressed_table.columns = ["ID", "Страна / агрегат", "Регион", "Мин. ВВП idx", "Средн. напряж.", "Средн. доверие", "Макс. клим. риск"]
    for col in ["Мин. ВВП idx", "Средн. напряж.", "Средн. доверие", "Макс. клим. риск"]:
        stressed_table[col] = stressed_table[col].map(lambda x: fmt(x, 2))

    return {
        "global_df": global_table,
        "region_df": pd.DataFrame(region_rows),
        "stressed_df": stressed_table,
        "global": table_html(global_table, classes="data-table compact"),
        "region": table_html(pd.DataFrame(region_rows), classes="data-table"),
        "stressed": table_html(stressed_table, classes="data-table compact"),
    }


def facts(data: dict[str, pd.DataFrame]) -> dict[str, object]:
    final = data["final"].set_index("scenario")
    region = data["region"]
    country = data["country"]
    exposure = population_exposure(data["all_actor"]).set_index("scenario")
    final_year = int(region["year"].max())
    rf = region[region["year"] == final_year]
    cf = country[country["year"] == final_year]
    ssp1 = final.loc["ssp1_sustainability"]
    ssp5 = final.loc["ssp5_fossil_growth"]
    delayed = final.loc["delayed_transition"]
    best_gdp = data["final"].sort_values("gdp_index_mean", ascending=False).iloc[0]
    best_climate = data["final"].sort_values("temperature_mean").iloc[0]
    worst_conflict = data["final"].sort_values("avg_relation_conflict_mean", ascending=False).iloc[0]
    top_regions_ssp5 = rf[rf["scenario"] == "ssp5_fossil_growth"].sort_values("gdp_index_mean", ascending=False).head(3)
    top_regions_ssp1 = rf[rf["scenario"] == "ssp1_sustainability"].sort_values("gdp_index_mean", ascending=False).head(3)
    weak_regions_ssp1 = rf[rf["scenario"] == "ssp1_sustainability"].sort_values("gdp_index_mean").head(2)
    top_countries_ssp5 = cf[cf["scenario"] == "ssp5_fossil_growth"].sort_values("gdp_index_mean", ascending=False).head(5)
    weak_countries_ssp1 = cf[cf["scenario"] == "ssp1_sustainability"].sort_values("gdp_index_mean").head(5)
    focus_values = cf[cf["agent_name"].isin(["United States", "China", "India", "Germany", "Saudi Arabia", "Brazil"])]
    return {
        "final": final,
        "ssp1": ssp1,
        "ssp5": ssp5,
        "delayed": delayed,
        "best_gdp": best_gdp,
        "best_climate": best_climate,
        "worst_conflict": worst_conflict,
        "exposure": exposure,
        "top_regions_ssp5": top_regions_ssp5,
        "top_regions_ssp1": top_regions_ssp1,
        "weak_regions_ssp1": weak_regions_ssp1,
        "top_countries_ssp5": top_countries_ssp5,
        "weak_countries_ssp1": weak_countries_ssp1,
        "focus_values": focus_values,
        "gdp_gap": float(ssp5["gdp_index_mean"] - ssp1["gdp_index_mean"]),
        "gdp_gap_rel": float(ssp5["gdp_index_mean"] / ssp1["gdp_index_mean"] - 1.0),
        "warming_gap": float(ssp5["temperature_mean"] - ssp1["temperature_mean"]),
        "emissions_ratio": float(ssp5["emissions_index_mean"] / ssp1["emissions_index_mean"]),
    }


def list_join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " и " + items[-1]


def render_html(run_dir: Path, data: dict[str, pd.DataFrame], asset_names: dict[str, str]) -> Path:
    tables = build_tables(data)
    f = facts(data)
    final = f["final"]
    ssp1 = f["ssp1"]
    ssp5 = f["ssp5"]
    delayed = f["delayed"]
    exposure = f["exposure"]
    best_gdp = f["best_gdp"]
    best_climate = f["best_climate"]
    worst_conflict = f["worst_conflict"]
    img = {key: f"report_assets_ru/{value}" for key, value in asset_names.items()}
    top_regions_ssp5 = "; ".join(
        f"{region_ru(r.region)} {fmt(r.gdp_index_mean, 1)}" for r in f["top_regions_ssp5"].itertuples(index=False)
    )
    top_regions_ssp1 = "; ".join(
        f"{region_ru(r.region)} {fmt(r.gdp_index_mean, 1)}" for r in f["top_regions_ssp1"].itertuples(index=False)
    )
    weak_regions_ssp1 = "; ".join(
        f"{region_ru(r.region)} {fmt(r.gdp_index_mean, 1)}" for r in f["weak_regions_ssp1"].itertuples(index=False)
    )
    top_countries_ssp5 = "; ".join(
        f"{country_ru(r.agent_name)} {fmt(r.gdp_index_mean, 1)}" for r in f["top_countries_ssp5"].itertuples(index=False)
    )
    weak_countries_ssp1 = "; ".join(
        f"{country_ru(r.agent_name)} {fmt(r.gdp_index_mean, 1)}" for r in f["weak_countries_ssp1"].itertuples(index=False)
    )
    exp_ssp1 = exposure.loc["ssp1_sustainability"]
    exp_ssp3 = exposure.loc["ssp3_fragmentation"]
    exp_ssp5 = exposure.loc["ssp5_fossil_growth"]
    exp_delayed = exposure.loc["delayed_transition"]
    html_text = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GIM18: климато-энергетический стресс-тест</title>
  <style>
    :root {{ --ink:#111827; --muted:#5b6472; --line:#e5e7eb; --paper:#fbfaf7; --card:#ffffff; --green:#1f8a70; --gold:#b88a00; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--paper); color:var(--ink); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif; line-height:1.5; }}
    .page {{ max-width:1180px; margin:0 auto; padding:44px 34px 80px; }}
    header {{ border-bottom:1px solid var(--line); padding-bottom:24px; margin-bottom:28px; }}
    .eyebrow {{ color:var(--green); text-transform:uppercase; letter-spacing:.14em; font-size:12px; font-weight:750; }}
    h1 {{ font-size:42px; line-height:1.04; margin:12px 0 14px; letter-spacing:-.035em; max-width:980px; }}
    h2 {{ font-size:24px; margin:38px 0 14px; letter-spacing:-.02em; }}
    p {{ color:#263241; margin:0 0 12px; }}
    .lead {{ font-size:18px; color:#263241; max-width:980px; }}
    .meta {{ display:flex; gap:20px; flex-wrap:wrap; margin-top:18px; color:var(--muted); font-size:13px; }}
    .cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin:24px 0 28px; }}
    .card {{ background:#fff; border:1px solid var(--line); border-radius:16px; padding:18px; box-shadow:0 1px 2px rgba(17,24,39,.04); }}
    .metric {{ font-size:28px; font-weight:760; letter-spacing:-.03em; }}
    .label {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.09em; font-weight:750; }}
    .note {{ color:var(--muted); font-size:13px; margin-top:6px; }}
    .grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:22px; align-items:start; }}
    figure {{ margin:18px 0 28px; background:#fff; border:1px solid var(--line); border-radius:18px; padding:16px; }}
    figure img {{ display:block; width:100%; height:auto; border-radius:10px; }}
    figcaption {{ color:var(--muted); font-size:12px; margin-top:10px; }}
    .data-table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid var(--line); border-radius:14px; overflow:hidden; font-size:13px; }}
    .data-table th {{ text-align:left; background:#f3f4f6; color:#374151; font-size:11px; text-transform:uppercase; letter-spacing:.06em; }}
    .data-table th,.data-table td {{ padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
    .data-table tr:last-child td {{ border-bottom:none; }}
    .compact td,.compact th {{ padding:7px 8px; font-size:12px; }}
    .bullets {{ display:grid; gap:10px; margin:12px 0; }}
    .bullet {{ background:#fff; border:1px solid var(--line); border-radius:14px; padding:14px 16px; }}
    .callout {{ border-left:4px solid var(--green); padding:10px 0 10px 16px; margin:18px 0; color:#263241; }}
    footer {{ margin-top:44px; border-top:1px solid var(--line); padding-top:18px; color:var(--muted); font-size:12px; }}
    @media (max-width:900px) {{ .cards,.grid-2 {{ grid-template-columns:1fr; }} h1 {{ font-size:32px; }} .page {{ padding:28px 18px 60px; }} }}
    @media print {{ body {{ background:#fff; }} .page {{ max-width:none; padding:24px; }} figure,.card,.data-table {{ break-inside:avoid; }} }}
  </style>
</head>
<body>
<main class="page">
  <header>
    <div class="eyebrow">GIM18 analytical report</div>
    <h1>Климато-энергетический стресс-тест мировой модели, 2026-2056</h1>
    <p class="lead">Ансамбль из 5 SSP-подобных режимов и 5 сидов сравнивает траектории ВВП, выбросов, температуры, социального напряжения, доверия, миграционного давления, энергетического дефицита и эндогенного геополитического риска. Войны не задавались извне: конфликт появляется только через динамику модели.</p>
    <div class="meta">
      <span>Папка прогона: <code>{esc(run_dir.name)}</code></span>
      <span>Сформировано: {datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
      <span>Панель: 57 стран/агрегатов, 5 сидов, 5 сценариев</span>
    </div>
  </header>

  <section class="cards">
    <div class="card"><div class="label">Лидер ВВП</div><div class="metric">{fmt(best_gdp['gdp_index_mean'],1)}</div><div class="note">{SCENARIO_LABELS[best_gdp['scenario']]}, индекс ВВП в 2056</div></div>
    <div class="card"><div class="label">Минимум потепления</div><div class="metric">{fmt(best_climate['temperature_mean'],2)} °C</div><div class="note">{SCENARIO_LABELS[best_climate['scenario']]}</div></div>
    <div class="card"><div class="label">Минимум выбросов</div><div class="metric">{fmt(ssp1['emissions_index_mean'],1)}</div><div class="note">SSP1, индекс годовых выбросов</div></div>
    <div class="card"><div class="label">Активные войны</div><div class="metric">{fmt(final['war_pairs_mean'].max(),1)}</div><div class="note">финальное среднее по ансамблю</div></div>
  </section>

  <section>
    <h2>Выводы</h2>
    <div class="bullets">
      <div class="bullet"><strong>Экономический максимум дает ископаемый рост.</strong> В SSP5 индекс ВВП достигает {fmt(ssp5['gdp_index_mean'],1)} к 2056 году. Это на {fmt(f['gdp_gap'],1)} пункта, или на {pct(f['gdp_gap_rel'],1)}, выше SSP1 ({fmt(ssp1['gdp_index_mean'],1)}). Цена траектории: температура {fmt(ssp5['temperature_mean'],3)} °C и индекс годовых выбросов {fmt(ssp5['emissions_index_mean'],1)}.</div>
      <div class="bullet"><strong>Климатический минимум находится в SSP1.</strong> В устойчивом сценарии температура равна {fmt(ssp1['temperature_mean'],3)} °C, выбросы {fmt(ssp1['emissions_index_mean'],1)}, энергетический стресс log10(1+дефицит) {fmt(ssp1['energy_gap_log_mean'],3)}. Разница с SSP5 по температуре составляет {fmt(f['warming_gap'],3)} °C, по выбросам SSP5 выше в {fmt(f['emissions_ratio'],2)} раза.</div>
      <div class="bullet"><strong>Отложенный переход является компромиссом по выпуску и выбросам.</strong> Он дает ВВП {fmt(delayed['gdp_index_mean'],1)}, выбросы {fmt(delayed['emissions_index_mean'],1)} и температуру {fmt(delayed['temperature_mean'],3)} °C. Это близко к низкоэмиссионному кластеру, но социальное напряжение остается высоким: {fmt(delayed['tension_mean'],3)} при доверии {fmt(delayed['trust_mean'],3)}.</div>
      <div class="bullet"><strong>Военный исход не реализуется, но давление на отношения растет.</strong> Во всех сценариях финальное число пар в войне равно {fmt(final['war_pairs_mean'].max(),1)}, однако средний двусторонний конфликт достигает {fmt(worst_conflict['avg_relation_conflict_mean'],3)} в {SCENARIO_LABELS[worst_conflict['scenario']]}. Это индикатор предкризисной среды: барьеры торговли, низкое доверие и социальное напряжение.</div>
    </div>
  </section>

  <section>
    <h2>Сценарная таблица</h2>
    {tables['global']}
  </section>

  <section>
    <h2>Глобальные траектории</h2>
    <figure><img src="{img['global']}" alt="Глобальные траектории"><figcaption>ВВП, температура, выбросы и конфликтное давление. Все значения — средние по 5 сидам.</figcaption></figure>
    <div class="grid-2">
      <figure><img src="{img['tradeoff']}" alt="Компромисс выпуск-климат"><figcaption>Размер точки пропорционален индексу финальных выбросов. SSP5 — фронтир выпуска; SSP1 — фронтир климатического риска.</figcaption></figure>
      <figure><img src="{img['population']}" alt="Экспозиция населения"><figcaption>Доля населения в высоком соцстрессе: SSP1 {pct(exp_ssp1['high_social_stress_pop'],1)}, отложенный переход {pct(exp_delayed['high_social_stress_pop'],1)}, SSP5 {pct(exp_ssp5['high_social_stress_pop'],1)}, SSP3 {pct(exp_ssp3['high_social_stress_pop'],1)}.</figcaption></figure>
    </div>
  </section>

  <section>
    <h2>Экономика и страны</h2>
    <p>Рост концентрируется в высокодоходных, технологически сильных и институционально устойчивых экономиках. В SSP5 лидируют {top_countries_ssp5}. В SSP1 слабейшие исходы ВВП дают {weak_countries_ssp1}. Это не прогноз фактического ВВП, а индексная реакция модели на заданные режимы политики.</p>
    <figure><img src="{img['countries']}" alt="Страновые выбросы распределения"><figcaption>Слева — лидеры прироста в SSP5; справа — нижний хвост распределения ВВП в SSP1.</figcaption></figure>
    <figure><img src="{img['focus']}" alt="Ключевые страны"><figcaption>Ключевые страны показывают асимметрию: США и Китай слабее реагируют на переходные режимы, Индия и Германия сохраняют более высокий индекс выпуска.</figcaption></figure>
  </section>

  <section>
    <h2>Регионы и население</h2>
    <p>В SSP5 региональные лидеры выпуска: {top_regions_ssp5}. В SSP1 верхний кластер: {top_regions_ssp1}; нижний кластер: {weak_regions_ssp1}. По населению высокий климатический риск выше в фрагментации и ископаемом росте: SSP3 {pct(exp_ssp3['high_climate_risk_pop'],1)}, SSP5 {pct(exp_ssp5['high_climate_risk_pop'],1)} против SSP1 {pct(exp_ssp1['high_climate_risk_pop'],1)}.</p>
    {tables['region']}
    <figure><img src="{img['regions']}" alt="Региональный heatmap"><figcaption>Индекс ВВП по регионам и сценариям в 2056 году, среднее по ансамблю.</figcaption></figure>
  </section>

  <section>
    <h2>Устойчиво уязвимые страны и агрегаты</h2>
    <p>Рейтинг ниже использует минимальный индекс ВВП по сценариям, среднее социальное напряжение, среднее доверие и максимальный климатический риск. Это не список «проигравших» одного сценария, а индикатор широкой уязвимости в сценарном пространстве.</p>
    {tables['stressed']}
  </section>

  <section>
    <h2>Механика и ограничения</h2>
    <p>Сценарии переводят SSP-нарративы в существующие рычаги GIM18: налог на топливо, интенсивность климатической политики, R&D, социальные расходы, военная позиция, торговые ограничения, рост спроса на энергию, эффективность и адаптация. Ядро перехода состояния остается прежним <code>step_world</code>.</p>
    <div class="callout">Энергетический стресс показан как log10(1+дефицит), потому что сырой дефицит очень велик в текущей калибровке блока ресурсов. Для сравнения сценариев используется лог-метрика; направление результата внутри эксперимента устойчиво.</div>
  </section>

  <footer>GIM18, климато-энергетический стресс-тест. Источники: <code>final_summary.csv</code>, <code>trajectory_summary.csv</code>, <code>all_actor_trajectories.csv</code>, <code>country_summary.csv</code>, <code>region_summary.csv</code>.</footer>
</main>
</body>
</html>
"""
    output = run_dir / "climate_energy_stress_report_ru.html"
    output.write_text(html_text, encoding="utf-8")
    return output


def add_wrapped(
    fig,
    text: str,
    x: float,
    y: float,
    width_chars: int,
    *,
    size: int = 10,
    weight: str = "normal",
    color: str = "#263241",
    line_gap: float = 1.22,
    family: str | None = None,
) -> float:
    lines: list[str] = []
    for part in text.split("\n"):
        if not part:
            lines.append("")
        else:
            lines.extend(textwrap.wrap(part, width=width_chars, break_long_words=False, replace_whitespace=False))
    page_height = fig.get_figheight()
    line_h = (size / 72.0) / page_height * line_gap
    for line in lines:
        fig.text(x, y, line, fontsize=size, fontweight=weight, color=color, va="top", family=family)
        y -= line_h
    return y


def card(fig, x: float, y: float, w: float, h: float, label: str, value: str, note: str, color: str = "#111827") -> None:
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.008,rounding_size=0.012",
        transform=fig.transFigure,
        fc="#ffffff",
        ec="#e5e7eb",
        lw=0.8,
    )
    fig.patches.append(box)
    fig.text(x + 0.015, y + h - 0.025, label.upper(), fontsize=7.5, color="#5b6472", weight="bold", va="top")
    fig.text(x + 0.015, y + h - 0.063, value, fontsize=18, color=color, weight="bold", va="top")
    fig.text(x + 0.015, y + 0.016, note, fontsize=7.5, color="#5b6472", va="bottom")


def add_image(fig, path: Path, x: float, y: float, w: float, h: float) -> None:
    ax = fig.add_axes([x, y, w, h])
    with Image.open(path) as image:
        ax.imshow(image)
    ax.axis("off")


def add_table_text(fig, df: pd.DataFrame, x: float, y: float, widths: list[int], *, size: int = 8) -> float:
    header = "  ".join(str(col)[:width].ljust(width) for col, width in zip(df.columns, widths))
    y = add_wrapped(
        fig,
        header,
        x,
        y,
        sum(widths) + 2 * len(widths),
        size=size,
        weight="bold",
        color="#111827",
        line_gap=1.05,
        family="DejaVu Sans Mono",
    )
    y -= 0.006
    for row in df.itertuples(index=False, name=None):
        line = "  ".join(str(value)[:width].ljust(width) for value, width in zip(row, widths))
        y = add_wrapped(
            fig,
            line,
            x,
            y,
            sum(widths) + 2 * len(widths),
            size=size,
            color="#263241",
            line_gap=1.05,
            family="DejaVu Sans Mono",
        )
    return y


def render_pdf(run_dir: Path, data: dict[str, pd.DataFrame], asset_names: dict[str, str]) -> Path:
    output = run_dir / "climate_energy_stress_report_ru.pdf"
    assets_dir = run_dir / "report_assets_ru"
    tables = build_tables(data)
    f = facts(data)
    final = f["final"]
    ssp1 = f["ssp1"]
    ssp5 = f["ssp5"]
    delayed = f["delayed"]
    exposure = f["exposure"]
    worst_conflict = f["worst_conflict"]
    page_size = (11.69, 8.27)

    with PdfPages(output) as pdf:
        fig = plt.figure(figsize=page_size, facecolor="#fbfaf7")
        fig.text(0.055, 0.925, "GIM18 analytical report", fontsize=8, color="#1f8a70", weight="bold")
        fig.text(0.055, 0.865, "Климато-энергетический стресс-тест, 2026-2056", fontsize=26, color="#111827", weight="bold")
        y = add_wrapped(
            fig,
            "Пять SSP-подобных режимов политики протестированы на 30-летнем горизонте. "
            "Войны не задавались извне: геополитический риск возникает через отношения, торговые барьеры, "
            "доверие, социальное напряжение и ресурсный стресс.",
            0.055,
            0.805,
            118,
            size=11,
        )
        y -= 0.02
        card_y = y - 0.145
        card(fig, 0.055, card_y, 0.20, 0.125, "Лидер ВВП", fmt(ssp5["gdp_index_mean"], 1), "SSP5, индекс ВВП", "#111827")
        card(fig, 0.275, card_y, 0.20, 0.125, "Минимум T", f"{fmt(ssp1['temperature_mean'], 3)} °C", "SSP1", "#1f8a70")
        card(fig, 0.495, card_y, 0.20, 0.125, "Выбросы SSP1", fmt(ssp1["emissions_index_mean"], 1), "индекс CO₂", "#1f8a70")
        card(fig, 0.715, card_y, 0.20, 0.125, "Активные войны", fmt(final["war_pairs_mean"].max(), 1), "финальное среднее", "#b88a00")
        y -= 0.200
        bullets = [
            f"SSP5 завершает период с ВВП {fmt(ssp5['gdp_index_mean'],1)}: на {fmt(f['gdp_gap'],1)} пункта выше SSP1 и на {fmt(ssp5['gdp_index_mean'] - delayed['gdp_index_mean'],1)} пункта выше отложенного перехода.",
            f"SSP1 минимизирует климатический риск: температура {fmt(ssp1['temperature_mean'],3)} °C, выбросы {fmt(ssp1['emissions_index_mean'],1)}, энергетический стресс {fmt(ssp1['energy_gap_log_mean'],3)}.",
            f"Отложенный переход дает ВВП {fmt(delayed['gdp_index_mean'],1)}, выбросы {fmt(delayed['emissions_index_mean'],1)} и напряжение {fmt(delayed['tension_mean'],3)}; это компромисс, но не социально мягкий путь.",
            f"Войны не реализуются: максимум war_pairs_mean равен {fmt(final['war_pairs_mean'].max(),1)}. При этом конфликтное давление доходит до {fmt(worst_conflict['avg_relation_conflict_mean'],3)} в {SCENARIO_LABELS[worst_conflict['scenario']]}.",
        ]
        for item in bullets:
            y = add_wrapped(fig, "• " + item, 0.07, y, 118, size=10)
            y -= 0.008
        y -= 0.01
        fig.text(0.055, y, "Сценарная таблица", fontsize=13, weight="bold", color="#111827", va="top")
        y -= 0.035
        add_table_text(fig, tables["global_df"], 0.055, y, [20, 8, 7, 10, 8, 8, 11, 9, 9], size=6.8)
        fig.text(0.055, 0.045, f"Источник: {run_dir.name}; 57 стран/агрегатов, 5 сидов, 5 сценариев.", fontsize=7.5, color="#5b6472")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        fig = plt.figure(figsize=page_size, facecolor="#ffffff")
        fig.text(0.055, 0.935, "1. Глобальная динамика", fontsize=17, weight="bold", color="#111827")
        add_image(fig, assets_dir / asset_names["global"], 0.055, 0.235, 0.89, 0.62)
        add_wrapped(
            fig,
            f"К 2056 году выпуск расходится сильнее, чем температура: SSP5 достигает {fmt(ssp5['gdp_index_mean'],1)}, "
            f"SSP1 — {fmt(ssp1['gdp_index_mean'],1)}, SSP2 — {fmt(final.loc['ssp2_middle_road','gdp_index_mean'],1)}, "
            f"SSP3 — {fmt(final.loc['ssp3_fragmentation','gdp_index_mean'],1)}. "
            f"Температурный диапазон между SSP1 и SSP5 составляет {fmt(f['warming_gap'],3)} °C.",
            0.07,
            0.17,
            132,
            size=10,
        )
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        fig = plt.figure(figsize=page_size, facecolor="#ffffff")
        fig.text(0.055, 0.935, "2. Компромисс выпуск-климат и население", fontsize=17, weight="bold", color="#111827")
        add_image(fig, assets_dir / asset_names["tradeoff"], 0.055, 0.47, 0.42, 0.39)
        add_image(fig, assets_dir / asset_names["population"], 0.535, 0.47, 0.42, 0.39)
        text_left = (
            f"SSP5 находится на фронтире выпуска: ВВП {fmt(ssp5['gdp_index_mean'],1)}, температура {fmt(ssp5['temperature_mean'],3)} °C, "
            f"выбросы {fmt(ssp5['emissions_index_mean'],1)}. SSP1 находится на климатическом фронтире: ВВП {fmt(ssp1['gdp_index_mean'],1)}, "
            f"температура {fmt(ssp1['temperature_mean'],3)} °C, выбросы {fmt(ssp1['emissions_index_mean'],1)}."
        )
        text_right = (
            f"Доля населения в высоком социальном стрессе: SSP1 {pct(exposure.loc['ssp1_sustainability','high_social_stress_pop'],1)}, "
            f"отложенный переход {pct(exposure.loc['delayed_transition','high_social_stress_pop'],1)}, "
            f"SSP5 {pct(exposure.loc['ssp5_fossil_growth','high_social_stress_pop'],1)}, "
            f"SSP3 {pct(exposure.loc['ssp3_fragmentation','high_social_stress_pop'],1)}. "
            f"Высокий климатический риск: SSP3 {pct(exposure.loc['ssp3_fragmentation','high_climate_risk_pop'],1)}, "
            f"SSP5 {pct(exposure.loc['ssp5_fossil_growth','high_climate_risk_pop'],1)}, SSP1 {pct(exposure.loc['ssp1_sustainability','high_climate_risk_pop'],1)}."
        )
        add_wrapped(fig, text_left, 0.065, 0.375, 62, size=9.5)
        add_wrapped(fig, text_right, 0.535, 0.375, 64, size=9.5)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        fig = plt.figure(figsize=page_size, facecolor="#ffffff")
        fig.text(0.055, 0.935, "3. Регионы", fontsize=17, weight="bold", color="#111827")
        add_image(fig, assets_dir / asset_names["regions"], 0.055, 0.31, 0.89, 0.56)
        top_regions_ssp5 = list_join(
            [f"{region_ru(r.region)} {fmt(r.gdp_index_mean,1)}" for r in f["top_regions_ssp5"].itertuples(index=False)]
        )
        top_regions_ssp1 = list_join(
            [f"{region_ru(r.region)} {fmt(r.gdp_index_mean,1)}" for r in f["top_regions_ssp1"].itertuples(index=False)]
        )
        weak_regions_ssp1 = list_join(
            [f"{region_ru(r.region)} {fmt(r.gdp_index_mean,1)}" for r in f["weak_regions_ssp1"].itertuples(index=False)]
        )
        add_wrapped(
            fig,
            f"В SSP5 лидируют {top_regions_ssp5}. В SSP1 верхний кластер — {top_regions_ssp1}; нижний кластер — {weak_regions_ssp1}. "
            "Смысл результата: малые и открытые высокодоходные регионы лучше конвертируют технологическую и институциональную базу в индексный рост, "
            "а крупные континентальные системы сильнее ограничены социально-энергетическим каналом.",
            0.07,
            0.24,
            132,
            size=10,
        )
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        fig = plt.figure(figsize=page_size, facecolor="#ffffff")
        fig.text(0.055, 0.935, "4. Страны и фокусные экономики", fontsize=17, weight="bold", color="#111827")
        add_image(fig, assets_dir / asset_names["countries"], 0.055, 0.50, 0.89, 0.36)
        add_image(fig, assets_dir / asset_names["focus"], 0.055, 0.13, 0.89, 0.31)
        top_countries = list_join(
            [f"{country_ru(r.agent_name)} {fmt(r.gdp_index_mean,1)}" for r in f["top_countries_ssp5"].itertuples(index=False)]
        )
        weak_countries = list_join(
            [f"{country_ru(r.agent_name)} {fmt(r.gdp_index_mean,1)}" for r in f["weak_countries_ssp1"].itertuples(index=False)]
        )
        add_wrapped(
            fig,
            f"В SSP5 максимальные индексы ВВП получают {top_countries}. "
            f"В SSP1 нижний хвост формируют {weak_countries}. "
            "График фокусных стран показывает, что США и Китай более чувствительны к переходным режимам, тогда как Германия и Индия сохраняют более высокий выпуск.",
            0.07,
            0.075,
            130,
            size=9.5,
        )
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        fig = plt.figure(figsize=page_size, facecolor="#fbfaf7")
        fig.text(0.055, 0.925, "5. Метод и границы интерпретации", fontsize=17, weight="bold", color="#111827")
        y = 0.86
        method = [
            "Сценарии задают не CMIP/IPCC forcing pathways, а сравнительные режимы политики внутри GIM18. SSP-нарративы переводятся в налог на топливо, климатическую политику, R&D, социальные расходы, военную позицию, торговые ограничения, спрос на энергию, эффективность и адаптацию.",
            "Ядро динамики остается прежним step_world. Поэтому отчет проверяет эндогенные механизмы модели: выпуск, климатические потери, ресурсный стресс, миграционное давление, социальную стабильность, торговые барьеры и конфликтное давление.",
            f"Энергетический стресс дан как log10(1+дефицит). В финале он равен {fmt(ssp1['energy_gap_log_mean'],3)} в SSP1, {fmt(final.loc['ssp2_middle_road','energy_gap_log_mean'],3)} в SSP2, {fmt(final.loc['ssp3_fragmentation','energy_gap_log_mean'],3)} в SSP3, {fmt(ssp5['energy_gap_log_mean'],3)} в SSP5 и {fmt(delayed['energy_gap_log_mean'],3)} в отложенном переходе.",
            "Главное ограничение: абсолютные уровни не следует читать как прогноз мирового ВВП или температуры. Это индексные и сравнительные результаты текущей калибровки GIM18.",
        ]
        for paragraph in method:
            y = add_wrapped(fig, paragraph, 0.065, y, 125, size=10.5)
            y -= 0.035
        fig.text(0.065, 0.20, "Файлы данных", fontsize=12, weight="bold", color="#111827")
        add_wrapped(
            fig,
            "final_summary.csv, trajectory_summary.csv, all_actor_trajectories.csv, country_summary.csv, region_summary.csv, action_log.csv",
            0.065,
            0.165,
            125,
            size=9.5,
            color="#5b6472",
        )
        fig.text(0.065, 0.055, f"Сформировано из локальной папки: {run_dir}", fontsize=7.5, color="#5b6472")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    return output


def build_report(run_dir: Path) -> tuple[Path, Path]:
    run_dir = run_dir.resolve()
    assets_dir = run_dir / "report_assets_ru"
    assets_dir.mkdir(exist_ok=True)
    data = prepare_data(run_dir)
    exposure = population_exposure(data["all_actor"])
    asset_names = {
        "global": plot_global_panel(data["summary"], assets_dir),
        "tradeoff": plot_tradeoff(data["final"], assets_dir),
        "regions": plot_region_heatmap(data["region"], assets_dir),
        "population": plot_population_exposure(exposure, assets_dir),
        "countries": plot_country_outliers(data["country"], assets_dir),
        "focus": plot_focus_heatmap(data["focus"], assets_dir),
    }
    html_output = render_html(run_dir, data, asset_names)
    pdf_output = render_pdf(run_dir, data, asset_names)
    return html_output, pdf_output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Russian HTML and PDF report for GIM18 climate/energy run.")
    parser.add_argument("run_dir", help="Path to results/climate_energy_stress-* directory")
    args = parser.parse_args()
    html_output, pdf_output = build_report(Path(args.run_dir))
    print(html_output)
    print(pdf_output)


if __name__ == "__main__":
    main()
