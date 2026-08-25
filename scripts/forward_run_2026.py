#!/usr/bin/env python3
"""Forward validation (THE-130): fit window 2015–2025, holdout 2026.

True out-of-time test — nothing after 2023 touched the fit. The block layer is
initialised from 2023 actuals and rolled forward in full-endogenous mode: the
only inputs are the actual Brent path and the regime dummies (war continues).
Predictions are compared with actuals already on disk (budget to 2026, CPI and
SIPRI to 2025, CBR rate/fx to 2026-08) — i.e. with "current news".

Run from repo root: python3 scripts/forward_run_2026.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from gim.blocks.dynamics import BlockState, MacroState, load_params, run_endogenous
from fit_block_dynamics import annual_inputs  # noqa: E402

RAW = Path("data/blocks/RUS/raw")
FORWARD_YEARS = [2024, 2025, 2026]


def forward_actuals() -> pd.DataFrame:
    """Actuals for 2024–2026 from already-downloaded files (never seen by the fit)."""
    df = pd.DataFrame(index=FORWARD_YEARS)

    brent = pd.read_csv(RAW / "energy/brent_daily_fred.csv")
    brent["year"] = brent["observation_date"].str[:4].astype(int)
    df["brent"] = brent.groupby("year")["DCOILBRENTEU"].mean()

    kr = (RAW / "cbr/keyrate_2024_2026.xml").read_text()
    rows = re.findall(r"<DT>(\d{4})-\d{2}-\d{2}T[^<]*</DT><Rate>([\d.]+)</Rate>", kr)
    kr_df = pd.DataFrame(rows, columns=["year", "rate"]).astype(
        {"year": int, "rate": float})
    df["key_rate"] = kr_df.groupby("year")["rate"].mean()

    fx = (RAW / "cbr/usd_rub_daily_2024_2026.xml").read_text(encoding="windows-1251")
    rows = re.findall(r'Date="\d{2}\.\d{2}\.(\d{4})"[^>]*>.*?<VunitRate>([\d,]+)<', fx)
    fx_df = pd.DataFrame(rows, columns=["year", "v"])
    fx_df["v"] = fx_df["v"].str.replace(",", ".").astype(float)
    df["usd_rub"] = fx_df.astype({"year": int}).groupby("year")["v"].mean()

    cpi = pd.read_excel(RAW / "rosstat/cpi_55396_emiss.xls", header=None)
    hdr = cpi.iloc[2]
    years = {i: int(float(v)) for i, v in hdr.items()
             if str(v).replace(".0", "").isdigit()}
    row = cpi[cpi.apply(lambda r: "643 Российская Федерация" in str(r.tolist()),
                        axis=1)].iloc[0]
    df["inflation"] = pd.Series({yr: float(row[c]) - 100.0
                                 for c, yr in years.items()
                                 if pd.notna(row[c])}).reindex(FORWARD_YEARS)

    bud = pd.read_csv("data/blocks/RUS/series/minfin_budget_quarterly.csv")
    ann = bud.groupby(["series", "year"])["value"].sum().unstack(0)
    df["expenditure"] = ann["expenditure_total"].reindex(FORWARD_YEARS)
    df["oilgas_rev"] = ann["revenue_oilgas"].reindex(FORWARD_YEARS)
    # 2026 budget rows cover only H1 — annualise crudely (×2) and mark it
    df.attrs["partial_2026"] = True
    quarters_2026 = bud[(bud.year == 2026) & (bud.series == "expenditure_total")]
    if 0 < len(quarters_2026) < 4:
        scale = 4 / len(quarters_2026)
        df.loc[2026, "expenditure"] *= scale
        df.loc[2026, "oilgas_rev"] *= scale

    sipri = pd.read_csv("data/blocks/RUS/series/sipri_milex_annual.csv")
    df["milex_share"] = (sipri[sipri.series == "milex_pct_gdp"]
                         .set_index("year")["value"] * 100).reindex(FORWARD_YEARS)
    return df


def main() -> None:
    d = annual_inputs()          # 2015–2023, the fit window
    fwd = forward_actuals()
    params = load_params()

    r = d.loc[2023]
    lev = params.get("levada_levels_2023", {})
    init = BlockState(2023, r.key_rate, r.oilgas_rev, r.expenditure,
                      r.milex_share, r.real_income_growth,
                      social_tension=lev.get("tension", 0.0),
                      trust_gov=lev.get("trust_gov", 0.0))
    macro0 = MacroState(usd_rub=float(r.usd_rub), inflation=float(r.inflation))
    brent_path = [(y, float(fwd.loc[y, "brent"])) for y in FORWARD_YEARS]
    states, macros = run_endogenous(init, macro0, brent_path, params,
                                    brent0=float(r.brent))
    pred = {s.year: s for s in states}
    mpred = dict(zip([2023] + FORWARD_YEARS, macros))

    print("Forward run 2024–2026 (fitted on 2015–2023; inputs: Brent + war dummy)")
    print("2026 budget actuals annualised from H1; SIPRI/CPI end 2025.\n")
    fields = [("key_rate", "%", 1), ("usd_rub", "rub", 1), ("inflation", "pp", 1),
              ("oilgas_rev", "bln", 0), ("expenditure", "bln", 0),
              ("milex_share", "%GDP", 2)]
    for year in FORWARD_YEARS:
        print(f"— {year}")
        for f, unit, nd in fields:
            if f in ("usd_rub", "inflation"):
                p = getattr(mpred[year], f)
            else:
                p = getattr(pred[year], f)
            a = fwd.loc[year, f] if f in fwd else float("nan")
            note = ""
            if year == 2026 and f in ("oilgas_rev", "expenditure"):
                note = " (H1×2)"
            if pd.notna(a):
                err = (p - a) / a * 100 if a else float("nan")
                print(f"  {f:12s} pred {p:10.{nd}f}  fact {a:10.{nd}f}  "
                      f"err {err:+6.1f}%{note}")
            else:
                print(f"  {f:12s} pred {p:10.{nd}f}  fact       n/a{note}")
        s = pred[year]
        print(f"  tension      pred {s.social_tension:10.3f}  "
              f"trust_gov pred {s.trust_gov:.3f}")


if __name__ == "__main__":
    main()
