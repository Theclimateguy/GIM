from typing import Dict, Iterable

from .core import (
    Action,
    AgentState,
    TradeRestrictionLevel,
    WorldState,
    clamp01,
    effective_trade_intensity,
)
from .metrics import compute_debt_stress, compute_protest_risk, compute_reserve_years


def update_political_state(agent: AgentState, world: WorldState) -> None:
    del world
    trust = clamp01(agent.society.trust_gov)
    tension = clamp01(agent.society.social_tension)
    gini = clamp01(agent.society.inequality_gini / 100.0)

    protest_risk = clamp01(compute_protest_risk(agent))
    debt_stress = clamp01(compute_debt_stress(agent) / 3.0)

    legitimacy = clamp01(0.6 * trust + 0.4 * (1.0 - tension))
    protest_pressure = clamp01(0.5 * protest_risk + 0.5 * tension)

    reserves = compute_reserve_years(agent)
    energy_years = reserves.get("energy", 10.0)
    food_years = reserves.get("food", 10.0)
    metals_years = reserves.get("metals", 10.0)

    def _stress(years: float, threshold: float) -> float:
        return clamp01(1.0 - years / threshold)

    resource_stress = clamp01(
        0.5 * _stress(energy_years, 5.0)
        + 0.3 * _stress(food_years, 3.0)
        + 0.2 * _stress(metals_years, 5.0)
    )

    hawkishness = clamp01(
        0.3 * agent.risk.conflict_proneness
        + 0.25 * (1.0 - trust)
        + 0.25 * (1.0 - agent.risk.regime_stability)
        + 0.20 * resource_stress
    )
    protectionism = clamp01(
        0.4 * agent.economy.unemployment + 0.3 * gini + 0.3 * (1.0 - trust)
    )
    coalition_openness = clamp01(0.6 * trust + 0.4 * (1.0 - tension))
    sanction_propensity = clamp01(0.6 * hawkishness + 0.4 * (1.0 - coalition_openness))

    policy_space = clamp01(
        0.5 * legitimacy + 0.3 * (1.0 - protest_pressure) + 0.2 * (1.0 - debt_stress)
    )

    agent.political.legitimacy = legitimacy
    agent.political.protest_pressure = protest_pressure
    agent.political.hawkishness = hawkishness
    agent.political.protectionism = protectionism
    agent.political.coalition_openness = coalition_openness
    agent.political.sanction_propensity = sanction_propensity
    agent.political.policy_space = policy_space


def update_political_states(world: WorldState) -> None:
    for agent in world.agents.values():
        update_political_state(agent, world)


def apply_political_constraints(action: Action, agent: AgentState) -> Action:
    dom = action.domestic_policy
    pol = agent.political

    scale = 0.4 + 0.6 * clamp01(pol.policy_space)

    if dom.tax_fuel_change > 0:
        dom.tax_fuel_change *= max(0.2, 1.0 - 0.7 * pol.protest_pressure)
    dom.tax_fuel_change *= scale
    dom.social_spending_change *= scale
    dom.military_spending_change *= scale
    dom.rd_investment_change *= scale

    fp = action.foreign_policy

    if pol.sanction_propensity < 0.2:
        fp.sanctions_actions = []
    elif pol.sanction_propensity < 0.4:
        for sanction in fp.sanctions_actions:
            if sanction.type == "strong":
                sanction.type = "mild"

    if pol.protectionism < 0.2:
        fp.trade_restrictions = []
    elif pol.protectionism < 0.4:
        for restriction in fp.trade_restrictions:
            if restriction.level == "hard":
                restriction.level = "soft"

    if pol.protest_pressure > 0.7 and pol.legitimacy < 0.4:
        fp.security_actions.type = "none"
        fp.security_actions.target = None

    return action


def _intent_map_sanctions(action: Action | None) -> Dict[str, str]:
    if action is None:
        return {}
    intents: Dict[str, str] = {}
    for sanction in action.foreign_policy.sanctions_actions:
        target = (sanction.target or "").strip()
        if not target:
            continue
        current = intents.get(target, "none")
        if sanction.type == "strong" or current == "strong":
            intents[target] = "strong"
        elif sanction.type == "mild" or current == "mild":
            intents[target] = "mild"
    return intents


def _intent_map_restrictions(action: Action | None) -> Dict[str, TradeRestrictionLevel]:
    if action is None:
        return {}
    intents: Dict[str, TradeRestrictionLevel] = {}
    for restriction in action.foreign_policy.trade_restrictions:
        target = (restriction.target or "").strip()
        if not target:
            continue
        current = intents.get(target, "none")
        if restriction.level == "hard" or current == "hard":
            intents[target] = "hard"
        elif restriction.level == "soft" or current == "soft":
            intents[target] = "soft"
    return intents


def _sanction_support(actor: AgentState, target: AgentState, relation, intent_type: str) -> float:
    base = (
        0.4 * actor.political.sanction_propensity
        + 0.3 * relation.conflict_level
        + 0.3 * (1.0 - relation.trust)
    )
    if intent_type == "strong":
        base += 0.10
    elif intent_type == "mild":
        base += 0.05

    if actor.alliance_block != "NonAligned" and actor.alliance_block == target.alliance_block:
        base *= 0.6
    elif actor.alliance_block != target.alliance_block:
        base += 0.05

    return clamp01(base)


def _desired_sanction_type(support: float) -> str:
    if support < 0.35:
        return "none"
    if support < 0.65:
        return "mild"
    return "strong"


def resolve_sanctions(world: WorldState, actions: Dict[str, Action]) -> None:
    min_duration = 2
    severity = {"none": 0, "mild": 1, "strong": 2}
    for actor_id, actor in world.agents.items():
        intents = _intent_map_sanctions(actions.get(actor_id))
        new_active: Dict[str, str] = {}
        new_years: Dict[str, int] = {}

        targets = set(intents.keys()) | set(actor.active_sanctions.keys())
        for target_id in targets:
            if target_id == actor_id:
                continue
            if target_id not in world.agents:
                continue

            intent_type = intents.get(target_id, "none")
            existing_type = actor.active_sanctions.get(target_id)
            existing_years = actor.sanction_years.get(target_id, 0)

            if intent_type != "none":
                relation = world.relations.get(actor_id, {}).get(target_id)
                target = world.agents.get(target_id)
                if relation is None or target is None:
                    continue
                support = _sanction_support(actor, target, relation, intent_type)
                desired = _desired_sanction_type(support) if support >= 0.35 else "none"
                if desired != "none":
                    if intent_type != "strong" and desired == "strong":
                        desired = "mild"
                    if severity[desired] < severity[intent_type]:
                        desired = intent_type
                if desired != "none":
                    new_active[target_id] = desired
                    new_years[target_id] = max(existing_years, min_duration)
                    continue

            if existing_type and existing_years > 0:
                new_active[target_id] = existing_type
                new_years[target_id] = existing_years - 1

        actor.active_sanctions = new_active
        actor.sanction_years = new_years


def update_trade_barriers(world: WorldState, actions: Dict[str, Action]) -> None:
    for actor_id, rels in world.relations.items():
        actor = world.agents.get(actor_id)
        if actor is None:
            continue
        intents = _intent_map_restrictions(actions.get(actor_id))

        for target_id, relation in rels.items():
            target = world.agents.get(target_id)
            if target is None:
                continue

            intent_level = intents.get(target_id, "none")
            intent_boost = {"none": 0.0, "soft": 0.15, "hard": 0.35}.get(
                intent_level, 0.0
            )

            base = (
                0.15 * actor.political.protectionism
                + 0.25 * relation.conflict_level
                + 0.25 * (1.0 - relation.trust)
            )

            if actor.alliance_block != "NonAligned" and actor.alliance_block == target.alliance_block:
                base *= 0.7

            sanction_type = actor.active_sanctions.get(target_id)
            has_intent = intent_level != "none"

            if has_intent or sanction_type in {"mild", "strong"}:
                desired = base + intent_boost
                if sanction_type == "strong":
                    desired = max(desired, 0.5)
                elif sanction_type == "mild":
                    desired = max(desired, 0.25)
            else:
                if relation.trust < 0.25 or relation.conflict_level > 0.6:
                    desired = base * 0.7
                else:
                    desired = 0.0

            desired = clamp01(desired)
            relation.trade_barrier = clamp01(0.7 * relation.trade_barrier + 0.3 * desired)


def apply_trade_barrier_effects(world: WorldState) -> None:
    for actor_id, rels in world.relations.items():
        actor = world.agents.get(actor_id)
        if actor is None:
            continue
        for target_id, relation in rels.items():
            target = world.agents.get(target_id)
            if target is None:
                continue
            avg_tension = 0.5 * (
                clamp01(actor.society.social_tension) + clamp01(target.society.social_tension)
            )
            conflict = clamp01(relation.conflict_level)
            friction = 0.04 * conflict + 0.02 * avg_tension

            decay = 0.05 * relation.trade_barrier + friction
            relation.trade_intensity = max(0.0, relation.trade_intensity * (1.0 - decay))


def update_relations_endogenous(world: WorldState) -> None:
    baseline_trade = 0.5
    baseline_trust = 0.6
    baseline_conflict = 0.1

    trade_conflict: Dict[str, float] = {}
    for actor_id, rels in world.relations.items():
        total_weight = 0.0
        weighted_conflict = 0.0
        for rel in rels.values():
            weight = max(0.0, rel.trade_intensity)
            weighted_conflict += weight * rel.conflict_level
            total_weight += weight
        trade_conflict[actor_id] = (
            weighted_conflict / total_weight if total_weight > 0.0 else 0.0
        )

    block_tension: Dict[tuple[str, str], float] = {}
    block_pairs: Dict[tuple[str, str], list[float]] = {}
    for actor_id, rels in world.relations.items():
        actor = world.agents.get(actor_id)
        if actor is None:
            continue
        for target_id, rel in rels.items():
            target = world.agents.get(target_id)
            if target is None:
                continue
            key = (actor.alliance_block, target.alliance_block)
            block_pairs.setdefault(key, []).append(rel.conflict_level)
    for key, values in block_pairs.items():
        if values:
            block_tension[key] = sum(values) / len(values)

    security_orgs = [
        org for org in world.institutions.values() if org.org_type == "SecurityOrg"
    ]
    security_legitimacy = (
        sum(org.legitimacy for org in security_orgs) / len(security_orgs)
        if security_orgs
        else 0.0
    )

    for actor_id, rels in world.relations.items():
        actor = world.agents.get(actor_id)
        if actor is None:
            continue

        for target_id, relation in rels.items():
            target = world.agents.get(target_id)
            if target is None:
                continue

            avg_tension = 0.5 * (
                clamp01(actor.society.social_tension) + clamp01(target.society.social_tension)
            )
            trade_gap = relation.trade_intensity - baseline_trade
            trade_short = max(0.0, baseline_trade - relation.trade_intensity)

            own_mil = max(actor.technology.military_power, 1e-6)
            other_mil = max(target.technology.military_power, 0.0)
            mil_gap = max(0.0, (other_mil - own_mil) / own_mil)

            sanction_flag = 1.0 if target_id in actor.active_sanctions else 0.0
            barrier = clamp01(relation.trade_barrier)
            propagation = 0.03 * (trade_conflict.get(actor_id, 0.0) + trade_conflict.get(target_id, 0.0))
            block_key = (actor.alliance_block, target.alliance_block)
            block_rivalry = 0.0
            if actor.alliance_block != "NonAligned" and target.alliance_block != "NonAligned":
                block_rivalry = 0.04 * block_tension.get(block_key, 0.0)

            shared_security = any(
                actor_id in org.members and target_id in org.members for org in security_orgs
            )
            mediation = 0.03 * security_legitimacy * (1.6 if shared_security else 1.0)

            conflict_drift = 0.02 * (baseline_conflict - relation.conflict_level)
            conflict_push = (
                0.04 * trade_short
                + 0.05 * avg_tension
                + 0.06 * mil_gap
                + 0.04 * barrier
                + 0.03 * sanction_flag
                + propagation
                + block_rivalry
            )
            conflict_push = max(0.0, conflict_push - mediation)
            relation.conflict_level = clamp01(
                relation.conflict_level + conflict_drift + conflict_push
            )

            trust_drift = 0.02 * (baseline_trust - relation.trust)
            trust_push = (
                0.04 * trade_gap
                - 0.05 * relation.conflict_level
                - 0.04 * avg_tension
                - 0.05 * barrier
                - 0.03 * sanction_flag
                + 0.5 * mediation
            )
            relation.trust = clamp01(relation.trust + trust_drift + trust_push)


def _block_score(agent_id: str, block: str, blocks: Dict[str, list[str]], world: WorldState) -> float:
    agent = world.agents[agent_id]
    if block == "NonAligned":
        return 0.05 * agent.political.coalition_openness

    members = [mid for mid in blocks.get(block, []) if mid != agent_id]
    if not members:
        return -1.0

    total = 0.0
    for member_id in members:
        relation = world.relations.get(agent_id, {}).get(member_id)
        if relation is None:
            continue
        total += relation.trust - 0.6 * relation.conflict_level + 0.3 * effective_trade_intensity(relation)

    avg = total / max(len(members), 1)
    return agent.political.coalition_openness * avg


def update_coalitions(world: WorldState, cooldown: int = 3) -> None:
    blocks: Dict[str, list[str]] = {}
    for agent in world.agents.values():
        blocks.setdefault(agent.alliance_block, []).append(agent.id)
    blocks.setdefault("NonAligned", [])

    for agent in world.agents.values():
        if world.time - agent.political.last_block_change < cooldown:
            continue

        current = agent.alliance_block
        current_score = _block_score(agent.id, current, blocks, world)
        best_block = current
        best_score = current_score

        for block in blocks.keys():
            if block == current:
                continue
            score = _block_score(agent.id, block, blocks, world)
            if score > best_score:
                best_score = score
                best_block = block

        if best_block != current and (best_score - current_score) > 0.08:
            agent.alliance_block = best_block
            agent.political.last_block_change = world.time


def resolve_foreign_policy(world: WorldState, actions: Dict[str, Action]) -> None:
    resolve_sanctions(world, actions)
    update_trade_barriers(world, actions)
    update_coalitions(world)
