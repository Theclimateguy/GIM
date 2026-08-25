"""#18 Global Sensitivity Analysis (Sobol/Saltelli) over the top-20 prior parameters.

Self-contained numpy/scipy implementation (no SALib dependency, to keep the locked runtime untouched):
  - Low-discrepancy Sobol sampling (scipy.stats.qmc) of the A, B matrices (fast Saltelli convergence).
  - Saltelli (2010) first-order S1 estimator + Jansen (1999) total-order ST estimator.
  - 4 outputs at 2050: global GMST, global GDP, atmospheric CO2, mean Gini.
  - N*(D+2) model evaluations (first- and total-order indices).

Each evaluation runs a deterministic 2015->2050 forward projection (extreme events + temperature
variability off -> deterministic given params, so the Sobol indices are clean).

Output: calibration/gsa_results.json (S1/ST per parameter per output + ranking + screening verdict).
ST < 0.01 -> freezable; ST > 0.05 -> GIM18 calibration priority.

Run:  PYTHONPATH=<repo root> python3 calibration/global_sensitivity.py [N]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import qmc

from gim.core.policy import make_policy_map
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv
from gim.historical_backtest import DEFAULT_INITIAL_STATE_CSV, DEFAULT_POLICY_MODE

OUT = Path(__file__).resolve().parent / "gsa_results.json"

# (name, low, high). Ranges from CALIBRATION_STATUS / validated CIs / defensible prior bounds.
PARAMS = [
    ("ECS_DEFAULT", 2.0, 4.0),
    ("DAMAGE_QUAD_COEFF", 0.0026, 0.0115),          # DICE .. Howard-Sterner incl-catastrophic
    ("TFP_CONVERGENCE_SENS", 0.0068, 0.022),        # #13 95% CI
    ("DECARB_RATE_STRUCTURAL", 0.010, 0.025),
    ("SAVINGS_BASE", 0.20, 0.28),
    ("DEBT_SPREAD_LINEAR", 0.043, 0.086),           # #14 Hilscher-Nosbusch 90% range
    ("DEBT_SPREAD_QUADRATIC", 0.05, 0.15),
    ("CRISK_TEMP_SENSITIVITY", 0.30, 0.60),
    ("PHILLIPS_SLOPE", 0.10, 0.40),
    ("OKUN_COEFF", 0.20, 0.50),
    ("GINI_GROWTH_SENS", 3.0, 9.0),
    ("TRUST_UNEMPLOYMENT_SENS", -0.045, -0.015),
    ("EVENT_BASE_PROB", 0.006, 0.020),
    ("CES_SIGMA_KE", 0.30, 0.50),
    ("SFC_ACCEL_SENS", 0.30, 0.70),
    ("TAYLOR_PHI_PI", 0.30, 0.70),
    ("STRUCTURAL_TRANSITION_POLICY_SENS", 0.30, 0.70),
    ("MIGRATION_BASE_RATE", 0.0005, 0.002),
    ("RESILIENCE_TECH_W", 0.20, 0.40),
    ("CARBON_FEEDBACK_CO2_GTCO2_PER_C", 0.0, 8.0),  # live only with the feedback switch on (below)
]
# CARBON_FEEDBACK_CO2_GTCO2_PER_C is gated by CARBON_CYCLE_FEEDBACK; enable it so the parameter is live.
BASE_OVERRIDES = {"CARBON_CYCLE_FEEDBACK": True}
OUTPUTS = ["gmst_2050", "gdp_2050", "co2_2050", "gini_2050"]


def evaluate(sample: np.ndarray) -> list[float]:
    overrides = dict(BASE_OVERRIDES)
    for (name, _, _), val in zip(PARAMS, sample):
        overrides[name] = float(val)
    world = make_world_from_csv(str(DEFAULT_INITIAL_STATE_CSV))
    world.params = world.params.with_overrides(overrides)
    policies = make_policy_map(world.agents.keys(), mode=DEFAULT_POLICY_MODE)
    for _ in range(2050 - 2015):
        world = step_world(world, policies, enable_extreme_events=False)
    gdp = sum(a.economy.gdp for a in world.agents.values())
    gini = float(np.mean([a.society.inequality_gini for a in world.agents.values()]))
    return [world.global_state.temperature_global, gdp, world.global_state.co2, gini]


def scale(unit: np.ndarray) -> np.ndarray:
    lo = np.array([p[1] for p in PARAMS])
    hi = np.array([p[2] for p in PARAMS])
    return lo + unit * (hi - lo)


def sobol_indices(N: int) -> dict:
    D = len(PARAMS)
    sob = qmc.Sobol(d=2 * D, scramble=True, seed=2026)
    base = sob.random(N)
    A_u, B_u = base[:, :D], base[:, D:]
    A, B = scale(A_u), scale(B_u)

    def run_matrix(M):
        return np.array([evaluate(M[i]) for i in range(M.shape[0])])

    Y_A = run_matrix(A)
    Y_B = run_matrix(B)
    Y_ABi = []
    for i in range(D):
        AB = A.copy()
        AB[:, i] = B[:, i]
        Y_ABi.append(run_matrix(AB))
        print(f"  param {i+1}/{D} done", flush=True)

    results = {}
    for o, oname in enumerate(OUTPUTS):
        ya, yb = Y_A[:, o], Y_B[:, o]
        varY = np.var(np.concatenate([ya, yb]), ddof=1)
        s1, st = {}, {}
        for i, (name, _, _) in enumerate(PARAMS):
            yab = Y_ABi[i][:, o]
            s1[name] = float(np.mean(yb * (yab - ya)) / varY) if varY > 0 else 0.0
            st[name] = float(0.5 * np.mean((ya - yab) ** 2) / varY) if varY > 0 else 0.0
        results[oname] = {"S1": s1, "ST": st, "var": float(varY)}
    return results


def main() -> None:
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 128
    D = len(PARAMS)
    print(f"GSA: N={N}, D={D}, evaluations={N*(D+2)} (2015->2050 each)", flush=True)
    res = sobol_indices(N)

    ranking = {}
    for oname in OUTPUTS:
        st = res[oname]["ST"]
        ranking[oname] = sorted(st.items(), key=lambda kv: kv[1], reverse=True)

    # Aggregate: a parameter's max ST across the 4 outputs.
    max_st = {name: max(res[o]["ST"][name] for o in OUTPUTS) for name, _, _ in PARAMS}
    freezable = [n for n, v in max_st.items() if v < 0.01]
    priorities = sorted([(n, v) for n, v in max_st.items() if v > 0.05], key=lambda kv: kv[1], reverse=True)

    out = {
        "method": "Sobol variance decomposition (Saltelli 2010 S1 + Jansen 1999 ST), Sobol-sequence sampling",
        "N": N,
        "D": D,
        "evaluations": N * (D + 2),
        "horizon": "2015->2050 deterministic forward run",
        "outputs": OUTPUTS,
        "param_ranges": {p[0]: [p[1], p[2]] for p in PARAMS},
        "results": res,
        "ranking_by_total_order": {o: [(n, round(v, 4)) for n, v in ranking[o]] for o in OUTPUTS},
        "max_ST_across_outputs": {n: round(v, 4) for n, v in sorted(max_st.items(), key=lambda kv: kv[1], reverse=True)},
        "freezable_ST_lt_0p01": freezable,
        "gim18_priorities_ST_gt_0p05": [(n, round(v, 4)) for n, v in priorities],
        "sources": [
            "Saltelli et al. (2010) Comp. Phys. Comm. 181:259",
            "Jansen (1999) Comp. Phys. Comm. 120:131",
            "Herman & Usher (2017) JOSS 2:97 (SALib reference)",
        ],
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print("wrote", OUT, flush=True)
    print("Top total-order drivers (max ST across outputs):")
    for n, v in sorted(max_st.items(), key=lambda kv: kv[1], reverse=True)[:8]:
        print(f"  {n:36s} ST_max={v:.3f}")


if __name__ == "__main__":
    main()
