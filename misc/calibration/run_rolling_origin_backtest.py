#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gim.historical_backtest import DEFAULT_INITIAL_STATE_CSV, DEFAULT_OBSERVED_FIXTURE
from gim.rolling_backtest import (
    build_origin_windows,
    format_rolling_backtest_result,
    format_stage_bc_result,
    run_block4_stage_bc,
    run_stepwise_rolling_backtest,
)


def _default_output_dir() -> Path:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return REPO_ROOT / "results" / "backtest" / f"rolling_{ts}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build rolling-origin windows and run stepwise recalibrated historical backtest."
    )
    parser.add_argument("--base-state-csv", default=str(DEFAULT_INITIAL_STATE_CSV))
    parser.add_argument("--observed-fixture", default=str(DEFAULT_OBSERVED_FIXTURE))
    parser.add_argument("--output-dir", default=str(_default_output_dir()))
    parser.add_argument("--stage", choices=("pairwise", "block4"), default="pairwise")
    parser.add_argument("--origin-start-year", type=int, default=None)
    parser.add_argument("--origin-end-year", type=int, default=None)
    parser.add_argument("--policy-mode", default="simple")
    parser.add_argument("--economy-param-name", default="TFP_RD_SHARE_SENS")
    parser.add_argument("--climate-param-name", default="DECARB_RATE_STRUCTURAL")
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Only generate origin windows and fixtures, do not run recalibration/backtest.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.build_only:
        windows = build_origin_windows(
            output_dir=args.output_dir,
            base_state_csv=args.base_state_csv,
            observed_fixture=args.observed_fixture,
            policy_mode=args.policy_mode,
            origin_start_year=args.origin_start_year,
            origin_end_year=args.origin_end_year,
        )
        if windows:
            print(
                "Built origin windows "
                f"{windows[0].origin_year}-{windows[-1].origin_year} ({len(windows)} windows)"
            )
        else:
            print("Built 0 windows")
        print(f"Artifacts: {Path(args.output_dir).resolve()}")
        return 0

    if args.stage == "pairwise":
        result = run_stepwise_rolling_backtest(
            output_dir=args.output_dir,
            base_state_csv=args.base_state_csv,
            observed_fixture=args.observed_fixture,
            policy_mode=args.policy_mode,
            origin_start_year=args.origin_start_year,
            origin_end_year=args.origin_end_year,
            economy_param_name=args.economy_param_name,
            climate_param_name=args.climate_param_name,
        )
        print(format_rolling_backtest_result(result))
    else:
        result = run_block4_stage_bc(
            output_dir=args.output_dir,
            base_state_csv=args.base_state_csv,
            observed_fixture=args.observed_fixture,
            policy_mode=args.policy_mode,
            origin_start_year=args.origin_start_year,
            origin_end_year=args.origin_end_year,
        )
        print(format_stage_bc_result(result))
    print(f"Artifacts: {Path(args.output_dir).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
