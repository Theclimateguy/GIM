from __future__ import annotations

from collections.abc import Iterable

from ..actions import pop_actions_critical_deltas
from ..climate import pop_climate_critical_deltas
from ..critical_pending import add_transition_delta, clear_transition_pending, get_transition_pending
from ..economy import pop_economy_critical_deltas
from ..geopolitics import pop_geopolitics_critical_deltas
from ..institutions import pop_institution_critical_deltas
from ..social import pop_social_critical_deltas
from .baseline import capture_critical_fields
from .schemas import CriticalFieldSnapshot, PropagationDeltas


def build_propagation_snapshot(
    world,
    world_metrics: dict[str, float],
    cards: list[dict],
    *,
    metadata: dict | None = None,
) -> PropagationDeltas:
    return PropagationDeltas(
        world_metrics=dict(world_metrics),
        critical_fields_by_agent=capture_effective_critical_fields(world),
        cards=list(cards),
        metadata=dict(metadata or {}),
    )


def reset_transition_pending(world) -> None:
    clear_transition_pending(world)


def capture_effective_critical_fields(world) -> dict[str, CriticalFieldSnapshot]:
    base = capture_critical_fields(world)
    pending = get_transition_pending(world)
    snapshots: dict[str, CriticalFieldSnapshot] = {}
    for agent_id, state in base.items():
        delta = pending.get(agent_id, {})
        snapshots[agent_id] = CriticalFieldSnapshot(
            gdp=state.gdp + float(delta.get("gdp", 0.0)),
            capital=state.capital + float(delta.get("capital", 0.0)),
            public_debt=state.public_debt + float(delta.get("public_debt", 0.0)),
            trust_gov=state.trust_gov + float(delta.get("trust_gov", 0.0)),
            social_tension=state.social_tension + float(delta.get("social_tension", 0.0)),
        )
    return snapshots


def _agent_scope(agent_ids: Iterable[str] | None) -> set[str] | None:
    if agent_ids is None:
        return None
    return set(agent_ids)


def apply_institution_pending_deltas(world) -> dict[str, int]:
    pending = pop_institution_critical_deltas(world)
    applied_agents = 0
    for agent_id, delta in pending.items():
        debt_delta = float(delta.get("public_debt", 0.0))
        trust_delta = float(delta.get("trust_gov", 0.0))
        tension_delta = float(delta.get("social_tension", 0.0))
        if debt_delta == 0.0 and trust_delta == 0.0 and tension_delta == 0.0:
            continue
        add_transition_delta(
            world,
            agent_id,
            public_debt=debt_delta,
            trust_gov=trust_delta,
            social_tension=tension_delta,
        )
        applied_agents += 1
    return {
        "queued_agents": len(pending),
        "applied_agents": applied_agents,
    }


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
        add_transition_delta(
            world,
            agent_id,
            gdp=gdp_delta,
            capital=capital_delta,
            public_debt=debt_delta,
            trust_gov=trust_delta,
            social_tension=tension_delta,
        )
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
        gdp_delta = float(delta.get("gdp", 0.0))
        capital_delta = float(delta.get("capital", 0.0))
        trust_delta = float(delta.get("trust_gov", 0.0))
        tension_delta = float(delta.get("social_tension", 0.0))
        if gdp_delta == 0.0 and capital_delta == 0.0 and trust_delta == 0.0 and tension_delta == 0.0:
            continue
        add_transition_delta(
            world,
            agent_id,
            gdp=gdp_delta,
            capital=capital_delta,
            trust_gov=trust_delta,
            social_tension=tension_delta,
        )
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
        gdp_delta = float(delta.get("gdp", 0.0))
        capital_delta = float(delta.get("capital", 0.0))
        debt_delta = float(delta.get("public_debt", 0.0))
        if gdp_delta == 0.0 and capital_delta == 0.0 and debt_delta == 0.0:
            continue
        add_transition_delta(
            world,
            agent_id,
            gdp=gdp_delta,
            capital=capital_delta,
            public_debt=debt_delta,
        )
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
        capital_delta = float(delta.get("capital", 0.0))
        trust_delta = float(delta.get("trust_gov", 0.0))
        tension_delta = float(delta.get("social_tension", 0.0))
        if capital_delta == 0.0 and trust_delta == 0.0 and tension_delta == 0.0:
            continue
        add_transition_delta(
            world,
            agent_id,
            capital=capital_delta,
            trust_gov=trust_delta,
            social_tension=tension_delta,
        )
        applied_agents += 1
    return {
        "queued_agents": len(pending),
        "applied_agents": applied_agents,
    }


def apply_social_pending_deltas(world) -> dict[str, int]:
    pending = pop_social_critical_deltas(world)
    applied_agents = 0
    for agent_id, delta in pending.items():
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
        add_transition_delta(
            world,
            agent_id,
            gdp=gdp_delta,
            capital=capital_delta,
            public_debt=debt_delta,
            trust_gov=trust_delta,
            social_tension=tension_delta,
        )
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
    "capture_effective_critical_fields",
    "reset_transition_pending",
]
