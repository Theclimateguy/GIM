#!/usr/bin/env python3
"""Stage-1 (F3) external-data ingestion for GIM17 unique-layer grounding/validation.

Pulls the established external indices that ground GIM's social / geopolitical / military
layers (see docs/SOCIAL_GEO_METRICS.md) into tidy long CSVs under data/external/.

Two classes of source:

  A. World Bank API (live, no auth) — fetched here:
       - WDI:  GDP (NY.GDP.MKTP.CD), population (SP.POP.TOTL), energy use
               (EG.USE.PCAP.KG.OE), military expenditure SIPRI-sourced
               (MS.MIL.XPND.CD, MS.MIL.XPND.GD.ZS), Gini (SI.POV.GINI).
       - WGI (archive source 57): Political Stability (PV.EST), Voice & Accountability
               (VA.EST), Government Effectiveness (GE.EST), Rule of Law (RL.EST).
     These give CINC components (pop, energy, milex, GDP-industrial proxy), the inequality
     anchor (Gini ~ SWIID proxy) and the governance/stability anchors.

  B. Bulk archives the World Bank API does NOT serve and that must be downloaded by hand
     (zip / xlsx / rda) and placed in data/external/raw/ — this script then parses them:
       - UCDP/PRIO Armed Conflict Dataset v24.1  -> ucdp-prio-acd-241.csv
       - SWIID v9.x (Gini, standardized)          -> swiid9_x_summary.csv
       - Correlates of War NMC v6.0 (CINC)        -> NMC-60-abridged.csv
       - SIPRI Milex (full)                       -> SIPRI-Milex-data.xlsx
       - Global Sanctions Database (GSDB)         -> GSDB_V3.xlsx
     Download URLs are listed in data/external/SOURCES.md.

Usage:
    python3 scripts/ingest_external_data.py            # World Bank live + any present bulk files
    python3 scripts/ingest_external_data.py --wb-only  # skip bulk parsing

Compliance note: this performs HTTP requests to the World Bank API; run it in an
environment with normal outbound network (your machine), not inside a restricted sandbox.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_CSV = os.path.join(REPO, "data", "agent_states_operational_2026_calibrated.csv")
OUT_DIR = os.path.join(REPO, "data", "external")
RAW_DIR = os.path.join(OUT_DIR, "raw")

WDI_INDICATORS = {
    "gdp_usd": "NY.GDP.MKTP.CD",
    "population": "SP.POP.TOTL",
    "energy_use_pc_kgoe": "EG.USE.PCAP.KG.OE",
    "milex_usd": "MS.MIL.XPND.CD",         # SIPRI-sourced
    "milex_pct_gdp": "MS.MIL.XPND.GD.ZS",  # SIPRI-sourced
    "gini_wb": "SI.POV.GINI",
}
# WGI live under the archived source id 57; path-style endpoint avoids the source-param strip.
WGI_SERIES = {
    "wgi_political_stability": "PV.EST",
    "wgi_voice_accountability": "VA.EST",
    "wgi_gov_effectiveness": "GE.EST",
    "wgi_rule_of_law": "RL.EST",
}
YEAR_START, YEAR_END = 1990, 2024


def gim_iso3() -> List[str]:
    """Real ISO3 countries in the GIM state CSV (excludes AG_* aggregate rows)."""
    out = []
    with open(STATE_CSV, newline="") as fh:
        for row in csv.reader(fh):
            cid = row[0].strip()
            if cid and cid != "id" and not cid.startswith("AG_"):
                out.append(cid)
    return out


def _get_json(url: str, retries: int = 3) -> Optional[object]:
    for i in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            if i == retries - 1:
                print(f"  ! failed {url}: {e}", file=sys.stderr)
                return None
            time.sleep(2 * (i + 1))
    return None


def fetch_wdi(countries: List[str]) -> List[dict]:
    rows: List[dict] = []
    cc = ";".join(countries)
    for name, code in WDI_INDICATORS.items():
        page, pages = 1, 1
        while page <= pages:
            url = (f"https://api.worldbank.org/v2/country/{cc}/indicator/{code}"
                   f"?date={YEAR_START}%3A{YEAR_END}&format=json&per_page=20000&page={page}")
            data = _get_json(url)
            if not data or len(data) < 2 or not data[1]:
                break
            pages = data[0].get("pages", 1)
            for obs in data[1]:
                if obs.get("value") is None:
                    continue
                rows.append({"iso3": obs["countryiso3code"], "year": int(obs["date"]),
                             "variable": name, "wb_code": code, "value": obs["value"]})
            page += 1
        print(f"  WDI {name} ({code}): cumulative {len(rows)} obs")
    return rows


def fetch_wgi(countries: List[str]) -> List[dict]:
    """WGI archive (source 57) via the path-style series endpoint; keep latest version per (country,year)."""
    rows: List[dict] = []
    for c in countries:
        for name, code in WGI_SERIES.items():
            url = (f"https://api.worldbank.org/v2/sources/57/country/{c}"
                   f"/series/{code}/time/all/data?format=json&per_page=20000")
            data = _get_json(url)
            if not isinstance(data, dict):
                continue
            latest: Dict[int, tuple] = {}
            for rec in data.get("source", {}).get("data", []):
                if rec.get("value") is None:
                    continue
                vmap = {v["concept"]: v for v in rec["variable"]}
                yr = int(vmap["Time"]["id"].replace("YR", ""))
                ver = vmap.get("Version", {}).get("id", "0")
                if yr < YEAR_START:
                    continue
                if yr not in latest or ver > latest[yr][0]:
                    latest[yr] = (ver, float(rec["value"]))
            for yr, (_, val) in latest.items():
                rows.append({"iso3": c, "year": yr, "variable": name, "wb_code": code, "value": val})
        print(f"  WGI {c}: cumulative {len(rows)} obs")
    return rows


def write_long(rows: List[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["iso3", "year", "variable", "wb_code", "value"])
        w.writeheader()
        for r in sorted(rows, key=lambda d: (d["variable"], d["iso3"], d["year"])):
            w.writerow(r)
    print(f"  -> wrote {len(rows)} rows to {os.path.relpath(path, REPO)}")


def parse_bulk() -> None:
    """Parse hand-downloaded bulk archives in data/external/raw/ if present."""
    jobs = {
        "ucdp-prio-acd-241.csv": "UCDP/PRIO ACD (conflict onset backtest target)",
        "swiid9_x_summary.csv": "SWIID gini (preferred inequality anchor)",
        "NMC-60-abridged.csv": "CoW NMC / CINC (military capability validation)",
        "SIPRI-Milex-data.xlsx": "SIPRI milex (full series)",
        "GSDB_V3.xlsx": "Global Sanctions Database",
    }
    present = []
    for fn, desc in jobs.items():
        p = os.path.join(RAW_DIR, fn)
        if os.path.exists(p):
            present.append((fn, desc, p))
    if not present:
        print("  (no bulk files in data/external/raw/ — see data/external/SOURCES.md for download URLs)")
        return
    for fn, desc, p in present:
        print(f"  found {fn} — {desc}; add a parser here for your analysis pipeline.")
    # Parsers are intentionally left as explicit per-dataset steps (formats differ by version);
    # the conflict backtest reads ucdp-prio-acd-*.csv directly in scripts/conflict_backtest.py.


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wb-only", action="store_true", help="skip bulk-archive parsing")
    ap.add_argument("--no-wgi", action="store_true", help="skip the (slow, per-country) WGI pull")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)
    countries = gim_iso3()
    print(f"GIM ISO3 country set: {len(countries)} countries")

    print("Fetching World Bank WDI (GDP, population, energy, milex[SIPRI], Gini)...")
    write_long(fetch_wdi(countries), os.path.join(OUT_DIR, "worldbank_wdi_1990_2024.csv"))

    if not args.no_wgi:
        print("Fetching World Bank WGI archive (PS, V&A, GovEff, RuleOfLaw)...")
        write_long(fetch_wgi(countries), os.path.join(OUT_DIR, "worldbank_wgi_1990_2024.csv"))

    if not args.wb_only:
        print("Scanning for hand-downloaded bulk archives...")
        parse_bulk()

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
