import os
from pathlib import Path

from .core.core import AgentState, RelationState, WorldState
from .core.world_factory import make_world_from_csv
from .paths import DEFAULT_STATE_CSV


REPO_ROOT = Path(__file__).resolve().parent.parent
MISC_ROOT = REPO_ROOT / "misc"


def default_state_csv() -> str:
    for env_name in ("GIM14_STATE_CSV", "GIM_STATE_CSV", "GIM13_STATE_CSV"):
        explicit = os.environ.get(env_name)
        if explicit:
            return explicit

    preferred = MISC_ROOT / "data" / "agent_states_operational.csv"
    if preferred.exists() and preferred.stat().st_size > 0:
        return str(preferred)
    return str(DEFAULT_STATE_CSV)


def load_world(state_csv: str | None = None, max_agents: int | None = None) -> WorldState:
    return make_world_from_csv(state_csv or default_state_csv(), max_agents=max_agents)


__all__ = [
    "AgentState",
    "RelationState",
    "WorldState",
    "MISC_ROOT",
    "REPO_ROOT",
    "default_state_csv",
    "load_world",
]
