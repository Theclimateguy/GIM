import math

from .core import Action, AgentState, WorldState, clamp01, effective_trade_intensity
from .economy import compute_effective_interest_rate


def update_population(agent: AgentState, world: WorldState) -> None:
    gdp_per_capita = agent.economy.gdp_per_capita
    gini = agent.society.inequality_gini / 100.0

    food = agent.resources.get("food")
    if food is not None:
        availability_ratio = (food.production + 0.2 * food.own_reserve) / max(
            food.consumption, 1e-6
        )
    else:
        availability_ratio = 1.0
    availability_ratio = min(2.0, max(0.0, availability_ratio))
    scarcity = max(0.0, 1.0 - availability_ratio)

    baseline = getattr(world.global_state, "baseline_gdp_pc", 0.0) or 1.0
    ratio = max(gdp_per_capita / baseline, 1e-6)
    prosperity = 1.0 / (1.0 + math.exp(-1.2 * math.log(ratio)))

    base_birth = 0.025
    birth_decline = 0.000001
    birth_rate = base_birth - birth_decline * gdp_per_capita
    birth_rate *= (1.0 - 0.5 * prosperity)
    birth_rate *= (1.0 - 0.6 * scarcity)
    birth_rate *= (1.0 - 0.3 * gini)
    agent.economy.birth_rate = max(0.006, min(0.04, birth_rate))

    base_death = 0.012
    death_decline = 0.0000005
    death_rate = base_death - death_decline * gdp_per_capita
    death_rate *= (1.0 + 1.0 * scarcity + 0.4 * gini)
    death_rate *= (1.0 - 0.2 * prosperity)
    agent.economy.death_rate = max(0.004, min(0.03, death_rate))

    growth_rate = agent.economy.birth_rate - agent.economy.death_rate
    agent.economy.population *= 1 + growth_rate


def update_migration_flows(world: WorldState) -> None:
    baseline = getattr(world.global_state, "baseline_gdp_pc", 0.0) or 1.0
    base_rate = 0.001
    max_share = 0.003

    gdp_pc: dict[str, float] = {}
    for agent in world.agents.values():
        if agent.economy.gdp_per_capita > 0:
            gdp_pc_val = agent.economy.gdp_per_capita
        else:
            gdp_pc_val = agent.economy.gdp * 1e12 / max(agent.economy.population, 1.0)
        gdp_pc[agent.id] = gdp_pc_val

    net_flows: dict[str, float] = {agent_id: 0.0 for agent_id in world.agents}

    for origin_id, origin in world.agents.items():
        income_gap = max(0.0, (baseline - gdp_pc[origin_id]) / baseline)
        conflict_push = clamp01(origin.risk.conflict_proneness)
        push = 0.6 * income_gap + 0.4 * conflict_push
        if push <= 0.0:
            continue

        population = origin.economy.population
        outflow = base_rate * population * push
        outflow = min(outflow, max_share * population)
        if outflow <= 0.0:
            continue

        weights: dict[str, float] = {}
        total_weight = 0.0
        for dest_id, rel in world.relations.get(origin_id, {}).items():
            dest = world.agents.get(dest_id)
            if dest is None:
                continue
            gap = max(0.0, (gdp_pc[dest_id] - gdp_pc[origin_id]) / baseline)
            if gap <= 0.0:
                continue
            dest_conflict = clamp01(dest.risk.conflict_proneness)
            trade_weight = max(0.0, effective_trade_intensity(rel))
            weight = trade_weight * gap * (1.0 - 0.5 * dest_conflict)
            if weight <= 0.0:
                continue
            weights[dest_id] = weight
            total_weight += weight

        if total_weight <= 0.0:
            continue

        for dest_id, weight in weights.items():
            flow = outflow * (weight / total_weight)
            net_flows[origin_id] -= flow
            net_flows[dest_id] += flow

    for agent_id, delta in net_flows.items():
        if abs(delta) <= 0.0:
            continue
        agent = world.agents[agent_id]
        agent.economy.population = max(0.0, agent.economy.population + delta)


def update_social_state(agent: AgentState, action: Action, world: WorldState) -> None:
    del world

    gdp_pc_effect = 0.00005 * (agent.economy.gdp_per_capita / 10000.0)
    unemployment_effect = -0.025 * agent.economy.unemployment
    inflation_effect = -0.025 * agent.economy.inflation
    inequality_trust_penalty = -0.0004 * agent.society.inequality_gini
    tension_trust_penalty = -0.08 * max(0.0, agent.society.social_tension - 0.3)

    trust_change = (
        gdp_pc_effect
        + unemployment_effect
        + inflation_effect
        + inequality_trust_penalty
        + tension_trust_penalty
    )
    agent.society.trust_gov = max(0.0, min(1.0, agent.society.trust_gov + trust_change))

    inequality_sensitivity = 1.0 - agent.culture.idv / 100.0
    inequality_effect = 0.0005 * agent.society.inequality_gini * inequality_sensitivity
    stress_effect = 0.01 * agent.economy.unemployment + 0.005 * agent.economy.inflation
    trust_anchor = 0.06 * (0.5 - agent.society.trust_gov)

    tension_change = inequality_effect + stress_effect + trust_anchor
    agent.society.social_tension = max(
        0.0,
        min(1.0, agent.society.social_tension + tension_change),
    )

    # Inequality dynamics: GDP growth distribution, fiscal policy, and social tension.
    prev_gdp = getattr(agent.economy, "_gdp_prev", agent.economy.gdp)
    gdp = agent.economy.gdp
    gdp_growth = (gdp - prev_gdp) / max(prev_gdp, 1e-6)
    agent.economy._gdp_prev = gdp

    social_spend_delta = action.domestic_policy.social_spending_change
    growth_effect = 6.0 * gdp_growth
    recession_penalty = 4.0 * abs(min(0.0, gdp_growth)) * (0.5 + agent.society.social_tension)
    fiscal_effect = -60.0 * social_spend_delta
    tension_effect = 1.2 * (agent.society.social_tension - 0.4)

    gini_next = (
        agent.society.inequality_gini
        + growth_effect
        + recession_penalty
        + fiscal_effect
        + tension_effect
    )
    agent.society.inequality_gini = max(20.0, min(70.0, gini_next))


def check_regime_stability(agent: AgentState) -> None:
    trust_threshold = 0.2
    tension_threshold = 0.8

    if agent.society.trust_gov < trust_threshold and agent.society.social_tension > tension_threshold:
        if not hasattr(agent, "_collapsed_this_step") or not agent._collapsed_this_step:
            agent._collapsed_this_step = True

            agent.economy.capital *= 0.7
            agent.economy.gdp *= 0.8
            agent.economy.public_debt *= 0.7

            agent.society.trust_gov = max(agent.society.trust_gov, 0.25)
            agent.society.social_tension = min(agent.society.social_tension, 0.6)
            agent.risk.regime_stability = max(0.0, agent.risk.regime_stability - 0.2)
    elif hasattr(agent, "_collapsed_this_step"):
        agent._collapsed_this_step = False


def check_debt_crisis(agent: AgentState, world: WorldState) -> None:
    economy = agent.economy
    risk = agent.risk
    society = agent.society

    gdp = max(economy.gdp, 1e-6)
    debt_gdp = economy.public_debt / gdp
    interest_rate = compute_effective_interest_rate(agent, world)

    if debt_gdp > 1.2 and interest_rate > 0.12:
        if not hasattr(agent, "_debt_crisis_this_step") or not agent._debt_crisis_this_step:
            agent._debt_crisis_this_step = True

            economy.public_debt *= 0.6
            economy.gdp *= 0.9
            economy.unemployment = min(0.3, economy.unemployment + 0.05)

            society.trust_gov = max(0.0, society.trust_gov - 0.15)
            society.social_tension = min(1.0, society.social_tension + 0.15)
            risk.regime_stability = max(0.0, risk.regime_stability - 0.15)
    elif hasattr(agent, "_debt_crisis_this_step"):
        agent._debt_crisis_this_step = False
