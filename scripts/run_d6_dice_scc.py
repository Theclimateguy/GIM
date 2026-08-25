#!/usr/bin/env python3
"""D6 — DICE/SCC reproduction (the keystone cross-model check, THE-16).

Reproduce Nordhaus's DICE-2016R social cost of carbon (~$31/tCO2) with GIM's OWN, independently
built marginal-pulse SCC engine (gim/scc.py). This is the decisive economic-core validation: if
GIM's valuation machinery, fed DICE's assumptions, lands near DICE's number, the core is sound and
any headline difference is attributable to inputs (the damage function), not the engine.

GIM already shares DICE-2016R's discounting (eta=1.45, rho=1.5%) and ECS (~3.0). The remaining lever
is the damage function -- same quadratic form (loss = a2 * T^2) but GIM's a2=0.006 (~5.4% at 3C, a
literature-based prior ~2.5x DICE) vs DICE-2016R a2=0.00236 (~2.12% at 3C; Nordhaus 2017, PNAS). DICE
also integrates damages over multiple centuries, so we report several horizons (a short horizon
truncates the long-run damage tail and understates the SCC -- see docs/climate/WELFARE_SCC.md).

Run: python3 scripts/run_d6_dice_scc.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gim.core.params import default_params  # noqa: E402
from gim.scc import social_cost_of_carbon    # noqa: E402

STATE = os.getenv("STATE_CSV", "data/agent_states_operational.csv")
DICE_DAMAGE_A2 = 0.00236   # DICE-2016R quadratic damage coefficient (~2.12% of output at 3C)
GIM_DAMAGE_A2 = 0.006      # GIM default prior (~5.4% at 3C)
HORIZONS = (30, 100, 200, 300)
DICE_TARGET = 31.0         # Nordhaus DICE-2016R central SCC, ~$31/tCO2 (2015, 2010 USD)


def _scc(coeff: float, years: int) -> float:
    ps = default_params().with_overrides({"DAMAGE_QUAD_COEFF": coeff})
    return social_cost_of_carbon(
        STATE, years=years, pulse_gtco2=10.0, params=ps, seed=2026, max_agents=100, base_year=2023,
    )["scc_usd_per_tco2"]


def main() -> int:
    p = default_params()
    print("D6 — DICE/SCC reproduction (keystone cross-model check)")
    print(f"discounting: eta={p.ELASTICITY_MARGINAL_UTILITY}, rho={p.PURE_TIME_PREFERENCE} "
          f"(DICE-2016R = GIM default); ECS={p.ECS_DEFAULT}")
    print(f"\n{'horizon':>8} | {'GIM damages 0.006':>18} | {'DICE damages 0.00236':>21}")
    print("-" * 56)
    dice_curve = {}
    for h in HORIZONS:
        g = _scc(GIM_DAMAGE_A2, h)
        d = _scc(DICE_DAMAGE_A2, h)
        dice_curve[h] = d
        print(f"{h:>6}y  | ${g:>16.1f} | ${d:>19.1f}")

    converged = dice_curve[max(HORIZONS)]
    print(f"\nDICE-damages SCC converges to ~${converged:.1f}/tCO2 at {max(HORIZONS)}y "
          f"(target Nordhaus ~${DICE_TARGET:.0f}).")
    ok = 0.7 * DICE_TARGET <= converged <= 1.4 * DICE_TARGET
    print("RESULT:", "REPRODUCED — GIM's SCC engine recovers DICE under DICE's inputs."
          if ok else "OUTSIDE the DICE neighborhood — investigate.")
    print("Interpretation: GIM's higher headline SCC is the damage function (~2.5x DICE), not the engine.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
