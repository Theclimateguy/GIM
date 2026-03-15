from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gim.sensitivity_sweep import (
    format_geo_sensitivity_report,
    run_geo_sensitivity_sweep,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a sensitivity sweep over crisis outcome weights.")
    parser.add_argument("--suite", default="operational_v1")
    parser.add_argument("--state-csv")
    parser.add_argument("--weights", nargs="*")
    parser.add_argument("--case-ids", nargs="*")
    parser.add_argument("--scale-down", type=float, default=0.8)
    parser.add_argument("--scale-up", type=float, default=1.2)
    parser.add_argument("--out")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = run_geo_sensitivity_sweep(
        suite_id=args.suite,
        state_csv=args.state_csv,
        weight_paths=args.weights,
        case_ids=set(args.case_ids) if args.case_ids else None,
        scale_factors=(args.scale_down, args.scale_up),
    )
    print(format_geo_sensitivity_report(report))
    if args.out:
        Path(args.out).write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
