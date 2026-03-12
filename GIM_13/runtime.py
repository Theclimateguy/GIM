import os
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
LEGACY_CORE = REPO_ROOT / "legacy" / "GIM_11_1"

legacy_core_str = str(LEGACY_CORE)
if LEGACY_CORE.exists() and legacy_core_str not in sys.path:
    sys.path.insert(0, legacy_core_str)

from gim_11_1.core import AgentState, RelationState, WorldState  # noqa: E402
from gim_11_1.world_factory import make_world_from_csv  # noqa: E402


def default_state_csv() -> str:
    explicit = os.environ.get("GIM13_STATE_CSV")
    if explicit:
        return explicit
    preferred = REPO_ROOT / "GIM_12" / "agent_states_gim13.csv"
    if os.environ.get("GIM13_USE_EXPERIMENTAL_STATE") == "1" and preferred.exists() and preferred.stat().st_size > 0:
        return str(preferred)
    return str(REPO_ROOT / "GIM_12" / "agent_states.csv")


def load_world(state_csv: str | None = None, max_agents: int | None = None) -> WorldState:
    return make_world_from_csv(state_csv or default_state_csv(), max_agents=max_agents)


__all__ = [
    "AgentState",
    "RelationState",
    "WorldState",
    "REPO_ROOT",
    "default_state_csv",
    "load_world",
]
