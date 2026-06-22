#!/usr/bin/env python3
"""F2.4 (D4): headline GDP skill-vs-naive + SSP growth alignment.

The honest accuracy metric for multi-year GDP is skill vs a naive persistence/trend baseline
(IMF-WEO evaluation, Celasun et al. 2021): even professional 2-5y forecasts often fail to beat it.
This surfaces GIM's 2015-2023 backtest skill as the headline, alongside where GIM's baseline TFP
growth sits relative to the SSP narratives.

    python3 scripts/report_gdp_skill.py
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.benchmark_alignment import backtest_skill_report  # noqa: E402
from gim.scenario_alignment import gdp_growth_alignment_report  # noqa: E402


def main() -> int:
    skill = backtest_skill_report()
    growth = gdp_growth_alignment_report()

    print("=== GDP skill vs naive (2015-2023 backtest) ===")
    for series, d in skill.items():
        sk = d.get("skill_vs_persistence")
        verdict = "beats naive" if (sk is not None and sk > 0) else "below naive"
        print(f"  {series:24s} skill={sk:+.3f}  ({verdict})")

    print("\n=== Baseline TFP-growth vs SSP anchors ===")
    print(f"  GIM TFP drift: {growth['gim_tfp_drift']:.3f}  nearest SSP: {growth['nearest_ssp']}"
          f"  below SSP2: {growth['below_ssp2']}")
    for ssp, v in growth["ssp_tfp_drift"].items():
        print(f"    {ssp}: {v:.3f}")

    os.makedirs(os.path.join(REPO, "results", "calibration"), exist_ok=True)
    out = os.path.join(REPO, "results", "calibration", "gdp_skill_ssp_report.json")
    with open(out, "w") as fh:
        json.dump({"skill": skill, "growth_alignment": growth}, fh, indent=2, default=str)
        fh.write("\n")
    print(f"\nReport -> {os.path.relpath(out, REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
