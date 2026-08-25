#!/usr/bin/env python3
"""B8: ensemble fan chart for the 20-year integrated run.

Runs the coupled core+blocks model once per A4 posterior draw (see
fit_block_dynamics.py --bayes): each draw overrides the nine behavioural
equations in dynamics_params.json, everything else (core bridge seed, B1
peace channel, B4 rent elasticity) stays the production fit. Per year the
script collects RUS gdp / key rate / inflation / tension / trust and writes
quantile bands (5-95 and 25-75) plus the median and the production point
trajectory.

Params are injected by monkeypatching gim19.dynamics.load_params (and the
name re-imported in gim19.core_adapter) — gim.blocks.* are shims over the
same module objects, so the core sees the patch; the interaction cache is
cleared per draw.

Run from repo root: python3 scripts/run_ensemble_forward.py [--draws N]
Output: results/forward20/fan.csv + fan.png
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gim.blocks  # noqa: F401 — bootstraps lib/ onto sys.path
import gim19.core_adapter as core_adapter
import gim19.dynamics as dynamics
from gim.core import calibration_params as cal
from gim.core.policy import make_policy_map
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv

STATE_CSV = "data/agent_states_operational.csv"
ENS_PATH = Path("data/blocks/RUS/dynamics_params_ensemble.json")
OUT_DIR = Path("results/forward20")
YEARS = 20
FIELDS = ["gdp", "key_rate", "inflation", "tension", "trust"]


def run_one(params: dict) -> list[dict]:
    orig_load = dynamics.load_params
    dynamics.load_params = lambda path=None: params
    core_adapter.load_params = dynamics.load_params
    core_adapter._interaction_params.cache_clear()
    try:
        cal.BLOCK_LAYER_AGENTS = ("RUS",)
        world = make_world_from_csv(STATE_CSV, max_agents=57, base_year=2023)
        policies = make_policy_map(world.agents.keys(), mode="simple")
        rows = []
        for t in range(YEARS):
            world = step_world(world, policies, enable_extreme_events=False)
            rus = world.agents["RUS"]
            carried = getattr(rus, "_block_bridge_state", None)
            bridge = carried[0] if carried else None
            rows.append({
                "year": 2024 + t,
                "gdp": float(rus.economy.gdp),
                "key_rate": float(getattr(bridge, "key_rate", float("nan"))),
                "inflation": float(rus.economy.inflation),
                "tension": float(rus.society.social_tension),
                "trust": float(rus.society.trust_gov),
            })
        return rows
    finally:
        dynamics.load_params = orig_load
        core_adapter.load_params = orig_load
        core_adapter._interaction_params.cache_clear()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=None,
                    help="limit the number of ensemble members (default: all)")
    args = ap.parse_args()

    base = json.loads(Path(dynamics.PARAMS_PATH).read_text())
    ens = json.loads(ENS_PATH.read_text())
    draws = ens["draws"][: args.draws] if args.draws else ens["draws"]

    point = run_one(base)
    trajs = []
    for k, override in enumerate(draws):
        params = copy.deepcopy(base)
        for eq, coeffs in override.items():
            params[eq] = {**params.get(eq, {}), **coeffs}
        trajs.append(run_one(params))
        if (k + 1) % 10 == 0:
            print(f"{k + 1}/{len(draws)} members done")

    import numpy as np
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_rows = []
    for i, year in enumerate(r["year"] for r in point):
        row = {"year": year}
        for f in FIELDS:
            vals = np.array([t[i][f] for t in trajs])
            row[f + "_point"] = point[i][f]
            for q, tag in ((5, "q05"), (25, "q25"), (50, "q50"),
                           (75, "q75"), (95, "q95")):
                row[f"{f}_{tag}"] = float(np.percentile(vals, q))
        out_rows.append(row)
    with open(OUT_DIR / "fan.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)
    print(f"saved {OUT_DIR/'fan.csv'}: {len(trajs)} members")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    titles = {"gdp": "ВВП RUS, трлн (мод. ед.)", "key_rate": "Ключевая ставка, %",
              "inflation": "Инфляция (доля)", "tension": "Соц. напряжённость",
              "trust": "Доверие правительству"}
    years = [r["year"] for r in out_rows]
    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    for ax, f in zip(axes.flat, FIELDS):
        ax.fill_between(years, [r[f + "_q05"] for r in out_rows],
                        [r[f + "_q95"] for r in out_rows],
                        alpha=0.2, color="#0b6aa8", label="5–95%")
        ax.fill_between(years, [r[f + "_q25"] for r in out_rows],
                        [r[f + "_q75"] for r in out_rows],
                        alpha=0.35, color="#0b6aa8", label="25–75%")
        ax.plot(years, [r[f + "_q50"] for r in out_rows],
                color="#0b6aa8", lw=1.5, label="медиана")
        ax.plot(years, [r[f + "_point"] for r in out_rows],
                color="#b3541e", lw=1.8, ls="--", label="точечная")
        ax.set_title(titles[f])
        ax.grid(alpha=0.3)
    axes.flat[0].legend(loc="upper left", fontsize=9)
    axes.flat[-1].axis("off")
    fig.suptitle(f"Ансамбль A4-постериора, {len(trajs)} членов — 20-летний "
                 "интегрированный прогон (B8)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fan.png", dpi=140)
    print(f"saved {OUT_DIR/'fan.png'}")


if __name__ == "__main__":
    main()
