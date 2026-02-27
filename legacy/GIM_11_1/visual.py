#!/usr/bin/env python3
import argparse
import csv
import math
import os
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import matplotlib.pyplot as plt


def find_latest_log(logs_dir: Path) -> Path:
    if not logs_dir.exists():
        raise FileNotFoundError(f"Logs directory not found: {logs_dir}")
    candidates = list(logs_dir.glob("*.csv"))
    if not candidates:
        raise FileNotFoundError(f"No CSV logs found in: {logs_dir}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_agent_names(agents_csv: Path) -> List[Tuple[str, str]]:
    if not agents_csv.exists():
        raise FileNotFoundError(f"Agent CSV not found: {agents_csv}")
    rows: List[Tuple[str, str]] = []
    with agents_csv.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            agent_id = row.get("id", "").strip()
            name = row.get("name", "").strip()
            if agent_id and name:
                rows.append((agent_id, name))
    return rows


def parse_log(
    log_path: Path,
    agent_ids: List[str],
    metrics: Dict[str, Tuple[str, Callable[[float], float]]],
) -> Tuple[List[int], Dict[str, Dict[str, List[float]]]]:
    times_set = set()
    data: Dict[str, Dict[str, Dict[int, float]]] = {
        agent_id: {metric_key: {} for metric_key in metrics} for agent_id in agent_ids
    }

    with log_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            agent_id = row.get("agent_id", "")
            if agent_id not in data:
                continue
            try:
                t = int(row.get("time", "0"))
            except ValueError:
                continue
            times_set.add(t)
            for metric_key, (col, transform) in metrics.items():
                raw = row.get(col, "")
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    val = math.nan
                data[agent_id][metric_key][t] = transform(val)

    times = sorted(times_set)
    series: Dict[str, Dict[str, List[float]]] = {
        agent_id: {metric_key: [] for metric_key in metrics} for agent_id in agent_ids
    }
    for agent_id in agent_ids:
        for metric_key in metrics:
            points = []
            values = data[agent_id][metric_key]
            for t in times:
                points.append(values.get(t, math.nan))
            series[agent_id][metric_key] = points

    return times, series


def build_dashboard(
    times: List[int],
    series: Dict[str, Dict[str, List[float]]],
    agent_names: Dict[str, str],
    metrics: Dict[str, Tuple[str, Callable[[float], float]]],
    output_path: Path,
) -> None:
    metric_keys = list(metrics.keys())
    total_plots = len(metric_keys)
    rows = 3
    cols = 3
    fig, axes = plt.subplots(rows, cols, figsize=(18, 12), sharex=True)
    axes_flat = axes.flatten()

    cmap = plt.get_cmap("tab20")
    agent_ids = list(series.keys())
    colors = {agent_id: cmap(i % 20) for i, agent_id in enumerate(agent_ids)}

    handles = []
    labels = []

    for idx, metric_key in enumerate(metric_keys):
        ax = axes_flat[idx]
        for agent_id in agent_ids:
            line, = ax.plot(
                times,
                series[agent_id][metric_key],
                color=colors[agent_id],
                linewidth=1.5,
            )
            if idx == 0:
                handles.append(line)
                labels.append(agent_names.get(agent_id, agent_id))
        ax.set_title(metric_key)
        ax.grid(True, linewidth=0.3, alpha=0.6)

    # Hide unused axes.
    for idx in range(total_plots, rows * cols):
        axes_flat[idx].axis("off")

    for ax in axes_flat[:total_plots]:
        ax.set_xlabel("Year")

    fig.suptitle("World Simulation Dashboard", fontsize=16, y=0.98)
    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=5,
        fontsize=8,
        frameon=False,
    )
    fig.tight_layout(rect=[0, 0.06, 1, 0.95])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a dashboard from the latest simulation log."
    )
    parser.add_argument("--logs-dir", default="logs")
    parser.add_argument("--agents-csv", default="agent_states.csv")
    parser.add_argument("--output", default=None)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    logs_dir = Path(args.logs_dir).expanduser()
    agents_csv = Path(args.agents_csv).expanduser()
    latest_log = find_latest_log(logs_dir)

    agent_rows = load_agent_names(agents_csv)
    agent_ids = [agent_id for agent_id, name in agent_rows if name.lower() != "rest of world"]
    agent_names = {agent_id: name for agent_id, name in agent_rows}

    if len(agent_ids) != 20:
        agent_ids = agent_ids[:20]

    metrics: Dict[str, Tuple[str, Callable[[float], float]]] = {
        "GDP ($T)": ("gdp", lambda v: v),
        "Population (B)": ("population", lambda v: v / 1e9),
        "Trust": ("trust_gov", lambda v: v),
        "Tension": ("social_tension", lambda v: v),
        "CO2 Emissions (Gt)": ("co2_annual_emissions", lambda v: v),
        "Biodiversity": ("biodiversity_local", lambda v: v),
        "Energy Reserves (ZJ)": ("energy_own_reserve", lambda v: v),
    }

    times, series = parse_log(latest_log, agent_ids, metrics)

    if args.output:
        output_path = Path(args.output).expanduser()
    else:
        stem = latest_log.stem
        output_path = latest_log.with_name(f"{stem}_dashboard.png")

    build_dashboard(times, series, agent_names, metrics, output_path)
    print(f"Log: {latest_log}")
    print(f"Dashboard: {output_path}")

    if args.show:
        import matplotlib.pyplot as plt  # re-import for interactive show

        img = plt.imread(str(output_path))
        plt.figure(figsize=(10, 7))
        plt.imshow(img)
        plt.axis("off")
        plt.show()


if __name__ == "__main__":
    main()
