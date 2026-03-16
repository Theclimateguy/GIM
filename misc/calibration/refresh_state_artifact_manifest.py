from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_CSV = REPO_ROOT / "data" / "agent_states_operational.csv"
DEFAULT_OBSERVED_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "historical_backtest_observed.json"
DEFAULT_REFERENCE_STATE_CSV = REPO_ROOT / "tests" / "fixtures" / "historical_backtest_state_2015.csv"
DEFAULT_DECARB_CALIBRATION = Path(__file__).resolve().with_name("decarb_rate_calibration.json")
DEFAULT_BUILDER_REFERENCE = "GIM15/scripts/build_gim13_agent_states.py"
DEFAULT_HANDOFF_CONTRACT = (
    "EMISSIONS_SCALE is data-derived during manifest refresh from the historical backtest fixture, "
    "while DECARB_RATE may be stamped from either the legacy pipeline value or an observed prior. "
    "These coefficients must only change when the state CSV or the refresh inputs change and the "
    "manifest is regenerated."
)

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gim.core.state_artifact import compute_emissions_scale_from_state_csv  # noqa: E402
from gim.historical_backtest import estimate_observed_decarb_rate, load_historical_observed_fixture  # noqa: E402


def _compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _count_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def build_manifest(
    *,
    state_csv: Path,
    manifest_path: Path,
    emissions_scale: float,
    decarb_rate: float,
    target_year: int,
    builder_reference: str,
    handoff_contract: str,
    rebuild_source: str,
    emissions_reference_year: int | None = None,
    emissions_reference_gtco2: float | None = None,
    emissions_reference_state_csv: Path | None = None,
    decarb_source: str = "legacy",
    decarb_reference_rate: float | None = None,
    decarb_reference_start_year: int | None = None,
    decarb_reference_end_year: int | None = None,
) -> dict[str, object]:
    emissions_reference = None
    if (
        emissions_reference_year is not None
        and emissions_reference_gtco2 is not None
        and emissions_reference_state_csv is not None
    ):
        emissions_reference = {
            "year": emissions_reference_year,
            "global_co2_gtco2": emissions_reference_gtco2,
            "state_csv": os.path.relpath(emissions_reference_state_csv, manifest_path.parent),
        }
    return {
        "manifest_version": 1,
        "state_csv": os.path.relpath(state_csv, manifest_path.parent),
        "state_csv_sha256": _compute_sha256(state_csv),
        "state_row_count": _count_rows(state_csv),
        "compiled_target_year": target_year,
        "artifact_parameters": {
            "emissions_scale": emissions_scale,
            "decarb_rate": decarb_rate,
        },
        "change_requires_pipeline_rebuild": True,
        "builder_reference": builder_reference,
        "handoff_contract": handoff_contract,
        "rebuild_source": rebuild_source,
        "emissions_reference": emissions_reference,
        "decarb_reference": {
            "source": decarb_source,
            "rate": decarb_reference_rate,
            "start_year": decarb_reference_start_year,
            "end_year": decarb_reference_end_year,
        },
    }


def _load_observed_global_co2(observed_fixture: Path, year: int) -> float:
    raw = json.loads(observed_fixture.read_text(encoding="utf-8"))
    return float(raw["global_co2_gtco2"][str(year)])


def _load_observed_window(observed_fixture: Path) -> tuple[int, int]:
    raw = load_historical_observed_fixture(observed_fixture)
    return int(raw["start_year"]), int(raw["end_year"])


def _load_decarb_calibration_reference() -> tuple[float, int, int] | None:
    if not DEFAULT_DECARB_CALIBRATION.exists():
        return None
    raw = json.loads(DEFAULT_DECARB_CALIBRATION.read_text(encoding="utf-8"))
    global_fit = raw.get("global")
    if not isinstance(global_fit, dict):
        return None
    estimate = global_fit.get("estimate")
    start_year = global_fit.get("start_year")
    end_year = global_fit.get("end_year")
    if estimate is None or start_year is None or end_year is None:
        return None
    return float(estimate), int(start_year), int(end_year)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh the hash-locked state-artifact manifest used by the legacy climate layer."
    )
    parser.add_argument(
        "--state-csv",
        default=str(DEFAULT_STATE_CSV),
        help="Compiled state CSV to bind. Defaults to data/agent_states_operational.csv.",
    )
    parser.add_argument(
        "--manifest",
        help="Output manifest path. Defaults to <state-csv>.artifacts.json.",
    )
    parser.add_argument(
        "--emissions-scale",
        type=float,
        help="Explicit EMISSIONS_SCALE override. If omitted, derive it from the historical fixture.",
    )
    parser.add_argument(
        "--decarb-rate",
        type=float,
        help="Explicit active DECARB_RATE override for the artifact manifest.",
    )
    parser.add_argument(
        "--decarb-source",
        choices=("legacy", "observed", "manual"),
        default="legacy",
        help="How to stamp DECARB_RATE into the manifest.",
    )
    parser.add_argument(
        "--observed-decarb-rate",
        type=float,
        help="Observed decarbonization prior used when --decarb-source=observed. Defaults to a fit from the bundled observed fixture.",
    )
    parser.add_argument(
        "--observed-decarb-start-year",
        type=int,
        help="Start year for the observed decarbonization reference window. Defaults to the fixture start year.",
    )
    parser.add_argument(
        "--observed-decarb-end-year",
        type=int,
        help="End year for the observed decarbonization reference window. Defaults to the fixture end year.",
    )
    parser.add_argument(
        "--target-year",
        type=int,
        default=2023,
        help="Compiled target year represented by the state CSV.",
    )
    parser.add_argument(
        "--reference-state-csv",
        default=str(DEFAULT_REFERENCE_STATE_CSV),
        help="State CSV used to derive EMISSIONS_SCALE from observed global CO2.",
    )
    parser.add_argument(
        "--observed-fixture",
        default=str(DEFAULT_OBSERVED_FIXTURE),
        help="Observed backtest fixture containing global CO2 history.",
    )
    parser.add_argument(
        "--reference-year",
        type=int,
        default=2015,
        help="Observed reference year used when deriving EMISSIONS_SCALE.",
    )
    parser.add_argument(
        "--builder-reference",
        default=DEFAULT_BUILDER_REFERENCE,
        help="Human-readable pointer to the upstream state builder.",
    )
    parser.add_argument(
        "--handoff-contract",
        default=DEFAULT_HANDOFF_CONTRACT,
        help="Guardrail note explaining why the artifact parameters are compile-bound.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    state_csv = Path(args.state_csv).expanduser().resolve()
    manifest_path = (
        Path(args.manifest).expanduser().resolve()
        if args.manifest
        else state_csv.with_suffix(".artifacts.json")
    )
    if not state_csv.exists():
        raise SystemExit(f"State CSV not found: {state_csv}")

    reference_state_csv = Path(args.reference_state_csv).expanduser().resolve()
    observed_fixture = Path(args.observed_fixture).expanduser().resolve()
    if args.emissions_scale is None:
        if not reference_state_csv.exists():
            raise SystemExit(f"Reference state CSV not found: {reference_state_csv}")
        if not observed_fixture.exists():
            raise SystemExit(f"Observed fixture not found: {observed_fixture}")
        observed_global_co2_gtco2 = _load_observed_global_co2(observed_fixture, args.reference_year)
        emissions_scale = compute_emissions_scale_from_state_csv(
            reference_state_csv,
            observed_global_co2_gtco2,
        )
        rebuild_source = "data"
        emissions_reference_year = int(args.reference_year)
        emissions_reference_gtco2 = observed_global_co2_gtco2
        emissions_reference_state_csv = reference_state_csv
    else:
        emissions_scale = float(args.emissions_scale)
        rebuild_source = "manual"
        emissions_reference_year = None
        emissions_reference_gtco2 = None
        emissions_reference_state_csv = None

    if args.decarb_source == "legacy":
        decarb_rate = 0.049 if args.decarb_rate is None else float(args.decarb_rate)
        decarb_source = "legacy"
        decarb_reference_rate = decarb_rate
        decarb_reference_start_year = None
        decarb_reference_end_year = None
    elif args.decarb_source == "observed":
        calibration_reference = _load_decarb_calibration_reference()
        if calibration_reference is None:
            observed_start_year, observed_end_year = _load_observed_window(observed_fixture)
            observed_reference_rate = (
                float(args.observed_decarb_rate)
                if args.observed_decarb_rate is not None
                else estimate_observed_decarb_rate(observed_fixture, method="mean_pairwise")
            )
        else:
            observed_reference_rate, observed_start_year, observed_end_year = calibration_reference
            if args.observed_decarb_rate is not None:
                observed_reference_rate = float(args.observed_decarb_rate)
        decarb_rate = float(args.decarb_rate) if args.decarb_rate is not None else observed_reference_rate
        decarb_source = "observed"
        decarb_reference_rate = observed_reference_rate
        decarb_reference_start_year = (
            int(args.observed_decarb_start_year)
            if args.observed_decarb_start_year is not None
            else observed_start_year
        )
        decarb_reference_end_year = (
            int(args.observed_decarb_end_year)
            if args.observed_decarb_end_year is not None
            else observed_end_year
        )
    else:
        if args.decarb_rate is None:
            raise SystemExit("--decarb-rate is required when --decarb-source=manual")
        decarb_rate = float(args.decarb_rate)
        decarb_source = "manual"
        decarb_reference_rate = decarb_rate
        decarb_reference_start_year = None
        decarb_reference_end_year = None

    manifest = build_manifest(
        state_csv=state_csv,
        manifest_path=manifest_path,
        emissions_scale=emissions_scale,
        decarb_rate=decarb_rate,
        target_year=args.target_year,
        builder_reference=args.builder_reference,
        handoff_contract=args.handoff_contract,
        rebuild_source=rebuild_source,
        emissions_reference_year=emissions_reference_year,
        emissions_reference_gtco2=emissions_reference_gtco2,
        emissions_reference_state_csv=emissions_reference_state_csv,
        decarb_source=decarb_source,
        decarb_reference_rate=decarb_reference_rate,
        decarb_reference_start_year=decarb_reference_start_year,
        decarb_reference_end_year=decarb_reference_end_year,
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(manifest_path)


if __name__ == "__main__":
    main()
