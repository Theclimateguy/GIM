import math
from typing import Dict

from . import calibration_params as cal
from .core import Action, AgentState, WorldState, clamp01, effective_trade_intensity
from .economy import compute_effective_interest_rate

_SOCIAL_CRITICAL_PENDING_ATTR = "_social_critical_pending"


def _get_social_pending(world: WorldState) -> Dict[str, Dict[str, float]]:
    pending = getattr(world.global_state, _SOCIAL_CRITICAL_PENDING_ATTR, None)
    if pending is None:
        pending = {}
        setattr(world.global_state, _SOCIAL_CRITICAL_PENDING_ATTR, pending)
    return pending


def _effective_critical(agent: AgentState, world: WorldState, field: str) -> float:
    pending = _get_social_pending(world).get(agent.id, {})
    base = {
        "gdp": float(agent.economy.gdp),
        "capital": float(agent.economy.capital),
        "public_debt": float(agent.economy.public_debt),
        "trust_gov": float(agent.society.trust_gov),
        "social_tension": float(agent.society.social_tension),
    }[field]
    return base + float(pending.get(field, 0.0))


def _add_critical_delta(
    world: WorldState,
    agent: AgentState,
    *,
    gdp: float = 0.0,
    capital: float = 0.0,
    public_debt: float = 0.0,
    trust_gov: float = 0.0,
    social_tension: float = 0.0,
) -> None:
    pending = _get_social_pending(world)
    values = pending.setdefault(
        agent.id,
        {
            "gdp": 0.0,
            "capital": 0.0,
            "public_debt": 0.0,
            "trust_gov": 0.0,
            "social_tension": 0.0,
        },
    )
    values["gdp"] += float(gdp)
    values["capital"] += float(capital)
    values["public_debt"] += float(public_debt)
    values["trust_gov"] += float(trust_gov)
    values["social_tension"] += float(social_tension)


def _set_critical_effective(world: WorldState, agent: AgentState, field: str, target: float) -> None:
    current = _effective_critical(agent, world, field)
    delta = float(target) - current
    if delta == 0.0:
        return
    _add_critical_delta(world, agent, **{field: delta})


def pop_social_critical_deltas(world: WorldState) -> Dict[str, Dict[str, float]]:
    pending = getattr(world.global_state, _SOCIAL_CRITICAL_PENDING_ATTR, None)
    if not pending:
        return {}
    setattr(world.global_state, _SOCIAL_CRITICAL_PENDING_ATTR, {})
    return {
        agent_id: {
            "gdp": float(values.get("gdp", 0.0)),
            "capital": float(values.get("capital", 0.0)),
            "public_debt": float(values.get("public_debt", 0.0)),
            "trust_gov": float(values.get("trust_gov", 0.0)),
            "social_tension": float(values.get("social_tension", 0.0)),
        }
        for agent_id, values in pending.items()
    }


def _flush_social_pending_for_agent(world: WorldState, agent: AgentState) -> None:
    pending = _get_social_pending(world)
    values = pending.pop(agent.id, None)
    if not values:
        return
    economy = agent.economy
    society = agent.society
    setattr(economy, "gdp", max(0.0, float(economy.gdp) + float(values.get("gdp", 0.0))))
    setattr(economy, "capital", max(0.0, float(economy.capital) + float(values.get("capital", 0.0))))
    setattr(
        economy,
        "public_debt",
        max(0.0, float(economy.public_debt) + float(values.get("public_debt", 0.0))),
    )
    setattr(society, "trust_gov", clamp01(float(society.trust_gov) + float(values.get("trust_gov", 0.0))))
    setattr(
        society,
        "social_tension",
        clamp01(float(society.social_tension) + float(values.get("social_tension", 0.0))),
    )


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
    gdp_pc_effect = cal.TRUST_GDP_PC_SENS * (agent.economy.gdp_per_capita / cal.TRUST_GDP_PC_REF)
    unemployment_effect = cal.TRUST_UNEMPLOYMENT_SENS * agent.economy.unemployment
    inflation_effect = cal.TRUST_INFLATION_SENS * agent.economy.inflation
    inequality_trust_penalty = cal.TRUST_GINI_SENS * agent.society.inequality_gini
    current_tension = _effective_critical(agent, world, "social_tension")
    tension_trust_penalty = cal.TRUST_TENSION_SENS * max(
        0.0,
        current_tension - cal.TRUST_TENSION_THRESHOLD,
    )

    trust_change = (
        gdp_pc_effect
        + unemployment_effect
        + inflation_effect
        + inequality_trust_penalty
        + tension_trust_penalty
    )
    current_trust = _effective_critical(agent, world, "trust_gov")
    trust_next = clamp01(current_trust + trust_change)
    _set_critical_effective(world, agent, "trust_gov", trust_next)

    inequality_sensitivity = 1.0 - agent.culture.idv / 100.0
    inequality_effect = cal.INEQUALITY_EFFECT_SENS * agent.society.inequality_gini * inequality_sensitivity
    stress_effect = (
        cal.SOCIAL_STRESS_UNEMPLOYMENT_SENS * agent.economy.unemployment
        + cal.SOCIAL_STRESS_INFLATION_SENS * agent.economy.inflation
    )
    trust_anchor = cal.SOCIAL_TRUST_ANCHOR_SENS * (cal.SOCIAL_TRUST_ANCHOR_REF - trust_next)

    tension_change = inequality_effect + stress_effect + trust_anchor
    tension_next = clamp01(current_tension + tension_change)
    _set_critical_effective(world, agent, "social_tension", tension_next)

    # Inequality dynamics: GDP growth distribution, fiscal policy, and social tension.
    prev_gdp = getattr(
        agent.economy,
        "_gdp_step_start",
        getattr(agent.economy, "_gdp_prev", agent.economy.gdp),
    )
    gdp = agent.economy.gdp
    gdp_growth = (gdp - prev_gdp) / max(prev_gdp, 1e-6)

    social_spend_delta = action.domestic_policy.social_spending_change
    growth_effect = cal.GINI_GROWTH_SENS * gdp_growth
    recession_penalty = cal.GINI_RECESSION_SENS * abs(min(0.0, gdp_growth)) * (
        cal.GINI_RECESSION_TENSION_OFFSET + tension_next
    )
    fiscal_effect = cal.GINI_FISCAL_SENS * social_spend_delta
    tension_effect = cal.GINI_TENSION_SENS * (tension_next - cal.GINI_TENSION_REF)

    gini_next = (
        agent.society.inequality_gini
        + growth_effect
        + recession_penalty
        + fiscal_effect
        + tension_effect
    )
    agent.society.inequality_gini = max(cal.GINI_MIN, min(cal.GINI_MAX, gini_next))


def check_regime_stability(agent: AgentState, world: WorldState | None = None) -> None:
    # WRITES: risk.regime_crisis_active_years, economy.capital, economy.gdp,
    # economy.public_debt, society.trust_gov, society.social_tension
    if world is None:
        trust_threshold = cal.REGIME_COLLAPSE_TRUST_THRESHOLD
        tension_threshold = cal.REGIME_COLLAPSE_TENSION_THRESHOLD
        in_crisis = (
            agent.society.trust_gov < trust_threshold
            and agent.society.social_tension > tension_threshold
        )
        if in_crisis:
            agent.risk.regime_crisis_active_years = min(
                agent.risk.regime_crisis_active_years + 1,
                cal.REGIME_CRISIS_MAX_YEARS,
            )
            crisis_year = agent.risk.regime_crisis_active_years
            if crisis_year == 1:
                economy = agent.economy
                society = agent.society
                setattr(economy, "capital", economy.capital * cal.REGIME_COLLAPSE_CAPITAL_MULT)
                setattr(economy, "gdp", economy.gdp * cal.REGIME_COLLAPSE_GDP_MULT)
                setattr(economy, "public_debt", economy.public_debt * cal.REGIME_COLLAPSE_DEBT_MULT)
                setattr(society, "trust_gov", max(society.trust_gov, cal.REGIME_COLLAPSE_TRUST_FLOOR))
                setattr(society, "social_tension", min(society.social_tension, cal.REGIME_COLLAPSE_TENSION_CAP))
                agent.risk.regime_stability = max(
                    0.0,
                    agent.risk.regime_stability - cal.REGIME_COLLAPSE_STABILITY_HIT,
                )
            else:
                economy = agent.economy
                setattr(economy, "capital", economy.capital * cal.REGIME_CRISIS_PERSIST_CAPITAL_MULT)
                setattr(economy, "gdp", economy.gdp * cal.REGIME_CRISIS_PERSIST_GDP_MULT)
        else:
            agent.risk.regime_crisis_active_years = 0
        return

    trust_threshold = cal.REGIME_COLLAPSE_TRUST_THRESHOLD
    tension_threshold = cal.REGIME_COLLAPSE_TENSION_THRESHOLD
    trust_effective = _effective_critical(agent, world, "trust_gov")
    tension_effective = _effective_critical(agent, world, "social_tension")
    in_crisis = (
        trust_effective < trust_threshold
        and tension_effective > tension_threshold
    )
    if in_crisis:
        agent.risk.regime_crisis_active_years = min(
            agent.risk.regime_crisis_active_years + 1,
            cal.REGIME_CRISIS_MAX_YEARS,
        )
        crisis_year = agent.risk.regime_crisis_active_years
        if crisis_year == 1:
            _set_critical_effective(
                world,
                agent,
                "capital",
                _effective_critical(agent, world, "capital") * cal.REGIME_COLLAPSE_CAPITAL_MULT,
            )
            _set_critical_effective(
                world,
                agent,
                "gdp",
                _effective_critical(agent, world, "gdp") * cal.REGIME_COLLAPSE_GDP_MULT,
            )
            _set_critical_effective(
                world,
                agent,
                "public_debt",
                _effective_critical(agent, world, "public_debt") * cal.REGIME_COLLAPSE_DEBT_MULT,
            )

            _set_critical_effective(
                world,
                agent,
                "trust_gov",
                max(_effective_critical(agent, world, "trust_gov"), cal.REGIME_COLLAPSE_TRUST_FLOOR),
            )
            _set_critical_effective(
                world,
                agent,
                "social_tension",
                min(_effective_critical(agent, world, "social_tension"), cal.REGIME_COLLAPSE_TENSION_CAP),
            )
            agent.risk.regime_stability = max(
                0.0,
                agent.risk.regime_stability - cal.REGIME_COLLAPSE_STABILITY_HIT,
            )
        else:
            _set_critical_effective(
                world,
                agent,
                "capital",
                _effective_critical(agent, world, "capital") * cal.REGIME_CRISIS_PERSIST_CAPITAL_MULT,
            )
            _set_critical_effective(
                world,
                agent,
                "gdp",
                _effective_critical(agent, world, "gdp") * cal.REGIME_CRISIS_PERSIST_GDP_MULT,
            )
    else:
        agent.risk.regime_crisis_active_years = 0


def check_debt_crisis(agent: AgentState, world: WorldState, *, defer_critical_writes: bool = False) -> None:
    economy = agent.economy
    risk = agent.risk

    # WRITES: risk.debt_crisis_active_years, economy.public_debt, economy.gdp,
    # economy.unemployment, society.trust_gov, society.social_tension
    def _estimate_fx_cover_months() -> float:
        prices = getattr(world.global_state, "prices", {}) or {}
        annual_import_bill = 0.0
        for resource_name in ("energy", "food", "metals"):
            resource = agent.resources.get(resource_name)
            if resource is None:
                continue
            unit_price = float(prices.get(resource_name, 1.0))
            net_import_volume = max(0.0, float(resource.consumption) - float(resource.production))
            annual_import_bill += net_import_volume * max(unit_price, 1e-6)
        monthly_import_bill = max(annual_import_bill / 12.0, 1e-6)
        return float(economy.fx_reserves) / monthly_import_bill

    gdp = max(_effective_critical(agent, world, "gdp"), 1e-6)
    debt_gdp = _effective_critical(agent, world, "public_debt") / gdp
    interest_rate = compute_effective_interest_rate(agent, world)
    fx_cover_months = _estimate_fx_cover_months()
    inflation = float(economy.inflation)

    debt_trigger = (
        debt_gdp > cal.DEBT_CRISIS_DEBT_THRESHOLD
        and interest_rate > cal.DEBT_CRISIS_RATE_THRESHOLD
    )
    fx_trigger = (
        inflation > cal.FX_CRISIS_INFLATION_THRESHOLD
        and fx_cover_months < cal.FX_CRISIS_RESERVE_MONTHS_THRESHOLD
    )
    trigger_kind = "fx" if fx_trigger and not debt_trigger else "debt"

    if risk.debt_crisis_active_years == 0:
        in_crisis = debt_trigger or fx_trigger
        if in_crisis:
            risk.debt_crisis_trigger = trigger_kind
        recovered = False
    else:
        current_trigger = risk.debt_crisis_trigger if risk.debt_crisis_trigger in {"debt", "fx"} else "debt"
        if debt_trigger:
            current_trigger = "debt"
            risk.debt_crisis_trigger = "debt"
        recovery_window_open = risk.debt_crisis_active_years >= 2
        debt_recovered = (
            debt_gdp < cal.DEBT_CRISIS_EXIT_THRESHOLD
            and interest_rate < cal.DEBT_CRISIS_EXIT_RATE
        )
        fx_recovered = (
            inflation < cal.FX_CRISIS_EXIT_INFLATION
            and fx_cover_months > cal.FX_CRISIS_EXIT_RESERVE_MONTHS
        )
        recovered = fx_recovered if current_trigger == "fx" else debt_recovered
        in_crisis = not (recovery_window_open and recovered)
    if in_crisis:
        risk.debt_crisis_active_years = min(
            risk.debt_crisis_active_years + 1,
            cal.DEBT_CRISIS_MAX_YEARS,
        )
        crisis_year = risk.debt_crisis_active_years
        if crisis_year == 1:
            if risk.debt_crisis_trigger == "fx":
                _set_critical_effective(
                    world,
                    agent,
                    "public_debt",
                    _effective_critical(agent, world, "public_debt") * cal.FX_CRISIS_DEBT_MULT,
                )
                _set_critical_effective(
                    world,
                    agent,
                    "gdp",
                    _effective_critical(agent, world, "gdp") * cal.FX_CRISIS_GDP_MULT,
                )
                unemployment_hit = cal.FX_CRISIS_UNEMPLOYMENT_HIT
                trust_hit = cal.FX_CRISIS_TRUST_HIT
                tension_hit = cal.FX_CRISIS_TENSION_HIT
                stability_hit = cal.FX_CRISIS_STABILITY_HIT
            else:
                _set_critical_effective(
                    world,
                    agent,
                    "public_debt",
                    _effective_critical(agent, world, "public_debt") * cal.DEBT_CRISIS_DEBT_MULT,
                )
                _set_critical_effective(
                    world,
                    agent,
                    "gdp",
                    _effective_critical(agent, world, "gdp") * cal.DEBT_CRISIS_GDP_MULT,
                )
                unemployment_hit = cal.DEBT_CRISIS_UNEMPLOYMENT_HIT
                trust_hit = cal.DEBT_CRISIS_TRUST_HIT
                tension_hit = cal.DEBT_CRISIS_TENSION_HIT
                stability_hit = cal.DEBT_CRISIS_STABILITY_HIT
            economy.unemployment = min(
                cal.DEBT_CRISIS_UNEMPLOYMENT_MAX,
                economy.unemployment + unemployment_hit,
            )

            _set_critical_effective(
                world,
                agent,
                "trust_gov",
                max(0.0, _effective_critical(agent, world, "trust_gov") - trust_hit),
            )
            _set_critical_effective(
                world,
                agent,
                "social_tension",
                min(1.0, _effective_critical(agent, world, "social_tension") + tension_hit),
            )
            risk.regime_stability = max(0.0, risk.regime_stability - stability_hit)
        elif not recovered:
            _set_critical_effective(
                world,
                agent,
                "gdp",
                _effective_critical(agent, world, "gdp") * cal.DEBT_CRISIS_PERSIST_GDP_MULT,
            )
            _set_critical_effective(
                world,
                agent,
                "trust_gov",
                max(0.0, _effective_critical(agent, world, "trust_gov") - cal.DEBT_CRISIS_PERSIST_TRUST_HIT),
            )
            _set_critical_effective(
                world,
                agent,
                "social_tension",
                min(
                    1.0,
                    _effective_critical(agent, world, "social_tension") + cal.DEBT_CRISIS_PERSIST_TENSION_HIT,
                ),
            )
    else:
        risk.debt_crisis_active_years = 0
        risk.debt_crisis_trigger = "debt"
    if not defer_critical_writes:
        _flush_social_pending_for_agent(world, agent)
