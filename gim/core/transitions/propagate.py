from __future__ import annotations

from collections.abc import Iterable

from ..actions import pop_actions_critical_deltas
from ..climate import pop_climate_critical_deltas
from ..core import clamp01
from ..economy import pop_economy_critical_deltas
from ..geopolitics import pop_geopolitics_critical_deltas
from ..institutions import pop_institution_critical_deltas
from ..social import pop_social_critical_deltas
from .baseline import capture_critical_fields
from .schemas import PropagationDeltas


def build_propagation_snapshot(
    world,
    world_metrics: dict[str, float],
    cards: list[dict],
    *,
    metadata: dict | None = None,
) -> PropagationDeltas:
    return PropagationDeltas(
        world_metrics=dict(world_metrics),
        critical_fields_by_agent=capture_critical_fields(world),
        cards=list(cards),
        metadata=dict(metadata or {}),
    )


def apply_institution_pending_deltas(world) -> dict[str, int]:
    pending = pop_institution_critical_deltas(world)
    applied_agents = 0
    for agent_id, delta in pending.items():
        agent = world.agents.get(agent_id)
        if agent is None:
            continue
        debt_delta = float(delta.get("public_debt", 0.0))
        trust_delta = float(delta.get("trust_gov", 0.0))
        tension_delta = float(delta.get("social_tension", 0.0))
        if debt_delta == 0.0 and trust_delta == 0.0 and tension_delta == 0.0:
            continue
        agent.economy.public_debt = max(0.0, agent.economy.public_debt + debt_delta)
        agent.society.trust_gov = clamp01(agent.society.trust_gov + trust_delta)
        agent.society.social_tension = clamp01(agent.society.social_tension + tension_delta)
        applied_agents += 1
    return {
        "queued_agents": len(pending),
        "applied_agents": applied_agents,
    }


def _agent_scope(agent_ids: Iterable[str] | None) -> set[str] | None:
    if agent_ids is None:
        return None
    return set(agent_ids)


def apply_actions_pending_deltas(
    world,
    *,
    agent_ids: Iterable[str] | None = None,
) -> dict[str, int]:
    pending = pop_actions_critical_deltas(world)
    scope = _agent_scope(agent_ids)
    applied_agents = 0
    deferred: dict[str, dict[str, float]] = {}
    for agent_id, delta in pending.items():
        if scope is not None and agent_id not in scope:
            deferred[agent_id] = delta
            continue
        agent = world.agents.get(agent_id)
        if agent is None:
            continue
        gdp_delta = float(delta.get("gdp", 0.0))
        capital_delta = float(delta.get("capital", 0.0))
        debt_delta = float(delta.get("public_debt", 0.0))
        trust_delta = float(delta.get("trust_gov", 0.0))
        tension_delta = float(delta.get("social_tension", 0.0))
        if (
            gdp_delta == 0.0
            and capital_delta == 0.0
            and debt_delta == 0.0
            and trust_delta == 0.0
            and tension_delta == 0.0
        ):
            continue
        agent.economy.gdp = max(0.0, agent.economy.gdp + gdp_delta)
        agent.economy.capital = max(0.0, agent.economy.capital + capital_delta)
        agent.economy.public_debt = max(0.0, agent.economy.public_debt + debt_delta)
        agent.society.trust_gov = clamp01(agent.society.trust_gov + trust_delta)
        agent.society.social_tension = clamp01(agent.society.social_tension + tension_delta)
        applied_agents += 1
    if deferred:
        setattr(world.global_state, "_actions_critical_pending", deferred)
    return {
        "queued_agents": len(pending),
        "applied_agents": applied_agents,
    }


def apply_geopolitics_pending_deltas(world) -> dict[str, int]:
    pending = pop_geopolitics_critical_deltas(world)
    applied_agents = 0
    for agent_id, delta in pending.items():
        agent = world.agents.get(agent_id)
        if agent is None:
            continue
        gdp_delta = float(delta.get("gdp", 0.0))
        capital_delta = float(delta.get("capital", 0.0))
        trust_delta = float(delta.get("trust_gov", 0.0))
        tension_delta = float(delta.get("social_tension", 0.0))
        if gdp_delta == 0.0 and capital_delta == 0.0 and trust_delta == 0.0 and tension_delta == 0.0:
            continue
        agent.economy.gdp = max(0.0, agent.economy.gdp + gdp_delta)
        agent.economy.capital = max(0.0, agent.economy.capital + capital_delta)
        agent.society.trust_gov = clamp01(agent.society.trust_gov + trust_delta)
        agent.society.social_tension = clamp01(agent.society.social_tension + tension_delta)
        applied_agents += 1
    return {
        "queued_agents": len(pending),
        "applied_agents": applied_agents,
    }


def apply_economy_pending_deltas(
    world,
    *,
    agent_ids: Iterable[str] | None = None,
) -> dict[str, int]:
    pending = pop_economy_critical_deltas(world)
    scope = _agent_scope(agent_ids)
    applied_agents = 0
    deferred: dict[str, dict[str, float]] = {}
    for agent_id, delta in pending.items():
        if scope is not None and agent_id not in scope:
            deferred[agent_id] = delta
            continue
        agent = world.agents.get(agent_id)
        if agent is None:
            continue
        gdp_delta = float(delta.get("gdp", 0.0))
        capital_delta = float(delta.get("capital", 0.0))
        debt_delta = float(delta.get("public_debt", 0.0))
        if gdp_delta == 0.0 and capital_delta == 0.0 and debt_delta == 0.0:
            continue
        agent.economy.gdp = max(0.0, agent.economy.gdp + gdp_delta)
        agent.economy.capital = max(0.0, agent.economy.capital + capital_delta)
        agent.economy.public_debt = max(0.0, agent.economy.public_debt + debt_delta)
        applied_agents += 1
    if deferred:
        setattr(world.global_state, "_economy_critical_pending", deferred)
    return {
        "queued_agents": len(pending),
        "applied_agents": applied_agents,
    }


def apply_climate_pending_deltas(world) -> dict[str, int]:
    pending = pop_climate_critical_deltas(world)
    applied_agents = 0
    for agent_id, delta in pending.items():
        agent = world.agents.get(agent_id)
        if agent is None:
            continue
        capital_delta = float(delta.get("capital", 0.0))
        trust_delta = float(delta.get("trust_gov", 0.0))
        tension_delta = float(delta.get("social_tension", 0.0))
        if capital_delta == 0.0 and trust_delta == 0.0 and tension_delta == 0.0:
            continue
        agent.economy.capital = max(0.0, agent.economy.capital + capital_delta)
        agent.society.trust_gov = clamp01(agent.society.trust_gov + trust_delta)
        agent.society.social_tension = clamp01(agent.society.social_tension + tension_delta)
        applied_agents += 1
    return {
        "queued_agents": len(pending),
        "applied_agents": applied_agents,
    }


def apply_social_pending_deltas(world) -> dict[str, int]:
    pending = pop_social_critical_deltas(world)
    applied_agents = 0
    for agent_id, delta in pending.items():
        agent = world.agents.get(agent_id)
        if agent is None:
            continue
        gdp_delta = float(delta.get("gdp", 0.0))
        capital_delta = float(delta.get("capital", 0.0))
        debt_delta = float(delta.get("public_debt", 0.0))
        trust_delta = float(delta.get("trust_gov", 0.0))
        tension_delta = float(delta.get("social_tension", 0.0))
        if (
            gdp_delta == 0.0
            and capital_delta == 0.0
            and debt_delta == 0.0
            and trust_delta == 0.0
            and tension_delta == 0.0
        ):
            continue
        agent.economy.gdp = max(0.0, agent.economy.gdp + gdp_delta)
        agent.economy.capital = max(0.0, agent.economy.capital + capital_delta)
        agent.economy.public_debt = max(0.0, agent.economy.public_debt + debt_delta)
        agent.society.trust_gov = clamp01(agent.society.trust_gov + trust_delta)
        agent.society.social_tension = clamp01(agent.society.social_tension + tension_delta)
        applied_agents += 1
    return {
        "queued_agents": len(pending),
        "applied_agents": applied_agents,
    }


__all__ = [
    "apply_actions_pending_deltas",
    "apply_climate_pending_deltas",
    "apply_economy_pending_deltas",
    "apply_geopolitics_pending_deltas",
    "apply_institution_pending_deltas",
    "apply_social_pending_deltas",
    "build_propagation_snapshot",
]
