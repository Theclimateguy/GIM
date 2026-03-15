from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from .paths import RESULTS_ROOT


@dataclass(frozen=True)
class RunArtifacts:
    command: str
    run_timestamp: str
    run_id: str
    run_dir: Path


def build_run_artifacts(command: str) -> RunArtifacts:
    stamp = datetime.now()
    run_timestamp = stamp.strftime("%Y-%m-%d %H:%M")
    run_id = f"{command}-{stamp.strftime('%Y%m%d-%H%M%S')}"
    run_dir = RESULTS_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return RunArtifacts(
        command=command,
        run_timestamp=run_timestamp,
        run_id=run_id,
        run_dir=run_dir,
    )


def resolve_run_output_path(run_dir: Path, raw_path: str | Path | None, default_filename: str) -> Path:
    if raw_path is None:
        return run_dir / default_filename

    raw_text = str(raw_path).strip()
    if not raw_text:
        return run_dir / default_filename

    candidate = Path(raw_text).expanduser()
    if candidate.is_absolute():
        return candidate
    if candidate.parent != Path("."):
        return candidate
    return run_dir / candidate.name


def write_json_artifact(payload: Any, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def write_run_manifest(payload: dict[str, Any], run_dir: Path, filename: str = "run_manifest.json") -> Path:
    return write_json_artifact(payload, run_dir / filename)
