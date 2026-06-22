#!/usr/bin/env python3
"""Stage-4 (F3) initial-state anchoring against external data.

Grounds GIM's unique-layer initial state in observable external indices (docs/SOCIAL_GEO_METRICS.md):

  * military_power -> CINC (Composite Index of National Capability) — computed in-repo from the
    components GIM tracks (population, energy, GDP, mil-spending); validated vs published CINC.
    This part is fully self-contained and runs anywhere.
  * inequality_gini -> World Bank Gini (SI.POV.GINI) / SWIID — anchored if the external file from
    scripts/ingest_external_data.py is present (data/external/worldbank_wdi_*.csv).
  * regime_stability -> WGI Political Stability (PV.EST), rescaled from [-2.5,2.5] to [0,1] —
    anchored if data/external/worldbank_wgi_*.csv is present.

Writes an anchored state CSV + a JSON report of per-country deltas. The CINC grounding shifts
conflict dynamics, so it is applied to a *separate* anchored CSV, not the golden-bound primary.

    python3 scripts/anchor_initial_state.py
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys
from typing import Dict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from gim.capability import capability_ranking, composite_capability_index, ground_military_power  # noqa: E402
from gim.core.world_factory import make_world_from_csv  # noqa: E402
STATE = os.path.join(REPO, "data", "agent_states_operational_2026_calibrated.csv")
OUT_CSV = os.path.join(REPO, "data", "agent_states_operational_2026_anchored.csv")
REPORT = os.path.join(REPO, "results", "calibration", "f3_anchoring_report.json")


def _load_external(pattern: str, variable: str) -> Dict[str, float]:
    """Latest-year value per iso3 for `variable` from a tidy external CSV, if present."""
    files = sorted(glob.glob(os.path.join(REPO, "data", "external", pattern)))
    if not files:
        return {}
    latest: Dict[str, tuple] = {}
    with open(files[-1], newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("variable") != variable:
                continue
            try:
                yr = int(row["year"]); val = float(row["value"]); iso = row["iso3"]
            except (KeyError, ValueError):
                continue
            if iso not in latest or yr > latest[iso][0]:
                latest[iso] = (yr, val)
    return {k: v for k, (_, v) in latest.items()}


def main() -> int:
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    world = make_world_from_csv(STATE, max_agents=100, base_year=2026)

    # 1) CINC grounding (always available)
    before = {aid: a.technology.military_power for aid, a in world.agents.items()}
    cinc = composite_capability_index(world)
    ground_military_power(world)
    after = {aid: a.technology.military_power for aid, a in world.agents.items()}
    ranking = capability_ranking(world, top=10)

    # 2) External anchors (only if ingested files are present)
    gini_ext = _load_external("worldbank_wdi_*.csv", "gini_wb")
    pv_ext = _load_external("worldbank_wgi_*.csv", "wgi_political_stability")

    gini_deltas, stab_deltas = {}, {}
    for aid, a in world.agents.items():
        if aid in gini_ext:
            old = a.society.inequality_gini
            a.society.inequality_gini = gini_ext[aid]
            gini_deltas[aid] = {"old": old, "new": gini_ext[aid]}
        if aid in pv_ext:
            old = a.risk.regime_stability
            new = max(0.0, min(1.0, (pv_ext[aid] + 2.5) / 5.0))  # [-2.5,2.5] -> [0,1]
            a.risk.regime_stability = new
            stab_deltas[aid] = {"old": old, "new": round(new, 3)}

    report = {
        "cinc_grounding": {
            "method": "Correlates of War CINC (computed in-repo from pop/energy/GDP/milex)",
            "top10_capability_share": [{"country": c, "cinc": round(v, 4)} for c, v in ranking],
            "military_power_before_after_sample": {
                aid: {"before": round(before[aid], 3), "after": round(after[aid], 3)}
                for aid in list(world.agents)[:8]
            },
        },
        "external_anchors": {
            "gini_wb_anchored_countries": len(gini_deltas),
            "wgi_stability_anchored_countries": len(stab_deltas),
            "gini_sample": {k: gini_deltas[k] for k in list(gini_deltas)[:5]},
            "stability_sample": {k: stab_deltas[k] for k in list(stab_deltas)[:5]},
            "note": ("inequality_gini <- World Bank Gini (SI.POV.GINI, SWIID proxy); "
                     "regime_stability <- WGI Political Stability (PV.EST) rescaled [-2.5,2.5]->[0,1]. "
                     "0 here would mean data/external/*.csv is missing -> run scripts/ingest_external_data.py."),
        },
    }
    with open(REPORT, "w") as fh:
        json.dump(report, fh, indent=2); fh.write("\n")

    # Write a loadable anchored state CSV (CINC military_power + WGI/Gini anchors applied).
    anchored = "(skipped)"
    try:
        from gim.state_projection import write_compiled_state_csv
        write_compiled_state_csv(world, OUT_CSV)
        anchored = os.path.relpath(OUT_CSV, REPO)
    except Exception as e:  # noqa: BLE001
        anchored = f"(could not write: {e})"

    print("CINC capability ranking (top 10):")
    for c, v in ranking:
        print(f"  {c:20s} {v:.4f}")
    print(f"\nGini anchored: {len(gini_deltas)} countries; WGI-stability anchored: {len(stab_deltas)}")
    print(f"Anchored state CSV -> {anchored}")
    print(f"Report -> {os.path.relpath(REPORT, REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
