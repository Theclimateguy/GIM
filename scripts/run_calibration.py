#!/usr/bin/env python3
"""History-matching calibration over the 2015-2023 backtest (Phase 2-B).

Samples the calibration parameters from their priors, scores each draw's implausibility vs
observations, and reports the NROY posterior and per-parameter constraints. Writes
results/calibration-<ts>/calibration.json + manifest.

Env: CAL_SAMPLES, CAL_THRESHOLD, CAL_SEED, CAL_NAMES (comma list).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gim.calibration_hm import DEFAULT_CALIBRATION_PARAMS, history_match
from gim.results import build_run_artifacts, write_json_artifact, write_run_manifest


def main() -> int:
    names_env = os.getenv("CAL_NAMES")
    names = [n.strip() for n in names_env.split(",")] if names_env else DEFAULT_CALIBRATION_PARAMS
    n_samples = int(os.getenv("CAL_SAMPLES", "200"))
    threshold = float(os.getenv("CAL_THRESHOLD", "3.0"))
    seed = int(os.getenv("CAL_SEED", "2026"))

    print(f"History matching: {n_samples} draws over {len(names)} params, threshold={threshold}")
    t0 = datetime.now()
    res = history_match(names=names, n_samples=n_samples, threshold=threshold, seed=seed)
    elapsed = (datetime.now() - t0).total_seconds()

    payload = res.to_dict()
    artifacts = build_run_artifacts("calibration")
    path = write_json_artifact(payload, artifacts.run_dir / "calibration.json")
    write_run_manifest(
        {"command": "calibration", "run_id": artifacts.run_id,
         "summary": {"n_members": payload["n_members"], "n_nroy": payload["n_nroy"],
                     "elapsed_sec": round(elapsed, 1),
                     "best_implausibility": payload["best"]["implausibility"]["max"],
                     "created_at": datetime.now().isoformat(timespec="seconds")},
         "outputs": {"calibration_json": str(path)}},
        artifacts.run_dir,
    )

    print(f"Done in {elapsed:.1f}s. NROY: {payload['n_nroy']}/{payload['n_members']}")
    print("Per-parameter NROY constraint (retained fraction of prior range; lower = better constrained):")
    for name, c in payload["constraints"].items():
        rf = c.get("retained_fraction")
        print(f"  {name:24s} " + (f"retained={rf:.2f}  NROY[{c['nroy_min']:.4g}, {c['nroy_max']:.4g}]" if rf is not None else "(no NROY draws)"))
    print(f"Artifacts: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
