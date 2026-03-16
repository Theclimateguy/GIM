#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gim.paths import OPERATIONAL_STATE_CSV  # noqa: E402
from gim.state_projection import project_state_csv, write_projection_metadata  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Project a compiled operational state CSV forward with deterministic GIM15 simulation."
    )
    parser.add_argument(
        "--state-csv",
        default=str(OPERATIONAL_STATE_CSV),
        help="Input compiled state CSV. Defaults to data/agent_states_operational.csv.",
    )
    parser.add_argument(
        "--output",
        help="Output projected state CSV. Defaults to data/agent_states_operational_<target-year>.csv.",
    )
    parser.add_argument(
        "--state-year",
        type=int,
        default=2023,
        help="Calendar year represented by the input state CSV. Default: 2023.",
    )
    parser.add_argument(
        "--years",
        type=int,
        default=3,
        help="Projection horizon in yearly GIM steps. Default: 3.",
    )
    parser.add_argument(
        "--policy-mode",
        choices=("simple", "growth", "llm", "auto"),
        default="simple",
        help="Background policy regime for the projection. Default: simple.",
    )
    parser.add_argument(
        "--enable-extreme-events",
        action="store_true",
        help="Enable stochastic extreme-event shocks. Disabled by default for a stable baseline projection.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Deterministic seed for temperature variability and stochastic channels. Default: 0.",
    )
    parser.add_argument(
        "--max-countries",
        type=int,
        help="Optional cap on loaded actors.",
    )
    parser.add_argument(
        "--metadata",
        help="Optional JSON summary path. Defaults to <output>.projection.json.",
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Skip writing the projection summary JSON sidecar.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target_year = int(args.state_year) + int(args.years)
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else (REPO_ROOT / "data" / f"agent_states_operational_{target_year}.csv").resolve()
    )
    metadata_path = (
        Path(args.metadata).expanduser().resolve()
        if args.metadata
        else output_path.with_suffix(".projection.json")
    )

    summary = project_state_csv(
        state_csv=args.state_csv,
        output_csv=output_path,
        years=args.years,
        state_year=args.state_year,
        policy_mode=args.policy_mode,
        enable_extreme_events=args.enable_extreme_events,
        seed=args.seed,
        max_countries=args.max_countries,
    )

    print(f"Projected state CSV: {summary.output_state_csv}")
    print(
        f"Calendar years: {summary.baseline_year} -> {summary.target_year} "
        f"(steps={summary.simulated_years}, policy_mode={summary.policy_mode})"
    )
    print(
        "World GDP: "
        f"{summary.world_gdp_start:.3f}T -> {summary.world_gdp_end:.3f}T "
        f"({(summary.world_gdp_end / summary.world_gdp_start - 1.0) * 100.0:+.2f}%)"
    )
    print(
        "World population: "
        f"{summary.world_population_start / 1e9:.3f}B -> "
        f"{summary.world_population_end / 1e9:.3f}B"
    )
    print(
        "Agent CO2: "
        f"{summary.total_co2_start:.3f}Gt -> {summary.total_co2_end:.3f}Gt"
    )
    print(
        "Global temperature: "
        f"{summary.global_temp_start:.4f}C -> {summary.global_temp_end:.4f}C"
    )

    if not args.no_metadata:
        written_metadata = write_projection_metadata(summary, metadata_path)
        print(f"Projection metadata: {written_metadata}")


if __name__ == "__main__":
    main()
