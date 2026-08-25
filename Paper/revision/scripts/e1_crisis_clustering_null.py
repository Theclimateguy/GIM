#!/usr/bin/env python3
"""E1 -- null models for the Section 6 claim "late clustering of failures".

The paper reports: active crises per year rise from 1-2 in the 2020s to ~10 in the
2040s on the deterministic 30-year baseline, with a Fano (dispersion) index of 2.0,
and reads this as slow accumulators across blocks maturing together.

Two things are untested there.

(a) Fano is computed on a TRENDING deterministic series. Any monotone ramp has
    var/mean > 1 regardless of clustering, so the homogeneous-Poisson reference
    (Fano = 1) is the wrong null. The right reference is an INHOMOGENEOUS Poisson
    process with the same time-varying intensity: it reproduces the trend by
    construction and keeps only genuine excess dispersion.

(b) "Mature together" is a CROSS-BLOCK SYNCHRONY claim -- economic accumulators
    (debt, reserves) and social accumulators (trust, tension) crossing thresholds in
    the same window. Dispersion of a pooled count says nothing about synchrony.
    The test has to sever the coupling and see whether the co-timing survives.

This script runs the baseline plus six coupling-severed nulls (see
Paper/revision/CROSS_BLOCK_MAP.md) and computes, for each:

  * per-year counts of active crises by type (debt / fx / regime)
  * raw Fano, and Fano of the inhomogeneous-Poisson surrogate with matched intensity
  * detrended dispersion (residuals after a quadratic trend fit)
  * cross-block synchrony: lag-0 correlation of the economic-crisis and social-crisis
    onset series, and the share of onsets falling in the final decade

Writes Paper/revision/results/e1_crisis_clustering_null.json
"""
from __future__ import annotations

import copy
import json
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.core.policy import make_policy_map          # noqa: E402
from gim.core.simulation import step_world           # noqa: E402
from gim.runtime import load_world                   # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                   "e1_crisis_clustering_null.json")
HORIZON = 30
BASE_YEAR = 2023
SURROGATES = 4000
SEED = 20260824

# --- null configurations: parameter overrides that sever one named channel --------
# Names and membership are documented in Paper/revision/CROSS_BLOCK_MAP.md.
C1_ECONOMY_TO_SOCIETY = {
    "TRUST_GDP_PC_SENS": 0.0,
    "TRUST_UNEMPLOYMENT_SENS": 0.0,
    "TRUST_INFLATION_SENS": 0.0,
    "SOCIAL_STRESS_UNEMPLOYMENT_SENS": 0.0,
    "SOCIAL_STRESS_INFLATION_SENS": 0.0,
    "GINI_GROWTH_SENS": 0.0,
    "GINI_RECESSION_SENS": 0.0,
}
C2_SOCIETY_TO_ECONOMY = {
    "DEBT_SPREAD_FRAGILITY_SENS": 0.0,
    "SAVINGS_TENSION_SENS": 0.0,
}
C3_CLIMATE_TO_ECONOMY = {
    "DAMAGE_QUAD_COEFF": 0.0,
    "DAMAGE_RISK_ADJ": 0.0,
    "GROWTH_DAMAGE_TFP_COEFF": 0.0,
}
C6_CROSS_COUNTRY = {
    "GEOGRAPHY_TENSION_LINKS": False,
    "GEOGRAPHY_CLIMATE_LINKS": False,
    "GEO_TENSION_SPILLOVER_W": 0.0,
    "GEO_CLIMATE_SPILLOVER_W": 0.0,
    "GEO_CONTAGION_W": 0.0,
    "TFP_DIFFUSION_SENS": 0.0,
    "TFP_TRADE_SPILLOVER_SENS": 0.0,
}

CONFIGS: dict[str, dict] = {
    "baseline": {},
    "null_C1_no_economy_to_society": dict(C1_ECONOMY_TO_SOCIETY),
    "null_C2_no_society_to_economy": dict(C2_SOCIETY_TO_ECONOMY),
    "null_C12_economy_society_decoupled": {**C1_ECONOMY_TO_SOCIETY, **C2_SOCIETY_TO_ECONOMY},
    "null_C3_no_climate_to_economy": dict(C3_CLIMATE_TO_ECONOMY),
    "null_C6_no_cross_country": dict(C6_CROSS_COUNTRY),
    "null_all_cross_block": {**C1_ECONOMY_TO_SOCIETY, **C2_SOCIETY_TO_ECONOMY,
                             **C3_CLIMATE_TO_ECONOMY, **C6_CROSS_COUNTRY},
}

CRISIS_FIELDS = {
    "debt": "debt_crisis_active_years",
    "fx": "fx_crisis_active_years",
    "regime": "regime_crisis_active_years",
}
ECONOMIC = ("debt", "fx")
SOCIAL = ("regime",)


def run_trajectory(overrides: dict) -> dict:
    """One deterministic 30-year run; returns per-year active counts and onset counts."""
    world = load_world(forward_init=True)
    if overrides:
        world.params = world.params.with_overrides(overrides)
    policies = make_policy_map(list(world.agents.keys()), mode="simple")

    active = {k: [] for k in CRISIS_FIELDS}
    onsets = {k: [] for k in CRISIS_FIELDS}
    prev = {k: {aid: 0 for aid in world.agents} for k in CRISIS_FIELDS}

    for _ in range(HORIZON):
        world = step_world(world, policies, enable_extreme_events=False)
        for kind, field in CRISIS_FIELDS.items():
            n_active = 0
            n_onset = 0
            for aid, agent in world.agents.items():
                years = int(getattr(agent.risk, field))
                if years > 0:
                    n_active += 1
                # an onset is the transition into a crisis, i.e. the counter restarting at 1
                if years == 1 and prev[kind][aid] == 0:
                    n_onset += 1
                prev[kind][aid] = years
            active[kind].append(n_active)
            onsets[kind].append(n_onset)

    return {"active": active, "onsets": onsets}


def fano(x: np.ndarray) -> float:
    m = float(x.mean())
    return float(x.var() / m) if m > 0 else float("nan")


def inhomogeneous_poisson_fano(intensity: np.ndarray, rng: np.random.Generator,
                               draws: int = SURROGATES) -> dict:
    """Fano distribution of a Poisson process whose intensity follows the SAME trend.

    This is the null that isolates clustering from trend: the surrogate reproduces the
    rise from 1-2 to ~10 by construction, so any excess dispersion in the model is
    what remains.
    """
    lam = np.clip(intensity, 1e-9, None)
    samples = rng.poisson(lam=lam, size=(draws, lam.size))
    vals = np.array([fano(s.astype(float)) for s in samples])
    vals = vals[np.isfinite(vals)]
    return {
        "mean": float(vals.mean()),
        "sd": float(vals.std()),
        "q05": float(np.quantile(vals, 0.05)),
        "q50": float(np.quantile(vals, 0.50)),
        "q95": float(np.quantile(vals, 0.95)),
        "n": int(vals.size),
    }


def detrended_dispersion(x: np.ndarray) -> dict:
    """Dispersion of residuals after removing a quadratic trend.

    Under a pure inhomogeneous-Poisson process the residual variance equals the mean
    intensity, so residual_var / mean is the trend-free analogue of the Fano index and
    has an expected value of 1 whether or not the rate is time-varying.
    """
    t = np.arange(x.size, dtype=float)
    coef = np.polyfit(t, x.astype(float), 2)
    fit = np.polyval(coef, t)
    resid = x - fit
    m = float(np.clip(fit, 1e-9, None).mean())
    return {
        "trend_fit_first": float(fit[0]),
        "trend_fit_last": float(fit[-1]),
        "residual_var": float(resid.var()),
        "detrended_dispersion": float(resid.var() / m),
        "r2_trend": float(1.0 - resid.var() / x.astype(float).var()) if x.var() > 0 else float("nan"),
    }


def synchrony(onsets: dict) -> dict:
    """Cross-block co-timing of crisis onsets: economic (debt+fx) vs social (regime)."""
    econ = np.array([sum(onsets[k][t] for k in ECONOMIC) for t in range(HORIZON)], dtype=float)
    soc = np.array([sum(onsets[k][t] for k in SOCIAL) for t in range(HORIZON)], dtype=float)

    def corr(a, b):
        if a.std() == 0 or b.std() == 0:
            return float("nan")
        return float(np.corrcoef(a, b)[0, 1])

    last_decade = slice(HORIZON - 10, HORIZON)
    def late_share(v):
        tot = v.sum()
        return float(v[last_decade].sum() / tot) if tot > 0 else float("nan")

    return {
        "econ_onsets_total": float(econ.sum()),
        "social_onsets_total": float(soc.sum()),
        "corr_lag0": corr(econ, soc),
        "corr_lag1_econ_leads": corr(econ[:-1], soc[1:]) if HORIZON > 2 else float("nan"),
        "corr_lag2_econ_leads": corr(econ[:-2], soc[2:]) if HORIZON > 3 else float("nan"),
        "econ_late_decade_share": late_share(econ),
        "social_late_decade_share": late_share(soc),
        "econ_centroid_year": float(BASE_YEAR + 1 + (econ * np.arange(HORIZON)).sum() / econ.sum())
                              if econ.sum() > 0 else float("nan"),
        "social_centroid_year": float(BASE_YEAR + 1 + (soc * np.arange(HORIZON)).sum() / soc.sum())
                                if soc.sum() > 0 else float("nan"),
    }


def analyse(name: str, traj: dict, rng: np.random.Generator) -> dict:
    active = traj["active"]
    total = np.array([sum(active[k][t] for k in CRISIS_FIELDS) for t in range(HORIZON)], dtype=float)

    t = np.arange(HORIZON, dtype=float)
    intensity = np.polyval(np.polyfit(t, total, 2), t)

    out = {
        "counts_total_per_year": [int(v) for v in total],
        "counts_by_type": {k: [int(v) for v in active[k]] for k in CRISIS_FIELDS},
        "onsets_by_type": {k: [int(v) for v in traj["onsets"][k]] for k in CRISIS_FIELDS},
        "mean_per_year": float(total.mean()),
        "first_decade_mean": float(total[:10].mean()),
        "last_decade_mean": float(total[-10:].mean()),
        "fano_raw": fano(total),
        "fano_inhomogeneous_poisson_null": inhomogeneous_poisson_fano(intensity, rng),
        "detrended": detrended_dispersion(total),
        "synchrony": synchrony(traj["onsets"]),
    }
    null = out["fano_inhomogeneous_poisson_null"]
    out["fano_excess_over_trend_null"] = out["fano_raw"] - null["mean"]
    out["fano_exceeds_null_q95"] = bool(out["fano_raw"] > null["q95"])
    print(f"{name:38s} mean/yr {out['mean_per_year']:5.2f}  "
          f"{out['first_decade_mean']:5.2f}->{out['last_decade_mean']:5.2f}  "
          f"Fano {out['fano_raw']:5.2f} (trend-null {null['mean']:.2f} "
          f"[{null['q05']:.2f},{null['q95']:.2f}])  "
          f"detrended {out['detrended']['detrended_dispersion']:5.2f}  "
          f"sync r0 {out['synchrony']['corr_lag0']:+.2f}")
    return out


def main() -> int:
    rng = np.random.default_rng(SEED)
    results = {}
    for name, overrides in CONFIGS.items():
        traj = run_trajectory(overrides)
        results[name] = analyse(name, traj, rng)
        results[name]["overrides"] = {k: (v if isinstance(v, (int, float, bool)) else str(v))
                                      for k, v in overrides.items()}

    payload = {
        "experiment": "E1",
        "question": "Is the late clustering of failures a cross-block effect, and is Fano "
                    "the right statistic for it?",
        "config": {"horizon": HORIZON, "base_year": BASE_YEAR, "policy": "simple",
                   "extreme_events": False, "forward_init": True,
                   "poisson_surrogates": SURROGATES, "seed": SEED},
        "results": results,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(os.path.abspath(OUT), "w") as fh:
        json.dump(payload, fh, indent=1)
    print("wrote", os.path.abspath(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
