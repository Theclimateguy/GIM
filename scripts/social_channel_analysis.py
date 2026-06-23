#!/usr/bin/env python3
"""Is there a statistically significant (possibly lagged) channel from physico-economic
conditions to social tension?

Background. The headline Morris screen varies the 26 *key* (physico-economic) priors and finds
mean social tension nearly insensitive. This script tests the reviewer-style hypothesis that the
channel is real but (a) mediated and (b) lagged, because tension is an *accumulator*
(`tension_{t+1} = clamp01(tension_t + stress_effect + inequality_effect + trust_anchor)`), so a
fixed short horizon understates it. Four complementary, reproducible analyses:

  1. LOCALIZATION. An ensemble that also varies the *direct* social-channel priors
     (SOCIAL_STRESS_*, INEQUALITY_EFFECT_SENS, SOCIAL_TRUST_ANCHOR_SENS — present in `all`, absent
     from `key`). Spearman correlation of each varied prior with final-year mean tension (+p-value)
     shows which parameters actually govern tension — i.e. where the channel lives.
  2. ACCUMULATION. Cross-member spread (std, 5-95%) of mean tension at horizons 5/10/25/50 — does
     the parameter-induced spread grow with horizon (the lag/accumulation signature)?
  3. IMPULSE RESPONSE. A paired baseline-vs-shock experiment: an exogenous stagflation pulse
     (unemployment +DU, inflation +DPI over a window) injected into the labour market AFTER its
     normal update (so the social block sees it the same year). IRF = tension(shock)-tension(base)
     by lag, with a 5-95% band across parameter draws and the share of draws with a positive
     response — the causal, lag-resolved channel, robust to parameter uncertainty.
  4. DISTRIBUTED-LAG REGRESSION. Within-member (fixed-effects) regression of the annual change in
     tension on contemporaneous and lagged economic stress, cluster-robust by member — formal
     p-values for the transmission coefficients.

    python3 scripts/social_channel_analysis.py
Env: N_ENS (120), N_IRF (40), YEARS (50), MAX_AGENTS (100=all 57), SEED (2026),
SHOCK_DU (0.05), SHOCK_DPI (0.05), SHOCK_START (5), SHOCK_WIN (3), IRF_H (25), MAXLAG (5).
"""
from __future__ import annotations

import json
import os
import random
import sys
from datetime import datetime

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gim.core.calibration_params import INFLATION_MAX, UNEMPLOYMENT_MAX
from gim.core.params import default_params
from gim.core.policy import make_policy_map
from gim.core.priors import all_priors, key_priors, sample_parameter_set
from gim.core.rng import seed_world
from gim.core.simulation import step_world  # warms up the package (avoids a circular import)
from gim.core.world_factory import make_world_from_csv

# Module handle so we can wrap update_inflation_unemployment as step_world looks it up.
sim = sys.modules["gim.core.simulation"]

CSV = os.getenv("STATE_CSV", "data/agent_states_operational_2026_calibrated.csv")
SOCIAL_PRIORS = [
    "SOCIAL_STRESS_UNEMPLOYMENT_SENS",
    "SOCIAL_STRESS_INFLATION_SENS",
    "INEQUALITY_EFFECT_SENS",
    "SOCIAL_TRUST_ANCHOR_SENS",
]

# --- exogenous labour-market shock, applied AFTER the normal Okun/Phillips update ---
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
    return (
        sum(a.society.social_tension for a in ag) / n,
        sum(a.economy.unemployment for a in ag) / n,
        sum(a.economy.inflation for a in ag) / n,
        sum(a.society.inequality_gini for a in ag) / n,
        sum(a.economy.gdp for a in ag),
    )


def run_member(seed, params, years, max_agents, shock_years=None, du=0.0, dpi=0.0):
    """Return trajectory array [years+1, 5] of (tension, unemp, infl, gini, gdp) means."""
    world = make_world_from_csv(CSV, max_agents=max_agents, base_year=2026)
    world.params = params
    seed_world(world, seed)
    pol = make_policy_map(world.agents.keys(), mode="simple")
    shock_years = set(shock_years or [])
    traj = [_means(world)]
    for yr in range(years):
        if yr in shock_years:
            _SHOCK.update(active=True, du=du, dpi=dpi)
        else:
            _SHOCK["active"] = False
        step_world(world, pol)
        traj.append(_means(world))
    _SHOCK["active"] = False
    return np.array(traj)


def _member_seed(master, i):
    return (int(master) * 1_000_003 + int(i)) & 0x7FFFFFFF


def main() -> int:
    n_ens = int(os.getenv("N_ENS", "120"))
    n_irf = int(os.getenv("N_IRF", "40"))
    years = int(os.getenv("YEARS", "50"))
    max_agents = int(os.getenv("MAX_AGENTS", "100"))
    seed = int(os.getenv("SEED", "2026"))
    du = float(os.getenv("SHOCK_DU", "0.05"))
    dpi = float(os.getenv("SHOCK_DPI", "0.05"))
    sh_start = int(os.getenv("SHOCK_START", "5"))
    sh_win = int(os.getenv("SHOCK_WIN", "3"))
    irf_h = int(os.getenv("IRF_H", "25"))
    maxlag = int(os.getenv("MAXLAG", "5"))

    base = default_params()
    kp = key_priors()
    ap = all_priors()
    # curated set: key (physico-economic) + the direct social-channel priors
    curated = dict(kp)
    for nm in SOCIAL_PRIORS:
        if nm in ap:
            curated[nm] = ap[nm]
    curated_names = list(curated.keys())

    t0 = datetime.now()
    print(f"Social-channel analysis: ensemble N={n_ens} x {years}y, agents<= {max_agents}, "
          f"curated priors={len(curated_names)} (key {len(kp)} + social {len(SOCIAL_PRIORS)})")

    # ---------- ensemble (vary curated priors); record params + trajectories ----------
    P = []         # sampled curated-prior values per member
    TRAJ = []      # [member][year, 5]
    for i in range(n_ens):
        s = _member_seed(seed, i)
        sampled = sample_parameter_set(base, curated, random.Random(s))
        P.append([float(getattr(sampled, nm)) for nm in curated_names])
        TRAJ.append(run_member(s, sampled, years, max_agents))
    P = np.array(P)                 # [N, n_priors]
    TRAJ = np.array(TRAJ)           # [N, years+1, 5]
    ten = TRAJ[:, :, 0]             # [N, years+1]

    # 1. LOCALIZATION: Spearman(prior, final tension)
    final_ten = ten[:, years]
    loc = []
    for j, nm in enumerate(curated_names):
        if np.std(P[:, j]) == 0:
            continue
        rho, p = spearmanr(P[:, j], final_ten)
        loc.append((nm, float(rho), float(p)))
    loc.sort(key=lambda r: -abs(r[1]))

    # 2. ACCUMULATION: cross-member spread vs horizon
    accum = {}
    for h in sorted({h for h in (5, 10, 25, 50) if h <= years}):
        col = ten[:, h]
        accum[h] = {"mean": float(col.mean()), "std": float(col.std(ddof=1)),
                    "p5": float(np.percentile(col, 5)), "p95": float(np.percentile(col, 95))}

    # 4. DISTRIBUTED-LAG REGRESSION (within-member FE, cluster-robust) on the ensemble panel
    import statsmodels.api as smf
    rows_y, rows_x, rows_g = [], [], []
    for m in range(n_ens):
        tr = TRAJ[m]
        stress = tr[:, 1] + tr[:, 2]          # unemployment + inflation
        dten = np.diff(tr[:, 0])              # Δtension_t, t=1..years
        for t in range(maxlag, years):
            rows_y.append(dten[t])            # change over year t -> t+1 index align (dten[t]=ten[t+1]-ten[t])
            rows_x.append([stress[t - k] for k in range(maxlag + 1)])
            rows_g.append(m)
    Y = np.array(rows_y); X = np.array(rows_x); G = np.array(rows_g)
    # within-member demeaning (entity fixed effects)
    Yc = Y.copy(); Xc = X.copy()
    for m in np.unique(G):
        idx = G == m
        Yc[idx] -= Yc[idx].mean()
        Xc[idx] -= Xc[idx].mean(axis=0)
    Xd = smf.add_constant(Xc, has_constant="add")
    ols = smf.OLS(Yc, Xd).fit(cov_type="cluster", cov_kwds={"groups": G})
    lag_coef = []
    for k in range(maxlag + 1):
        c = float(ols.params[k + 1]); pv = float(ols.pvalues[k + 1])
        lag_coef.append({"lag": k, "beta": c, "p_value": pv})
    cum_effect = float(sum(d["beta"] for d in lag_coef))

    # 3. IMPULSE RESPONSE: paired baseline vs stagflation shock over key (physico-economic) priors
    shock_years = list(range(sh_start, sh_start + sh_win))
    irf = np.zeros((n_irf, irf_h + 1))
    base_path = np.zeros((n_irf, irf_h + 1))
    for i in range(n_irf):
        s = _member_seed(seed + 777, i)
        sp = sample_parameter_set(base, kp, random.Random(s))
        tb = run_member(s, sp, sh_start + irf_h, max_agents)
        ts = run_member(s, sp, sh_start + irf_h, max_agents, shock_years=shock_years, du=du, dpi=dpi)
        for h in range(irf_h + 1):
            irf[i, h] = ts[sh_start + h, 0] - tb[sh_start + h, 0]
            base_path[i, h] = tb[sh_start + h, 0]
    irf_mean = irf.mean(axis=0)
    irf_lo = np.percentile(irf, 5, axis=0)
    irf_hi = np.percentile(irf, 95, axis=0)
    frac_pos = (irf > 0).mean(axis=0)
    peak_lag = int(np.argmax(irf_mean))

    elapsed = (datetime.now() - t0).total_seconds()
    out = {
        "experiment": "Physico-economic -> social-tension channel: localization, accumulation, "
                      "impulse response, distributed-lag regression",
        "config": {"n_ens": n_ens, "n_irf": n_irf, "years": years, "max_agents": max_agents,
                   "seed": seed, "shock": {"du": du, "dpi": dpi, "years": shock_years},
                   "irf_horizon": irf_h, "maxlag": maxlag, "curated_priors": curated_names},
        "localization_spearman_top": [
            {"prior": nm, "rho": round(r, 3), "p_value": round(p, 5)} for nm, r, p in loc[:12]],
        "accumulation_spread": {str(h): {k: round(v, 5) for k, v in d.items()}
                                for h, d in accum.items()},
        "impulse_response": {
            "lag_years": list(range(irf_h + 1)),
            "mean": [round(float(x), 5) for x in irf_mean],
            "p5": [round(float(x), 5) for x in irf_lo],
            "p95": [round(float(x), 5) for x in irf_hi],
            "frac_positive": [round(float(x), 3) for x in frac_pos],
            "peak_lag": peak_lag,
            "peak_response": round(float(irf_mean[peak_lag]), 5),
            "response_at_lag10": round(float(irf_mean[min(10, irf_h)]), 5),
            "baseline_tension_at_shock": round(float(base_path[:, 0].mean()), 4),
        },
        "distributed_lag_regression": {
            "spec": "within-member FE; dep=Δtension_t; regr=stress(u+π) lags 0..K; cluster SE by member",
            "n_obs": int(len(Y)), "coefficients": lag_coef,
            "cumulative_effect": round(cum_effect, 5),
            "r_squared_within": round(float(ols.rsquared), 4),
        },
        "elapsed_sec": round(elapsed, 1),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "results", "social_channel")
    os.makedirs(out_dir, exist_ok=True)
    fp = os.path.join(out_dir, "social_channel.json")
    with open(fp, "w") as fh:
        json.dump(out, fh, indent=2)
        fh.write("\n")

    print(f"\n[1] LOCALIZATION — Spearman(prior, final tension), top 6:")
    for nm, r, p in loc[:6]:
        tag = "  <-- social-channel prior" if nm in SOCIAL_PRIORS else ""
        print(f"    {nm:32s} rho={r:+.3f}  p={p:.4g}{tag}")
    print(f"[2] ACCUMULATION — cross-member tension std grows with horizon:")
    for h in sorted(accum):
        print(f"    h={h:>2}: std={accum[h]['std']:.5f}  (5-95%: {accum[h]['p5']:.4f}-{accum[h]['p95']:.4f})")
    print(f"[3] IMPULSE RESPONSE — stagflation pulse (u+{du}, π+{dpi}, {sh_win}y):")
    print(f"    peak Δtension={irf_mean[peak_lag]:+.5f} at lag {peak_lag}y; "
          f"at lag10={irf_mean[min(10,irf_h)]:+.5f}; share positive at peak={frac_pos[peak_lag]:.0%}")
    print(f"[4] DISTRIBUTED-LAG REGRESSION — Δtension on stress lags (FE, clustered):")
    for d in lag_coef:
        star = "***" if d["p_value"] < 0.001 else "**" if d["p_value"] < 0.01 else "*" if d["p_value"] < 0.05 else ""
        print(f"    lag {d['lag']}: beta={d['beta']:+.4f}  p={d['p_value']:.4g} {star}")
    print(f"    cumulative effect={cum_effect:+.4f},  within-R^2={ols.rsquared:.3f}")
    print(f"\nDone in {elapsed:.1f}s. ledger -> {os.path.relpath(fp, os.getcwd())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
