import math
from typing import Dict

from .core import Action, PricePreference, WorldState, clamp01


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _normalize_domestic_levers(action: Action, world: WorldState) -> None:
    dom = action.domestic_policy
    agent = world.agents[action.agent_id]
    debt_gdp = agent.economy.public_debt / max(agent.economy.gdp, 1e-6)

    dom.tax_fuel_change = _clamp(float(dom.tax_fuel_change), -1.5, 1.5)
    dom.social_spending_change = _clamp(float(dom.social_spending_change), -0.015, 0.02)
    dom.military_spending_change = _clamp(float(dom.military_spending_change), -0.01, 0.015)
    dom.rd_investment_change = _clamp(float(dom.rd_investment_change), -0.002, 0.008)

    total_expansion = (
        max(0.0, dom.social_spending_change)
        + max(0.0, dom.military_spending_change)
        + max(0.0, dom.rd_investment_change)
    )
    max_expansion = 0.03
    if debt_gdp > 1.2:
        max_expansion = 0.02
    if total_expansion > max_expansion and total_expansion > 0:
        scale = max_expansion / total_expansion
        dom.social_spending_change *= scale
        dom.military_spending_change *= scale
        dom.rd_investment_change *= scale


def apply_action(world: WorldState, action: Action) -> None:
    _normalize_domestic_levers(action, world)
    agent = world.agents[action.agent_id]
    domestic = action.domestic_policy

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

        economy.gdp *= max(0.0, 1.0 - gdp_factor * fuel_tax_delta)
        society.trust_gov = clamp01(
            society.trust_gov - trust_factor * fuel_tax_delta * sensitivity_tax
        )
        society.social_tension = clamp01(
            society.social_tension + tension_factor * fuel_tax_delta * sensitivity_ineq
        )

    social_spending_delta = domestic.social_spending_change
    if abs(social_spending_delta) > 1e-6:
        delta_spending = social_spending_delta * economy.gdp
        economy.social_spending += delta_spending
        economy.gov_spending += delta_spending
        economy.public_debt += delta_spending

        gdp_share = delta_spending / max(economy.gdp, 1e-6)
        society.trust_gov = clamp01(society.trust_gov + 0.1 * gdp_share)
        society.social_tension = clamp01(society.social_tension - 0.08 * gdp_share)

    military_spending_delta = domestic.military_spending_change
    if abs(military_spending_delta) > 1e-6:
        delta_mil = military_spending_delta * economy.gdp
        economy.military_spending += delta_mil
        economy.gov_spending += delta_mil
        economy.public_debt += delta_mil

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

        society.trust_gov = clamp01(society.trust_gov + trust_delta)

    rd_delta = domestic.rd_investment_change
    if abs(rd_delta) > 1e-6:
        delta_rd = rd_delta * economy.gdp
        economy.rd_spending += delta_rd
        economy.gov_spending += delta_rd
        economy.public_debt += delta_rd

        technology.tech_level = max(0.5, technology.tech_level * (1.0 + 0.08 * rd_delta))
        for resource in agent.resources.values():
            resource.efficiency *= math.exp(-0.02 * rd_delta)

    if domestic.climate_policy != "none":
        reduction = {"weak": 0.05, "moderate": 0.15, "strong": 0.30}.get(
            domestic.climate_policy,
            0.0,
        )
        climate.co2_annual_emissions *= 1.0 - reduction
        economy.gdp *= max(0.0, 1.0 - 0.003 * reduction)

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

        society.trust_gov = clamp01(society.trust_gov + trust_delta)
        if risk_level > 0.5 and self_expression > 0.5:
            society.social_tension = max(
                0.0,
                society.social_tension - 0.01 * intensity * self_expression,
            )


def apply_trade_deals(world: WorldState, actions: Dict[str, Action]) -> None:
    global_prices = world.global_state.prices
    # Net exports are tracked per-step; reset before applying new deals.
    for agent in world.agents.values():
        agent.economy.net_exports = 0.0

    def get_price(resource: str, preference: PricePreference) -> float:
        base_price = global_prices.get(resource, 1.0)
        modifier = {"cheap": 0.9, "fair": 1.0, "premium": 1.1}.get(preference, 1.0)
        return base_price * modifier

    for initiator_id, action in actions.items():
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
                export_capacity = max(0.0, init_resource.production - init_resource.consumption)
                if export_capacity <= 0.0:
                    continue

                fx_limit = max(0.0, partner.economy.fx_reserves) / max(price, 1e-6)
                volume_real = min(volume_desired, export_capacity, fx_limit)
                if volume_real <= 0.0:
                    continue

                value = volume_real * price
                partner_resource.consumption += volume_real

                initiator.economy.fx_reserves += value
                partner.economy.fx_reserves -= value
                initiator.economy.net_exports += value
                partner.economy.net_exports -= value

            elif deal.direction == "import":
                export_capacity = max(0.0, partner_resource.production - partner_resource.consumption)
                if export_capacity <= 0.0:
                    continue

                fx_limit = max(0.0, initiator.economy.fx_reserves) / max(price, 1e-6)
                volume_real = min(volume_desired, export_capacity, fx_limit)
                if volume_real <= 0.0:
                    continue

                value = volume_real * price
                init_resource.consumption += volume_real

                initiator.economy.fx_reserves -= value
                partner.economy.fx_reserves += value
                initiator.economy.net_exports -= value
                partner.economy.net_exports += value

            else:
                continue

            if initiator_id in world.relations and partner_id in world.relations[initiator_id]:
                rel_ip = world.relations[initiator_id][partner_id]
                rel_pi = world.relations[partner_id][initiator_id]
                delta_intensity = 0.01 * volume_real
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
