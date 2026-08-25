#!/usr/bin/env python3
"""A5 experiment: constrained SUR/FGLS on the quarterly trio — NEGATIVE RESULT.

Hypothesis (roadmap A5): equation errors share common shocks (oil, war), so
joint GLS estimation should beat equation-by-equation constrained LSQ.

Setup: the quarterly production equations (regulator, inflation, executive)
aligned on a common T=40 sample; iterated FGLS with the A2 bounds preserved
(the stacked system is transformed by chol(Σ⁻¹) and solved with lsq_linear);
rolling leave-future-out OOS exactly as in fit_block_dynamics.oos_report.

Result (2026-08-04, fit window 2015Q1–2025Q4):
  error correlations: regulator↔inflation 0.53, inflation↔executive 0.20
  OOS RMSE           SUR      hybrid(production)
    key_rate         2.67     2.39
    inflation        4.58     3.72
    expenditure      3395     3620
  Verdict: SUR degrades exactly where the correlation is strongest — the
  small-sample Σ estimate is too noisy and FGLS reallocates variance against
  the forecast (it zeroes the rate's π response and the pass-through). The
  executive gain (−6%) is within the noise of a 7-point OOS and does not
  justify the machinery. NOT adopted; the hybrid constrained fit stays.

Run from repo root: python3 scripts/sur_experiment.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import numpy as np

from fit_block_dynamics import (annual_inputs, clsq, equation_designs,
                                fit_annual, fit_security_annual,
                                quarterly_inputs)
from gim.blocks.dynamics import BlockState, MacroState, run_endogenous

TRIO = (("regulator", 3), ("inflation", 3), ("executive", 0))


def sur_trio(d_sub, dq_sub, n_iter: int = 3) -> dict:
    """Iterated constrained FGLS over the quarterly trio; returns the
    annualized production-schema coefficients."""
    from scipy.optimize import lsq_linear
    designs = equation_designs(d_sub, dq_sub)
    eqs = {}
    for eq, cut in TRIO:
        dz = designs[eq]
        eqs[eq] = {"y": dz["y"][cut:], "X": dz["X"][cut:],
                   "bounds": dz["bounds"], "names": dz["names"],
                   "annualize": dz["annualize"]}
    keys = list(eqs)
    T = min(len(eqs[k]["y"]) for k in keys)
    for k in keys:
        eqs[k]["y"], eqs[k]["X"] = eqs[k]["y"][-T:], eqs[k]["X"][-T:]
    X1 = {k: np.column_stack([np.ones(T), eqs[k]["X"]]) for k in keys}
    betas = {k: clsq(eqs[k]["y"], eqs[k]["X"], eqs[k]["bounds"])[0]
             for k in keys}
    for _ in range(n_iter):
        E = np.column_stack([eqs[k]["y"] - X1[k] @ betas[k] for k in keys])
        Sigma = (E.T @ E) / T
        W = np.linalg.cholesky(np.linalg.inv(Sigma))
        p = [X1[k].shape[1] for k in keys]
        Xs = np.zeros((T * len(keys), sum(p)))
        ys = np.zeros(T * len(keys))
        for i in range(len(keys)):
            for j in range(len(keys)):
                w = W[j, i]
                if w == 0:
                    continue
                ys[i * T:(i + 1) * T] += w * eqs[keys[j]]["y"]
                c0 = sum(p[:j])
                Xs[i * T:(i + 1) * T, c0:c0 + p[j]] += w * X1[keys[j]]
        lo, hi = [], []
        for k in keys:
            lo.append(-np.inf)
            hi.append(np.inf)
            lo += [b[0] for b in eqs[k]["bounds"]]
            hi += [b[1] for b in eqs[k]["bounds"]]
        res = lsq_linear(Xs, ys, bounds=(np.array(lo), np.array(hi)))
        for idx, k in enumerate(keys):
            c0 = sum(p[:idx])
            betas[k] = res.x[c0:c0 + p[idx]]
    out = {}
    for k in keys:
        coeffs = {nm: float(betas[k][i]) for i, nm in enumerate(eqs[k]["names"])}
        out[k] = eqs[k]["annualize"](coeffs)
    return out


def main() -> None:
    d, dq = annual_inputs(), quarterly_inputs()
    fields = ["key_rate", "inflation", "expenditure"]
    errs = {f: [] for f in fields}
    for T in range(2018, 2025):
        d_sub, dq_sub = d.loc[:T], dq.loc[:(T, 4)]
        params = fit_annual(d_sub)
        params["security"] = fit_security_annual(d_sub)
        params.update(sur_trio(d_sub, dq_sub))
        rT, rT1 = d.loc[T], d.loc[T + 1]
        init = BlockState(T, float(rT.key_rate), float(rT.oilgas_rev),
                          float(rT.expenditure), float(rT.milex_share),
                          float(rT.real_income_growth))
        macro0 = MacroState(usd_rub=float(rT.usd_rub),
                            inflation=float(rT.inflation))
        states, macros = run_endogenous(
            init, macro0, [(T + 1, float(rT1.brent))], params,
            brent0=float(rT.brent))
        errs["key_rate"].append(float(states[-1].key_rate) - float(rT1.key_rate))
        errs["expenditure"].append(
            float(states[-1].expenditure) - float(rT1.expenditure))
        errs["inflation"].append(macros[-1].inflation - float(rT1.inflation))
    print("SUR OOS RMSE (vs hybrid golden in test_block_oos_golden):")
    for f in fields:
        rmse = float(np.sqrt(np.mean(np.square(errs[f]))))
        print(f"  {f:14s} {rmse:10.2f}")


if __name__ == "__main__":
    main()
