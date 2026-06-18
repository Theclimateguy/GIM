#!/usr/bin/env python3
"""Build a polished HTML report for a GIM17 climate/energy stress-test run."""

from __future__ import annotations

import argparse
import html
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


SCENARIO_LABELS = {
    "ssp1_sustainability": "SSP1 sustainability",
    "ssp2_middle_road": "SSP2 middle road",
    "ssp3_fragmentation": "SSP3 fragmentation",
    "ssp5_fossil_growth": "SSP5 fossil growth",
    "delayed_transition": "Delayed transition",
}

SCENARIO_COLORS = {
    "ssp1_sustainability": "#1f8a70",
    "ssp2_middle_road": "#4b6cb7",
    "ssp3_fragmentation": "#b65f28",
    "ssp5_fossil_growth": "#111827",
    "delayed_transition": "#b88a00",
}

ORDER = [
    "ssp1_sustainability",
    "ssp2_middle_road",
    "ssp3_fragmentation",
    "ssp5_fossil_growth",
    "delayed_transition",
]


def fmt(value: float, digits: int = 1) -> str:
    return f"{float(value):,.{digits}f}"


def pct(value: float, digits: int = 0) -> str:
    return f"{100.0 * float(value):,.{digits}f}%"


def esc(value: object) -> str:
    return html.escape(str(value))


def table_html(df: pd.DataFrame, *, classes: str = "") -> str:
    rows = []
    rows.append("<thead><tr>" + "".join(f"<th>{esc(col)}</th>" for col in df.columns) + "</tr></thead>")
    body = []
    for row in df.itertuples(index=False, name=None):
        body.append("<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>")
    rows.append("<tbody>" + "".join(body) + "</tbody>")
    return f"<table class=\"{classes}\">{''.join(rows)}</table>"


def prepare_data(run_dir: Path) -> dict[str, pd.DataFrame]:
    data = {
        "final": pd.read_csv(run_dir / "final_summary.csv"),
        "summary": pd.read_csv(run_dir / "trajectory_summary.csv"),
        "region": pd.read_csv(run_dir / "region_summary.csv"),
        "country": pd.read_csv(run_dir / "country_summary.csv"),
        "all_actor": pd.read_csv(run_dir / "all_actor_trajectories.csv"),
        "focus": pd.read_csv(run_dir / "focus_actor_trajectories.csv"),
    }
    for key, df in data.items():
        if "scenario" in df.columns:
            df["scenario_label"] = df["scenario"].map(SCENARIO_LABELS).fillna(df["scenario"])
    return data


def style_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, color="#e5e7eb", linewidth=0.8)
    ax.tick_params(colors="#374151", labelsize=8)
    ax.title.set_color("#111827")
    ax.xaxis.label.set_color("#374151")
    ax.yaxis.label.set_color("#374151")


def plot_global_panel(summary: pd.DataFrame, assets_dir: Path) -> str:
    metrics = [
        ("gdp_index_mean", "GDP index, 2026=100"),
        ("temperature_mean", "Temperature anomaly, C"),
        ("emissions_index_mean", "Annual CO2 emissions index"),
        ("avg_relation_conflict_mean", "Mean bilateral conflict"),
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
    fig.suptitle("Global trajectories under climate/energy policy modes", fontsize=13, x=0.02, ha="left")
    fig.tight_layout(rect=[0, 0.08, 1, 0.95])
    path = assets_dir / "01_global_trajectories.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path.name


def plot_tradeoff(final: pd.DataFrame, assets_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(8.7, 5.6))
    points = []
    for scenario in ORDER:
        row = final[final["scenario"] == scenario].iloc[0]
        x = float(row["temperature_mean"])
        y = float(row["gdp_index_mean"])
        points.append((x, y))
        ax.scatter(
            x,
            y,
            s=90 + 5 * row["emissions_index_mean"],
            color=SCENARIO_COLORS[scenario],
            alpha=0.9,
            edgecolor="white",
            linewidth=1.2,
        )
        offsets = {
            "ssp1_sustainability": (12, 12, "left"),
            "ssp2_middle_road": (-22, -26, "right"),
            "ssp3_fragmentation": (-8, 18, "right"),
            "ssp5_fossil_growth": (-10, 20, "right"),
            "delayed_transition": (30, 22, "left"),
        }
        dx, dy, ha = offsets.get(scenario, (8, 8, "left"))
        ax.annotate(
            SCENARIO_LABELS[scenario],
            xy=(x, y),
            xytext=(dx, dy),
            textcoords="offset points",
            ha=ha,
            va="center",
            fontsize=8,
            color="#111827",
        )
    xs, ys = zip(*points)
    ax.set_xlim(min(xs) - 0.006, max(xs) + 0.006)
    ax.set_ylim(min(ys) - 4, max(ys) + 4)
    ax.set_title("Output vs warming trade-off at 2056", fontsize=12, pad=10)
    ax.set_xlabel("Temperature anomaly, C")
    ax.set_ylabel("Global GDP index, 2026=100")
    style_axes(ax)
    fig.tight_layout()
    path = assets_dir / "02_tradeoff_gdp_temperature.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path.name


def plot_region_heatmap(region: pd.DataFrame, assets_dir: Path) -> str:
    final_year = int(region["year"].max())
    df = region[region["year"] == final_year].copy()
    pivot = df.pivot_table(index="region", columns="scenario", values="gdp_index_mean", aggfunc="mean")
    pivot = pivot[[col for col in ORDER if col in pivot.columns]]
    pivot = pivot.sort_values("ssp5_fossil_growth", ascending=False)
    labels = [SCENARIO_LABELS[col].replace(" ", "\n", 1) for col in pivot.columns]
    fig, ax = plt.subplots(figsize=(10.8, 5.8))
    im = ax.imshow(pivot.values, aspect="auto", cmap="YlGnBu")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_title("Regional GDP index at 2056", fontsize=12, pad=10)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            value = pivot.values[i, j]
            ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=7, color="#111827")
    cbar = fig.colorbar(im, ax=ax, shrink=0.82)
    cbar.set_label("GDP index, 2026=100", fontsize=8)
    fig.tight_layout()
    path = assets_dir / "03_region_gdp_heatmap.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path.name


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
                ].clip(lower=0).sum()
                / max(pop, 1.0),
                "high_climate_risk_pop": group.loc[group["climate_risk"] >= 0.65, "population"].clip(lower=0).sum()
                / max(pop, 1.0),
                "low_food_buffer_pop": group.loc[group["food_reserve_years"] <= 0.25, "population"].clip(lower=0).sum()
                / max(pop, 1.0),
            }
        )
    return pd.DataFrame(rows).groupby("scenario", as_index=False).mean(numeric_only=True)


def plot_population_exposure(exposure: pd.DataFrame, assets_dir: Path) -> str:
    metrics = [
        ("high_social_stress_pop", "Social stress"),
        ("high_climate_risk_pop", "Climate risk"),
        ("low_food_buffer_pop", "Low food buffer"),
    ]
    df = exposure.set_index("scenario").loc[[s for s in ORDER if s in exposure["scenario"].values]]
    x = np.arange(len(df.index))
    width = 0.23
    fig, ax = plt.subplots(figsize=(11, 5.4))
    for idx, (col, label) in enumerate(metrics):
        ax.bar(x + (idx - 1) * width, df[col] * 100.0, width=width, label=label)
    ax.set_xticks(x)
    ax.set_xticklabels([SCENARIO_LABELS[s].replace(" ", "\n", 1) for s in df.index], fontsize=8)
    ax.set_ylabel("Population share, %")
    ax.set_title("Population exposure at 2056", fontsize=12, pad=10)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12), fontsize=8)
    style_axes(ax)
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    path = assets_dir / "04_population_exposure.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path.name


def plot_country_outliers(country: pd.DataFrame, assets_dir: Path) -> str:
    final_year = int(country["year"].max())
    df = country[country["year"] == final_year].copy()
    fossil = df[df["scenario"] == "ssp5_fossil_growth"].sort_values("gdp_index_mean", ascending=False).head(8)
    transition = df[df["scenario"] == "ssp1_sustainability"].sort_values("gdp_index_mean").head(8)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6))
    axes[0].barh(fossil["agent_name"], fossil["gdp_index_mean"], color="#111827")
    axes[0].invert_yaxis()
    axes[0].set_title("Largest GDP gains: fossil-growth path", fontsize=10)
    axes[0].set_xlabel("GDP index")
    style_axes(axes[0])
    axes[1].barh(transition["agent_name"], transition["gdp_index_mean"], color="#1f8a70")
    axes[1].invert_yaxis()
    axes[1].set_title("Weakest GDP outcomes: sustainability path", fontsize=10)
    axes[1].set_xlabel("GDP index")
    style_axes(axes[1])
    fig.suptitle("Country-level outliers at 2056", fontsize=13, x=0.02, ha="left")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    path = assets_dir / "05_country_outliers.png"
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
    ax.set_xticklabels([SCENARIO_LABELS[s].replace(" ", "\n", 1) for s in pivot.columns], fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_title("Focus-country GDP index at 2056", fontsize=12, pad=10)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, f"{pivot.values[i, j]:.0f}", ha="center", va="center", fontsize=7)
    cbar = fig.colorbar(im, ax=ax, shrink=0.85)
    cbar.set_label("GDP index", fontsize=8)
    fig.tight_layout()
    path = assets_dir / "06_focus_country_heatmap.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path.name


def build_tables(data: dict[str, pd.DataFrame]) -> dict[str, str]:
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
    rename = {
        "scenario": "Scenario",
        "gdp_index_mean": "GDP idx",
        "temperature_mean": "Temp C",
        "emissions_index_mean": "Emissions idx",
        "tension_mean": "Tension",
        "trust_mean": "Trust",
        "energy_gap_log_mean": "Energy stress",
        "avg_relation_conflict_mean": "Conflict",
        "migration_pressure_mean": "Migration proxy",
    }
    global_table = global_table.rename(columns=rename)
    for col in global_table.columns:
        if col != "Scenario":
            global_table[col] = global_table[col].map(lambda x: fmt(x, 3 if x < 10 else 1))

    region = data["region"]
    rf = region[region["year"] == region["year"].max()]
    region_rows = []
    for scenario in ["ssp1_sustainability", "ssp5_fossil_growth", "delayed_transition"]:
        top = rf[rf["scenario"] == scenario].sort_values("gdp_index_mean", ascending=False).head(3)
        stressed = rf[rf["scenario"] == scenario].sort_values("social_stress_share_mean", ascending=False).head(2)
        region_rows.append(
            {
                "Scenario": SCENARIO_LABELS[scenario],
                "Top output regions": "; ".join(
                    f"{r.region} ({r.gdp_index_mean:.0f})" for r in top.itertuples(index=False)
                ),
                "Highest social stress": "; ".join(
                    f"{r.region} ({100*r.social_stress_share_mean:.0f}%)" for r in stressed.itertuples(index=False)
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
    stressed_table.columns = ["ID", "Country / aggregate", "Region", "Min GDP idx", "Mean tension", "Mean trust", "Max climate risk"]
    for col in ["Min GDP idx", "Mean tension", "Mean trust", "Max climate risk"]:
        stressed_table[col] = stressed_table[col].map(lambda x: fmt(x, 2))

    return {
        "global": table_html(global_table, classes="data-table compact"),
        "region": table_html(pd.DataFrame(region_rows), classes="data-table"),
        "stressed_countries": table_html(stressed_table, classes="data-table compact"),
    }


def render_html(run_dir: Path, data: dict[str, pd.DataFrame], assets: list[str]) -> Path:
    final = data["final"]
    exposure = population_exposure(data["all_actor"])
    tables = build_tables(data)
    best_gdp = final.sort_values("gdp_index_mean", ascending=False).iloc[0]
    best_climate = final.sort_values("temperature_mean", ascending=True).iloc[0]
    best_energy = final.sort_values("energy_gap_log_mean", ascending=True).iloc[0]
    worst_conflict = final.sort_values("avg_relation_conflict_mean", ascending=False).iloc[0]
    exp_table = exposure.set_index("scenario")
    ssp1 = final[final["scenario"] == "ssp1_sustainability"].iloc[0]
    ssp5 = final[final["scenario"] == "ssp5_fossil_growth"].iloc[0]
    delayed = final[final["scenario"] == "delayed_transition"].iloc[0]

    img = {Path(name).stem: f"report_assets/{name}" for name in assets}
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GIM17 Climate/Energy Stress Test</title>
  <style>
    :root {{
      --ink:#111827; --muted:#5b6472; --line:#e5e7eb; --paper:#fbfaf7; --card:#ffffff;
      --green:#1f8a70; --gold:#b88a00; --blue:#4b6cb7; --orange:#b65f28;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--paper); color:var(--ink); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Arial,sans-serif; line-height:1.48; }}
    .page {{ max-width:1180px; margin:0 auto; padding:44px 34px 80px; }}
    header {{ border-bottom:1px solid var(--line); padding-bottom:24px; margin-bottom:28px; }}
    .eyebrow {{ color:var(--green); text-transform:uppercase; letter-spacing:.14em; font-size:12px; font-weight:700; }}
    h1 {{ font-size:42px; line-height:1.04; margin:12px 0 14px; letter-spacing:-.035em; max-width:920px; }}
    h2 {{ font-size:24px; margin:38px 0 14px; letter-spacing:-.02em; }}
    h3 {{ font-size:16px; margin:22px 0 8px; }}
    p {{ color:#263241; margin:0 0 12px; }}
    .lead {{ font-size:18px; color:#263241; max-width:950px; }}
    .meta {{ display:flex; gap:20px; flex-wrap:wrap; margin-top:18px; color:var(--muted); font-size:13px; }}
    .cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin:24px 0 28px; }}
    .card {{ background:var(--card); border:1px solid var(--line); border-radius:16px; padding:18px; box-shadow:0 1px 2px rgba(17,24,39,.04); }}
    .metric {{ font-size:28px; font-weight:750; letter-spacing:-.03em; }}
    .label {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.09em; font-weight:700; }}
    .note {{ color:var(--muted); font-size:13px; margin-top:6px; }}
    .grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:22px; align-items:start; }}
    figure {{ margin:18px 0 28px; background:#fff; border:1px solid var(--line); border-radius:18px; padding:16px; }}
    figure img {{ display:block; width:100%; height:auto; border-radius:10px; }}
    figcaption {{ color:var(--muted); font-size:12px; margin-top:10px; }}
    .data-table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid var(--line); border-radius:14px; overflow:hidden; font-size:13px; }}
    .data-table th {{ text-align:left; background:#f3f4f6; color:#374151; font-size:11px; text-transform:uppercase; letter-spacing:.06em; }}
    .data-table th, .data-table td {{ padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
    .data-table tr:last-child td {{ border-bottom:none; }}
    .compact td, .compact th {{ padding:7px 8px; font-size:12px; }}
    .callout {{ border-left:4px solid var(--green); padding:10px 0 10px 16px; margin:18px 0; color:#263241; }}
    .bullets {{ display:grid; gap:10px; margin:12px 0; }}
    .bullet {{ background:#fff; border:1px solid var(--line); border-radius:14px; padding:14px 16px; }}
    .small {{ color:var(--muted); font-size:12px; }}
    footer {{ margin-top:44px; border-top:1px solid var(--line); padding-top:18px; color:var(--muted); font-size:12px; }}
    @media (max-width:900px) {{ .cards,.grid-2 {{ grid-template-columns:1fr; }} h1 {{ font-size:32px; }} .page {{ padding:28px 18px 60px; }} }}
    @media print {{ body {{ background:#fff; }} .page {{ max-width:none; padding:24px; }} figure,.card,.data-table {{ break-inside:avoid; }} }}
  </style>
</head>
<body>
<main class="page">
  <header>
    <div class="eyebrow">GIM17 research note</div>
    <h1>Climate and energy policy stress-test, 2026-2056</h1>
    <p class="lead">Thirty-year scenario experiment comparing five SSP-like policy regimes through GDP, emissions, temperature, social stability, migration pressure, resource stress and endogenous geopolitical risk. The experiment does not impose wars; conflicts emerge only from the model dynamics.</p>
    <div class="meta">
      <span>Run directory: <code>{esc(run_dir.name)}</code></span>
      <span>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
      <span>Panel: 57 countries / aggregates, 5 seeds, 5 scenarios</span>
    </div>
  </header>

  <section class="cards">
    <div class="card"><div class="label">GDP leader</div><div class="metric">{fmt(best_gdp['gdp_index_mean'],1)}</div><div class="note">{SCENARIO_LABELS[best_gdp['scenario']]} final GDP index</div></div>
    <div class="card"><div class="label">Lowest warming</div><div class="metric">{fmt(best_climate['temperature_mean'],2)} C</div><div class="note">{SCENARIO_LABELS[best_climate['scenario']]}, final global state</div></div>
    <div class="card"><div class="label">Lowest energy stress</div><div class="metric">{fmt(best_energy['energy_gap_log_mean'],2)}</div><div class="note">log10(1 + shortfall), {SCENARIO_LABELS[best_energy['scenario']]}</div></div>
    <div class="card"><div class="label">War signal</div><div class="metric">0.0</div><div class="note">active war pairs at final-year ensemble mean</div></div>
  </section>

  <section>
    <h2>Executive conclusions</h2>
    <div class="bullets">
      <div class="bullet"><strong>Growth dominates in the fossil-growth run.</strong> {SCENARIO_LABELS[best_gdp['scenario']]} ends at GDP index {fmt(best_gdp['gdp_index_mean'],1)}, versus {fmt(delayed['gdp_index_mean'],1)} in delayed transition and {fmt(ssp1['gdp_index_mean'],1)} in sustainability. The gain is purchased with the highest warming ({fmt(ssp5['temperature_mean'],2)} C) and highest emissions index ({fmt(ssp5['emissions_index_mean'],1)}).</div>
      <div class="bullet"><strong>Sustainability dominates climate and energy risk.</strong> SSP1 finishes with the lowest temperature ({fmt(ssp1['temperature_mean'],2)} C), lowest annual emissions index ({fmt(ssp1['emissions_index_mean'],1)}) and lowest log energy stress ({fmt(ssp1['energy_gap_log_mean'],3)}). It is not socially frictionless: final social tension remains {fmt(ssp1['tension_mean'],3)}.</div>
      <div class="bullet"><strong>Delayed transition is the intermediate macro path.</strong> It preserves more output than SSP1 and SSP2 while landing close to the low-emissions cluster: GDP index {fmt(delayed['gdp_index_mean'],1)}, emissions index {fmt(delayed['emissions_index_mean'],1)}, temperature {fmt(delayed['temperature_mean'],2)} C.</div>
      <div class="bullet"><strong>Endogenous risk appears as system-wide conflict pressure, not realized wars.</strong> Final active war pairs are zero across scenarios, but mean bilateral conflict reaches {fmt(worst_conflict['avg_relation_conflict_mean'],3)} in {SCENARIO_LABELS[worst_conflict['scenario']]}. Treat this as a pre-war stress indicator: trade barriers, low trust and high social tension, not a deterministic war forecast.</div>
    </div>
  </section>

  <section>
    <h2>Scenario scoreboard</h2>
    {tables['global']}
  </section>

  <section>
    <h2>Global trajectories</h2>
    <figure><img src="{img['01_global_trajectories']}" alt="Global trajectories"><figcaption>GDP, temperature, emissions and bilateral conflict. Legends are shared below the panel to avoid axis overlap.</figcaption></figure>
    <div class="grid-2">
      <figure><img src="{img['02_tradeoff_gdp_temperature']}" alt="Output warming tradeoff"><figcaption>Bubble size scales with final emissions index. SSP5 is the output frontier; SSP1 is the climate frontier.</figcaption></figure>
      <figure><img src="{img['04_population_exposure']}" alt="Population exposure"><figcaption>Population-weighted exposure in the final year. Low food buffer is high across the panel because the calibrated food-reserve state is tight at baseline.</figcaption></figure>
    </div>
  </section>

  <section>
    <h2>Economic readout</h2>
    <p>Output gains are concentrated in high-income, high-trust economies with strong initial capital and technology positions. Ireland, Norway, Switzerland, Denmark and Finland lead the fossil-growth case, with final GDP indices between roughly 329 and 403. Large continental systems are more constrained: China ends at 109.7 under fossil growth and 103.3 under sustainability; the United States ends at 90.8 under sustainability and 78.0 under the middle-road case.</p>
    <figure><img src="{img['05_country_outliers']}" alt="Country outliers"><figcaption>Left: countries with the largest final GDP gains in the fossil-growth path. Right: weakest GDP outcomes under the sustainability transition.</figcaption></figure>
    <figure><img src="{img['06_focus_country_heatmap']}" alt="Focus country heatmap"><figcaption>GDP index for selected large economies and resource-sensitive countries.</figcaption></figure>
  </section>

  <section>
    <h2>Regional and population effects</h2>
    <p>Regional output rankings are stable across objectives: Oceania and Europe show the largest GDP-index gains; South Asia grows strongly but carries elevated social tension. Middle East and East Asia show the highest combined climate and social risk. North America is the weakest region in the sustainability transition, driven by the United States response in the current calibration.</p>
    {tables['region']}
    <figure><img src="{img['03_region_gdp_heatmap']}" alt="Regional GDP heatmap"><figcaption>Final GDP index by region and scenario. Values are ensemble means across seeds.</figcaption></figure>
  </section>

  <section>
    <h2>Countries with broad downside exposure</h2>
    <p>The table ranks countries and aggregate regions by a cross-scenario stress score using minimum GDP index, mean social tension, mean trust and maximum climate risk. It identifies persistent vulnerability rather than one-scenario outliers.</p>
    {tables['stressed_countries']}
  </section>

  <section>
    <h2>Climate, energy and social channels</h2>
    <p>Climate policy shifts emissions and temperature first, but the modeled second-round effects run through energy stress, trust, social tension and relation quality. SSP1 cuts emissions most aggressively and minimizes energy stress; SSP5 maximizes output and leaves the highest emissions and warming. SSP3 lowers social tension relative to transition-heavy cases in this calibration, but it does so with weaker mitigation and higher migration pressure.</p>
    <div class="callout">Energy stress is reported as log10(1 + shortfall). Raw energy shortfall ratios are very large in this calibration because the resource block combines country-level calibrated demand with a compact global fossil supply cap. The log metric is used for cross-scenario comparison; the directional result is robust inside this experiment.</div>
  </section>

  <section>
    <h2>Method and boundaries</h2>
    <p>The experiment maps SSP-like narratives to existing GIM levers: fuel tax, climate policy intensity, R&D, social spending, military posture, trade restrictions, energy demand growth, efficiency and adaptation spending. The state transition remains the unchanged yearly <code>step_world</code> core.</p>
    <p>These are not calibrated CMIP/IPCC forcing pathways. The scenarios are comparative stress tests for endogenous GIM mechanisms: macro output, climate damages, resource scarcity, migration proxy, social stability, trade barriers and conflict pressure.</p>
    <p>Files backing this report: <code>final_summary.csv</code>, <code>trajectory_summary.csv</code>, <code>all_actor_trajectories.csv</code>, <code>country_summary.csv</code>, <code>region_summary.csv</code>, <code>action_log.csv</code>.</p>
  </section>

  <footer>
    GIM17 climate/energy policy stress-test. HTML report generated from local artifacts in <code>{esc(str(run_dir))}</code>.
  </footer>
</main>
</body>
</html>
"""
    out = run_dir / "climate_energy_stress_report.html"
    out.write_text(html_text, encoding="utf-8")
    return out


def build_report(run_dir: Path) -> Path:
    run_dir = run_dir.resolve()
    assets_dir = run_dir / "report_assets"
    assets_dir.mkdir(exist_ok=True)
    data = prepare_data(run_dir)
    exposure = population_exposure(data["all_actor"])
    assets = [
        plot_global_panel(data["summary"], assets_dir),
        plot_tradeoff(data["final"], assets_dir),
        plot_region_heatmap(data["region"], assets_dir),
        plot_population_exposure(exposure, assets_dir),
        plot_country_outliers(data["country"], assets_dir),
        plot_focus_heatmap(data["focus"], assets_dir),
    ]
    return render_html(run_dir, data, assets)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build polished HTML report for GIM17 climate/energy run.")
    parser.add_argument("run_dir", help="Path to results/climate_energy_stress-* directory")
    args = parser.parse_args()
    output = build_report(Path(args.run_dir))
    print(output)


if __name__ == "__main__":
    main()
