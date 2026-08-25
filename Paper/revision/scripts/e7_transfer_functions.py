#!/usr/bin/env python3
"""E7 -- what the integration benchmark actually shows.

Appendix B currently argues that across three channels "GIM shows a positive, measurable
slope where every sectoral model is flat at zero -- the integration dividend, quantified".
A sectoral model has no society block, so its slope on the society axis is zero by
construction rather than by measurement; the comparison cannot be a benchmark. What IS
measurable, and worth reporting, is the SHAPE and GAIN of each cross-sector transfer
function, and where in the chain the nonlinearity is generated.

This script re-reads the benchmark sweeps and asks, per channel:
  1. shape -- log-log exponent, curvature against a linear fit, and step structure;
  2. WHERE the nonlinearity lives -- for the crop chain, whether the resource -> society
     leg contributes any curvature of its own or transmits with constant gain;
  3. the cascade ordering -- which countries tip under the oil burden, at what dose, and
     whether that ordering is anything more than a ranking on the trigger's own variable;
  4. an injection-point audit -- how much of each claimed chain is inside the model and
     how much is computed by hand outside it.

Writes Paper/revision/results/e7_transfer_functions.json
"""
from __future__ import annotations

import copy
import glob
import json
import math
import os
import sys

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.core.policy import simple_rule_based_policy   # noqa: E402
from gim.core.simulation import step_world             # noqa: E402
from gim.runtime import load_world                     # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results",
                   "e7_transfer_functions.json")
HORIZON = 10
SHOCK_WINDOW = 4
BURDENS = [0.0, 0.02, 0.03, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20]


def loglog_exponent(x, y):
    """Power-law exponent of y ~ x^b over the strictly positive points."""
    pts = [(a, b) for a, b in zip(x, y) if a > 0 and b > 0]
    if len(pts) < 3:
        return None
    lx = np.log([a for a, _ in pts])
    ly = np.log([b for _, b in pts])
    b, a = np.polyfit(lx, ly, 1)
    resid = ly - (a + b * lx)
    r2 = 1.0 - resid.var() / ly.var() if ly.var() > 0 else float("nan")
    return {"exponent": float(b), "r2_loglog": float(r2), "n_points": len(pts)}


def curvature(x, y):
    """Quadratic-vs-linear fit through the origin: how much curvature is there?"""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    lin = np.polyfit(x, y, 1)
    quad = np.polyfit(x, y, 2)
    r_lin = y - np.polyval(lin, x)
    r_quad = y - np.polyval(quad, x)
    return {
        "linear_slope": float(lin[0]),
        "quadratic_coef": float(quad[0]),
        "r2_linear": float(1.0 - r_lin.var() / y.var()) if y.var() > 0 else float("nan"),
        "r2_quadratic": float(1.0 - r_quad.var() / y.var()) if y.var() > 0 else float("nan"),
        "max_step_jump": float(np.max(np.abs(np.diff(y)))) if y.size > 1 else 0.0,
        "n_distinct_levels": int(len(set(np.round(y, 9)))),
    }


def gain_constancy(num, den):
    """Is the second leg of a chain a constant-gain (linear) map of the first?"""
    r = [(n / d) for n, d in zip(num, den) if d not in (0, 0.0)]
    if not r:
        return None
    r = np.array(r)
    return {"gain_mean": float(r.mean()), "gain_min": float(r.min()),
            "gain_max": float(r.max()),
            "relative_spread": float((r.max() - r.min()) / r.mean()),
            "gains": [float(v) for v in r]}


# ---------------------------------------------------------------- oil cascade ordering
def _policies(world):
    return {aid: simple_rule_based_policy for aid in world.agents}


def oil_cascade_ordering(forward_init: bool):
    """forward_init=False reproduces the benchmark's own configuration
    (gim_benchmark.py:371 calls load_world() with the default), which E6 showed is the
    one where resource prices pin. forward_init=True is the headline forward config."""
    base = load_world(forward_init=forward_init)
    importers = [i for i, a in base.agents.items()
                 if (a.resources.get("energy") is None)
                 or (a.resources["energy"].production < a.resources["energy"].consumption)]
    pre = {i: {"debt_gdp": float(base.agents[i].economy.public_debt /
                                 max(base.agents[i].economy.gdp, 1e-9)),
               "fx_reserves_gdp": float(getattr(base.agents[i].economy, "fx_reserves", 0.0) /
                                        max(base.agents[i].economy.gdp, 1e-9)),
               "gdp": float(base.agents[i].economy.gdp)}
           for i in importers}

    def run(burden):
        # Mirrors gim_benchmark.run_trajectory exactly: persistent memory dict, and the
        # shock hook applied AFTER the step (gim_benchmark.py:62-66), not before.
        w = copy.deepcopy(base)
        pol = _policies(w)
        mem: dict = {}
        for y in range(HORIZON):
            w = step_world(w, pol, memory=mem, enable_extreme_events=False)
            if y < SHOCK_WINDOW:
                for i in importers:
                    a = w.agents[i]
                    cost = burden * max(a.economy.gdp, 0.0)
                    a.economy.public_debt += cost
                    a.economy.fx_reserves = max(0.0, a.economy.fx_reserves - 0.5 * cost)
        return {i for i in importers
                if i in w.agents and w.agents[i].risk.debt_crisis_active_years > 0}

    baseline_set = run(0.0)
    tip_dose = {}
    per_burden = {}
    for b in BURDENS:
        s = run(b)
        extra = sorted(s - baseline_set)
        per_burden[f"{b:g}"] = {"n_extra": len(extra), "extra": extra}
        for c in extra:
            tip_dose.setdefault(c, b)

    tipped = sorted(tip_dose, key=lambda c: (tip_dose[c], c))
    rows = [{"country": c, "tip_burden": tip_dose[c], **pre[c]} for c in tipped]

    corr = {}
    if len(rows) >= 3:
        d = np.array([r["tip_burden"] for r in rows])
        for key in ("debt_gdp", "fx_reserves_gdp", "gdp"):
            v = np.array([r[key] for r in rows])
            if v.std() > 0 and d.std() > 0:
                rd = np.argsort(np.argsort(d)).astype(float)
                rv = np.argsort(np.argsort(v)).astype(float)
                corr[key] = float(np.corrcoef(rd, rv)[0, 1])
    return {
        "n_importers": len(importers),
        "n_in_crisis_at_zero_burden": len(baseline_set),
        "per_burden": per_burden,
        "tipping_order": rows,
        "spearman_tip_dose_vs_preshock": corr,
    }


def main() -> int:
    bpath = sorted(glob.glob(os.path.join(REPO, "results", "integration_benchmark",
                                          "*", "benchmark.json")))[-1]
    scen = {s["id"]: s for s in json.load(open(bpath))["scenarios"]}

    a = scen["A_carbon_tax"]["sweep"]
    b = scen["B_oil_shock"]["sweep"]
    c = scen["C_crop_shock"]["sweep"]

    shapes = {
        "A_carbon_tax": {
            "dose": a["carbon"],
            "emissions_cut_pct": {"values": a["emissions_cut_pct"],
                                  "loglog": loglog_exponent(a["carbon"], a["emissions_cut_pct"]),
                                  "fit": curvature(a["carbon"], a["emissions_cut_pct"])},
            "tension_delta": {"values": a["tension_delta"],
                              "loglog": loglog_exponent(a["carbon"], a["tension_delta"]),
                              "fit": curvature(a["carbon"], a["tension_delta"])},
        },
        "B_oil_shock": {
            "dose": b["burden_gdp"],
            "extra_in_crisis": {"values": b["extra_in_crisis"],
                                "fit": curvature(b["burden_gdp"], b["extra_in_crisis"])},
            "dca_delta": {"values": b["dca_delta"],
                          "fit": curvature(b["burden_gdp"], b["dca_delta"])},
        },
        "C_crop_shock": {
            "dose": c["yield_cut"],
            "food_delta": {"values": c["food_delta"],
                           "loglog": loglog_exponent(c["yield_cut"], c["food_delta"]),
                           "fit": curvature(c["yield_cut"], c["food_delta"])},
            "protest_delta": {"values": c["protest_delta"],
                              "loglog": loglog_exponent(c["yield_cut"], c["protest_delta"]),
                              "fit": curvature(c["yield_cut"], c["protest_delta"])},
            # the decisive test: does the resource -> society leg add curvature of its own?
            "protest_over_food_gain": gain_constancy(c["protest_delta"], c["food_delta"]),
        },
    }

    print("--- shapes ---")
    for k, v in shapes.items():
        print(k)
        for kk, vv in v.items():
            if kk == "dose" or not isinstance(vv, dict):
                continue
            ll = vv.get("loglog")
            fit = vv.get("fit")
            if ll and fit:
                print(f"   {kk:20s} exponent {ll['exponent']:+.3f} (R2 {ll['r2_loglog']:.4f})"
                      f"  R2_lin {fit['r2_linear']:.4f} -> R2_quad {fit['r2_quadratic']:.4f}"
                      f"  levels {fit['n_distinct_levels']}")
            elif fit:
                print(f"   {kk:20s} R2_lin {fit['r2_linear']:.4f} -> R2_quad {fit['r2_quadratic']:.4f}"
                      f"  max jump {fit['max_step_jump']:.3f}  levels {fit['n_distinct_levels']}")
    g = shapes["C_crop_shock"]["protest_over_food_gain"]
    print(f"\ncrop chain: protest/food gain = {g['gain_mean']:.5f} "
          f"[{g['gain_min']:.5f}, {g['gain_max']:.5f}], relative spread "
          f"{g['relative_spread']*100:.2f}%")

    cascades = {}
    for label, fi in (("benchmark_config_forward_init_false", False),
                      ("headline_forward_init_true", True)):
        print(f"\n--- oil cascade ordering [{label}] ---")
        casc = oil_cascade_ordering(fi)
        cascades[label] = casc
        print(f"importers {casc['n_importers']}, in crisis at zero burden "
              f"{casc['n_in_crisis_at_zero_burden']}")
        for r in casc["tipping_order"]:
            print(f"   {r['country']:10s} tips at burden {r['tip_burden']:.2f}  "
                  f"pre-shock debt/gdp {r['debt_gdp']:.3f}  reserves/gdp {r['fx_reserves_gdp']:.4f}")
        print("   Spearman tip-dose vs pre-shock:", casc["spearman_tip_dose_vs_preshock"])

    payload = {
        "experiment": "E7",
        "question": "What shape do the three cross-sector transfer functions have, where "
                    "is the nonlinearity generated, and is the cascade ordering more than "
                    "a ranking on the trigger's own variable?",
        "benchmark_source": os.path.relpath(bpath, REPO),
        "config": {"horizon": HORIZON, "shock_window": SHOCK_WINDOW, "burdens": BURDENS},
        "shapes": shapes,
        "oil_cascade": cascades,
        "injection_point_audit": {
            "A_carbon_tax": "carbon price enters as a CPI wedge; the emissions and "
                            "tension legs are both inside the model.",
            "B_oil_shock": "the supply cut is converted to an import bill OUTSIDE the "
                           "model by two hard-coded constants (elasticity 0.30, import "
                           "intensity 0.05, gim_benchmark.py:201-207) and injected "
                           "directly into public_debt and fx_reserves. The "
                           "resources -> finance leg is therefore NOT demonstrated; what is "
                           "demonstrated is finance -> sovereign-crisis thresholding.",
            "C_crop_shock": "the yield cut enters at the food supply gap; the "
                            "affordability and protest legs are inside the model.",
        },
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(os.path.abspath(OUT), "w") as fh:
        json.dump(payload, fh, indent=1)
    print("wrote", os.path.abspath(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
