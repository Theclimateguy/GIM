from __future__ import annotations

import csv
import importlib
import re
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[2]
CAL_PATH = REPO_ROOT / "gim" / "core" / "calibration_params.py"
OUT_PATH = REPO_ROOT / "data" / "parameters_v15.csv"

TAG_RE = re.compile(r"^([A-Z][A-Z0-9_]+)\s*=.*?#\s*\[([^\]]+)\]")
ASSIGN_RE = re.compile(r"^([A-Z][A-Z0-9_]+)\s*=")

UNCERTAINTY_BY_STATUS = {
    "validated": "low",
    "backtest": "medium",
    "cross_section": "medium",
    "data": "medium",
    "artifact": "medium",
    "prior": "high",
    "questionable": "high",
}

UNCERTAINTY_BY_TAG = {
    "PWT10": "low",
    "WDI23": "low",
    "WEO25": "medium",
    "IPCC_AR6": "low",
    "DICE16": "medium",
    "SIPRI23": "medium",
    "GCP2023": "medium",
    "BACKTEST": "medium",
    "XSECTION": "medium",
    "PRIOR": "high",
    "ARTIFACT": "medium",
    "UNSPECIFIED": "unspecified",
}

def _source_tags(path: Path) -> Dict[str, str]:
    tags: Dict[str, str] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            m = TAG_RE.match(line.strip())
            if m:
                tags[m.group(1)] = m.group(2)
    return tags


def _assignment_names(path: Path) -> list[str]:
    names: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            m = ASSIGN_RE.match(line.strip())
            if not m:
                continue
            name = m.group(1)
            if name in {"SOURCE_TAG_NOTES", "CALIBRATION_STATUS"}:
                continue
            names.append(name)
    return names


def _is_param_value(value: Any) -> bool:
    scalar = isinstance(value, (int, float, bool, str))
    tuple_num = isinstance(value, tuple) and all(isinstance(x, (int, float)) for x in value)
    return scalar or tuple_num


def main() -> int:
    mod = importlib.import_module("gim.core.calibration_params")
    tags = _source_tags(CAL_PATH)
    status_map: Dict[str, str] = dict(getattr(mod, "CALIBRATION_STATUS", {}))

    names = _assignment_names(CAL_PATH)

    rows = []
    for name in names:
        if not hasattr(mod, name):
            continue
        value = getattr(mod, name)
        if not _is_param_value(value):
            continue
        status = status_map.get(name, "unspecified")
        tag = tags.get(name, "UNSPECIFIED")
        uncertainty = UNCERTAINTY_BY_STATUS.get(status, UNCERTAINTY_BY_TAG.get(tag, "unspecified"))
        if isinstance(value, tuple):
            value_repr = "[" + ", ".join(str(v) for v in value) + "]"
            unit = "vector"
        elif isinstance(value, bool):
            value_repr = str(value).lower()
            unit = "bool"
        elif isinstance(value, int):
            value_repr = str(value)
            unit = "count"
        elif isinstance(value, float):
            value_repr = f"{value:.12g}"
            unit = "dimensionless"
        else:
            value_repr = str(value)
            unit = "text"

        rows.append(
            {
                "parameter": name,
                "value": value_repr,
                "unit": unit,
                "module": "gim.core.calibration_params",
                "source_tag": tag,
                "uncertainty_level": uncertainty,
                "calibration_status": status,
            }
        )

    rows.sort(key=lambda r: r["parameter"])

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "parameter",
                "value",
                "unit",
                "module",
                "source_tag",
                "uncertainty_level",
                "calibration_status",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {OUT_PATH} ({len(rows)} parameters)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
