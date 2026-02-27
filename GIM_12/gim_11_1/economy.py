from .climate import effective_damage_multiplier
from .core import AgentState, WorldState, clamp01, effective_trade_intensity
from .metrics import update_tfp_endogenous


def update_capital_endogenous(agent: AgentState) -> None:
    economy = agent.economy
    risk = agent.risk

    gdp = max(economy.gdp, 1e-6)
    capital = max(economy.capital, 1e-6)
    depreciation = 0.05

    base_savings = 0.24
    stability = clamp01(risk.regime_stability)
    tension = clamp01(agent.society.social_tension)

    savings_rate = base_savings * (0.7 + 0.6 * stability - 0.4 * tension)
    savings_rate = max(0.05, min(0.40, savings_rate))

    investment = savings_rate * gdp
    economy.capital = max(1e-6, (1.0 - depreciation) * capital + investment)


def update_economy_output(agent: AgentState, world: WorldState) -> None:
    economy = agent.economy
    update_tfp_endogenous(agent, world)

    alpha = 0.3
    beta = 0.60
    gamma = 0.10

    capital = max(economy.capital, 1e-6)
    labor = max(economy.population / 1e9, 1e-3)

    energy = agent.resources.get("energy")
    if energy:
        efficiency = max(0.5, energy.efficiency)
        energy_input = max((energy.consumption / 1000.0) * efficiency, 1e-3)
    else:
        energy_input = 1.0

    tfp = getattr(economy, "tfp", getattr(economy, "_tfp", 1.0))
    tech_level = max(0.5, agent.technology.tech_level)
    tech_factor = 1.0 + 0.6 * max(0.0, tech_level - 1.0)
    gdp_potential = tfp * tech_factor * (capital**alpha) * (labor**beta) * (energy_input**gamma)

    if (not hasattr(economy, "_scale_factor")) or getattr(economy, "_scale_factor", None) is None:
        economy._scale_factor = economy.gdp / gdp_potential if gdp_potential > 0 else 1.0

    gdp_target = gdp_potential * economy._scale_factor * effective_damage_multiplier(agent, world)
    if economy.climate_shock_years > 0:
        gdp_target *= max(0.0, 1.0 - economy.climate_shock_penalty)
        economy.climate_shock_years -= 1
        if economy.climate_shock_years <= 0:
            economy.climate_shock_penalty = 0.0

    # Endogenous catch-up: faster when realized GDP is below potential,
    # slower when above. No exogenous growth term is introduced.
    gdp_now = max(economy.gdp, 1e-6)
    gap = (gdp_target - gdp_now) / gdp_now
    adjust_speed = 0.30 + 0.35 * clamp01(max(0.0, gap))
    economy.gdp = (1.0 - adjust_speed) * economy.gdp + adjust_speed * gdp_target

    update_capital_endogenous(agent)

    if economy.population > 0:
        economy.gdp_per_capita = economy.gdp * 1e12 / economy.population


def compute_effective_interest_rate(agent: AgentState, world: WorldState | None = None) -> float:
    economy = agent.economy
    risk = agent.risk

    base_rate = 0.02

    gdp = max(economy.gdp, 1e-6)
    debt_gdp = economy.public_debt / gdp

    excess = max(0.0, debt_gdp - 0.6)
    spread_raw = 0.03 * excess + 0.10 * (excess**2)

    fragility = 1.0 - risk.regime_stability
    spread = spread_raw * (0.5 + 0.5 * risk.debt_crisis_prone) * (0.7 + 0.6 * fragility)

    contagion_spread = 0.0
    if world is not None:
        total_weight = 0.0
        stress_sum = 0.0
        for partner_id, rel in world.relations.get(agent.id, {}).items():
            partner = world.agents.get(partner_id)
            if partner is None:
                continue
            partner_gdp = max(partner.economy.gdp, 1e-6)
            partner_debt_gdp = partner.economy.public_debt / partner_gdp
            partner_excess = max(0.0, partner_debt_gdp - 0.9)
            partner_stress = partner_excess * partner.risk.debt_crisis_prone
            weight = max(0.0, effective_trade_intensity(rel))
            stress_sum += weight * partner_stress
            total_weight += weight
        if total_weight > 0.0:
            avg_partner_stress = stress_sum / total_weight
            contagion_spread = min(0.05, 0.02 * avg_partner_stress)

    rate = base_rate + min(spread, 0.25) + contagion_spread
    return float(max(0.0, min(rate, 0.35)))


def update_public_finances(agent: AgentState, world: WorldState) -> None:
    economy = agent.economy

    gdp = max(economy.gdp, 1e-6)

    # Baseline fiscal drivers to avoid mechanical debt repayment.
    base_social_share = 0.15
    base_military_share = 0.035
    climate_adaptation_share = 0.005 + 0.015 * max(0.0, agent.climate.climate_risk)
    economy.climate_adaptation_spending = gdp * climate_adaptation_share

    baseline_spending = gdp * (base_social_share + base_military_share + climate_adaptation_share)
    policy_spending = economy.social_spending + economy.military_spending + economy.rd_spending
    economy.gov_spending = max(0.0, baseline_spending + policy_spending)

    economy.taxes = 0.22 * gdp
    effective_rate = compute_effective_interest_rate(agent, world)
    economy.interest_payments = effective_rate * economy.public_debt

    primary_deficit = economy.gov_spending - economy.taxes
    total_deficit = primary_deficit + economy.interest_payments

    max_new_debt = 0.05 * gdp
    if total_deficit > 0:
        new_borrowing = min(total_deficit, max_new_debt)
    else:
        new_borrowing = 0.0
        economy.public_debt = max(0.0, economy.public_debt + total_deficit)

    economy.public_debt += new_borrowing

    economy.rd_spending *= 0.85
