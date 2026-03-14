from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_CSV = REPO_ROOT / "misc" / "data" / "agent_states_gim13.csv"
DEFAULT_BUILDER_REFERENCE = "GIM/GIM_12/scripts/build_gim13_agent_states.py"
DEFAULT_HANDOFF_CONTRACT = (
    "EMISSIONS_SCALE and DECARB_RATE are compile-bound coefficients attached to the compiled "
    "state artifact. They do not carry standalone physical meaning and must only change when "
    "the state CSV is recompiled and this manifest is regenerated from the pipeline handoff."
)


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
) -> dict[str, object]:
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
    }


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
        default=1.8,
        help="Pipeline-bound EMISSIONS_SCALE to stamp into the manifest.",
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

    manifest = build_manifest(
        state_csv=state_csv,
        manifest_path=manifest_path,
        emissions_scale=args.emissions_scale,
        decarb_rate=args.decarb_rate,
        target_year=args.target_year,
        builder_reference=args.builder_reference,
        handoff_contract=args.handoff_contract,
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(manifest_path)


if __name__ == "__main__":
    main()
