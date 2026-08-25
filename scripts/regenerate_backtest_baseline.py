#!/usr/bin/env python3
"""Regenerate tests/fixtures/historical_backtest_baseline.json.

The baseline is the reference the envelope test in tests/test_historical_backtest.py guards
against: a regression is a run that leaves the band around these numbers. It was previously
hand-maintained, with no generator, so moving it was a manual edit with no record of what was
run. It also predated resource prices becoming a validation target and so carried no price
fields, which meant the price subsystem was outside the guard entirely.

Note on configuration: the baseline and the envelope test both call run_historical_backtest()
with its DEFAULTS, i.e. the temperature ENSEMBLE with internal variability on. Comparing a
stored ensemble number against a deterministic single-member run (which
temperature_variability_sigma_override=0.0 produces, and which most of the diagnostic scripts
here use) compares two different things -- the deterministic temperature RMSE is 0.0989 where
the ensemble figure is 0.1447. Regenerate through this script so the configuration matches.

Run this deliberately, after a reviewed model change, and commit the result with the reason:

    python3 scripts/regenerate_backtest_baseline.py

Refuses to overwrite unless --force is given when the new numbers are WORSE than the stored
ones, so that regenerating cannot silently launder a regression into the reference.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from gim.historical_backtest import (            # noqa: E402
    DEFAULT_BASELINE_FIXTURE,
    load_historical_backtest_baseline,
    run_historical_backtest,
)

GUARDED = ("gdp_rmse_trillions", "global_co2_rmse_gtco2", "temperature_rmse_c")


def _git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
            text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="write even when a guarded metric got worse")
    ap.add_argument("--reason", default="", help="why the baseline is being moved")
    args = ap.parse_args()

    result = run_historical_backtest()
    payload = result.to_dict()
    payload["_provenance"] = {
        "generated_by": "scripts/regenerate_backtest_baseline.py",
        "git_head": _git_head(),
        "reason": args.reason,
    }

    worse = []
    if DEFAULT_BASELINE_FIXTURE.exists():
        old = load_historical_backtest_baseline()
        print(f"{'metric':30s} {'stored':>10s} {'new':>10s} {'change':>9s}")
        # 1% of slack: run-to-run and ensemble noise are not regressions, and a guard that
        # trips on 0.05% would just be forced past every time, which defeats it.
        for k in GUARDED:
            o, n = float(getattr(old, k)), float(getattr(result, k))
            print(f"{k:30s} {o:10.4f} {n:10.4f} {100*(n-o)/o:+8.2f}%")
            if n > o * 1.01:
                worse.append(k)
        for c, o in sorted(old.country_gdp_rmse_trillions.items()):
            n = result.country_gdp_rmse_trillions[c]
            if n > o * 1.02:
                worse.append(f"country:{c}")
        if result.resource_price_rmse:
            print("\nresource price RMSE (new field):",
                  {k: round(v, 4) for k, v in result.resource_price_rmse.items()})

    if worse and not args.force:
        print("\nREFUSED: these got worse ->", ", ".join(worse))
        print("Re-run with --force --reason '...' if the regression is intended and reviewed.")
        return 1

    DEFAULT_BASELINE_FIXTURE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {DEFAULT_BASELINE_FIXTURE.relative_to(REPO)} at {_git_head()}")
    if worse:
        print("forced past regressions in:", ", ".join(worse))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
