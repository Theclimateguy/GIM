from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path


@dataclass(frozen=True)
class StateArtifactBinding:
    manifest_version: int
    manifest_path: Path
    state_csv_path: Path
    state_csv_sha256: str
    state_row_count: int
    target_year: int
    emissions_scale: float
    decarb_rate: float
    change_requires_pipeline_rebuild: bool
    builder_reference: str
    handoff_contract: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _primary_state_csv(repo_root: Path) -> Path:
    return (repo_root / "misc" / "data" / "agent_states_gim13.csv").resolve()


def _resolve_state_csv_path(path: str | Path) -> Path:
    resolved = Path(path).expanduser()
    if not resolved.is_absolute():
        resolved = (Path.cwd() / resolved).resolve()
    else:
        resolved = resolved.resolve()
    return resolved


def _active_state_csv_override() -> str | None:
    raw = os.environ.get("GIM13_STATE_CSV")
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def _manifest_path_for_state_csv(repo_root: Path, state_csv_path: Path) -> Path:
    primary_state_csv = _primary_state_csv(repo_root)
    if state_csv_path == primary_state_csv:
        return primary_state_csv.with_suffix(".artifacts.json")
    return state_csv_path.with_suffix(".artifacts.json")


def _compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _count_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def load_state_artifact(state_csv: str | Path | None = None) -> StateArtifactBinding:
    repo_root = _repo_root()
    requested_state_csv = state_csv or _active_state_csv_override() or _primary_state_csv(repo_root)
    state_csv_path = _resolve_state_csv_path(requested_state_csv)
    manifest_path = _manifest_path_for_state_csv(repo_root, state_csv_path)
    if not manifest_path.exists():
        raise RuntimeError(
            f"State artifact manifest is missing: {manifest_path}. "
            "Restore the manifest or regenerate it from the state pipeline handoff before "
            "changing compiled-state climate coefficients."
        )

    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_version = int(raw.get("manifest_version", 1))
    if manifest_version != 1:
        raise RuntimeError(
            f"Unsupported state artifact manifest version {manifest_version} in {manifest_path}"
        )

    manifest_state_csv = Path(str(raw["state_csv"]))
    if not manifest_state_csv.is_absolute():
        manifest_state_csv = (manifest_path.parent / manifest_state_csv).resolve()
    else:
        manifest_state_csv = manifest_state_csv.resolve()
    if manifest_state_csv != state_csv_path:
        raise RuntimeError(
            "State artifact manifest does not match the requested compiled state. "
            f"Requested {state_csv_path}, manifest points to {manifest_state_csv}."
        )
    if not state_csv_path.exists():
        raise RuntimeError(
            f"Primary compiled state referenced by the artifact manifest is missing: {state_csv_path}"
        )

    expected_sha = str(raw["state_csv_sha256"])
    actual_sha = _compute_sha256(state_csv_path)
    if actual_sha != expected_sha:
        raise RuntimeError(
            "Primary compiled state hash mismatch. "
            "EMISSIONS_SCALE and DECARB_RATE are pipeline-bound artifact parameters and must be "
            "refreshed together with the compiled state handoff."
        )
    expected_rows = int(raw["state_row_count"])
    actual_rows = _count_rows(state_csv_path)
    if actual_rows != expected_rows:
        raise RuntimeError(
            "Primary compiled state row count mismatch. "
            f"Manifest expects {expected_rows} rows but {state_csv_path} has {actual_rows}."
        )

    return StateArtifactBinding(
        manifest_version=manifest_version,
        manifest_path=manifest_path,
        state_csv_path=state_csv_path,
        state_csv_sha256=expected_sha,
        state_row_count=expected_rows,
        target_year=int(raw["compiled_target_year"]),
        emissions_scale=float(raw["artifact_parameters"]["emissions_scale"]),
        decarb_rate=float(raw["artifact_parameters"]["decarb_rate"]),
        change_requires_pipeline_rebuild=bool(raw["change_requires_pipeline_rebuild"]),
        builder_reference=str(raw.get("builder_reference", "")),
        handoff_contract=str(raw["handoff_contract"]),
    )


def load_primary_state_artifact() -> StateArtifactBinding:
    return load_state_artifact(_primary_state_csv(_repo_root()))


PRIMARY_STATE_ARTIFACT = load_primary_state_artifact()

active_state_csv_override = _active_state_csv_override()
if active_state_csv_override is None:
    ACTIVE_STATE_ARTIFACT = PRIMARY_STATE_ARTIFACT
else:
    active_state_csv_path = _resolve_state_csv_path(active_state_csv_override)
    if active_state_csv_path == PRIMARY_STATE_ARTIFACT.state_csv_path:
        ACTIVE_STATE_ARTIFACT = PRIMARY_STATE_ARTIFACT
    else:
        ACTIVE_STATE_ARTIFACT = load_state_artifact(active_state_csv_path)


__all__ = [
    "ACTIVE_STATE_ARTIFACT",
    "PRIMARY_STATE_ARTIFACT",
    "StateArtifactBinding",
    "load_state_artifact",
    "load_primary_state_artifact",
]
