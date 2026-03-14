import math

from . import calibration_params as cal
from .core import Action, AgentState, WorldState, clamp01, effective_trade_intensity
from .economy import compute_effective_interest_rate


def update_population(agent: AgentState, world: WorldState) -> None:
    gdp_per_capita = agent.economy.gdp_per_capita
    gini = agent.society.inequality_gini / 100.0

    food = agent.resources.get("food")
    if food is not None:
        availability_ratio = (food.production + cal.FOOD_RESERVE_WEIGHT * food.own_reserve) / max(
            food.consumption, 1e-6
        )
    else:
        availability_ratio = 1.0
    availability_ratio = min(cal.FOOD_AVAILABILITY_MAX, max(0.0, availability_ratio))
    scarcity = max(0.0, 1.0 - availability_ratio)

    baseline = getattr(world.global_state, "baseline_gdp_pc", 0.0) or 1.0
    ratio = max(gdp_per_capita / baseline, 1e-6)
    prosperity = 1.0 / (1.0 + math.exp(-cal.PROSPERITY_LOGIT_SENS * math.log(ratio)))

    birth_rate = cal.BASE_BIRTH_RATE - cal.BIRTH_GDP_PC_DECAY * gdp_per_capita
    birth_rate *= 1.0 - cal.BIRTH_PROSPERITY_DAMP * prosperity
    birth_rate *= 1.0 - cal.BIRTH_SCARCITY_DAMP * scarcity
    birth_rate *= 1.0 - cal.BIRTH_GINI_DAMP * gini
    agent.economy.birth_rate = max(cal.BIRTH_RATE_MIN, min(cal.BIRTH_RATE_MAX, birth_rate))

    death_rate = cal.BASE_DEATH_RATE - cal.DEATH_GDP_PC_DECAY * gdp_per_capita
    death_rate *= 1.0 + cal.DEATH_SCARCITY_SENS * scarcity + cal.DEATH_GINI_SENS * gini
    death_rate *= 1.0 - cal.DEATH_PROSPERITY_DAMP * prosperity
    agent.economy.death_rate = max(cal.DEATH_RATE_MIN, min(cal.DEATH_RATE_MAX, death_rate))

    growth_rate = agent.economy.birth_rate - agent.economy.death_rate
    agent.economy.population *= 1 + growth_rate


def update_migration_flows(world: WorldState) -> None:
    baseline = getattr(world.global_state, "baseline_gdp_pc", 0.0) or 1.0
    base_rate = cal.MIGRATION_BASE_RATE
    max_share = cal.MIGRATION_MAX_SHARE

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
        push = cal.MIGRATION_INCOME_PUSH_W * income_gap + cal.MIGRATION_CONFLICT_PUSH_W * conflict_push
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
            weight = trade_weight * gap * (1.0 - cal.MIGRATION_DEST_CONFLICT_DAMP * dest_conflict)
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

    gdp_pc_effect = cal.TRUST_GDP_PC_SENS * (agent.economy.gdp_per_capita / cal.TRUST_GDP_PC_REF)
    unemployment_effect = cal.TRUST_UNEMPLOYMENT_SENS * agent.economy.unemployment
    inflation_effect = cal.TRUST_INFLATION_SENS * agent.economy.inflation
    inequality_trust_penalty = cal.TRUST_GINI_SENS * agent.society.inequality_gini
    tension_trust_penalty = cal.TRUST_TENSION_SENS * max(
        0.0,
        agent.society.social_tension - cal.TRUST_TENSION_THRESHOLD,
    )

    trust_change = (
        gdp_pc_effect
        + unemployment_effect
        + inflation_effect
        + inequality_trust_penalty
        + tension_trust_penalty
    )
    agent.society.trust_gov = max(0.0, min(1.0, agent.society.trust_gov + trust_change))

    inequality_sensitivity = 1.0 - agent.culture.idv / 100.0
    inequality_effect = cal.INEQUALITY_EFFECT_SENS * agent.society.inequality_gini * inequality_sensitivity
    stress_effect = (
        cal.SOCIAL_STRESS_UNEMPLOYMENT_SENS * agent.economy.unemployment
        + cal.SOCIAL_STRESS_INFLATION_SENS * agent.economy.inflation
    )
    trust_anchor = cal.SOCIAL_TRUST_ANCHOR_SENS * (
        cal.SOCIAL_TRUST_ANCHOR_REF - agent.society.trust_gov
    )

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
    growth_effect = cal.GINI_GROWTH_SENS * gdp_growth
    recession_penalty = cal.GINI_RECESSION_SENS * abs(min(0.0, gdp_growth)) * (
        cal.GINI_RECESSION_TENSION_OFFSET + agent.society.social_tension
    )
    fiscal_effect = cal.GINI_FISCAL_SENS * social_spend_delta
    tension_effect = cal.GINI_TENSION_SENS * (agent.society.social_tension - cal.GINI_TENSION_REF)

    gini_next = (
        agent.society.inequality_gini
        + growth_effect
        + recession_penalty
        + fiscal_effect
        + tension_effect
    )
    agent.society.inequality_gini = max(cal.GINI_MIN, min(cal.GINI_MAX, gini_next))


def check_regime_stability(agent: AgentState) -> None:
    trust_threshold = cal.REGIME_COLLAPSE_TRUST_THRESHOLD
    tension_threshold = cal.REGIME_COLLAPSE_TENSION_THRESHOLD
    recovery_stability = max(0.5, cal.REGIME_COLLAPSE_TRUST_FLOOR * 2.0)

    onset_trigger = (
        agent.society.trust_gov < trust_threshold
        and agent.society.social_tension > tension_threshold
    )
    persistence_trigger = (
        agent.risk.regime_crisis_active_years > 0
        and agent.risk.regime_stability < recovery_stability
    )
    in_crisis = onset_trigger or persistence_trigger
    if in_crisis:
        agent.risk.regime_crisis_active_years = min(
            agent.risk.regime_crisis_active_years + 1,
            cal.REGIME_CRISIS_MAX_YEARS,
        )
        crisis_year = agent.risk.regime_crisis_active_years
        if crisis_year == 1:
            agent.economy.capital *= cal.REGIME_COLLAPSE_CAPITAL_MULT
            agent.economy.gdp *= cal.REGIME_COLLAPSE_GDP_MULT
            agent.economy.public_debt *= cal.REGIME_COLLAPSE_DEBT_MULT

            agent.society.trust_gov = max(agent.society.trust_gov, cal.REGIME_COLLAPSE_TRUST_FLOOR)
            agent.society.social_tension = min(
                agent.society.social_tension,
                cal.REGIME_COLLAPSE_TENSION_CAP,
            )
            agent.risk.regime_stability = max(
                0.0,
                agent.risk.regime_stability - cal.REGIME_COLLAPSE_STABILITY_HIT,
            )
        else:
            agent.economy.capital *= cal.REGIME_CRISIS_PERSIST_CAPITAL_MULT
            agent.economy.gdp *= cal.REGIME_CRISIS_PERSIST_GDP_MULT
    else:
        agent.risk.regime_crisis_active_years = 0


def check_debt_crisis(agent: AgentState, world: WorldState) -> None:
    economy = agent.economy
    risk = agent.risk
    society = agent.society

    gdp = max(economy.gdp, 1e-6)
    debt_gdp = economy.public_debt / gdp
    interest_rate = compute_effective_interest_rate(agent, world)

    in_crisis = (
        debt_gdp > cal.DEBT_CRISIS_DEBT_THRESHOLD
        and interest_rate > cal.DEBT_CRISIS_RATE_THRESHOLD
    )
    if in_crisis:
        risk.debt_crisis_active_years = min(
            risk.debt_crisis_active_years + 1,
            cal.DEBT_CRISIS_MAX_YEARS,
        )
        crisis_year = risk.debt_crisis_active_years
        if crisis_year == 1:
            economy.public_debt *= cal.DEBT_CRISIS_DEBT_MULT
            economy.gdp *= cal.DEBT_CRISIS_GDP_MULT
            economy.unemployment = min(
                cal.DEBT_CRISIS_UNEMPLOYMENT_MAX,
                economy.unemployment + cal.DEBT_CRISIS_UNEMPLOYMENT_HIT,
            )

            society.trust_gov = max(0.0, society.trust_gov - cal.DEBT_CRISIS_TRUST_HIT)
            society.social_tension = min(1.0, society.social_tension + cal.DEBT_CRISIS_TENSION_HIT)
            risk.regime_stability = max(0.0, risk.regime_stability - cal.DEBT_CRISIS_STABILITY_HIT)
        else:
            economy.gdp *= cal.DEBT_CRISIS_PERSIST_GDP_MULT
            society.trust_gov = max(0.0, society.trust_gov - cal.DEBT_CRISIS_PERSIST_TRUST_HIT)
            society.social_tension = min(1.0, society.social_tension + cal.DEBT_CRISIS_PERSIST_TENSION_HIT)
    else:
        risk.debt_crisis_active_years = 0
