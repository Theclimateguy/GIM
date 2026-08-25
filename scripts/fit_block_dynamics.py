#!/usr/bin/env python3
"""Fit the block reaction functions (THE-126; roadmap A1-A3 refit 2026-08).

Five behavioural equations — one per pilot block — plus the macro bridge
(fx, inflation) and the Levada interaction channel (tension, trust), written
to data/blocks/RUS/dynamics_params.json:

  regulator      key_rate = a0 + a1·inflation + a2·fx_depreciation
                 (Taylor-style: CBR reacts to prices and the rouble)
  capital_elite  ln(oilgas_revenue_rub) = b0 + b1·ln(brent_usd · usd_rub)
                 (rent flow: price×fx elasticity; volumes move little)
  executive      Δln(expenditure_rub) = c0 + c1·Δln(oilgas_revenue_rub)
                 (fiscal rule: spending follows the rent, smoothed)
  security       milex_share = d0 + d1·milex_share₋₁ + d2·war_dummy(≥2022)
                 (persistence + regime break)
  households     real_income_growth = e0 + e1·(−inflation) + e2·Δln(oilgas_rev)
                 (petro-economy pass-through to incomes)

Estimation (roadmap A1-A3):
  A2  constrained least squares — sign/range bounds per coefficient (BOUNDS);
      the Taylor principle is checked and warned about, not enforced (see
      _fit_regulator: enforcing it cost OOS 2.39->3.09).
  A1  --freq q fits on the quarterly panel (44 points vs 10) and annualizes
      into the same parameter schema (see fit_quarterly's rules), so the
      annual engine, core bridge and propagate sub-step are untouched.
  A3  --oos prints the rolling leave-future-out report (fit [2015..T],
      predict T+1); --freq hybrid selects, per equation, the frequency that
      wins OOS RMSE — this is what produces the production params file.

Run from repo root: python3 scripts/fit_block_dynamics.py --freq hybrid
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

SERIES = Path("data/blocks/RUS/series")
RAW = Path("data/blocks/RUS/raw")
OUT = Path("data/blocks/RUS/dynamics_params.json")
# Fit window extended to 2025 (THE-130); 2026 stays a holdout for forward_run.
YEARS = list(range(2015, 2026))


def war_intensity(year: int) -> float:
    """Time-varying war-economy intensity: escalation years since 2022, capped at 4."""
    return float(min(max(0, year - 2021), 4))


def ols(y: np.ndarray, X: np.ndarray) -> tuple[np.ndarray, float]:
    X1 = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    resid = y - X1 @ beta
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) @ (y - y.mean())) or 1e-12)
    return beta, 1 - ss_res / ss_tot


def clsq(y: np.ndarray, X: np.ndarray,
         bounds: list[tuple[float, float]],
         intercept: bool = True) -> tuple[np.ndarray, float]:
    """Constrained least squares (roadmap A2): sign/range bounds per
    coefficient keep multicollinearity from flipping economic signs
    (pass-through and rent_contraction both did on the annual sample).
    `bounds` covers the slope columns; the intercept (prepended when
    `intercept`) is unbounded."""
    from scipy.optimize import lsq_linear
    X1 = np.column_stack([np.ones(len(y)), X]) if intercept else X
    all_bounds = ([(-np.inf, np.inf)] if intercept else []) + list(bounds)
    lo = np.array([b[0] for b in all_bounds])
    hi = np.array([b[1] for b in all_bounds])
    res = lsq_linear(X1, y, bounds=(lo, hi))
    beta = res.x
    resid = y - X1 @ beta
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) @ (y - y.mean())) or 1e-12)
    return beta, 1 - ss_res / ss_tot


def annual_inputs() -> pd.DataFrame:
    df = pd.DataFrame(index=YEARS)

    import re as _re
    kr_rows = []
    for f in (RAW / "cbr").glob("keyrate_*.xml"):
        kr_rows += _re.findall(r"<DT>(\d{4})-\d{2}-\d{2}T[^<]*</DT><Rate>([\d.]+)</Rate>",
                               f.read_text())
    kr = pd.DataFrame(kr_rows, columns=["year", "v"]).astype({"year": int, "v": float})
    df["key_rate"] = kr.groupby("year")["v"].mean()

    fx_rows = []
    for f in (RAW / "cbr").glob("usd_rub_daily_*.xml"):
        fx_rows += _re.findall(r'Date="\d{2}\.\d{2}\.(\d{4})"[^>]*>.*?<VunitRate>([\d,]+)<',
                               f.read_text(encoding="windows-1251"))
    fx = pd.DataFrame(fx_rows, columns=["year", "v"])
    fx["v"] = fx["v"].str.replace(",", ".").astype(float)
    df["usd_rub"] = fx.astype({"year": int}).groupby("year")["v"].mean()
    df["fx_depr"] = df["usd_rub"].pct_change() * 100

    cpi = pd.read_excel(RAW / "rosstat/cpi_55396_emiss.xls", header=None)
    hdr = cpi.iloc[2]
    years = {i: int(float(v)) for i, v in hdr.items()
             if str(v).replace(".0", "").isdigit()}
    rf = cpi[cpi.apply(lambda r: "643 Российская Федерация" in str(r.tolist()), axis=1)]
    row = rf.iloc[0]
    df["inflation"] = pd.Series(
        {yr: float(row[c]) - 100.0 for c, yr in years.items() if pd.notna(row[c])})

    bud = pd.read_csv(SERIES / "minfin_budget_quarterly.csv")
    ann = bud.groupby(["series", "year"])["value"].sum().unstack(0)
    df["oilgas_rev"] = ann["revenue_oilgas"]
    df["expenditure"] = ann["expenditure_total"]

    brent = pd.read_csv(RAW / "energy/brent_daily_fred.csv")
    brent["year"] = brent["observation_date"].str[:4].astype(int)
    df["brent"] = brent.groupby("year")["DCOILBRENTEU"].mean()

    sipri = pd.read_csv(SERIES / "sipri_milex_annual.csv")
    df["milex_share"] = sipri[sipri.series == "milex_pct_gdp"].set_index("year")["value"] * 100

    inc = pd.read_csv(SERIES / "rosstat_real_income_quarterly.csv")
    ri = inc[inc.series == "real_disposable_income_yoy"]
    df["real_income_growth"] = ri.groupby("year")["value"].mean() - 100.0

    return df.loc[YEARS]


QUARTERS = [(y, q) for y in YEARS for q in (1, 2, 3, 4)]


def quarterly_inputs() -> pd.DataFrame:
    """Quarterly panel for the A1 refit: same observables as annual_inputs()
    but 4 points per year (2015Q1–2025Q4 = 44). Security (SIPRI milex) stays
    annual — no quarterly source exists."""
    import re as _re
    idx = pd.MultiIndex.from_tuples(QUARTERS, names=["year", "quarter"])
    df = pd.DataFrame(index=idx)

    kr_rows = []
    for f in (RAW / "cbr").glob("keyrate_*.xml"):
        kr_rows += _re.findall(
            r"<DT>(\d{4})-(\d{2})-\d{2}T[^<]*</DT><Rate>([\d.]+)</Rate>",
            f.read_text())
    kr = pd.DataFrame(kr_rows, columns=["year", "mm", "v"]).astype(
        {"year": int, "mm": int, "v": float})
    kr["quarter"] = (kr["mm"] - 1) // 3 + 1
    df["key_rate"] = kr.groupby(["year", "quarter"])["v"].mean()

    fx_rows = []
    for f in (RAW / "cbr").glob("usd_rub_daily_*.xml"):
        fx_rows += _re.findall(
            r'Date="\d{2}\.(\d{2})\.(\d{4})"[^>]*>.*?<VunitRate>([\d,]+)<',
            f.read_text(encoding="windows-1251"))
    fx = pd.DataFrame(fx_rows, columns=["mm", "year", "v"])
    fx["v"] = fx["v"].str.replace(",", ".").astype(float)
    fx = fx.astype({"year": int, "mm": int})
    fx["quarter"] = (fx["mm"] - 1) // 3 + 1
    fxq = fx.groupby(["year", "quarter"])["v"].mean()
    df["usd_rub"] = fxq
    # YoY depreciation, % — same units as the annual spec (and the engine)
    df["fx_depr_yoy"] = (fxq / fxq.shift(4) - 1.0).reindex(idx) * 100

    cpi = pd.read_csv(SERIES / "cpi_monthly.csv")
    yoy = cpi[cpi.series == "cpi_yoy"].copy()
    yoy["year"] = yoy["month"].str[:4].astype(int)
    yoy["quarter"] = (yoy["month"].str[5:7].astype(int) - 1) // 3 + 1
    df["inflation"] = yoy.groupby(["year", "quarter"])["value"].mean() - 100.0

    bud = pd.read_csv(SERIES / "minfin_budget_quarterly.csv")
    q = bud.pivot_table(index=["year", "quarter"], columns="series",
                        values="value", aggfunc="sum")
    df["oilgas_rev"] = q["revenue_oilgas"]
    df["expenditure"] = q["expenditure_total"]

    brent = pd.read_csv(RAW / "energy/brent_daily_fred.csv").dropna()
    brent["year"] = brent["observation_date"].str[:4].astype(int)
    brent["quarter"] = (brent["observation_date"].str[5:7].astype(int) - 1) // 3 + 1
    df["brent"] = brent.groupby(["year", "quarter"])["DCOILBRENTEU"].mean()

    inc = pd.read_csv(SERIES / "rosstat_real_income_quarterly.csv")
    ri = inc[inc.series == "real_disposable_income_yoy"]
    df["real_income_growth"] = ri.set_index(["year", "quarter"])["value"] - 100.0

    lev_dir = pd.read_csv(SERIES / "levada_direction_monthly.csv")
    lev_dir["year"] = lev_dir["month"].str[:4].astype(int)
    lev_dir["quarter"] = (lev_dir["month"].str[5:7].astype(int) - 1) // 3 + 1
    df["tension"] = lev_dir.groupby(["year", "quarter"])["wrong_direction"].mean() / 100
    lev_app = pd.read_csv(SERIES / "levada_approval_monthly.csv")
    gov = lev_app[lev_app.entity == "government"].copy()
    gov["year"] = gov["month"].str[:4].astype(int)
    gov["quarter"] = (gov["month"].str[5:7].astype(int) - 1) // 3 + 1
    df["trust"] = gov.groupby(["year", "quarter"])["approve"].mean() / 100

    df["W"] = [war_intensity(y) for y, _ in df.index]
    return df.reindex(idx)


# A2 sign/range bounds, shared by both frequencies (slope columns only, in
# the column order each equation builds its design matrix):
INF = float("inf")
BOUNDS = {
    "regulator": [(0.01, 0.99), (0.0, INF), (0.0, INF)],   # lag, inflation, W
    "capital_elite": [(0.5, 1.2)],                          # rent elasticity
    "executive": [(0.0, INF), (0.0, INF)],                  # crisis, W
    "security": [(0.0, 0.99), (0.0, INF)],                  # lag, W
    "households": [(0.0, INF), (0.0, INF)],                 # −inflation, W
    "fx": [(-INF, 0.0), (0.0, INF), (-INF, 0.0)],           # dln_brent, W, real_rate
    "inflation": [(0.0, 0.99), (0.0, INF), (0.0, INF),      # lag, pass-through,
                  (0.0, INF), (-INF, 0.0)],                 # shock2022, W, rr_pos
    "tension": [(0.0, INF), (0.0, INF), (0.0, INF)],        # squeeze, rent, W
    "trust": [(-INF, 0.0)],                                 # d_tension
}


def _taylor_check(p: dict) -> None:
    lr = p["inflation"] / max(1e-9, 1.0 - p["lag_rate"])
    if lr <= 1.0:
        print(f"  WARNING: Taylor principle violated — long-run inflation "
              f"response {lr:.2f} <= 1")


def _fit_regulator(y: np.ndarray, X: np.ndarray,
                   lag_bounds: tuple[float, float] | None = None
                   ) -> tuple[np.ndarray, float]:
    """Regulator fit. The Taylor principle (long-run inflation response
    β/(1−ρ) > 1) is CHECKED but not enforced: A3 arbitrated it — enforcing
    the floor costs OOS RMSE 2.39→3.09 (and in-sample 0.89→0.78). On this
    sample the CBR reads as inertia + a neutral-rate anchor (const ≈ 4.8)
    + the war-economy premium, with a small short-run π response; the
    warning from _taylor_check keeps the violation visible in every fit
    report. `lag_bounds` lets quarterly fits impose the smoothing prior
    ρ_q ∈ [0.5, 0.95] of the Taylor-rule literature."""
    bounds = [list(b) for b in BOUNDS["regulator"]]
    if lag_bounds is not None:
        bounds[0] = list(lag_bounds)
    return clsq(y, X, [tuple(b) for b in bounds])


def fit_security_annual(d: pd.DataFrame) -> dict:
    """Security stays annual at any frequency: SIPRI milex is annual-only."""
    W = np.array([war_intensity(y) for y in d.index])
    y = d["milex_share"].to_numpy()[1:]
    lag = d["milex_share"].to_numpy()[:-1]
    beta, r2 = clsq(y, np.column_stack([lag, W[1:]]), BOUNDS["security"])
    return {"const": beta[0], "lag": beta[1], "war_intensity": beta[2], "r2": r2}


def fit_annual(d: pd.DataFrame) -> dict[str, dict]:
    years = list(d.index)
    params: dict[str, dict] = {}
    W = np.array([war_intensity(y) for y in years])

    # regulator: inertial Taylor rule + war-economy premium (overheated demand
    # forces rates far above the peacetime inflation response — 2024-25)
    y = d["key_rate"].to_numpy()[1:]
    X = np.column_stack([d["key_rate"].to_numpy()[:-1],
                         d["inflation"].to_numpy()[1:], W[1:]])
    beta, r2 = _fit_regulator(y, X)
    params["regulator"] = {"const": beta[0], "lag_rate": beta[1],
                           "inflation": beta[2], "war_intensity": beta[3], "r2": r2}
    _taylor_check(params["regulator"])

    # capital_elite (log-log)
    y = np.log(d["oilgas_rev"].to_numpy())
    X = np.log((d["brent"] * d["usd_rub"]).to_numpy()).reshape(-1, 1)
    beta, r2 = clsq(y, X, BOUNDS["capital_elite"])
    params["capital_elite"] = {"const": beta[0], "ln_brent_rub": beta[1], "r2": r2}

    # executive: the fiscal rule DECOUPLES spending from oil (that is its purpose —
    # NWF absorbs the rent swing); expenditure = trend growth + crisis impulses.
    dl_exp = np.diff(np.log(d["expenditure"].to_numpy()))
    crisis = np.isin(years[1:], [2020, 2022]).astype(float)
    beta, r2 = clsq(dl_exp, np.column_stack([crisis, W[1:]]), BOUNDS["executive"])
    params["executive"] = {"const": beta[0], "crisis": beta[1],
                           "war_intensity": beta[2], "r2": r2}

    params["security"] = fit_security_annual(d)

    # households: inflation erodes income; war transfers scale with intensity
    y = d["real_income_growth"].to_numpy()[1:]
    X = np.column_stack([-d["inflation"].to_numpy()[1:], W[1:]])
    beta, r2 = clsq(y, X, BOUNDS["households"])
    params["households"] = {"const": beta[0], "neg_inflation": beta[1],
                            "war_intensity": beta[2], "r2": r2}

    # --- macro bridge: endogenous fx and inflation ------------------------
    # Real rate (lagged) is the policy channel THE-130 adds: a hawkish CBR
    # props the rouble up (2025) and suppresses inflation.
    real_rate_lag = (d["key_rate"] - d["inflation"]).to_numpy()[:-1]

    # fx: oil terms-of-trade + war pressure − real-rate support
    dl_fx = np.diff(np.log(d["usd_rub"].to_numpy()))
    dl_brent = np.diff(np.log(d["brent"].to_numpy()))
    beta, r2 = clsq(dl_fx, np.column_stack([dl_brent, W[1:], real_rate_lag / 100]),
                    BOUNDS["fx"])
    params["fx"] = {"const": beta[0], "dln_brent": beta[1],
                    "war_intensity": beta[2], "real_rate": beta[3], "r2": r2}

    # inflation: persistence + asymmetric fx pass-through + 2022 supply shock
    # + war-economy demand pull − real-rate suppression
    y = d["inflation"].to_numpy()[1:]
    depr_pos = np.clip(d["fx_depr"].to_numpy()[1:], 0, None)
    shock_2022 = (np.array(years[1:]) == 2022).astype(float)
    X = np.column_stack([d["inflation"].to_numpy()[:-1], depr_pos, shock_2022,
                         W[1:], np.clip(real_rate_lag, 0, None)])
    beta, r2 = clsq(y, X, BOUNDS["inflation"])
    params["inflation"] = {"const": beta[0], "lag": beta[1],
                           "fx_depr_pos": beta[2], "shock2022": beta[3],
                           "war_intensity": beta[4], "real_rate_pos": beta[5],
                           "r2": r2}

    # --- interaction channel: fitted on Levada (replaces structural priors) ---
    # tension proxy = wrong-direction share /100; trust = government approval /100
    lev_dir = pd.read_csv(SERIES / "levada_direction_monthly.csv")
    lev_dir["year"] = lev_dir["month"].str[:4].astype(int)
    tension = (lev_dir.groupby("year")["wrong_direction"].mean() / 100).reindex(years)
    lev_app = pd.read_csv(SERIES / "levada_approval_monthly.csv")
    lev_app["year"] = lev_app["month"].str[:4].astype(int)
    gov = lev_app[lev_app.entity == "government"]
    trust = (gov.groupby("year")["approve"].mean() / 100).reindex(years)

    dl_rev = np.diff(np.log(d["oilgas_rev"].to_numpy()))
    squeeze = -(d["real_income_growth"].to_numpy()[1:])
    rent_contr = np.clip(-dl_rev, 0, None)
    y = np.diff(tension.to_numpy())
    # No intercept: in a calm year (no squeeze, no rent contraction, no war)
    # tension must not drift — a fitted constant saturates 20-year runs.
    X = np.column_stack([squeeze, rent_contr, W[1:]])
    beta, r2 = clsq(y, X, BOUNDS["tension"], intercept=False)
    params["tension"] = {"const": 0.0, "squeeze": beta[0],
                         "rent_contraction": beta[1],
                         "war_intensity": beta[2], "r2": r2}
    y = np.diff(trust.to_numpy())
    beta, r2 = clsq(y, np.diff(tension.to_numpy()).reshape(-1, 1), BOUNDS["trust"])
    params["trust"] = {"const": beta[0], "d_tension": beta[1], "r2": r2}
    if 2023 in tension.index and pd.notna(tension.loc[2023]):
        params["levada_levels_2023"] = {"tension": float(tension.loc[2023]),
                                        "trust_gov": float(trust.loc[2023])}
    return params


def _annualize_ar(p: dict, lag_key: str, scale_keys: list[str]) -> dict:
    """AR(1) quarterly → annual: lag compounds (ρ_a = ρ_q⁴); the other
    coefficients scale by (1−ρ_a)/(1−ρ_q) so the long-run response — the
    economically identified quantity — is preserved exactly."""
    out = dict(p)
    rho_q = p[lag_key]
    rho_a = rho_q ** 4
    s = (1.0 - rho_a) / (1.0 - rho_q)
    out[lag_key] = rho_a
    for k in scale_keys:
        out[k] = p[k] * s
    return out


def fit_quarterly(dq: pd.DataFrame, d: pd.DataFrame) -> dict[str, dict]:
    """A1: fit on the quarterly panel (44 points vs 10 annual), then map every
    equation to the annual-engine parameter schema so dynamics.py, the core
    bridge and the propagate sub-step stay untouched.

    Annualization rules (documented per equation below):
      AR levels (regulator, inflation): ρ_a = ρ_q⁴, others × (1−ρ_a)/(1−ρ_q)
      YoY specs (executive Δ₄ln, households): coefficients transfer 1:1
      QoQ flows (fx Δln): const/W/real_rate × 4, brent slope × 1 (Δln sums)
      diffs (tension, trust const): × 4 per year; slopes on same-scale
      regressors (rent contraction, d_tension) × 1
      capital_elite: elasticity from the quarterly panel, intercept
      re-centred on annual identities (quarterly fit carries Q dummies)
      security: annual (SIPRI has no quarterly series)
    """
    params: dict[str, dict] = {}
    qraw: dict[str, dict] = {}
    W = dq["W"].to_numpy()

    # regulator — quarterly inertia on YoY inflation
    y = dq["key_rate"].to_numpy()[1:]
    X = np.column_stack([dq["key_rate"].to_numpy()[:-1],
                         dq["inflation"].to_numpy()[1:], W[1:]])
    # quarterly policy-rate smoothing prior: rho_q in [0.5, 0.95]
    beta, r2 = _fit_regulator(y, X, lag_bounds=(0.5, 0.95))
    qraw["regulator"] = {"const": beta[0], "lag_rate": beta[1],
                         "inflation": beta[2], "war_intensity": beta[3], "r2": r2}
    params["regulator"] = _annualize_ar(
        qraw["regulator"], "lag_rate", ["const", "inflation", "war_intensity"])
    _taylor_check(params["regulator"])

    # capital_elite — elasticity from 44 points (quarter dummies soak up the
    # rent seasonality), intercept re-centred on the annual identity
    y = np.log(dq["oilgas_rev"].to_numpy())
    qd = np.array([[1.0 if qq == k else 0.0 for k in (2, 3, 4)]
                   for _, qq in dq.index])
    X = np.column_stack([np.log((dq["brent"] * dq["usd_rub"]).to_numpy()), qd])
    beta, r2 = clsq(y, X, BOUNDS["capital_elite"] + [(-INF, INF)] * 3)
    b1 = beta[1]
    const_a = float(np.mean(np.log(d["oilgas_rev"].to_numpy())
                            - b1 * np.log((d["brent"] * d["usd_rub"]).to_numpy())))
    qraw["capital_elite"] = {"const": beta[0], "ln_brent_rub": b1, "r2": r2}
    params["capital_elite"] = {"const": const_a, "ln_brent_rub": b1, "r2": r2}

    # executive — Δ₄ln kills the Q4 spending spike; coefficients are already
    # annual-growth units, transfer 1:1
    lexp = np.log(dq["expenditure"].to_numpy())
    dl4 = lexp[4:] - lexp[:-4]
    yrs = np.array([yy for yy, _ in dq.index])[4:]
    crisis = np.isin(yrs, [2020, 2022]).astype(float)
    beta, r2 = clsq(dl4, np.column_stack([crisis, W[4:]]), BOUNDS["executive"])
    qraw["executive"] = params["executive"] = {
        "const": beta[0], "crisis": beta[1], "war_intensity": beta[2], "r2": r2}

    params["security"] = fit_security_annual(d)

    # households — YoY spec, transfers 1:1
    y = dq["real_income_growth"].to_numpy()
    X = np.column_stack([-dq["inflation"].to_numpy(), W])
    beta, r2 = clsq(y, X, BOUNDS["households"])
    qraw["households"] = params["households"] = {
        "const": beta[0], "neg_inflation": beta[1], "war_intensity": beta[2],
        "r2": r2}

    # fx — QoQ Δln: const/W/real-rate accumulate ×4 over a year, the brent
    # slope multiplies a Δln that itself sums to the annual Δln (×1)
    real_rate_lag = (dq["key_rate"] - dq["inflation"]).to_numpy()[:-1]
    dl_fx = np.diff(np.log(dq["usd_rub"].to_numpy()))
    dl_brent = np.diff(np.log(dq["brent"].to_numpy()))
    beta, r2 = clsq(dl_fx, np.column_stack([dl_brent, W[1:], real_rate_lag / 100]),
                    BOUNDS["fx"])
    qraw["fx"] = {"const": beta[0], "dln_brent": beta[1],
                  "war_intensity": beta[2], "real_rate": beta[3], "r2": r2}
    params["fx"] = {"const": beta[0] * 4, "dln_brent": beta[1],
                    "war_intensity": beta[2] * 4, "real_rate": beta[3] * 4,
                    "r2": r2}

    # inflation — quarterly AR on YoY levels; depreciation enters as YoY %
    # (same units as the annual engine feeds), so only the AR compounds
    y = dq["inflation"].to_numpy()[1:]
    depr_pos = np.clip(np.nan_to_num(dq["fx_depr_yoy"].to_numpy()[1:]), 0, None)
    shock_2022 = (np.array([yy for yy, _ in dq.index])[1:] == 2022).astype(float)
    X = np.column_stack([dq["inflation"].to_numpy()[:-1], depr_pos, shock_2022,
                         W[1:], np.clip(real_rate_lag, 0, None)])
    beta, r2 = clsq(y, X, BOUNDS["inflation"])
    qraw["inflation"] = {"const": beta[0], "lag": beta[1], "fx_depr_pos": beta[2],
                         "shock2022": beta[3], "war_intensity": beta[4],
                         "real_rate_pos": beta[5], "r2": r2}
    params["inflation"] = _annualize_ar(
        qraw["inflation"], "lag",
        ["const", "fx_depr_pos", "shock2022", "war_intensity", "real_rate_pos"])

    # tension — quarterly diffs of the Levada proxy; squeeze and W repeat 4×
    # a year (×4), rent contraction is a YoY log-drop like the annual one (×1)
    mask = dq["tension"].notna() & dq["real_income_growth"].notna()
    lrev = np.log(dq["oilgas_rev"].to_numpy())
    rent4 = np.full(len(dq), np.nan)
    rent4[4:] = np.clip(-(lrev[4:] - lrev[:-4]), 0, None)
    tn = dq["tension"].to_numpy()
    dt = np.full(len(dq), np.nan)
    dt[1:] = np.diff(tn)
    rows = mask.to_numpy() & ~np.isnan(dt) & ~np.isnan(rent4)
    y = dt[rows]
    X = np.column_stack([-dq["real_income_growth"].to_numpy()[rows],
                         rent4[rows], W[rows]])
    beta, r2 = clsq(y, X, BOUNDS["tension"], intercept=False)
    qraw["tension"] = {"const": 0.0, "squeeze": beta[0],
                       "rent_contraction": beta[1], "war_intensity": beta[2],
                       "r2": r2}
    params["tension"] = {"const": 0.0, "squeeze": beta[0] * 4,
                         "rent_contraction": beta[1],
                         "war_intensity": beta[2] * 4, "r2": r2}

    # trust — Δtrust on Δtension: slope ×1 (both diffs live on the same
    # timescale), drift const ×4
    tr = dq["trust"].to_numpy()
    dtr = np.diff(tr)
    ok = ~np.isnan(dtr) & ~np.isnan(dt[1:])
    beta, r2 = clsq(dtr[ok], dt[1:][ok].reshape(-1, 1), BOUNDS["trust"])
    qraw["trust"] = {"const": beta[0], "d_tension": beta[1], "r2": r2}
    params["trust"] = {"const": beta[0] * 4, "d_tension": beta[1], "r2": r2}

    if 2023 in dq.index.get_level_values(0):
        params["levada_levels_2023"] = {
            "tension": float(dq.loc[2023, "tension"].mean()),
            "trust_gov": float(dq.loc[2023, "trust"].mean())}
    params["quarterly"] = qraw
    return params


OOS_FIELDS = ["key_rate", "oilgas_rev", "expenditure", "milex_share",
              "real_income_growth", "usd_rub", "inflation"]


def oos_report(freq: str, d: pd.DataFrame, dq: pd.DataFrame | None,
               start_T: int = 2018) -> dict[str, float]:
    """A3: rolling leave-future-out. Fit on [2015..T], predict T+1 one step
    ahead from the ACTUAL state at T, slide T. The criterion is OOS RMSE —
    not r²: with 10 annual points an extra regressor always buys in-sample
    fit; only held-out error exposes overfitting."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from gim.blocks.dynamics import (BlockState, MacroState, run_endogenous)
    errs: dict[str, list[float]] = {f: [] for f in OOS_FIELDS}
    end_T = int(d.index.max()) - 1
    for T in range(start_T, end_T + 1):
        d_sub = d.loc[:T]
        if freq == "q":
            params = fit_quarterly(dq.loc[:(T, 4)], d_sub)
        else:
            params = fit_annual(d_sub)
        params["security"] = fit_security_annual(d_sub)
        rT, rT1 = d.loc[T], d.loc[T + 1]
        init = BlockState(T, float(rT.key_rate), float(rT.oilgas_rev),
                          float(rT.expenditure), float(rT.milex_share),
                          float(rT.real_income_growth))
        macro0 = MacroState(usd_rub=float(rT.usd_rub),
                            inflation=float(rT.inflation))
        states, macros = run_endogenous(
            init, macro0, [(T + 1, float(rT1.brent))], params,
            brent0=float(rT.brent))
        pred, mpred = states[-1], macros[-1]
        for f in OOS_FIELDS[:5]:
            errs[f].append(float(getattr(pred, f)) - float(rT1[f]))
        errs["usd_rub"].append(mpred.usd_rub - float(rT1.usd_rub))
        errs["inflation"].append(mpred.inflation - float(rT1.inflation))
    rmse = {f: float(np.sqrt(np.mean(np.square(e)))) for f, e in errs.items()}
    n = end_T + 1 - start_T
    print(f"\nOOS report ({'quarterly' if freq == 'q' else 'annual'} fit, "
          f"one-year-ahead, T={start_T}..{end_T}, n={n}):")
    for f, v in rmse.items():
        print(f"  {f:20s} rmse={v:10.2f}")
    return rmse


def fit_peace_channel(dq: pd.DataFrame) -> dict:
    """B1: peace-mode restoring forces, fitted on the quarterly Levada
    peace sub-window 2016Q1–2019Q4 (W = 0 throughout; 2015 is the
    post-Crimea shock year, 2020 is covid).

    tension mean-reversion   Δtension = κ_q·(base − tension₋₁)
      κ_q from the slope bound [−1, 0]; annualized κ_a = 1−(1−κ_q)⁴.
      War mode disables reversion in the engine (war holds tension).
    trust income recovery    Δtrust = c + γ·Δtension + β⁺·real_income_growth
      γ ≤ 0 controls for the 2018 pension-reform tension spike — without it
      the income coefficient clips to zero (the reform lands exactly when
      incomes finally grow). β⁺ ≥ 0 annualizes ×4 (YoY income repeats
      through the year). Only β⁺ enters the engine — the Δtension slope
      stays the full-window production fit."""
    peace = dq.loc[2016:2019]
    tn = peace["tension"].to_numpy()
    tr = peace["trust"].to_numpy()
    inc = peace["real_income_growth"].to_numpy()

    beta, r2_rev = clsq(np.diff(tn), tn[:-1].reshape(-1, 1), [(-1.0, 0.0)])
    kappa_q = -beta[1]
    base = float(beta[0] / kappa_q) if kappa_q > 1e-6 else 0.0
    kappa_a = 1.0 - (1.0 - kappa_q) ** 4

    beta, r2_rec = clsq(np.diff(tr),
                        np.column_stack([np.diff(tn), inc[1:]]),
                        [(-INF, 0.0), (0.0, INF)])
    recovery_a = float(beta[2] * 4)

    return {"reversion_kappa": float(kappa_a), "tension_base": base,
            "income_recovery": recovery_a,
            "r2_reversion": r2_rev, "r2_recovery": r2_rec,
            "window": "2016Q1-2019Q4"}


def fit_rent_investment(d: pd.DataFrame) -> dict:
    """B4: rent → core investment. Elasticity of real fixed-capital
    formation growth to real rent growth, W-controlled (the 2022-24 war
    investment boom is the milex channel's job — leaving W in the regression
    keeps it OUT of the rent coefficient; only the elasticity ships).
    Peacetime identification is clean: 2020 rent −46% → GFCF −4.1%,
    2021 rent +47% → GFCF +8.9%. Source: WDI NE.GDI.FTOT.KN (constant LCU)."""
    gfcf = pd.read_csv(RAW / "worldbank/gfcf_rus_constant_lcu.csv")         .set_index("year")["gfcf_constant_lcu"]
    years = [y for y in d.index if y in gfcf.index and y - 1 in gfcf.index
             and y - 1 in d.index]
    cpi = {years[0] - 1: 1.0}
    for y in range(years[0], years[-1] + 1):
        cpi[y] = cpi[y - 1] * (1 + float(d.loc[y, "inflation"]) / 100)
    dln_inv = np.array([np.log(gfcf[y] / gfcf[y - 1]) for y in years])
    dln_rent = np.array([
        np.log((d.loc[y, "oilgas_rev"] / cpi[y])
               / (d.loc[y - 1, "oilgas_rev"] / cpi[y - 1])) for y in years])
    W = np.array([war_intensity(y) for y in years])
    beta, r2 = clsq(dln_inv, np.column_stack([dln_rent, W]),
                    [(0.0, 0.5), (-INF, INF)])
    return {"elasticity": float(beta[1]), "war_coincident": float(beta[2]),
            "r2": r2, "n_obs": len(years),
            "source": "WDI NE.GDI.FTOT.KN, real rent = oilgas_rev/CPI"}


# observable judged by OOS → the equation it selects
OOS_EQ = {"key_rate": "regulator", "oilgas_rev": "capital_elite",
          "expenditure": "executive", "milex_share": "security",
          "real_income_growth": "households", "usd_rub": "fx",
          "inflation": "inflation"}


def fit_hybrid(d: pd.DataFrame, dq: pd.DataFrame) -> dict[str, dict]:
    """A3 selection: fit both frequencies, keep per equation whichever wins
    the rolling OOS (one-year-ahead RMSE). tension/trust have no OOS series
    in the report — they stay annual (the quarterly Levada diffs are survey
    noise: r² 0.05 vs 0.4 annual)."""
    rmse_a = oos_report("a", d, None)
    rmse_q = oos_report("q", d, dq)
    pa, pq = fit_annual(d), fit_quarterly(dq, d)
    params = dict(pa)
    chosen = {}
    for obs, eq in OOS_EQ.items():
        pick_q = rmse_q[obs] < rmse_a[obs]
        if pick_q:
            params[eq] = pq[eq]
        chosen[eq] = "q" if pick_q else "a"
    chosen["tension"] = chosen["trust"] = "a"
    params["quarterly"] = pq.get("quarterly", {})
    params["_selection"] = chosen
    print("\nhybrid selection (by OOS rmse):",
          " ".join(f"{k}={v}" for k, v in chosen.items()))
    return params


# === A4: Bayesian layer — conjugate-ridge posteriors with informative priors ===
# Priors (mean, sd) in the FIT space of each production equation (quarterly for
# regulator/executive/inflation, annual otherwise). Sources: policy-rate
# smoothing and Taylor-rule literature (lag), CBR pass-through estimates
# (long-run 0.05-0.1 -> quarterly-YoY spec ~0.03), rent price-elasticity range
# [0.5, 1.2], and weakly-informative war/crisis terms. The production POINT
# estimates stay the A2-constrained hybrid fit; the posterior supplies
# credible intervals and the B8 ensemble draws.
ENS_OUT = Path("data/blocks/RUS/dynamics_params_ensemble.json")

PRIORS = {
    "regulator": {"const": (1.0, 1.0), "lag_rate": (0.75, 0.10),
                  "inflation": (0.30, 0.20), "war_intensity": (0.50, 0.30)},
    "capital_elite": {"const": (2.3, 2.0), "ln_brent_rub": (0.80, 0.15)},
    "executive": {"const": (0.04, 0.02), "crisis": (0.12, 0.08),
                  "war_intensity": (0.02, 0.02)},
    "security": {"const": (2.0, 1.0), "lag": (0.45, 0.20),
                 "war_intensity": (0.50, 0.25)},
    "households": {"const": (0.5, 1.0), "neg_inflation": (0.30, 0.30),
                   "war_intensity": (2.0, 1.0)},
    "fx": {"const": (0.05, 0.05), "dln_brent": (-0.20, 0.10),
           "war_intensity": (0.03, 0.05), "real_rate": (-1.5, 1.0)},
    "inflation": {"const": (1.5, 1.5), "lag": (0.60, 0.20),
                  "fx_depr_pos": (0.03, 0.015), "shock2022": (6.0, 3.0),
                  "war_intensity": (0.40, 0.30), "real_rate_pos": (-0.05, 0.05)},
    "tension": {"squeeze": (0.010, 0.010), "rent_contraction": (0.030, 0.030),
                "war_intensity": (0.010, 0.010)},
    "trust": {"const": (0.0, 0.01), "d_tension": (-0.80, 0.30)},
}


def equation_designs(d: pd.DataFrame, dq: pd.DataFrame) -> dict[str, dict]:
    """Design matrices of the PRODUCTION equations (hybrid selection), one
    entry per equation: y, X (slope columns), coefficient names (const first
    when intercept), slope bounds, and the fit→production annualization.
    Mirrors fit_quarterly/fit_annual exactly — test_block_oos_golden pins the
    equivalence so the two never drift apart."""
    designs: dict[str, dict] = {}
    Wq = dq["W"].to_numpy()
    years = list(d.index)
    Wa = np.array([war_intensity(y) for y in years])

    def ann_ar(lag_key, scale_keys):
        return lambda p: _annualize_ar(p, lag_key, scale_keys)

    ident = lambda p: p

    designs["regulator"] = {
        "y": dq["key_rate"].to_numpy()[1:],
        "X": np.column_stack([dq["key_rate"].to_numpy()[:-1],
                              dq["inflation"].to_numpy()[1:], Wq[1:]]),
        "names": ["const", "lag_rate", "inflation", "war_intensity"],
        "bounds": [(0.5, 0.95), (0.0, INF), (0.0, INF)],
        "intercept": True,
        "annualize": ann_ar("lag_rate", ["const", "inflation", "war_intensity"]),
    }
    designs["capital_elite"] = {
        "y": np.log(d["oilgas_rev"].to_numpy()),
        "X": np.log((d["brent"] * d["usd_rub"]).to_numpy()).reshape(-1, 1),
        "names": ["const", "ln_brent_rub"],
        "bounds": BOUNDS["capital_elite"], "intercept": True,
        "annualize": ident,
    }
    lexp = np.log(dq["expenditure"].to_numpy())
    yrs_q = np.array([yy for yy, _ in dq.index])
    designs["executive"] = {
        "y": lexp[4:] - lexp[:-4],
        "X": np.column_stack([np.isin(yrs_q[4:], [2020, 2022]).astype(float),
                              Wq[4:]]),
        "names": ["const", "crisis", "war_intensity"],
        "bounds": BOUNDS["executive"], "intercept": True,
        "annualize": ident,
    }
    designs["security"] = {
        "y": d["milex_share"].to_numpy()[1:],
        "X": np.column_stack([d["milex_share"].to_numpy()[:-1], Wa[1:]]),
        "names": ["const", "lag", "war_intensity"],
        "bounds": BOUNDS["security"], "intercept": True,
        "annualize": ident,
    }
    designs["households"] = {
        "y": d["real_income_growth"].to_numpy()[1:],
        "X": np.column_stack([-d["inflation"].to_numpy()[1:], Wa[1:]]),
        "names": ["const", "neg_inflation", "war_intensity"],
        "bounds": BOUNDS["households"], "intercept": True,
        "annualize": ident,
    }
    rr_a = (d["key_rate"] - d["inflation"]).to_numpy()[:-1]
    designs["fx"] = {
        "y": np.diff(np.log(d["usd_rub"].to_numpy())),
        "X": np.column_stack([np.diff(np.log(d["brent"].to_numpy())),
                              Wa[1:], rr_a / 100]),
        "names": ["const", "dln_brent", "war_intensity", "real_rate"],
        "bounds": BOUNDS["fx"], "intercept": True,
        "annualize": ident,
    }
    rr_q = (dq["key_rate"] - dq["inflation"]).to_numpy()[:-1]
    designs["inflation"] = {
        "y": dq["inflation"].to_numpy()[1:],
        "X": np.column_stack([
            dq["inflation"].to_numpy()[:-1],
            np.clip(np.nan_to_num(dq["fx_depr_yoy"].to_numpy()[1:]), 0, None),
            (yrs_q[1:] == 2022).astype(float), Wq[1:],
            np.clip(rr_q, 0, None)]),
        "names": ["const", "lag", "fx_depr_pos", "shock2022",
                  "war_intensity", "real_rate_pos"],
        "bounds": BOUNDS["inflation"], "intercept": True,
        "annualize": ann_ar("lag", ["const", "fx_depr_pos", "shock2022",
                                    "war_intensity", "real_rate_pos"]),
    }
    lev_dir = pd.read_csv(SERIES / "levada_direction_monthly.csv")
    lev_dir["year"] = lev_dir["month"].str[:4].astype(int)
    tension = (lev_dir.groupby("year")["wrong_direction"].mean() / 100
               ).reindex(years)
    lev_app = pd.read_csv(SERIES / "levada_approval_monthly.csv")
    lev_app["year"] = lev_app["month"].str[:4].astype(int)
    gov = lev_app[lev_app.entity == "government"]
    trust = (gov.groupby("year")["approve"].mean() / 100).reindex(years)
    dl_rev = np.diff(np.log(d["oilgas_rev"].to_numpy()))
    designs["tension"] = {
        "y": np.diff(tension.to_numpy()),
        "X": np.column_stack([-(d["real_income_growth"].to_numpy()[1:]),
                              np.clip(-dl_rev, 0, None), Wa[1:]]),
        "names": ["squeeze", "rent_contraction", "war_intensity"],
        "bounds": BOUNDS["tension"], "intercept": False,
        "annualize": ident,
    }
    designs["trust"] = {
        "y": np.diff(trust.to_numpy()),
        "X": np.diff(tension.to_numpy()).reshape(-1, 1),
        "names": ["const", "d_tension"],
        "bounds": BOUNDS["trust"], "intercept": True,
        "annualize": ident,
    }
    return designs


def bayes_ensemble(d: pd.DataFrame, dq: pd.DataFrame,
                   n_draws: int = 100, seed: int = 42) -> dict:
    """Conjugate-ridge posterior per equation: with prior N(mu, diag(sd²)) and
    noise sigma² from the constrained-fit residuals,
      A = X'X/σ² + Λ,  β_post = A⁻¹(X'y/σ² + Λμ),  cov = A⁻¹.
    Draws are clipped to the A2 bounds and annualized through the same maps
    as the production fit. Returns the ensemble dict written to ENS_OUT."""
    rng = np.random.default_rng(seed)
    designs = equation_designs(d, dq)
    draws: list[dict] = [dict() for _ in range(n_draws)]
    summary: dict[str, dict] = {}
    for eq, dz in designs.items():
        y, X = dz["y"], dz["X"]
        names = dz["names"]
        intercept = dz["intercept"]
        X1 = np.column_stack([np.ones(len(y)), X]) if intercept else X
        prior = PRIORS[eq]
        mu = np.array([prior[nm][0] for nm in names])
        sd = np.array([prior[nm][1] for nm in names])
        # sigma² from the constrained point fit on the same design
        beta_c, _ = clsq(y, X, dz["bounds"], intercept=intercept)
        resid = y - X1 @ beta_c
        dof = max(1, len(y) - X1.shape[1])
        sigma2 = float(resid @ resid) / dof
        Lam = np.diag(1.0 / sd ** 2)
        A = X1.T @ X1 / sigma2 + Lam
        cov = np.linalg.inv(A)
        beta_post = cov @ (X1.T @ y / sigma2 + Lam @ mu)
        lo = np.array(([-np.inf] if intercept else [])
                      + [b[0] for b in dz["bounds"]])
        hi = np.array(([np.inf] if intercept else [])
                      + [b[1] for b in dz["bounds"]])
        sample = rng.multivariate_normal(beta_post, cov, size=n_draws)
        sample = np.clip(sample, lo, hi)
        q05, q95 = np.percentile(sample, [5, 95], axis=0)
        summary[eq] = {nm: {"post_mean": float(beta_post[i]),
                            "ci05": float(q05[i]), "ci95": float(q95[i]),
                            "prior": list(prior[nm])}
                       for i, nm in enumerate(names)}
        for k in range(n_draws):
            p = {nm: float(sample[k][i]) for i, nm in enumerate(names)}
            if not intercept:
                p["const"] = 0.0
            draws[k][eq] = dz["annualize"](p)
    ens = {"draws": draws,
           "summary": summary,
           "_meta": {"n_draws": n_draws, "seed": seed,
                     "estimator": "conjugate ridge (A4), sigma2 empirical, "
                                  "draws clipped to A2 bounds",
                     "note": "production point stays the constrained hybrid "
                             "fit; this file feeds the B8 ensemble"}}
    ENS_OUT.write_text(json.dumps(ens))
    print(f"{ENS_OUT}: {n_draws} draws")
    for eq, s in summary.items():
        ci = " ".join(f"{nm}[{v['ci05']:+.3f},{v['ci95']:+.3f}]"
                      for nm, v in s.items())
        print(f"  {eq:14s} {ci}")
    return ens


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--freq", choices=["a", "q", "hybrid"], default="a",
                    help="fit frequency: a = annual (10 pts), q = quarterly "
                         "(44 pts, annualized into the same schema)")
    ap.add_argument("--bayes", action="store_true",
                    help="A4: write the conjugate-ridge posterior ensemble "
                         "(dynamics_params_ensemble.json) and print credible "
                         "intervals; leaves the production params untouched")
    ap.add_argument("--oos", action="store_true",
                    help="A3: rolling leave-future-out report (fit [2015..T], "
                         "predict T+1); prints RMSE per observable, does not "
                         "change the params file")
    args = ap.parse_args()

    d = annual_inputs()
    print(d.round(2).to_string())
    if args.oos:
        dq = quarterly_inputs() if args.freq == "q" else None
        oos_report(args.freq, d, dq)
        return
    if args.bayes:
        bayes_ensemble(d, quarterly_inputs())
        return
    if args.freq == "q":
        dq = quarterly_inputs()
        params = fit_quarterly(dq, d)
        fitted_on = "2015Q1-2025Q4 quarterly (annualized)"
        n_obs = int(len(dq))
    elif args.freq == "hybrid":
        dq = quarterly_inputs()
        params = fit_hybrid(d, dq)
        fitted_on = "hybrid: per-equation OOS winner (annual 2015-2025 / quarterly 2015Q1-2025Q4)"
        n_obs = int(len(dq))
    else:
        params = fit_annual(d)
        fitted_on = "2015-2025 annual"
        n_obs = len(YEARS)

    # --- core policy bridge (THE-127): initial state for in-core stepping -----
    r23 = d.loc[2023]
    params["core_bridge"] = {
        "init": {"year": 2023, "key_rate": float(r23.key_rate),
                 "oilgas_rev": float(r23.oilgas_rev),
                 "expenditure": float(r23.expenditure),
                 "milex_share": float(r23.milex_share),
                 "real_income_growth": float(r23.real_income_growth)},
        "macro": {"usd_rub": float(r23.usd_rub), "inflation": float(r23.inflation)},
        "brent0": float(r23.brent),
    }

    # B4 rent → investment elasticity (used by the core credit channel)
    params["rent_investment"] = fit_rent_investment(d)

    # B1 peace channel: restoring forces merged into tension/trust
    peace = fit_peace_channel(quarterly_inputs())
    params["tension"]["reversion_kappa"] = peace["reversion_kappa"]
    params["tension"]["tension_base"] = peace["tension_base"]
    params["trust"]["income_recovery"] = peace["income_recovery"]
    params["peace_channel"] = peace

    params["_meta"] = {
        "fitted_on": fitted_on, "n_obs": n_obs,
        "estimator": "constrained lsq (A2 sign/range bounds)",
        "exogenous": ["brent", "war_intensity"],
    }
    OUT.write_text(json.dumps(params, indent=2, ensure_ascii=False))
    print(f"\n{OUT}:")
    for k, v in params.items():
        if k.startswith("_") or not isinstance(v, dict) or "r2" not in v:
            continue
        print(f"  {k:14s} r2={v['r2']:.3f}  " +
              " ".join(f"{kk}={vv:+.3f}" for kk, vv in v.items()
                       if kk != "r2" and isinstance(vv, (int, float))))


if __name__ == "__main__":
    main()
