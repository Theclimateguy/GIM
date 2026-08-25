#!/usr/bin/env python3
"""E5 -- does the Section 6 social-channel result survive the trust drift?

Section 6's first regularity says the mediation structure is not coded: in an ensemble
that also varies the social priors, "final tension is governed by them" (Spearman
r_s ~ +0.59 for inequality sensitivity, ~ -0.52 for the trust anchor, n = 120).

E2 showed mean tension is riding a monotone drift driven by trust_gov's missing
equilibrium term. `SOCIAL_TRUST_ANCHOR_SENS` and `INEQUALITY_EFFECT_SENS` are the
coefficients ON that drift (`tension_{t+1} = tension_t + INEQUALITY_EFFECT_SENS*gini
+ stress + SOCIAL_TRUST_ANCHOR_SENS*(ref - trust)`), so correlating them with the
final tension LEVEL recovers the drift rate rather than a mediation structure. That
is a coded consequence of a coded term, not an uncoded one.

The existing `scripts/social_channel_analysis.py` gets the impulse response right --
it is a paired baseline-vs-shock difference, so the drift cancels -- but the
localization half is a level analysis on a drifting series.

This script computes, per ensemble member and on the SAME draws:
  L  final-year mean tension (the paper's statistic)
  D  the member's baseline tension drift rate (slope, no shock)
  R  the causal shock response: integral of tension(shock) - tension(base) over lags
and reports Spearman of each prior against L, D and R, plus the partial correlation of
prior vs L controlling for D.

If a prior correlates with L and D but not with R, it is a drift coefficient and cannot
support an "emergent mediation" reading. If it correlates with R, the channel is real.

Writes Paper/revision/results/e5_social_channel_level_vs_response.json
"""
from __future__ import annotations

import json
import os
import random
import sys

import numpy as np
from scipy.stats import spearmanr

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.core import simulation as sim                                   # noqa: E402
from gim.core.calibration_params import INFLATION_MAX, UNEMPLOYMENT_MAX  # noqa: E402
from gim.core.params import default_params                               # noqa: E402
from gim.core.policy import make_policy_map                              # noqa: E402
from gim.core.priors import all_priors, key_priors, sample_parameter_set # noqa: E402
from gim.core.rng import seed_world                                      # noqa: E402
from gim.core.world_factory import make_world_from_csv                   # noqa: E402
from gim.runtime import default_state_csv                                # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                   "e5_social_channel_level_vs_response.json")
CSV = default_state_csv()

N_ENS = int(os.getenv("N_ENS", "120"))
YEARS = int(os.getenv("YEARS", "50"))
SEED = int(os.getenv("SEED", "2026"))
SHOCK_DU = 0.05
SHOCK_DPI = 0.05
SHOCK_START = 5
SHOCK_WIN = 3
IRF_H = 25

SOCIAL_PRIORS = [
    "SOCIAL_STRESS_UNEMPLOYMENT_SENS",
    "SOCIAL_STRESS_INFLATION_SENS",
    "INEQUALITY_EFFECT_SENS",
    "SOCIAL_TRUST_ANCHOR_SENS",
]

_ORIG_LABOR = sim.update_inflation_unemployment
_SHOCK = {"active": False, "du": 0.0, "dpi": 0.0}


def _patched_labor(world):
    _ORIG_LABOR(world)
    if _SHOCK["active"]:
        for a in world.agents.values():
            a.economy.unemployment = min(UNEMPLOYMENT_MAX, a.economy.unemployment + _SHOCK["du"])
            a.economy.inflation = min(INFLATION_MAX, a.economy.inflation + _SHOCK["dpi"])


sim.update_inflation_unemployment = _patched_labor


def _means(world):
    ag = list(world.agents.values())
    n = len(ag)
    return (sum(a.society.social_tension for a in ag) / n,
            sum(a.society.trust_gov for a in ag) / n)


def run_member(seed, params, years, shock_years=None):
    world = make_world_from_csv(CSV, max_agents=100, base_year=2023)
    world.params = params
    seed_world(world, seed)
    pol = make_policy_map(world.agents.keys(), mode="simple")
    shock_years = set(shock_years or [])
    traj = [_means(world)]
    for yr in range(years):
        _SHOCK.update(active=(yr in shock_years), du=SHOCK_DU, dpi=SHOCK_DPI)
        step_world_out = sim.step_world(world, pol)
        world = step_world_out if step_world_out is not None else world
        traj.append(_means(world))
    _SHOCK["active"] = False
    return np.array(traj)


def _member_seed(master, i):
    return (int(master) * 1_000_003 + int(i)) & 0x7FFFFFFF


def partial_spearman(x, y, z):
    """Spearman of x,y controlling for z (rank-residual method)."""
    def rk(v):
        return np.argsort(np.argsort(v)).astype(float)
    rx, ry, rz = rk(x), rk(y), rk(z)
    def resid(a, b):
        b1 = np.vstack([b, np.ones_like(b)]).T
        coef, *_ = np.linalg.lstsq(b1, a, rcond=None)
        return a - b1 @ coef
    ex, ey = resid(rx, rz), resid(ry, rz)
    if ex.std() == 0 or ey.std() == 0:
        return float("nan")
    return float(np.corrcoef(ex, ey)[0, 1])


def main() -> int:
    base = default_params()
    kp, ap = key_priors(), all_priors()
    curated = dict(kp)
    for nm in SOCIAL_PRIORS:
        if nm in ap:
            curated[nm] = ap[nm]
    names = list(curated.keys())

    rng = random.Random(SEED)
    draws, L, D, R, T_end = [], [], [], [], []
    shock_years = list(range(SHOCK_START, SHOCK_START + SHOCK_WIN))

    for i in range(N_ENS):
        params = sample_parameter_set(base, curated, rng, names=names)
        drawn = {n: float(params.get(n)) for n in names}
        s = _member_seed(SEED, i)

        base_traj = run_member(s, params, YEARS)
        shock_traj = run_member(s, params, SHOCK_START + IRF_H, shock_years=shock_years)

        ten_base = base_traj[:, 0]
        # L: the paper's statistic -- final-year mean tension level
        L.append(float(ten_base[-1]))
        T_end.append(float(base_traj[-1, 1]))
        # D: baseline drift rate of mean tension (OLS slope over the run, no shock)
        t = np.arange(ten_base.size, dtype=float)
        D.append(float(np.polyfit(t, ten_base, 1)[0]))
        # R: causal response -- integral of shock minus base over the IRF horizon
        h = min(shock_traj.shape[0], base_traj.shape[0])
        irf = shock_traj[:h, 0] - base_traj[:h, 0]
        R.append(float(irf[SHOCK_START:].sum()))

        draws.append(drawn)
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{N_ENS}")

    L, D, R = np.array(L), np.array(D), np.array(R)
    rows = {}
    for n in names:
        x = np.array([d[n] for d in draws])
        if x.std() == 0:
            continue
        rl, pl = spearmanr(x, L)
        rd, pd = spearmanr(x, D)
        rr, pr = spearmanr(x, R)
        rows[n] = {
            "rho_vs_final_tension_level": float(rl), "p_level": float(pl),
            "rho_vs_baseline_drift": float(rd), "p_drift": float(pd),
            "rho_vs_shock_response": float(rr), "p_response": float(pr),
            "partial_rho_level_given_drift": partial_spearman(x, L, D),
            "is_social_prior": n in SOCIAL_PRIORS,
        }

    rho_LD, _ = spearmanr(L, D)
    rho_LR, _ = spearmanr(L, R)

    ranked = sorted(rows.items(), key=lambda kv: -abs(kv[1]["rho_vs_final_tension_level"]))
    print(f"\nlevel vs drift: rho = {rho_LD:+.3f}   level vs shock response: rho = {rho_LR:+.3f}")
    print(f"mean final trust across members: {np.mean(T_end):.3f}\n")
    print(f"{'prior':34s} {'rho|level':>10s} {'rho|drift':>10s} {'rho|response':>13s} {'partial':>9s}")
    for n, r in ranked[:12]:
        mark = "*" if r["is_social_prior"] else " "
        print(f"{mark}{n:33s} {r['rho_vs_final_tension_level']:+10.3f} "
              f"{r['rho_vs_baseline_drift']:+10.3f} {r['rho_vs_shock_response']:+13.3f} "
              f"{r['partial_rho_level_given_drift']:+9.3f}")

    payload = {
        "experiment": "E5",
        "question": "Do the priors that govern the final tension LEVEL also govern the "
                    "causal shock RESPONSE, or are they drift coefficients?",
        "config": {"n_ensemble": N_ENS, "years": YEARS, "seed": SEED,
                   "shock": {"du": SHOCK_DU, "dpi": SHOCK_DPI, "years": shock_years},
                   "irf_horizon": IRF_H, "n_priors_varied": len(names)},
        "aggregate": {"rho_level_vs_drift": float(rho_LD),
                      "rho_level_vs_shock_response": float(rho_LR),
                      "mean_final_trust": float(np.mean(T_end)),
                      "mean_final_tension": float(L.mean()),
                      "mean_tension_drift_per_year": float(D.mean()),
                      "share_positive_shock_response": float((R > 0).mean())},
        "per_prior": rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(os.path.abspath(OUT), "w") as fh:
        json.dump(payload, fh, indent=1)
    print("wrote", os.path.abspath(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
