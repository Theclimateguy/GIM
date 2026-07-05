#!/usr/bin/env python3
"""Build data/external/sipri_milex_2023.csv — SIPRI 2023 military expenditure mapped
to GIM's 57 actors (Tier 1 milex grounding; see mil_risk/analysis/output/GIM_INTEGRATION_MEMO.md).

Country actors: direct SIPRI value (constant 2022 US$ m).
AG_* aggregates: sum of SIPRI countries whose wb_region (pipeline panel) matches the
aggregate's region, excluding explicit country actors. Countries SIPRI lacks (e.g.
North Korea) or that fail name-matching are reported and omitted.

Source file: the SIPRI milex workbook (constant 2022 US$) — path via --sipri, default
looks in ../mil_risk/data/raw/sipri/.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
PANEL = REPO / "data/agent_state_pipeline/generated/country_panel_imputed.csv"
BASE = REPO / "data/agent_state_pipeline/generated/actor_base_inputs.csv"
OUT = REPO / "data/external/sipri_milex_2023.csv"

# SIPRI country name -> World-Bank panel name (only where simple match fails)
FIX = {
    "United States of America": "United States",
    "Korea, South": "Korea, Rep.",
    "Russia": "Russian Federation",
    "Egypt": "Egypt, Arab Rep.",
    "Iran": "Iran, Islamic Rep.",
    "Türkiye": "Turkiye",
    "Venezuela": "Venezuela, RB",
    "Syria": "Syrian Arab Republic",
    "Congo, DR": "Congo, Dem. Rep.",
    "Congo, Republic": "Congo, Rep.",
    "Cote d'Ivoire": "Cote d'Ivoire",
    "Côte d'Ivoire": "Cote d'Ivoire",
    "Brunei": "Brunei Darussalam",
    "Laos": "Lao PDR",
    "Kyrgyzstan": "Kyrgyz Republic",
    "Slovakia": "Slovak Republic",
    "Yemen": "Yemen, Rep.",
    "Gambia, The": "Gambia, The",
    "Bahamas, The": "Bahamas, The",
    "Czechia": "Czechia",
    "North Macedonia": "North Macedonia",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Trinidad & Tobago": "Trinidad and Tobago",
    "Timor Leste": "Timor-Leste",
    "Cape Verde": "Cabo Verde",
}
YEAR = 2023


MIN_CARRY_YEAR = 2010  # last-observation carry-forward floor for SIPRI gaps (e.g. UAE ends 2014)


def load_sipri(path: Path) -> pd.DataFrame:
    """SIPRI constant-price sheet -> [country, milex, source_year].

    Value for YEAR when present, else the latest available year >= MIN_CARRY_YEAR
    (documented carry-forward for SIPRI coverage gaps such as UAE/Viet Nam).
    """
    xls = pd.ExcelFile(path)
    sheet = next((s for s in xls.sheet_names if "constant" in s.lower()), xls.sheet_names[0])
    raw = xls.parse(sheet, header=None)
    hdr = None
    for i in range(min(15, len(raw))):
        vals = [str(v) for v in raw.iloc[i].tolist()]
        if sum(1 for v in vals if v[:4].isdigit() and 1900 < int(v[:4]) < 2100) >= 5:
            hdr = i
            break
    df = xls.parse(sheet, header=hdr)
    df = df.rename(columns={df.columns[0]: "country"})
    year_cols = [c for c in df.columns if str(c)[:4].isdigit()
                 and MIN_CARRY_YEAR <= int(str(c)[:4]) <= YEAR]
    long = df.melt(id_vars=["country"], value_vars=year_cols,
                   var_name="year", value_name="milex")
    long["year"] = long["year"].astype(str).str[:4].astype(int)
    long["milex"] = pd.to_numeric(long["milex"], errors="coerce")
    long["country"] = long["country"].astype(str).str.strip()
    long = long.dropna(subset=["milex"])
    latest = long.sort_values("year").groupby("country").tail(1)
    return latest.rename(columns={"year": "source_year"})[["country", "milex", "source_year"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sipri", type=Path,
                    default=REPO.parent / "mil_risk/data/raw/sipri/SIPRI-Milex-1949-2024.xlsx")
    args = ap.parse_args()

    sipri = load_sipri(args.sipri)
    panel = pd.read_csv(PANEL, usecols=["iso3", "name", "model_region"])
    base = pd.read_csv(BASE, usecols=["iso3", "wb_region"])
    actor_ids = base.iso3.tolist()
    country_actors = [a for a in actor_ids if not a.startswith("AG_")]
    ag_region = {r.iso3: r.wb_region for r in base.itertuples() if r.iso3.startswith("AG_")}

    name2iso = dict(zip(panel.name, panel.iso3))
    # raw SIPRI name first (panel names are largely SIPRI-style), FIX fallback
    sipri["iso3"] = sipri.country.map(
        lambda c: name2iso.get(c, name2iso.get(FIX.get(c, c))))
    merged = sipri.merge(panel[["iso3", "model_region"]], on="iso3", how="left")

    unmatched = merged[merged.iso3.isna() & (merged.milex > 0)]
    if len(unmatched):
        total_um = unmatched.milex.sum()
        print(f"[warn] {len(unmatched)} SIPRI rows unmatched (sum {total_um:,.0f} US$m):",
              file=sys.stderr)
        for r in unmatched.sort_values("milex", ascending=False).head(12).itertuples():
            print(f"    {r.country:<28} {r.milex:>12,.1f}", file=sys.stderr)

    matched = merged.dropna(subset=["iso3"]).copy()

    rows = []
    # 1) explicit country actors
    for cid in country_actors:
        v = matched.loc[matched.iso3 == cid]
        rows.append({"id": cid,
                     "military_spending_musd": round(float(v.milex.iloc[0]), 1) if len(v) else 0.0,
                     "n_members": 1 if len(v) else 0,
                     "source_year": int(v.source_year.iloc[0]) if len(v) else 0})
    # 2) aggregates: region members not in explicit actors
    rest = matched[~matched.iso3.isin(country_actors)]
    global_south_regions = set(rest.model_region.dropna().unique()) - set(ag_region.values())
    for aid, region in sorted(ag_region.items()):
        if region == "Global South":
            # Global South + leftover regions with no aggregate of their own (e.g. North America)
            grp = rest[rest.model_region.isin(global_south_regions | {"Global South"})]
        else:
            grp = rest[rest.model_region == region]
        rows.append({"id": aid, "military_spending_musd": round(float(grp.milex.sum()), 1),
                     "n_members": int(len(grp)), "source_year": 0})

    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    world_total = sipri.milex.sum()
    covered = out.military_spending_musd.sum()
    print(f"actors: {len(out)}  |  covered {covered:,.0f} of SIPRI world {world_total:,.0f} US$m "
          f"({covered / world_total:.1%})")
    print(out.sort_values('military_spending_musd', ascending=False).head(12).to_string(index=False))
    print(f"-> {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
