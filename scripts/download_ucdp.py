#!/usr/bin/env python3
"""Download the UCDP/PRIO Armed Conflict Dataset (conflict-level CSV) for the F3 conflict backtest.

Run LOCALLY (normal network; the build sandbox can't reach the UCDP host). Places the CSV where
scripts/conflict_backtest.py expects it: data/external/raw/ucdp-prio-acd-<ver>.csv

    python3 scripts/download_ucdp.py            # tries v24.1, then v25.1
    python3 scripts/download_ucdp.py --version 25.1

If the direct URL ever changes, just download manually from the UCDP Download Center
(https://ucdp.uu.se/downloads/ -> "UCDP/PRIO Armed Conflict Dataset" -> CSV, Conflict version) and
drop the .csv into data/external/raw/.
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import urllib.request
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(REPO, "data", "external", "raw")

# UCDP Download Center direct paths (conflict-level CSV zips). Pattern is stable across versions.
URLS = {
    "24.1": "https://ucdp.uu.se/downloads/ucdpprio/ucdp-prio-acd-241-csv.zip",
    "25.1": "https://ucdp.uu.se/downloads/ucdpprio/ucdp-prio-acd-251-csv.zip",
}


def _try(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (GIM17 data fetch)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except Exception as e:  # noqa: BLE001
        print(f"  ! {url}: {e}", file=sys.stderr)
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=None, help="UCDP ACD version, e.g. 24.1 or 25.1")
    args = ap.parse_args()
    os.makedirs(RAW, exist_ok=True)

    versions = [args.version] if args.version else ["24.1", "25.1"]
    for ver in versions:
        url = URLS.get(ver) or f"https://ucdp.uu.se/downloads/ucdpprio/ucdp-prio-acd-{ver.replace('.', '')}-csv.zip"
        print(f"Fetching UCDP/PRIO ACD v{ver}: {url}")
        blob = _try(url)
        if not blob:
            continue
        try:
            zf = zipfile.ZipFile(io.BytesIO(blob))
            names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not names:
                print("  ! no CSV in archive"); continue
            name = names[0]
            out = os.path.join(RAW, f"ucdp-prio-acd-{ver.replace('.', '')}.csv")
            with zf.open(name) as src, open(out, "wb") as dst:
                dst.write(src.read())
            print(f"  -> {os.path.relpath(out, REPO)}  (from {name})")
            print("Done. Now run:  python3 scripts/conflict_backtest.py")
            return 0
        except zipfile.BadZipFile:
            # some endpoints serve the CSV directly
            out = os.path.join(RAW, f"ucdp-prio-acd-{ver.replace('.', '')}.csv")
            with open(out, "wb") as dst:
                dst.write(blob)
            print(f"  -> {os.path.relpath(out, REPO)} (raw)")
            return 0

    print("\nAutomatic download failed. Download manually from the UCDP Download Center:")
    print("  https://ucdp.uu.se/downloads/  ->  UCDP/PRIO Armed Conflict Dataset  ->  CSV (Conflict)")
    print(f"  then place the .csv in {os.path.relpath(RAW, REPO)}/ (name ucdp-prio-acd-*.csv)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
