#!/usr/bin/env python3
"""Ingest NGFS/CIE subnational climate projections for RUS provinces (THE-123 tail).

Source: Climate Impact Explorer API v2 (IIASA & Climate Analytics, NGFS consortium),
https://cie-api-v2.climateanalytics.org — province-level physical risk projections.
Region ids are GADM-style (RUS.N_1, 83 provinces, pre-2014 borders: no Crimea).

Downloads per province × variable one CSV (all scenarios in one file; we keep the
NGFS current-policies median + the net-zero-2050 median as the scenario contrast)
and folds everything into data/blocks/RUS/territories/climate_projections.csv with
regions renamed into the Rosstat namespace via the NE name map (GADM and NE share
the same English naming family).

Citation (per CIE terms): IIASA & Climate Analytics, 2025. Climate Impact Explorer.

Run from repo root: python3 scripts/ingest_cie_climate.py
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import time
import urllib.request
from pathlib import Path

API = "https://cie-api-v2.climateanalytics.org/api"
RAW_DIR = Path("data/blocks/RUS/raw/territories/cie")
OUT = Path("data/blocks/RUS/territories/climate_projections.csv")
NAME_MAP = Path("data/blocks/RUS/territories/region_name_map.csv")

VARS = {
    "tasAdjust": ("mean_air_temperature", "degC"),
    "labour-productivity-loss": ("labour_productivity_loss", "pct"),
    "wsi": ("water_stress_index", "index"),
    "fwixd": ("fire_weather_extreme_days", "days"),
}
SCENARIOS = {"h_cpol": "ngfs_current_policies", "o_1p5c": "ngfs_net_zero_2050"}
YEAR_MAX = 2050  # pilot horizon; the API serves to 2100


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "GIM19-research/0.1"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


def provinces() -> dict[str, str]:
    """GADM region id -> English name, from the geo-shapes endpoint."""
    g = json.loads(fetch(f"{API}/geo-shapes/?iso=RUS"))
    geom = g["country"]["objects"]["data"]["geometries"][0]
    return dict(geom["properties"]["subregions"])


def ne_to_rosstat() -> dict[str, str]:
    """English (NE/GADM family) name -> Rosstat region name."""
    out: dict[str, str] = {}
    with open(NAME_MAP, newline="") as fh:
        for row in csv.DictReader(fh):
            out[row["ne_name"]] = row["rosstat_name"]
    return out


def _resolve(gadm_name: str, ne_map: dict[str, str]) -> str | None:
    """GADM name -> Rosstat name. GADM and NE mostly share spellings; the Moscow
    pair differs: GADM 'Moscow City'/'Moskva' vs NE 'Moskva'/'Moskovskaya'."""
    if gadm_name == "Moscow City":
        return ne_map.get("Moskva")               # NE 'Moskva' is the federal city
    if gadm_name == "Moskva":
        return ne_map.get("Moskovskaya")          # NE name for Moscow Oblast
    aliases = {
        "Chukot": "Chukchi Autonomous Okrug",
        "Sakha": "Sakha (Yakutia)",
        "Zabaykal'ye": "Chita",                   # NE keeps the pre-2008 name
    }
    return ne_map.get(aliases.get(gadm_name, gadm_name))


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    provs = provinces()
    ne_map = ne_to_rosstat()

    rows: list[dict] = []
    misses: set[str] = set()
    n_req = 0
    for rid, gname in provs.items():
        rosstat = _resolve(gname, ne_map)
        if rosstat is None:
            misses.add(gname)
            continue
        for var, (series, unit) in VARS.items():
            cache = RAW_DIR / f"{rid.replace('.', '_')}__{var}.csv"
            if not cache.exists():
                url = (f"{API}/timeseries/?iso=RUS&region={rid}&scenario=h_cpol"
                       f"&var={var}&season=annual&aggregation_spatial=area&format=csv")
                try:
                    cache.write_bytes(fetch(url))
                except Exception as exc:                     # noqa: BLE001
                    print(f"  fail {rid} {var}: {exc}")
                    continue
                n_req += 1
                time.sleep(0.25)
            text = cache.read_text(errors="replace")
            if '"status"' in text[:200]:
                continue  # API error payload cached — variable unavailable here
            rows.extend(_parse_csv(text, rosstat, series, unit))

    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "region", "year", "series", "scenario", "value", "unit", "source"])
        w.writeheader()
        w.writerows(rows)
    print(f"{OUT}: {len(rows)} rows from {len(provs) - len(misses)} provinces "
          f"({n_req} new downloads); unmatched: {sorted(misses) or 'none'}")


def _parse_csv(text: str, region: str, series: str, unit: str) -> list[dict]:
    rows: list[dict] = []
    reader = csv.reader(io.StringIO(text))
    header: list[str] | None = None
    for rec in reader:
        if not rec:
            continue
        if rec[0].strip() == "year":
            header = rec
            continue
        if header is None or not rec[0].strip().replace(".0", "").isdigit():
            continue
        year = int(float(rec[0]))
        if year > YEAR_MAX:
            continue
        for scen_id, scen_name in SCENARIOS.items():
            col = f"{scen_id} median"
            if col in header:
                idx = header.index(col)
                if idx < len(rec) and rec[idx] not in ("", "nan"):
                    rows.append({"region": region, "year": year, "series": series,
                                 "scenario": scen_name, "value": float(rec[idx]),
                                 "unit": unit, "source": "cie_ngfs"})
    return rows


if __name__ == "__main__":
    main()
