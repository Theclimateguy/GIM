from __future__ import annotations

import csv
from dataclasses import fields
from pathlib import Path
from typing import Dict, List, Set, Tuple

from gim.core import core

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "docs" / "state_registry.csv"
OUT_PATH = REPO_ROOT / "docs" / "state_registry_coverage.md"

DOMAIN_CLASS_MAP = {
    "agent.economy": core.EconomyState,
    "agent.society": core.SocietyState,
    "agent.climate": core.ClimateSubState,
    "agent.risk": core.RiskState,
    "agent.technology": core.TechnologyState,
    "agent.political": core.PoliticalState,
    "relation": core.RelationState,
    "global": core.GlobalState,
    "institution": core.InstitutionState,
}

EXCLUDE_FIELDS = {
    "agent.economy._gdp_prev",
    "agent.economy._debt_gdp_prev",
    "agent.society._trust_prev",
    "agent.society._tension_prev",
    "agent.climate._emissions_prev",
    "agent.political.last_block_change",
    "global.prices",
    "global.global_reserves",
    "institution.id",
    "institution.name",
    "institution.org_type",
    "institution.mandate",
    "institution.members",
    "institution.base_budget_share",
}


def _expected_variables() -> Set[str]:
    expected: Set[str] = {"world.time"}
    for prefix, cls in DOMAIN_CLASS_MAP.items():
        for f in fields(cls):
            expected.add(f"{prefix}.{f.name}")
    for name in core.RESOURCE_NAMES:
        for f in fields(core.ResourceSubState):
            expected.add(f"agent.resources.{name}.{f.name}")
    return {item for item in expected if item not in EXCLUDE_FIELDS}


def _load_registry_vars(path: Path) -> Set[str]:
    out: Set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out.add(str(row["variable_name"]).strip())
    return out


def _group_missing(items: List[str]) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    for item in items:
        head = item.split(".", 2)[0]
        groups.setdefault(head, []).append(item)
    for key in groups:
        groups[key] = sorted(groups[key])
    return dict(sorted(groups.items()))


def main() -> int:
    expected = _expected_variables()
    actual = _load_registry_vars(REGISTRY_PATH)

    missing = sorted(expected - actual)
    extra = sorted(actual - expected)

    missing_groups = _group_missing(missing)
    extra_groups = _group_missing(extra)

    lines: List[str] = []
    lines.append("# State Registry Coverage")
    lines.append("")
    lines.append(f"- expected variables: `{len(expected)}`")
    lines.append(f"- registry variables: `{len(actual)}`")
    lines.append(f"- missing from registry: `{len(missing)}`")
    lines.append(f"- extra (registry-only): `{len(extra)}`")
    lines.append("")

    lines.append("## Missing")
    if not missing:
        lines.append("- none")
    else:
        for group, values in missing_groups.items():
            lines.append(f"- `{group}`: {len(values)}")
            for value in values:
                lines.append(f"  - `{value}`")
    lines.append("")

    lines.append("## Extra")
    if not extra:
        lines.append("- none")
    else:
        for group, values in extra_groups.items():
            lines.append(f"- `{group}`: {len(values)}")
            for value in values:
                lines.append(f"  - `{value}`")

    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print(f"missing={len(missing)} extra={len(extra)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
