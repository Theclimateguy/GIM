import os
from pathlib import Path

from .core.core import AgentState, RelationState, WorldState
from .core.world_factory import make_world_from_csv
from .paths import DEFAULT_STATE_CSV, OPERATIONAL_STATE_CSV


REPO_ROOT = Path(__file__).resolve().parent.parent
MISC_ROOT = REPO_ROOT / "misc"
DEFAULT_STATE_YEAR = 2023


def default_state_year() -> int:
    for env_name in (
        "GIM14_STATE_YEAR",
        "GIM_STATE_YEAR",
        "GIM13_STATE_YEAR",
        "STATE_YEAR",
        "SIM_START_YEAR",
    ):
        explicit = os.environ.get(env_name)
        if not explicit:
            continue
        try:
            return int(explicit)
        except ValueError:
            continue
    return DEFAULT_STATE_YEAR


def default_state_csv() -> str:
    for env_name in ("GIM14_STATE_CSV", "GIM_STATE_CSV", "GIM13_STATE_CSV"):
        explicit = os.environ.get(env_name)
        if explicit:
            return explicit

    preferred = OPERATIONAL_STATE_CSV
    if preferred.exists() and preferred.stat().st_size > 0:
        return str(preferred)
    return str(DEFAULT_STATE_CSV)


def load_world(
    state_csv: str | None = None,
    max_agents: int | None = None,
    state_year: int | None = None,
) -> WorldState:
    resolved_state_year = default_state_year() if state_year is None else int(state_year)
    return make_world_from_csv(
        state_csv or default_state_csv(),
        max_agents=max_agents,
        base_year=resolved_state_year,
    )


__all__ = [
    "AgentState",
    "RelationState",
    "WorldState",
    "MISC_ROOT",
    "REPO_ROOT",
    "default_state_csv",
    "default_state_year",
    "load_world",
]
