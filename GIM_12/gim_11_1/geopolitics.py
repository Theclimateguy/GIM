from typing import Any, Dict, Optional, Tuple
import random

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
    target_pressure: Dict[str, Dict[str, int]] = {}
    entries: list[tuple[str, str, str]] = []

    for actor_id, actor in world.agents.items():
        for target_id, sanction_type in actor.active_sanctions.items():
            if target_id not in world.agents or target_id == actor_id:
                continue
            entries.append((actor_id, target_id, sanction_type))
            bucket = target_pressure.setdefault(target_id, {"mild": 0, "strong": 0})
            if sanction_type == "strong":
                bucket["strong"] += 1
            elif sanction_type == "mild":
                bucket["mild"] += 1

    for actor_id, target_id, sanction_type in entries:
        actor = world.agents[actor_id]
        relation = world.relations.get(actor_id, {}).get(target_id)
        if relation is None:
            continue

        if sanction_type == "mild":
            relation.trade_intensity *= 0.85
            relation.trust *= 0.92
            relation.trade_barrier = min(1.0, relation.trade_barrier + 0.05)
        elif sanction_type == "strong":
            relation.trade_intensity *= 0.65
            relation.trust *= 0.85
            relation.trade_barrier = min(1.0, relation.trade_barrier + 0.15)
            actor.economy.gdp *= 0.995

    for target_id, counts in target_pressure.items():
        target = world.agents.get(target_id)
        if target is None:
            continue

        mild = counts.get("mild", 0)
        strong = counts.get("strong", 0)
        if mild <= 0 and strong <= 0:
            continue

        mild_factor = mild**0.5
        strong_factor = strong**0.5

        gdp_penalty = min(0.12, 0.01 * mild_factor + 0.03 * strong_factor)
        target.economy.gdp *= max(0.0, 1.0 - gdp_penalty)

        scale = min(0.12, 0.02 * mild_factor + 0.06 * strong_factor)
        autocracy_bias = min(0.04, 0.01 * mild_factor + 0.02 * strong_factor)
        tension_increase = min(0.08, 0.015 * mild_factor + 0.05 * strong_factor)

        _apply_sanction_social_reaction(
            target=target,
            scale=scale,
            autocracy_bias=autocracy_bias,
            tension_increase=tension_increase,
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


def _resource_index(agent: AgentState) -> float:
    energy = agent.resources.get("energy")
    food = agent.resources.get("food")
    metals = agent.resources.get("metals")
    return float(
        1.0 * (energy.own_reserve if energy else 0.0)
        + 0.6 * (food.own_reserve if food else 0.0)
        + 0.4 * (metals.own_reserve if metals else 0.0)
    )


def _ensure_war_start(rel: RelationState, agent: AgentState) -> None:
    if rel.war_start_gdp > 0.0:
        return
    rel.war_start_gdp = max(agent.economy.gdp, 1e-6)
    rel.war_start_pop = max(agent.economy.population, 1.0)
    rel.war_start_resource = max(_resource_index(agent), 1e-6)


def _resource_stress(agent: AgentState) -> float:
    reserves = {}
    for name, res in agent.resources.items():
        reserves[name] = res.own_reserve / max(res.production, 1e-6)

    def _stress(years: float, threshold: float) -> float:
        return clamp01(1.0 - years / threshold)

    energy_stress = _stress(reserves.get("energy", 10.0), 5.0)
    food_stress = _stress(reserves.get("food", 10.0), 3.0)
    metals_stress = _stress(reserves.get("metals", 10.0), 5.0)
    return clamp01(0.5 * energy_stress + 0.3 * food_stress + 0.2 * metals_stress)


def _auto_security_action(world: WorldState, actor_id: str) -> Optional[Tuple[str, str]]:
    actor = world.agents.get(actor_id)
    if actor is None:
        return None

    best_target = None
    best_score = 0.0
    for target_id, rel in world.relations.get(actor_id, {}).items():
        if target_id == actor_id:
            continue
        score = rel.conflict_level + 0.5 * (1.0 - rel.trust)
        if score > best_score:
            best_score = score
            best_target = target_id

    if best_target is None:
        return None

    rel = world.relations.get(actor_id, {}).get(best_target)
    if rel is None:
        return None

    resource_stress = _resource_stress(actor)
    tension = clamp01(actor.society.social_tension)
    fragility = 1.0 - clamp01(actor.risk.regime_stability)

    trigger = best_score * (0.55 + 0.45 * resource_stress)
    trigger *= (0.55 + 0.45 * tension)
    trigger *= (0.6 + 0.4 * fragility)

    if trigger < 0.45 or rel.conflict_level < 0.45:
        return None

    roll = random.random()
    if trigger > 0.8 and roll < 0.2 * trigger:
        return "border_incident", best_target
    if trigger > 0.65 and roll < 0.12 * trigger:
        return "arms_buildup", best_target
    if roll < 0.05 * trigger:
        return "military_exercise", best_target
    return None


def apply_security_actions(world: WorldState, actions: Dict[str, Action]) -> None:
    for action in actions.values():
        sec = action.foreign_policy.security_actions
        if sec.type == "none":
            auto = _auto_security_action(world, action.agent_id)
            if auto is None:
                continue
            sec.type, sec.target = auto

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

            rel_at.at_war = True
            rel_ta.at_war = True
            _ensure_war_start(rel_at, actor)
            _ensure_war_start(rel_ta, target)


def update_active_conflicts(world: WorldState) -> None:
    for actor_id, rels in world.relations.items():
        for target_id, rel_at in rels.items():
            if actor_id >= target_id:
                continue
            relation_pair = _get_bilateral_relation_pair(world, actor_id, target_id)
            if relation_pair is None:
                continue
            rel_at, rel_ta = relation_pair
            if not (rel_at.at_war or rel_ta.at_war):
                continue

            actor = world.agents.get(actor_id)
            target = world.agents.get(target_id)
            if actor is None or target is None:
                continue

            rel_at.at_war = True
            rel_ta.at_war = True
            rel_at.war_years += 1
            rel_ta.war_years += 1

            _ensure_war_start(rel_at, actor)
            _ensure_war_start(rel_ta, target)

            mil_actor = max(actor.technology.military_power, 1e-6)
            mil_target = max(target.technology.military_power, 1e-6)
            total_power = mil_actor + mil_target
            share_actor = mil_actor / total_power
            share_target = mil_target / total_power

            base_capital_loss = 0.04
            base_gdp_loss = 0.03

            cap_loss_actor = base_capital_loss * (0.8 + 0.4 * (1.0 - share_actor))
            cap_loss_target = base_capital_loss * (0.8 + 0.4 * (1.0 - share_target))
            gdp_loss_actor = base_gdp_loss * (0.8 + 0.4 * (1.0 - share_actor))
            gdp_loss_target = base_gdp_loss * (0.8 + 0.4 * (1.0 - share_target))

            actor.economy.capital *= max(0.0, 1.0 - cap_loss_actor)
            target.economy.capital *= max(0.0, 1.0 - cap_loss_target)
            actor.economy.gdp *= max(0.0, 1.0 - gdp_loss_actor)
            target.economy.gdp *= max(0.0, 1.0 - gdp_loss_target)

            rel_at.trade_intensity *= 0.92
            rel_ta.trade_intensity *= 0.92

            def _exhausted(rel: RelationState, side: AgentState) -> bool:
                gdp_ok = side.economy.gdp >= 0.7 * rel.war_start_gdp
                pop_ok = side.economy.population >= 0.9 * rel.war_start_pop
                res_ok = _resource_index(side) >= 0.5 * rel.war_start_resource
                return not (gdp_ok and pop_ok and res_ok)

            actor_exhausted = _exhausted(rel_at, actor)
            target_exhausted = _exhausted(rel_ta, target)

            if not (actor_exhausted or target_exhausted):
                continue

            rel_at.at_war = False
            rel_ta.at_war = False
            rel_at.war_years = 0
            rel_ta.war_years = 0
            rel_at.war_start_gdp = 0.0
            rel_ta.war_start_gdp = 0.0
            rel_at.war_start_pop = 0.0
            rel_ta.war_start_pop = 0.0
            rel_at.war_start_resource = 0.0
            rel_ta.war_start_resource = 0.0

            if actor_exhausted and target_exhausted:
                for side in (actor, target):
                    side.technology.military_power *= 0.9
                    side.society.social_tension = min(1.0, side.society.social_tension + 0.08)
                    side.society.trust_gov = max(0.0, side.society.trust_gov - 0.05)
                rel_at.conflict_level = 0.45
                rel_ta.conflict_level = 0.45
                rel_at.trust *= 0.9
                rel_ta.trust *= 0.9
                continue

            winner = target if actor_exhausted else actor
            loser = actor if actor_exhausted else target

            winner.society.trust_gov = clamp01(winner.society.trust_gov + 0.03)
            winner.society.social_tension = max(0.0, winner.society.social_tension - 0.03)
            loser.society.trust_gov = max(0.0, loser.society.trust_gov - 0.08)
            loser.society.social_tension = min(1.0, loser.society.social_tension + 0.10)
            loser.technology.military_power *= 0.85

            rel_at.conflict_level = 0.5
            rel_ta.conflict_level = 0.5
            rel_at.trust *= 0.85
            rel_ta.trust *= 0.85
