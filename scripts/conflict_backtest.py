#!/usr/bin/env python3
"""Stage-4 (F3) conflict backtest — skill vs base rate (the geopolitics analogue of the climate backtest).

Honest bar (docs/SOCIAL_GEO_METRICS.md): conflict is intrinsically low-signal, so the target is
*skill vs the empirical base rate*, not point prediction. This harness scores GIM's per-country
conflict risk (`conflict_proneness`, a 0-1 hazard score) against UCDP/PRIO realized conflict
involvement, using the Brier Skill Score (BSS) and AUC.

    BSS = 1 - Brier(model) / Brier(base_rate)      # >0 means GIM beats "predict the base rate"

Inputs:
  * GIM risk score: `conflict_proneness` per country, from the state CSV.
  * Labels: UCDP/PRIO ACD (data/external/raw/ucdp-prio-acd-*.csv) -> per-country "in conflict over
    the window" (1/0). If the file is absent, the harness reports the framework + the published
    base rate and exits (it does NOT fabricate a skill number).

    python3 scripts/conflict_backtest.py [--window 1990 2023]

Why score the input, not realized GIM onsets: GIM's rule-based ("simple") policy does not itself
generate interstate-war onsets without an explicit conflict scenario (see docs/STRESS_AUDIT.md),
so the meaningful, runnable skill test is whether GIM's *risk input* ranks conflict involvement
better than the base rate — exactly the climate-backtest's skill-vs-naive logic.
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import sys
from typing import Dict, List, Optional, Tuple

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

STATE = os.path.join(REPO, "data", "agent_states_operational_2026_calibrated.csv")
UCDP_GLOB = os.path.join(REPO, "data", "external", "raw", "ucdp-prio-acd-*.csv")

# Published reference: ~ fraction of country-years with an active state-based armed conflict,
# UCDP/PRIO ACD 1990-2023 (~0.15-0.20 across all countries; higher among GIM's large states).
UCDP_PUBLISHED_BASE_RATE = 0.18


def load_gim_conflict_proneness() -> Dict[str, float]:
    out: Dict[str, float] = {}
    with open(STATE, newline="") as fh:
        for row in csv.DictReader(fh):
            name = row.get("name") or row.get("id")
            try:
                out[name] = float(row["conflict_proneness"])
            except (KeyError, ValueError, TypeError):
                continue
    return out


def load_ucdp_labels(window: Tuple[int, int]) -> Optional[Dict[str, int]]:
    files = sorted(glob.glob(UCDP_GLOB))
    if not files:
        return None
    lo, hi = window
    involved: Dict[str, int] = {}
    with open(files[-1], newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                yr = int(float(row.get("year", "")))
            except ValueError:
                continue
            if not (lo <= yr <= hi):
                continue
            # country names appear in side_a / side_b / location depending on UCDP version
            for key in ("side_a", "side_b", "location"):
                for nm in str(row.get(key, "")).split(","):
                    nm = nm.strip()
                    if nm:
                        involved[nm] = 1
    return involved


def brier(probs: List[float], labels: List[int]) -> float:
    return sum((p - y) ** 2 for p, y in zip(probs, labels)) / max(1, len(labels))


def auc(probs: List[float], labels: List[int]) -> float:
    pos = [p for p, y in zip(probs, labels) if y == 1]
    neg = [p for p, y in zip(probs, labels) if y == 0]
    if not pos or not neg:
        return float("nan")
    wins = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return wins / (len(pos) * len(neg))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", nargs=2, type=int, default=[1990, 2023])
    args = ap.parse_args()

    gim = load_gim_conflict_proneness()
    labels_map = load_ucdp_labels(tuple(args.window))

    if labels_map is None:
        print("UCDP file not found (data/external/raw/ucdp-prio-acd-*.csv).")
        print("Framework ready; published base rate = %.2f." % UCDP_PUBLISHED_BASE_RATE)
        print("Base-rate Brier = p(1-p) = %.4f" %
              (UCDP_PUBLISHED_BASE_RATE * (1 - UCDP_PUBLISHED_BASE_RATE)))
        print("Download UCDP/PRIO ACD (see data/external/SOURCES.md) and re-run to score GIM's skill.")
        return 0

    names = [n for n in gim if n in labels_map] + [n for n in gim if n not in labels_map]
    probs = [gim[n] for n in names]
    labels = [labels_map.get(n, 0) for n in names]
    base_rate = sum(labels) / max(1, len(labels))
    bs_model = brier(probs, labels)
    bs_base = brier([base_rate] * len(labels), labels)
    bss = 1.0 - bs_model / bs_base if bs_base > 0 else float("nan")

    print(f"Countries scored: {len(names)}  base rate: {base_rate:.3f}")
    print(f"Brier(model)={bs_model:.4f}  Brier(base)={bs_base:.4f}  BSS={bss:+.3f}  AUC={auc(probs,labels):.3f}")
    print("BSS>0 => GIM conflict_proneness beats the base rate (has skill).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
