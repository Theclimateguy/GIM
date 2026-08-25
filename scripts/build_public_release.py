#!/usr/bin/env python3
"""Build the PUBLIC release tree: the model exactly as the paper describes it.

The paper models Russia as one consolidated country agent, the same as the other 56. It
never mentions the intra-country block layer -- only the authors' affiliations. The working
repository, however, carries a sub-national decomposition of Russia: 303 tracked data files
totalling 2.3 GB, six RUS-specific scripts, a nine-module block engine, its tests and a
specification document. None of that belongs in the public artifact or the paper.

Two things follow, and the second is the reason this is a build rather than a branch:

  1. The engine already runs Russia consolidated by DEFAULT. BLOCK_LAYER_AGENTS is empty,
     and gim/core/transitions/block_substep.py returns immediately on an empty list and
     imports gim.blocks only lazily, inside the guard. So removing the block layer changes
     no default behaviour -- and this script verifies exactly that rather than asserting it.
  2. A public BRANCH of this repository would still carry the 2.3 GB of Russia data in its
     object store, because git history is shared. The public tree therefore needs its own
     history, which is what --git-init gives it.

Usage:
    python3 scripts/build_public_release.py --out dist/gim-public [--git-init]

The build fails rather than shipping if the public tree does not reproduce the local
headline numbers, or if any excluded pattern survives into the output.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Everything Russia-specific, plus the generic block engine it exists to drive.
# Kept deliberately explicit: a reviewer should be able to read what was withheld.
EXCLUDE_DIRS = [
    "data/blocks",              # 2.3 GB of RUS sub-national source data
    "gim/blocks",               # the block engine (no data ships to drive it)
    "lib",                      # the packaged block-layer handoff bundle: gim19/ IS the block
                                # engine, and it carries its own second copy of the RUS data
    "Paper/thumbnails",         # figure scratch and preview renders
    "dist",
    "results",                  # working run outputs
    "macapp", "gim2",           # desktop app bundles; gim2 ships the Russia block by design
]
EXCLUDE_GLOBS = [
    # Manuscript sources go to the journal; Paper/revision (the validation scripts and their
    # JSON results) stays, because it is the evidence behind the paper's claims and GMD asks
    # for exactly that under code and data availability.
    # Paper/figures stays: make_paper_figures.py regenerates it from committed model
    # output, so shipping the generator without its output directory breaks the loop
    # the script exists to close. From 20.1 the canonical manuscript ships too (it is
    # tracked explicitly in .gitignore), so nothing under Paper/ is excluded by pattern
    # any more -- only build by-products.
    "Paper/*.aux", "Paper/*.log", "Paper/*.bbl", "Paper/*.blg", "Paper/*.out", "Paper/*.abs",
    "Paper/*.synctex.gz", "Paper/*.fdb_latexmk", "Paper/*.fls",
    "scripts/*rus*", "scripts/*_rus_*", "scripts/backtest_rus_blocks.py",
    "tests/test_block_*.py",
    "tests/test_gim2_*.py",     # the desktop app is excluded, so its tests go with it
    "tests/test_macapp*.py",
    "tests/test_regional_budget.py",      # reads data/blocks/RUS/territories
    "tests/test_integrated_golden_run.py",  # pins the RUS block trajectory; the public
                                            # reference is tests/test_global_golden_run.py
    "*субнациональная*",        # the sub-national specification document
    "*.pyc", "__pycache__", ".DS_Store", ".pytest_cache",
]
# Files that must NOT appear in the output, checked after the copy.
FORBIDDEN_SUBSTRINGS = ["blocks/RUS", "block_states_RUS", "субнацион"]


def tracked_files() -> list[str]:
    # -z: NUL-separated and unquoted. Without it git escapes non-ASCII paths, and the
    # sub-national specification document has a Cyrillic filename.
    out = subprocess.check_output(["git", "-C", str(REPO), "ls-files", "-z"])
    return [b.decode("utf-8") for b in out.split(b"\0") if b]


def excluded(rel: str) -> bool:
    p = Path(rel)
    for d in EXCLUDE_DIRS:
        if rel == d or rel.startswith(d + "/"):
            return True
    for g in EXCLUDE_GLOBS:
        if p.match(g) or any(part == g for part in p.parts):
            return True
        if g.startswith("*") and g.endswith("*") and g.strip("*") in rel:
            return True
    return False


def headline_numbers() -> dict:
    """The numbers the public tree has to reproduce, run in-process."""
    from gim.historical_backtest import run_historical_backtest
    r = run_historical_backtest(temperature_variability_sigma_override=0.0)
    return {
        "gdp_rmse_trillions": round(float(r.gdp_rmse_trillions), 8),
        "global_co2_rmse_gtco2": round(float(r.global_co2_rmse_gtco2), 8),
        "temperature_rmse_c": round(float(r.temperature_rmse_c), 8),
        "resource_price_rmse": {k: round(float(v), 8)
                                for k, v in sorted(r.resource_price_rmse.items())},
        "country_gdp_rmse_trillions": {k: round(float(v), 8) for k, v in
                                       sorted(r.country_gdp_rmse_trillions.items())},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist/gim-public")
    ap.add_argument("--git-init", action="store_true",
                    help="initialise a fresh repository in the output, with no shared history")
    args = ap.parse_args()

    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    print("computing local headline numbers ...")
    local = headline_numbers()

    out = (REPO / args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    kept, dropped, bytes_kept, bytes_dropped = 0, 0, 0, 0
    for rel in tracked_files():
        src = REPO / rel
        if not src.exists():
            continue
        size = src.stat().st_size
        if excluded(rel):
            dropped += 1
            bytes_dropped += size
            continue
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        kept += 1
        bytes_kept += size

    print(f"kept    {kept:5d} files  {bytes_kept/1e6:9.1f} MB")
    print(f"dropped {dropped:5d} files  {bytes_dropped/1e6:9.1f} MB")

    leaked = [str(p.relative_to(out)) for p in out.rglob("*")
              if p.is_file() and any(s in str(p) for s in FORBIDDEN_SUBSTRINGS)]
    if leaked:
        print("FAILED: excluded material present in the output:")
        for f in leaked[:20]:
            print("   ", f)
        return 1

    # The public tree must be the same model. Run its own backtest in a clean interpreter.
    print("\nverifying the public tree reproduces the local headline numbers ...")
    probe = ("import json,sys; sys.path.insert(0,'.');"
             "from gim.historical_backtest import run_historical_backtest as R;"
             "r=R(temperature_variability_sigma_override=0.0);"
             "print(json.dumps({'gdp_rmse_trillions':round(float(r.gdp_rmse_trillions),8),"
             "'global_co2_rmse_gtco2':round(float(r.global_co2_rmse_gtco2),8),"
             "'temperature_rmse_c':round(float(r.temperature_rmse_c),8),"
             "'resource_price_rmse':{k:round(float(v),8) for k,v in sorted(r.resource_price_rmse.items())},"
             "'country_gdp_rmse_trillions':{k:round(float(v),8) for k,v in "
             "sorted(r.country_gdp_rmse_trillions.items())}}))")
    res = subprocess.run([sys.executable, "-c", probe], cwd=out,
                         capture_output=True, text=True)
    if res.returncode != 0:
        print("FAILED: the public tree could not run the backtest")
        print(res.stderr[-2000:])
        return 1
    public = json.loads(res.stdout.strip().splitlines()[-1])

    if public != local:
        print("FAILED: the public tree does not reproduce the local numbers")
        for k in local:
            if public.get(k) != local[k]:
                print(f"   {k}: local {local[k]} != public {public.get(k)}")
        return 1
    print("  identical on every headline metric, including all 20 country RMSEs")

    print("\nrunning the public tree's own test suite ...")
    t = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"],
                       cwd=out, capture_output=True, text=True)
    tail = [ln for ln in t.stdout.strip().splitlines() if ln.strip()][-1:] or [""]
    print("  " + tail[0])
    if t.returncode != 0:
        print("FAILED: the public tree does not pass its own tests")
        print(t.stdout[-3000:])
        return 1

    (out / "PUBLIC_RELEASE.md").write_text(
        "# Public release\n\n"
        "Built by `scripts/build_public_release.py` from the working repository.\n\n"
        "Russia is modelled here as a single consolidated country agent, identically to the "
        "other 56 -- which is the model the paper describes. The working repository also "
        "carries an intra-country block layer and a sub-national decomposition of Russia; "
        "neither is part of this release, of the paper, or of any result reported in it.\n\n"
        "This is not a subset of the published model: the block layer is opt-in "
        "(`BLOCK_LAYER_AGENTS`, empty by default) and every number in the paper is produced "
        "with it inactive. The build verifies that by running the historical backtest in this "
        "tree and requiring it to match the working repository exactly on the GDP, CO2, "
        "temperature and resource-price RMSEs and on all 20 country-level GDP RMSEs.\n",
        encoding="utf-8")

    if args.git_init:
        subprocess.run(["git", "init", "-q"], cwd=out, check=True)
        subprocess.run(["git", "add", "-A"], cwd=out, check=True)
        subprocess.run(["git", "-c", "user.name=GIM", "-c", "user.email=noreply@example.org",
                        "commit", "-q", "-m",
                        "GIM public release: 57 consolidated country agents"],
                       cwd=out, check=True)
        print("  initialised a fresh repository (no shared history)")

    print(f"\npublic tree at {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
