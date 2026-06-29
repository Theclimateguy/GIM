"""Light world access for the v2 engine (no v1 world cache / exploratory stack)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

from gim.runtime import default_state_csv, load_world


@lru_cache(maxsize=8)
def _cached_world(state_csv: str, max_agents: int):
    return load_world(state_csv=state_csv, max_agents=max_agents)


def load_world_for(state_csv: Optional[str], max_agents: int = 57) -> Any:
    """Cached world for read-only menu/actor resolution (e.g. ``/ontology``)."""
    return _cached_world(state_csv or default_state_csv(), int(max_agents))


__all__ = ["load_world_for"]
