"""#12 Calibrate internal temperature variability (sigma, AR(1) rho) from observed residuals.

Procedure (Hawkins & Sutton 2009; Frankcombe et al. 2015):
  1. Drive GIM's 2-box EBM with OBSERVED CO2 concentration (concentration-mode climate backtest)
     to obtain the deterministic FORCED GMST response 1990-2023 (variability off).
  2. residual_t = observed_GMST_t - forced_GMST_t  (the internal/unforced component + obs noise).
  3. Demean, then fit AR(1):  rho = lag-1 autocorrelation,  sigma = stationary std of residuals.
  4. 95% CI by parametric AR(1) bootstrap (resample innovations, refit) — documents uncertainty.
  5. Cross-check sigma against the CMIP6 unforced GMST spread (~0.10-0.15 degC 1sigma, Deser 2020).

This replaces the 8-member 2015-2023 ensemble derivation of these parameters with a fit on the
full 1990-2023 observational record. The window is still short for ENSO (2-7 yr) — the CI is wide
and reported honestly — but it is the observational record we have bundled (HadCRUT5/NOAA fixture).

Run:  PYTHONPATH=<repo root> python3 calibration/calibrate_variability_ar1.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from gim.climate_backtest import run_climate_backtest

OUT = Path(__file__).resolve().parent / "variability_ar1_calibration.json"


def forced_residuals() -> tuple[np.ndarray, np.ndarray]:
    res = run_climate_backtest(mode="concentration")
    years = sorted(y for y in res.observed_temperature if y in res.predicted_temperature)
    obs = np.array([res.observed_temperature[y] for y in years])
    pred = np.array([res.predicted_temperature[y] for y in years])
    return np.array(years), obs - pred


def fit_ar1(resid: np.ndarray) -> tuple[float, float]:
    r = resid - resid.mean()
    sigma = float(np.std(r, ddof=1))
    # lag-1 autocorrelation
    num = float(np.sum(r[1:] * r[:-1]))
    den = float(np.sum(r * r))
    rho = num / den if den > 0 else 0.0
    return sigma, rho


def bootstrap_ci(resid: np.ndarray, n_boot: int = 5000, seed: int = 12) -> dict:
    rng = np.random.default_rng(seed)
    sigma0, rho0 = fit_ar1(resid)
    r = resid - resid.mean()
    n = len(r)
    # innovation std of the fitted AR(1): var_innov = sigma^2 * (1 - rho^2)
    innov_std = sigma0 * np.sqrt(max(1e-9, 1.0 - rho0 * rho0))
    sig_bs, rho_bs = [], []
    for _ in range(n_boot):
        w = np.zeros(n)
        w[0] = rng.normal(0.0, sigma0)
        eps = rng.normal(0.0, innov_std, size=n)
        for t in range(1, n):
            w[t] = rho0 * w[t - 1] + eps[t]
        s, rh = fit_ar1(w)
        sig_bs.append(s)
        rho_bs.append(rh)
    return {
        "sigma_ci95": [float(np.percentile(sig_bs, 2.5)), float(np.percentile(sig_bs, 97.5))],
        "rho_ci95": [float(np.percentile(rho_bs, 2.5)), float(np.percentile(rho_bs, 97.5))],
    }


def main() -> None:
    years, resid = forced_residuals()
    sigma, rho = fit_ar1(resid)
    ci = bootstrap_ci(resid)
    obs_std = float(np.std(resid - resid.mean(), ddof=1))
    out = {
        "method": "AR(1) fit on observed-minus-forced GMST residuals, 1990-2023",
        "n_years": int(len(years)),
        "year_range": [int(years[0]), int(years[-1])],
        "sigma_estimate": round(sigma, 4),
        "ar1_rho_estimate": round(rho, 4),
        "sigma_ci95": [round(x, 4) for x in ci["sigma_ci95"]],
        "rho_ci95": [round(x, 4) for x in ci["rho_ci95"]],
        "residual_std": round(obs_std, 4),
        "cmip6_internal_variability_ref": "0.10-0.15 degC 1sigma (Deser et al. 2020, Nat. Clim. Change)",
        "prior_values": {"sigma": 0.08, "rho": 0.65},
        "sources": [
            "Hawkins & Sutton (2009) BAMS 90:1095",
            "Frankcombe et al. (2015) J. Climate 28:8184",
            "Deser et al. (2020) Nat. Clim. Change 10:277",
            "Morice et al. (2021) JGR 126:e2019JD032361 (HadCRUT5)",
        ],
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
