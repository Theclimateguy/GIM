from typing import Any, Dict, Optional, Tuple

from .core import Action, AgentState, RelationState, WorldState, clamp01


def _coerce_agent_id(value: Any) -> Optional[str]:
    if isinstance(value, str):
        candidate = value.strip()
        return candidate or None
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item.strip()
    return None


def _apply_sanction_social_reaction(
    target: AgentState,
    scale: float,
    autocracy_bias: float,
    tension_increase: float,
) -> None:
    culture = target.culture
    pdi = culture.pdi / 100.0
    self_expression = culture.survival_self_expression / 10.0

    rally = scale * pdi
    blame = scale * (1.0 - pdi) * (0.5 + self_expression)

    if culture.regime_type == "Autocracy":
        trust_delta = rally - autocracy_bias
    else:
        trust_delta = -blame

    target.society.trust_gov = clamp01(target.society.trust_gov + trust_delta)
    target.society.social_tension = clamp01(target.society.social_tension + tension_increase)


def apply_sanctions_effects(world: WorldState) -> None:
    for agent_id, agent in world.agents.items():
        for target_id, sanction_type in agent.active_sanctions.items():
            if target_id not in world.agents:
                continue

            target = world.agents[target_id]
            relation = world.relations[agent_id][target_id]

            if sanction_type == "mild":
                relation.trade_intensity *= 0.8
                relation.trust *= 0.9
                target.economy.gdp *= 0.98
                _apply_sanction_social_reaction(
                    target=target,
                    scale=0.03,
                    autocracy_bias=0.01,
                    tension_increase=0.02,
                )
            elif sanction_type == "strong":
                relation.trade_intensity *= 0.5
                relation.trust *= 0.7
                target.economy.gdp *= 0.95
                agent.economy.gdp *= 0.99
                _apply_sanction_social_reaction(
                    target=target,
                    scale=0.08,
                    autocracy_bias=0.02,
                    tension_increase=0.06,
                )


def _get_bilateral_relation_pair(
    world: WorldState,
    actor_id: str,
    target_id: str,
) -> Optional[Tuple[RelationState, RelationState]]:
    actor_to_target = world.relations.get(actor_id, {}).get(target_id)
    target_to_actor = world.relations.get(target_id, {}).get(actor_id)
    if actor_to_target is None or target_to_actor is None:
        return None
    return actor_to_target, target_to_actor


def apply_security_actions(world: WorldState, actions: Dict[str, Action]) -> None:
    for action in actions.values():
        sec = action.foreign_policy.security_actions
        if sec.type == "none":
            continue

        actor_id = action.agent_id
        target_id = _coerce_agent_id(sec.target)
        if target_id is None:
            continue
        if target_id not in world.agents or actor_id not in world.agents:
            continue

        actor = world.agents[actor_id]
        target = world.agents[target_id]

        relation_pair = _get_bilateral_relation_pair(world, actor_id, target_id)
        if relation_pair is None:
            continue
        rel_at, rel_ta = relation_pair
        avg_conflict = 0.5 * (rel_at.conflict_level + rel_ta.conflict_level)

        # Escalation gate: avoid immediate catastrophic conflicts from single LLM decisions.
        if sec.type == "conflict" and (avg_conflict < 0.55 or rel_at.trust > 0.25):
            sec.type = "border_incident"
        elif sec.type == "border_incident" and avg_conflict < 0.30:
            sec.type = "military_exercise"

        if sec.type == "military_exercise":
            rel_at.conflict_level = min(1.0, rel_at.conflict_level + 0.05)
            rel_ta.conflict_level = min(1.0, rel_ta.conflict_level + 0.05)
            rel_at.trust *= 0.98
            rel_ta.trust *= 0.98

        elif sec.type == "arms_buildup":
            actor.technology.military_power *= 1.05
            rel_at.conflict_level = min(1.0, rel_at.conflict_level + 0.08)
            rel_ta.conflict_level = min(1.0, rel_ta.conflict_level + 0.08)

        elif sec.type == "border_incident":
            rel_at.conflict_level = min(1.0, rel_at.conflict_level + 0.20)
            rel_ta.conflict_level = min(1.0, rel_ta.conflict_level + 0.20)

            for side in (actor, target):
                side.economy.gdp *= 0.99
                side.society.social_tension = min(1.0, side.society.social_tension + 0.05)
                side.society.trust_gov = max(0.0, side.society.trust_gov - 0.03)

        elif sec.type == "conflict":
            mil_actor = actor.technology.military_power
            mil_target = target.technology.military_power
            total_power = max(mil_actor + mil_target, 1e-6)
            share_actor = mil_actor / total_power
            share_target = mil_target / total_power

            base_capital_loss = 0.15
            base_gdp_loss = 0.10

            cap_loss_actor = base_capital_loss * (0.7 + 0.6 * (1.0 - share_actor))
            cap_loss_target = base_capital_loss * (0.7 + 0.6 * (1.0 - share_target))
            gdp_loss_actor = base_gdp_loss * (0.7 + 0.6 * (1.0 - share_actor))
            gdp_loss_target = base_gdp_loss * (0.7 + 0.6 * (1.0 - share_target))

            actor.economy.capital *= max(0.0, 1.0 - cap_loss_actor)
            target.economy.capital *= max(0.0, 1.0 - cap_loss_target)
            actor.economy.gdp *= max(0.0, 1.0 - gdp_loss_actor)
            target.economy.gdp *= max(0.0, 1.0 - gdp_loss_target)

            for side in (actor, target):
                side.society.social_tension = min(1.0, side.society.social_tension + 0.15)
                side.society.trust_gov = max(0.0, side.society.trust_gov - 0.10)

            rel_at.conflict_level = min(1.0, rel_at.conflict_level + 0.4)
            rel_ta.conflict_level = min(1.0, rel_ta.conflict_level + 0.4)
            rel_at.trust *= 0.8
            rel_ta.trust *= 0.8
