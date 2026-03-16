from __future__ import annotations

from .schemas import BaselineState, CriticalFieldSnapshot


def capture_critical_fields(world) -> dict[str, CriticalFieldSnapshot]:
    snapshots: dict[str, CriticalFieldSnapshot] = {}
    for agent_id, agent in world.agents.items():
        snapshots[agent_id] = CriticalFieldSnapshot(
            gdp=float(agent.economy.gdp),
            capital=float(agent.economy.capital),
            public_debt=float(agent.economy.public_debt),
            trust_gov=float(agent.society.trust_gov),
            social_tension=float(agent.society.social_tension),
        )
    return snapshots


def build_baseline_state(world, world_metrics: dict[str, float]) -> BaselineState:
    return BaselineState(
        world_metrics=dict(world_metrics),
        critical_fields_by_agent=capture_critical_fields(world),
    )


__all__ = [
    "build_baseline_state",
    "capture_critical_fields",
]
