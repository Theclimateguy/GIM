from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_CSV = REPO_ROOT / "misc" / "data" / "agent_states_gim13.csv"
DEFAULT_OBSERVED_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "historical_backtest_observed.json"
DEFAULT_REFERENCE_STATE_CSV = REPO_ROOT / "tests" / "fixtures" / "historical_backtest_state_2015.csv"
DEFAULT_BUILDER_REFERENCE = "GIM/GIM_12/scripts/build_gim13_agent_states.py"
DEFAULT_HANDOFF_CONTRACT = (
    "EMISSIONS_SCALE is data-derived during manifest refresh from the historical backtest fixture, "
    "while DECARB_RATE remains compile-bound until the dedicated decarbonization pass lands. "
    "These coefficients must only change when the state CSV or the refresh inputs change and the "
    "manifest is regenerated."
)

LEGACY_CORE = REPO_ROOT / "legacy" / "GIM_11_1"
if str(LEGACY_CORE) not in sys.path:
    sys.path.insert(0, str(LEGACY_CORE))

from gim_11_1.state_artifact import compute_emissions_scale_from_state_csv  # noqa: E402


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
    }


def _load_observed_global_co2(observed_fixture: Path, year: int) -> float:
    raw = json.loads(observed_fixture.read_text(encoding="utf-8"))
    return float(raw["global_co2_gtco2"][str(year)])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh the hash-locked state-artifact manifest used by the legacy climate layer."
    )
    parser.add_argument(
        "--state-csv",
        default=str(DEFAULT_STATE_CSV),
        help="Compiled state CSV to bind. Defaults to misc/data/agent_states_gim13.csv.",
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
        default=0.049,
        help="Pipeline-bound DECARB_RATE to stamp into the manifest.",
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

    manifest = build_manifest(
        state_csv=state_csv,
        manifest_path=manifest_path,
        emissions_scale=emissions_scale,
        decarb_rate=args.decarb_rate,
        target_year=args.target_year,
        builder_reference=args.builder_reference,
        handoff_contract=args.handoff_contract,
        rebuild_source=rebuild_source,
        emissions_reference_year=emissions_reference_year,
        emissions_reference_gtco2=emissions_reference_gtco2,
        emissions_reference_state_csv=emissions_reference_state_csv,
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(manifest_path)


if __name__ == "__main__":
    main()
