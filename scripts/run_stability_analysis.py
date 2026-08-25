#!/usr/bin/env python3
"""Stability analysis of the one-year world map x_{t+1} = F(x_t).

Three diagnostics for the paper's convergence claim:

1. SPECTRAL RADIUS of the numerical Jacobian of F, linearized around the baseline
   trajectory at several years. State vector: per-agent (gdp, capital, public_debt,
   social_tension, trust_gov, unemployment, inflation) + global (temperature_global,
   temperature_ocean, carbon pools, resource prices). rho(J) < 1 means local
   contraction (perturbations damp within a year); rho(J) slightly above 1 with
   bounded fans indicates slow modes tamed by nonlinear anchors. Central finite
   differences on a deterministic step (extreme events off, simple policy).

2. TWIN RUNS: epsilon-perturbations of the initial state (GDP of the largest agent,
   global temperature), divergence of world aggregates over 30 years — bounded
   sensitivity to initial conditions, the trajectory-level convergence argument.

3. CRISIS CLUSTERING from the deterministic 30-year baseline: counts of active
   crises per year (dispersion index).

Deterministic configuration throughout: seeded world RNG, extreme events off,
simple background policy, forward_init=True (post-18.1.2 forward market fixes).

Writes results/calibration/stability_analysis.json.
"""
from __future__ import annotations

import copy
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.core.policy import make_policy_map
from gim.core.simulation import step_world
from gim.runtime import load_world

OUT = os.path.join(REPO, "results", "calibration", "stability_analysis.json")

AGENT_FIELDS = [
    ("economy", "gdp"),
    ("economy", "capital"),
    ("economy", "public_debt"),
    ("economy", "unemployment"),
    ("economy", "inflation"),
    ("society", "trust_gov"),
    ("society", "social_tension"),
]


def make_step():
    world0 = load_world(forward_init=True)
    ids = list(world0.agents.keys())
    policies = make_policy_map(ids, mode="simple")

    def step(world):
        return step_world(world, policies, enable_extreme_events=False)

    return world0, step


def get_vector(world):
    v, labels = [], []
    for a in world.agents.values():
        for block, field in AGENT_FIELDS:
            v.append(float(getattr(getattr(a, block), field)))
            labels.append(f"{a.id}.{field}")
    g = world.global_state
    v.append(float(g.temperature_global)); labels.append("T_surface")
    v.append(float(g.temperature_ocean)); labels.append("T_ocean")
    for i, p in enumerate(g.carbon_pools):
        v.append(float(p)); labels.append(f"carbon_pool_{i}")
    for r in ("energy", "food", "metals"):
        v.append(float(g.prices[r])); labels.append(f"price_{r}")
    return np.array(v), labels


def set_vector(world, v):
    k = 0
    for a in world.agents.values():
        for block, field in AGENT_FIELDS:
            setattr(getattr(a, block), field, float(v[k])); k += 1
    g = world.global_state
    g.temperature_global = float(v[k]); k += 1
    g.temperature_ocean = float(v[k]); k += 1
    for i in range(len(g.carbon_pools)):
        g.carbon_pools[i] = float(v[k]); k += 1
    for r in ("energy", "food", "metals"):
        g.prices[r] = float(v[k]); k += 1
    assert k == len(v)


def jacobian_at(world, step, scales):
    """Central-difference Jacobian of the one-year map at the given world state."""
    x0, labels = get_vector(world)
    n = len(x0)
    J = np.zeros((n, n))
    for i in range(n):
        h = max(1e-8, 1e-4 * scales[i])
        for sign in (+1, -1):
            w = copy.deepcopy(world)
            x = x0.copy(); x[i] += sign * h
            set_vector(w, x)
            w2 = step(w)
            xs, _ = get_vector(w2)
            J[:, i] += sign * xs / (2 * h)
    return J, labels


def main() -> int:
    world0, step = make_step()

    # ---- baseline trajectory (30 years), keep snapshots for linearization points
    horizon = 30
    lin_years = [2, 12, 22]  # 2025, 2035, 2045 with base year 2023
    snapshots = {}
    crisis_counts = []
    w = copy.deepcopy(world0)
    traj = []
    for t in range(horizon):
        w = step(w)
        vec, _ = get_vector(w)
        traj.append(vec)
        n_crisis = sum(
            (a.risk.debt_crisis_active_years > 0)
            + (a.risk.fx_crisis_active_years > 0)
            + (a.risk.regime_crisis_active_years > 0)
            for a in w.agents.values()
        )
        crisis_counts.append(int(n_crisis))
        if t in lin_years:
            snapshots[t] = copy.deepcopy(w)
    traj = np.array(traj)
    if not np.all(np.isfinite(traj)):
        print("WARNING: non-finite values in baseline trajectory")

    # normalization scales per coordinate (typical magnitude along trajectory)
    scales = np.maximum(np.abs(traj).mean(axis=0), 1e-3)

    # ---- 1. Jacobian spectral radius at linearization points
    spectral = {}
    for t, wsnap in snapshots.items():
        J, labels = jacobian_at(wsnap, step, scales)
        # scale-normalized Jacobian: D^{-1} J D so eigenvalues are unit-comparable
        D = np.diag(scales)
        Jn = np.linalg.solve(D, J @ D)
        eig = np.linalg.eigvals(Jn)
        mags = np.sort(np.abs(eig))[::-1]
        # top eigenvector coordinates for interpretation
        idx = int(np.argmax(np.abs(eig)))
        _, vecs = np.linalg.eig(Jn)
        top = vecs[:, idx]
        comp = sorted(zip(labels, np.abs(top)), key=lambda kv: -kv[1])[:6]
        spectral[2023 + t + 1] = {
            "rho": float(mags[0]),
            "eigs_re_im": [[float(z.real), float(z.imag)] for z in eig],
            "top5_eig_mags": [float(m) for m in mags[:5]],
            "n_eigs_above_1": int((np.abs(eig) > 1.0).sum()),
            "n_eigs_above_0.9": int((np.abs(eig) > 0.9).sum()),
            "dominant_mode_top_coords": [(l, float(m)) for l, m in comp],
            "n_state": len(labels),
        }
        print(f"year {2023+t+1}: rho(J) = {mags[0]:.4f}, "
              f"eigs>1: {spectral[2023+t+1]['n_eigs_above_1']}, top5 {mags[:5].round(3)}")

    # ---- 2. twin runs: epsilon-perturbed initial conditions
    def run_metrics(world_init):
        w = copy.deepcopy(world_init)
        out = []
        for _ in range(horizon):
            w = step(w)
            gdp = sum(a.economy.gdp for a in w.agents.values())
            out.append((gdp, w.global_state.temperature_global,
                        float(np.mean([a.society.social_tension for a in w.agents.values()]))))
        return np.array(out)

    base = run_metrics(world0)
    twins = {}
    perturbs = [
        ("gdp_usa_+0.1pct", lambda w: setattr(w.agents["USA"].economy, "gdp",
                                              w.agents["USA"].economy.gdp * 1.001)),
        ("temperature_+0.01C", lambda w: setattr(w.global_state, "temperature_global",
                                                 w.global_state.temperature_global + 0.01)),
        ("tension_all_+0.01", lambda w: [setattr(a.society, "social_tension",
                                                 min(1.0, a.society.social_tension + 0.01))
                                         for a in w.agents.values()]),
    ]
    for name, fn in perturbs:
        wp = copy.deepcopy(world0)
        fn(wp)
        m = run_metrics(wp)
        rel_gdp = np.abs(m[:, 0] - base[:, 0]) / base[:, 0]
        dT = np.abs(m[:, 1] - base[:, 1])
        dten = np.abs(m[:, 2] - base[:, 2])
        twins[name] = {
            "series_rel_gdp_gap": [float(x) for x in rel_gdp],
            "series_dT": [float(x) for x in dT],
            "series_dtension": [float(x) for x in dten],
            "rel_gdp_gap_y1": float(rel_gdp[0]), "rel_gdp_gap_y10": float(rel_gdp[9]),
            "rel_gdp_gap_y30": float(rel_gdp[-1]), "rel_gdp_gap_max": float(rel_gdp.max()),
            "dT_y30": float(dT[-1]), "dT_max": float(dT.max()),
            "dtension_y30": float(dten[-1]), "dtension_max": float(dten.max()),
        }
        print(name, "-> gdp gap y1/y10/y30: "
              f"{rel_gdp[0]:.2e}/{rel_gdp[9]:.2e}/{rel_gdp[-1]:.2e}")

    # ---- 3. crisis clustering on the baseline
    cc = np.array(crisis_counts)
    fano = float(cc.var() / cc.mean()) if cc.mean() > 0 else 0.0

    payload = {
        "config": {"horizon": horizon, "base_year": 2023, "policy": "simple",
                   "extreme_events": False, "forward_init": True,
                   "agent_fields": [f"{b}.{f}" for b, f in AGENT_FIELDS]},
        "baseline": {
            "world_gdp_2053": float(base[-1, 0]),
            "temperature_2053": float(base[-1, 1]),
            "mean_tension_2053": float(base[-1, 2]),
            "all_finite": bool(np.all(np.isfinite(traj))),
            "crisis_counts_per_year": crisis_counts,
            "crisis_fano": fano,
        },
        "spectral_radius": spectral,
        "twin_runs": twins,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(payload, fh, indent=1)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
