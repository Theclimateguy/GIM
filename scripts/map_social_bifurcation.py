#!/usr/bin/env python3
"""B2: bifurcation map of the social contour under a war impulse.

Sweeps the war impulse over (intensity I, duration D): the block layer's war
intensity is I for the first D years from 2024, then 0 (peace). Each cell runs
the INTEGRATED core+blocks model (57 agents, extreme events off) for HORIZON
annual steps and records how many peace years RUS social tension needs to
return to its pre-war level + margin.

Why integrated and not block-only: in the block model war RAISES incomes
(war transfers), the squeeze goes negative and the Levada tension proxy falls
— faithfully reproducing the observed 2022-25 rally effect. The hysteresis
lives in the coupled contour, where the core's price-income squeeze
(max(0, inflation − gdp growth), no transfers) drives tension up while the
trust channel bleeds. That is the contour the 20-year run found bistable —
and the B1 restoring forces are supposed to make finite.

Run from repo root: python3 scripts/map_social_bifurcation.py
Output: results/bifurcation/map.csv + map.png
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gim.core import calibration_params as cal
from gim.core.policy import make_policy_map
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv

STATE_CSV = "data/agent_states_operational.csv"
OUT_DIR = Path("results/bifurcation")
HORIZON = 30           # annual steps per cell
RETURN_MARGIN = 0.05   # "returned" = tension <= pre-war level + margin
INTENSITIES = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
DURATIONS = list(range(1, 11))                # 1 .. 10 years
START = 2024


def run_cell(intensity: float, duration: int) -> dict:
    def war_path(year: int) -> float:
        return intensity if year < START + duration else 0.0

    prev_agents, prev_fn = cal.BLOCK_LAYER_AGENTS, cal.BLOCK_WAR_INTENSITY_FN
    try:
        cal.BLOCK_LAYER_AGENTS = ("RUS",)
        cal.BLOCK_WAR_INTENSITY_FN = war_path
        world = make_world_from_csv(STATE_CSV, max_agents=57, base_year=2023)
        policies = make_policy_map(world.agents.keys(), mode="simple")
        t0 = float(world.agents["RUS"].society.social_tension)
        tensions, trusts = [], []
        for _ in range(HORIZON):
            world = step_world(world, policies, enable_extreme_events=False)
            rus = world.agents["RUS"]
            tensions.append(float(rus.society.social_tension))
            trusts.append(float(rus.society.trust_gov))
    finally:
        cal.BLOCK_LAYER_AGENTS = prev_agents
        cal.BLOCK_WAR_INTENSITY_FN = prev_fn

    peace_idx = duration  # first peace step index in the trajectory
    return_years = None
    for k in range(peace_idx, HORIZON):
        if tensions[k] <= t0 + RETURN_MARGIN:
            return_years = k - peace_idx
            break
    return {
        "intensity": intensity, "duration": duration,
        "tension_start": round(t0, 4),
        "tension_peak": round(max(tensions), 4),
        "return_years": return_years,
        "trust_final": round(trusts[-1], 4),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in INTENSITIES:
        for d in DURATIONS:
            r = run_cell(i, d)
            rows.append(r)
            ret = r["return_years"]
            print(f"I={i:3.1f} D={d:2d} peak={r['tension_peak']:.3f} "
                  f"return={'∞' if ret is None else ret}")
    with open(OUT_DIR / "map.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    n_stuck = sum(1 for r in rows if r["return_years"] is None)
    print(f"saved {OUT_DIR/'map.csv'}: {len(rows)} cells, "
          f"{n_stuck} without return inside the {HORIZON}y horizon")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    grid = np.full((len(INTENSITIES), len(DURATIONS)), np.nan)
    for r in rows:
        i = INTENSITIES.index(r["intensity"])
        j = DURATIONS.index(r["duration"])
        grid[i, j] = (r["return_years"] if r["return_years"] is not None
                      else np.nan)

    fig, ax = plt.subplots(figsize=(9, 6))
    masked = np.ma.masked_invalid(grid)
    cmap = plt.cm.viridis.copy()
    cmap.set_bad("firebrick")
    im = ax.pcolormesh(DURATIONS, INTENSITIES, masked, cmap=cmap,
                       shading="nearest")
    fig.colorbar(im, ax=ax, label="лет мира до возврата напряжённости")
    ax.set_xlabel("длительность военного импульса, лет")
    ax.set_ylabel("интенсивность импульса W")
    ax.set_title("Бифуркационная карта соцконтура ядро+блоки "
                 f"(красное — нет возврата за {HORIZON} лет)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "map.png", dpi=150)
    print(f"saved {OUT_DIR/'map.png'}")


if __name__ == "__main__":
    main()
