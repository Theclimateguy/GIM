#!/usr/bin/env python3
"""20-year forward run of the integrated core+blocks model (stability check).

Two runs from the 2023 baseline, 20 annual steps each:
  A. block layer ON for RUS (policy bridge + propagate sub-step)
  B. block layer OFF (pure GIM18 core) — the control

Collected per year: RUS gdp / inflation / unemployment / trust / tension,
block-bridge internals (key rate, milex share, rent, fx), world totals.
Output: results/forward20/trajectories.csv + trajectories.png
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv

from gim.core import calibration_params as cal
from gim.core.policy import make_policy_map
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv

STATE_CSV = "data/agent_states_operational.csv"
YEARS = 20
OUT_DIR = Path("results/forward20")


def run(block_on: bool) -> list[dict]:
    cal.BLOCK_LAYER_AGENTS = ("RUS",) if block_on else ()
    world = make_world_from_csv(STATE_CSV, max_agents=57, base_year=2023)
    policies = make_policy_map(world.agents.keys(), mode="simple")
    rows = []
    for t in range(YEARS):
        world = step_world(world, policies, enable_extreme_events=False)
        rus = world.agents["RUS"]
        carried = getattr(rus, "_block_bridge_state", None)
        bridge = carried[0] if carried else None
        row = {
            "year": 2024 + t,
            "run": "blocks" if block_on else "core",
            "rus_gdp": float(rus.economy.gdp),
            "rus_inflation": float(rus.economy.inflation),
            "rus_unemployment": float(rus.economy.unemployment),
            "rus_trust": float(rus.society.trust_gov),
            "rus_tension": float(rus.society.social_tension),
            "rus_debt_gdp": float(rus.economy.public_debt) / max(float(rus.economy.gdp), 1e-9),
            "world_gdp": sum(float(a.economy.gdp) for a in world.agents.values()),
            "energy_price": float(world.global_state.prices.get("energy", 1.0)),
            "block_key_rate": getattr(bridge, "key_rate", float("nan")) if bridge else float("nan"),
            "block_milex_share": getattr(bridge, "milex_share", float("nan")) if bridge else float("nan"),
            "block_rent": getattr(bridge, "oilgas_rev", float("nan")) if bridge else float("nan"),
        }
        rows.append(row)
        print(f"{row['run']} {row['year']} gdp={row['rus_gdp']:.3f} "
              f"infl={row['rus_inflation']:.3f} trust={row['rus_trust']:.3f} "
              f"tension={row['rus_tension']:.3f} rate={row['block_key_rate']}")
    return rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = run(block_on=True) + run(block_on=False)
    with open(OUT_DIR / "trajectories.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"saved {OUT_DIR/'trajectories.csv'}: {len(rows)} rows")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    years = [r["year"] for r in rows if r["run"] == "blocks"]
    panels = [
        ("rus_gdp", "ВВП RUS, трлн $ (модельные ед.)"),
        ("rus_inflation", "Инфляция RUS (доля)"),
        ("rus_unemployment", "Безработица RUS (доля)"),
        ("rus_trust", "Доверие (0–1)"),
        ("rus_tension", "Напряжённость (0–1)"),
        ("rus_debt_gdp", "Долг/ВВП RUS"),
        ("block_key_rate", "Ставка блока regulator, %"),
        ("block_milex_share", "Milex-доля блока security, % ВВП"),
        ("world_gdp", "Мировой ВВП, трлн $"),
    ]
    fig, axes = plt.subplots(3, 3, figsize=(15, 10))
    for ax, (key, title) in zip(axes.flat, panels):
        for run_name, style, label in (("blocks", "-", "ядро+блоки"),
                                       ("core", "--", "только ядро")):
            ys = [r[key] for r in rows if r["run"] == run_name]
            if all(y != y for y in ys):  # all-NaN panel (bridge-only field)
                continue
            ax.plot(years, ys, style, label=label, linewidth=1.8)
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.3)
        ax.tick_params(labelsize=8)
    axes.flat[0].legend(fontsize=9)
    fig.suptitle("GIM19: прогон 2024–2043, RUS с блочным слоем vs чистое ядро",
                 fontsize=13)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "trajectories.png", dpi=140)
    print(f"saved {OUT_DIR/'trajectories.png'}")


if __name__ == "__main__":
    main()
