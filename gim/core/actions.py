import math
from typing import Dict

from .climate import update_emissions_from_economy
from .critical_pending import get_transition_pending
from .core import Action, PricePreference, WorldState, clamp01

_ACTIONS_CRITICAL_PENDING_ATTR = "_actions_critical_pending"


def _get_actions_pending(world: WorldState) -> Dict[str, Dict[str, float]]:
    pending = getattr(world.global_state, _ACTIONS_CRITICAL_PENDING_ATTR, None)
    if pending is None:
        pending = {}
        setattr(world.global_state, _ACTIONS_CRITICAL_PENDING_ATTR, pending)
    return pending


def _effective_critical(world: WorldState, agent_id: str, field: str) -> float:
    agent = world.agents[agent_id]
    pending = _get_actions_pending(world).get(agent_id, {})
    transition_pending = get_transition_pending(world).get(agent_id, {})
    base = {
        "gdp": float(agent.economy.gdp),
        "capital": float(agent.economy.capital),
        "public_debt": float(agent.economy.public_debt),
        "trust_gov": float(agent.society.trust_gov),
        "social_tension": float(agent.society.social_tension),
    }[field]
    return base + float(transition_pending.get(field, 0.0)) + float(pending.get(field, 0.0))


def _add_critical_delta(
    world: WorldState,
    agent_id: str,
    *,
    gdp: float = 0.0,
    capital: float = 0.0,
    public_debt: float = 0.0,
    trust_gov: float = 0.0,
    social_tension: float = 0.0,
) -> None:
    pending = _get_actions_pending(world)
    values = pending.setdefault(
        agent_id,
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


def _set_critical_effective(world: WorldState, agent_id: str, field: str, target: float) -> None:
    current = _effective_critical(world, agent_id, field)
    delta = float(target) - current
    if delta == 0.0:
        return
    _add_critical_delta(world, agent_id, **{field: delta})


def pop_actions_critical_deltas(world: WorldState) -> Dict[str, Dict[str, float]]:
    pending = getattr(world.global_state, _ACTIONS_CRITICAL_PENDING_ATTR, None)
    if not pending:
        return {}
    setattr(world.global_state, _ACTIONS_CRITICAL_PENDING_ATTR, {})
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


def _flush_actions_pending(world: WorldState, agent_ids: set[str] | None = None) -> None:
    pending = _get_actions_pending(world)
    targets = list(pending.keys()) if agent_ids is None else [aid for aid in pending.keys() if aid in agent_ids]
    for agent_id in targets:
        values = pending.pop(agent_id, None)
        if not values:
            continue
        agent = world.agents.get(agent_id)
        if agent is None:
            continue
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


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _normalize_domestic_levers(action: Action, world: WorldState) -> None:
    dom = action.domestic_policy
    agent = world.agents[action.agent_id]
    debt_gdp = agent.economy.public_debt / max(agent.economy.gdp, 1e-6)

    dom.tax_fuel_change = _clamp(float(dom.tax_fuel_change), -1.5, 1.5)
    dom.social_spending_change = _clamp(float(dom.social_spending_change), -0.03, 0.04)
    dom.military_spending_change = _clamp(float(dom.military_spending_change), -0.02, 0.03)
    dom.rd_investment_change = _clamp(float(dom.rd_investment_change), -0.002, 0.008)

    total_expansion = (
        max(0.0, dom.social_spending_change)
        + max(0.0, dom.military_spending_change)
        + max(0.0, dom.rd_investment_change)
    )
    max_expansion = 0.05
    if debt_gdp > 1.2:
        max_expansion = 0.03
    if total_expansion > max_expansion and total_expansion > 0:
        scale = max_expansion / total_expansion
        dom.social_spending_change *= scale
        dom.military_spending_change *= scale
        dom.rd_investment_change *= scale


def apply_action(world: WorldState, action: Action, *, defer_critical_writes: bool = False) -> None:
    _normalize_domestic_levers(action, world)
    agent = world.agents[action.agent_id]
    domestic = action.domestic_policy

    # WRITES: economy.gdp, economy.public_debt, economy.gov_spending,
    # economy.social_spending, economy.military_spending, economy.rd_spending,
    # society.trust_gov, society.social_tension, technology.tech_level,
    # technology.military_power, resources.*.efficiency, climate.co2_annual_emissions
    economy = agent.economy
    society = agent.society
    culture = agent.culture
    technology = agent.technology
    climate = agent.climate

    fuel_tax_delta = domestic.tax_fuel_change
    if abs(fuel_tax_delta) > 1e-6:
        gdp_factor = 0.0012
        trust_factor = 0.02
        tension_factor = 0.02

        uai_factor = culture.uai / 100.0
        pdi_factor = 1.0 - (culture.pdi / 100.0) * 0.5

        regime_tension_mult = 1.0
        if culture.regime_type == "Democracy":
            regime_tension_mult = 1.2
        elif culture.regime_type == "Autocracy":
            regime_tension_mult = 0.8

        sensitivity_tax = (
            uai_factor
            * (1.0 + max(0.0, economy.unemployment - 0.05))
            * pdi_factor
        )
        sensitivity_ineq = (
            (culture.idv / 100.0)
            * (society.inequality_gini / 100.0)
            * regime_tension_mult
        )

        _set_critical_effective(
            world,
            action.agent_id,
            "gdp",
            _effective_critical(world, action.agent_id, "gdp")
            * max(0.0, 1.0 - gdp_factor * fuel_tax_delta),
        )
        _set_critical_effective(
            world,
            action.agent_id,
            "trust_gov",
            clamp01(
                _effective_critical(world, action.agent_id, "trust_gov")
                - trust_factor * fuel_tax_delta * sensitivity_tax
            ),
        )
        _set_critical_effective(
            world,
            action.agent_id,
            "social_tension",
            clamp01(
                _effective_critical(world, action.agent_id, "social_tension")
                + tension_factor * fuel_tax_delta * sensitivity_ineq
            ),
        )

    social_spending_delta = domestic.social_spending_change
    if abs(social_spending_delta) > 1e-6:
        gdp_effective = _effective_critical(world, action.agent_id, "gdp")
        delta_spending = social_spending_delta * gdp_effective
        economy.social_spending += delta_spending
        economy.gov_spending += delta_spending
        _add_critical_delta(world, action.agent_id, public_debt=delta_spending)

        gdp_share = delta_spending / max(gdp_effective, 1e-6)
        _set_critical_effective(
            world,
            action.agent_id,
            "trust_gov",
            clamp01(_effective_critical(world, action.agent_id, "trust_gov") + 0.1 * gdp_share),
        )
        _set_critical_effective(
            world,
            action.agent_id,
            "social_tension",
            clamp01(_effective_critical(world, action.agent_id, "social_tension") - 0.08 * gdp_share),
        )

    military_spending_delta = domestic.military_spending_change
    if abs(military_spending_delta) > 1e-6:
        gdp_effective = _effective_critical(world, action.agent_id, "gdp")
        delta_mil = military_spending_delta * gdp_effective
        economy.military_spending += delta_mil
        economy.gov_spending += delta_mil
        _add_critical_delta(world, action.agent_id, public_debt=delta_mil)

        base_gain = 0.3 * military_spending_delta * (1.0 + 0.5 * (technology.tech_level - 1.0))
        technology.military_power = max(0.0, technology.military_power * (1.0 + base_gain))

        threat_high = technology.security_index < 0.4
        mas_factor = culture.mas / 100.0
        self_expression = culture.survival_self_expression / 10.0

        regime_mult = 1.0
        if culture.regime_type == "Democracy":
            regime_mult = 1.3
        elif culture.regime_type == "Autocracy":
            regime_mult = 0.8

        if threat_high:
            trust_delta = 0.02 * military_spending_delta * (0.8 + 0.6 * mas_factor)
        else:
            trust_delta = (
                -0.03
                * military_spending_delta
                * (0.5 + self_expression)
                * (1.0 - mas_factor)
                * regime_mult
            )

        _set_critical_effective(
            world,
            action.agent_id,
            "trust_gov",
            clamp01(_effective_critical(world, action.agent_id, "trust_gov") + trust_delta),
        )

    rd_delta = domestic.rd_investment_change
    if abs(rd_delta) > 1e-6:
        gdp_effective = _effective_critical(world, action.agent_id, "gdp")
        delta_rd = rd_delta * gdp_effective
        economy.rd_spending += delta_rd
        economy.gov_spending += delta_rd
        _add_critical_delta(world, action.agent_id, public_debt=delta_rd)

        technology.tech_level = max(0.5, technology.tech_level * (1.0 + 0.08 * rd_delta))
        for resource in agent.resources.values():
            resource.efficiency *= math.exp(0.02 * rd_delta)

    policy_reduction = 0.0
    if domestic.climate_policy != "none":
        reduction = {"weak": 0.05, "moderate": 0.15, "strong": 0.30}.get(
            domestic.climate_policy,
            0.0,
        )
        policy_reduction = reduction
        _set_critical_effective(
            world,
            action.agent_id,
            "gdp",
            _effective_critical(world, action.agent_id, "gdp") * max(0.0, 1.0 - 0.003 * reduction),
        )

        intensity = {"weak": 0.01, "moderate": 0.03, "strong": 0.07}.get(
            domestic.climate_policy,
            0.0,
        )

        self_expression = culture.survival_self_expression / 10.0
        risk_level = climate.climate_risk
        base = intensity * (risk_level - 0.5)

        if base >= 0:
            trust_delta = base * (0.5 + self_expression)
        else:
            trust_delta = base * (1.5 - self_expression)

        if culture.regime_type == "Democracy":
            trust_delta *= 1.2

        _set_critical_effective(
            world,
            action.agent_id,
            "trust_gov",
            clamp01(_effective_critical(world, action.agent_id, "trust_gov") + trust_delta),
        )
        if risk_level > 0.5 and self_expression > 0.5:
            _set_critical_effective(
                world,
                action.agent_id,
                "social_tension",
                max(
                    0.0,
                    _effective_critical(world, action.agent_id, "social_tension")
                    - 0.01 * intensity * self_expression,
                ),
            )

    update_emissions_from_economy(
        agent,
        world.time,
        policy_reduction=policy_reduction,
        fuel_tax_change=fuel_tax_delta,
    )
    if not defer_critical_writes:
        _flush_actions_pending(world, {action.agent_id})


def apply_trade_deals(
    world: WorldState,
    actions: Dict[str, Action],
    *,
    defer_critical_writes: bool = False,
) -> None:
    global_prices = world.global_state.prices
    # Net exports are tracked per-step; reset before applying new deals.
    for agent in world.agents.values():
        agent.economy.net_exports = 0.0

    def get_price(resource: str, preference: PricePreference) -> float:
        base_price = global_prices.get(resource, 1.0)
        modifier = {"cheap": 0.9, "fair": 1.0, "premium": 1.1}.get(preference, 1.0)
        return base_price * modifier

    for initiator_id, action in actions.items():
        setattr(action, "_trade_realized", [])
        initiator = world.agents[initiator_id]

        for deal in action.foreign_policy.proposed_trade_deals:
            partner_id = deal.partner
            if partner_id not in world.agents:
                continue
            partner = world.agents[partner_id]

            resource_name = deal.resource
            if resource_name not in initiator.resources or resource_name not in partner.resources:
                continue

            volume_desired = max(0.0, deal.volume_change)
            if volume_desired <= 0.0:
                continue

            price = get_price(resource_name, deal.price_preference)
            init_resource = initiator.resources[resource_name]
            partner_resource = partner.resources[resource_name]

            if deal.direction == "export":
                export_capacity = max(
                    0.0,
                    init_resource.production
                    - init_resource.consumption
                    + 0.2 * max(0.0, init_resource.own_reserve),
                )
                if export_capacity <= 0.0:
                    continue

                trade_credit = 0.05 * max(partner.economy.gdp, 0.0)
                fx_limit = max(0.0, partner.economy.fx_reserves + trade_credit) / max(
                    price,
                    1e-6,
                )
                volume_real = min(volume_desired, export_capacity, fx_limit)
                if initiator_id in world.relations and partner_id in world.relations[initiator_id]:
                    rel_ip = world.relations[initiator_id][partner_id]
                    rel_pi = world.relations.get(partner_id, {}).get(initiator_id)
                    barrier = rel_ip.trade_barrier
                    if rel_pi is not None:
                        barrier = max(barrier, rel_pi.trade_barrier)
                    volume_real *= max(0.0, 1.0 - barrier)
                if volume_real <= 0.0:
                    continue

                value = volume_real * price
                partner_resource.consumption += volume_real

                initiator.economy.fx_reserves += value
                partner.economy.fx_reserves -= value
                initiator.economy.net_exports += value
                partner.economy.net_exports -= value
                action._trade_realized.append(
                    {
                        "partner": partner_id,
                        "resource": resource_name,
                        "direction": "export",
                        "volume_real": volume_real,
                        "price": price,
                        "value": value,
                    }
                )

            elif deal.direction == "import":
                export_capacity = max(
                    0.0,
                    partner_resource.production
                    - partner_resource.consumption
                    + 0.2 * max(0.0, partner_resource.own_reserve),
                )
                if export_capacity <= 0.0:
                    continue

                trade_credit = 0.05 * max(initiator.economy.gdp, 0.0)
                fx_limit = max(0.0, initiator.economy.fx_reserves + trade_credit) / max(
                    price,
                    1e-6,
                )
                volume_real = min(volume_desired, export_capacity, fx_limit)
                if initiator_id in world.relations and partner_id in world.relations[initiator_id]:
                    rel_ip = world.relations[initiator_id][partner_id]
                    rel_pi = world.relations.get(partner_id, {}).get(initiator_id)
                    barrier = rel_ip.trade_barrier
                    if rel_pi is not None:
                        barrier = max(barrier, rel_pi.trade_barrier)
                    volume_real *= max(0.0, 1.0 - barrier)
                if volume_real <= 0.0:
                    continue

                value = volume_real * price
                init_resource.consumption += volume_real

                initiator.economy.fx_reserves -= value
                partner.economy.fx_reserves += value
                initiator.economy.net_exports -= value
                partner.economy.net_exports += value
                action._trade_realized.append(
                    {
                        "partner": partner_id,
                        "resource": resource_name,
                        "direction": "import",
                        "volume_real": volume_real,
                        "price": price,
                        "value": value,
                    }
                )

                if resource_name == "metals":
                    _add_critical_delta(world, initiator_id, capital=0.001 * value)
                elif resource_name == "food":
                    _set_critical_effective(
                        world,
                        initiator_id,
                        "social_tension",
                        clamp01(
                            _effective_critical(world, initiator_id, "social_tension")
                            - 0.0003 * volume_real
                        ),
                    )
                    _set_critical_effective(
                        world,
                        initiator_id,
                        "trust_gov",
                        clamp01(
                            _effective_critical(world, initiator_id, "trust_gov")
                            + 0.00015 * volume_real
                        ),
                    )

            else:
                continue

            if initiator_id in world.relations and partner_id in world.relations[initiator_id]:
                rel_ip = world.relations[initiator_id][partner_id]
                rel_pi = world.relations[partner_id][initiator_id]
                delta_intensity = min(0.05, 0.002 * volume_real)
                rel_ip.trade_intensity += delta_intensity
                rel_pi.trade_intensity += delta_intensity

    # Enforce global trade balance by redistributing any residual (e.g. float drift).
    residual = -sum(agent.economy.net_exports for agent in world.agents.values())
    if abs(residual) > 1e-9:
        weights = [abs(agent.economy.net_exports) for agent in world.agents.values()]
        total_weight = sum(weights)
        if total_weight <= 0.0:
            weights = [agent.economy.gdp for agent in world.agents.values()]
            total_weight = sum(weights)
        if total_weight > 0.0:
            for agent, weight in zip(world.agents.values(), weights):
                agent.economy.net_exports += residual * (weight / total_weight)
    if not defer_critical_writes:
        _flush_actions_pending(world)
