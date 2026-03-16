from . import calibration_params as cal
from .climate import effective_damage_multiplier
from .core import AgentState, WorldState, clamp01, effective_trade_intensity
from .country_params import get_savings_rate, get_social_spend_share, get_tax_rate
from .metrics import update_tfp_endogenous


def _channel_disabled(world: WorldState | None, channel_name: str) -> bool:
    if world is None:
        return False
    disabled = getattr(world.global_state, "_ablation_disabled_channels", set())
    return channel_name in disabled


def _credit_zone_premium(zone: str) -> float:
    premiums = {
        "prime": 0.0,
        "investment": 0.0,
        "sub_investment": 0.020,
        "distressed": 0.060,
        "default": 0.150,
        "green": 0.0,
        "yellow": 0.020,
        "red": 0.060,
    }
    return float(premiums.get(zone, 0.0))


def update_capital_endogenous(agent: AgentState) -> None:
    economy = agent.economy
    risk = agent.risk

    # WRITES: economy.capital
    gdp = max(economy.gdp, 1e-6)
    capital = max(economy.capital, 1e-6)
    depreciation = cal.CAPITAL_DEPRECIATION

    base_savings = get_savings_rate(agent.name)
    stability = clamp01(risk.regime_stability)
    tension = clamp01(agent.society.social_tension)

    savings_rate = base_savings * (
        cal.SAVINGS_BASELINE_OFFSET
        + cal.SAVINGS_STABILITY_SENS * stability
        - cal.SAVINGS_TENSION_SENS * tension
    )
    savings_rate = max(cal.SAVINGS_MIN, min(cal.SAVINGS_MAX, savings_rate))

    investment = savings_rate * gdp
    economy.capital = max(1e-6, (1.0 - depreciation) * capital + investment)


def update_economy_output(agent: AgentState, world: WorldState) -> None:
    economy = agent.economy
    update_tfp_endogenous(agent, world)

    alpha = cal.ALPHA_CAPITAL
    beta = cal.BETA_LABOR
    gamma = cal.GAMMA_ENERGY

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
    tech_factor = 1.0 + cal.TECH_OUTPUT_SENS * max(0.0, tech_level - 1.0)
    gdp_potential = tfp * tech_factor * (capital**alpha) * (labor**beta) * (energy_input**gamma)

    if (not hasattr(economy, "_scale_factor")) or getattr(economy, "_scale_factor", None) is None:
        economy._scale_factor = economy.gdp / gdp_potential if gdp_potential > 0 else 1.0

    # WRITES: economy.gdp, economy.gdp_per_capita, economy.climate_damage_factor
    damage_multiplier = effective_damage_multiplier(agent, world)
    economy.climate_damage_factor = min(1.0, damage_multiplier)
    gdp_target = gdp_potential * economy._scale_factor * damage_multiplier
    if economy.climate_shock_years > 0:
        gdp_target *= max(0.0, 1.0 - economy.climate_shock_penalty)
        economy.climate_shock_years -= 1
        if economy.climate_shock_years <= 0:
            economy.climate_shock_penalty = 0.0

    # Endogenous catch-up: faster when realized GDP is below potential,
    # slower when above. No exogenous growth term is introduced.
    gdp_now = max(economy.gdp, 1e-6)
    gap = (gdp_target - gdp_now) / gdp_now
    adjust_speed = cal.GDP_ADJUST_SPEED_BASE + cal.GDP_ADJUST_SPEED_GAP_SENS * clamp01(max(0.0, gap))
    economy.gdp = (1.0 - adjust_speed) * economy.gdp + adjust_speed * gdp_target

    update_capital_endogenous(agent)

    if economy.population > 0:
        economy.gdp_per_capita = economy.gdp * 1e12 / economy.population


def compute_effective_interest_rate(agent: AgentState, world: WorldState | None = None) -> float:
    economy = agent.economy
    risk = agent.risk

    base_rate = cal.BASE_INTEREST_RATE

    gdp = max(economy.gdp, 1e-6)
    debt_gdp = economy.public_debt / gdp

    excess = max(0.0, debt_gdp - cal.DEBT_SPREAD_THRESHOLD)
    if _channel_disabled(world, "debt_spread_feedback"):
        spread_raw = 0.0
    else:
        spread_raw = cal.DEBT_SPREAD_LINEAR * excess + cal.DEBT_SPREAD_QUADRATIC * (excess**2)

    fragility = 1.0 - risk.regime_stability
    spread = spread_raw * (
        cal.DEBT_SPREAD_RISK_BASE + cal.DEBT_SPREAD_RISK_SENS * risk.debt_crisis_prone
    ) * (
        cal.DEBT_SPREAD_FRAGILITY_BASE + cal.DEBT_SPREAD_FRAGILITY_SENS * fragility
    )

    contagion_spread = 0.0
    if world is not None:
        if _channel_disabled(world, "debt_spread_feedback"):
            total_weight = 0.0
            stress_sum = 0.0
        else:
            total_weight = 0.0
            stress_sum = 0.0
            for partner_id, rel in world.relations.get(agent.id, {}).items():
                partner = world.agents.get(partner_id)
                if partner is None:
                    continue
                partner_gdp = max(partner.economy.gdp, 1e-6)
                partner_debt_gdp = partner.economy.public_debt / partner_gdp
                partner_excess = max(0.0, partner_debt_gdp - cal.CONTAGION_DEBT_THRESHOLD)
                partner_stress = partner_excess * partner.risk.debt_crisis_prone
                weight = max(0.0, effective_trade_intensity(rel))
                stress_sum += weight * partner_stress
                total_weight += weight
            if total_weight > 0.0:
                avg_partner_stress = stress_sum / total_weight
                contagion_spread = min(cal.CONTAGION_SPREAD_CAP, cal.CONTAGION_SPREAD_SENS * avg_partner_stress)

    zone = str(getattr(agent, "credit_zone", "investment"))
    if _channel_disabled(world, "credit_zone_premium"):
        zone_premium = 0.0
    else:
        zone_premium = _credit_zone_premium(zone)
    rate = base_rate + min(spread, cal.RATE_SPREAD_CAP) + contagion_spread + zone_premium
    return float(max(0.0, min(rate, cal.RATE_MAX)))


def update_public_finances(agent: AgentState, world: WorldState) -> None:
    economy = agent.economy

    gdp = max(economy.gdp, 1e-6)

    # Baseline fiscal drivers to avoid mechanical debt repayment.
    base_social_share = get_social_spend_share(agent.name)
    base_military_share = cal.MILITARY_SPEND_BASE
    climate_adaptation_share = cal.CLIMATE_ADAPT_BASE + cal.CLIMATE_ADAPT_RISK_SENS * max(
        0.0,
        agent.climate.climate_risk,
    )
    economy.climate_adaptation_spending = gdp * climate_adaptation_share

    baseline_spending = gdp * (base_social_share + base_military_share + climate_adaptation_share)
    policy_spending = economy.social_spending + economy.military_spending + economy.rd_spending
    economy.gov_spending = max(0.0, baseline_spending + policy_spending)

    economy.taxes = get_tax_rate(agent.name) * gdp
    effective_rate = compute_effective_interest_rate(agent, world)
    economy.interest_payments = effective_rate * economy.public_debt

    primary_deficit = economy.gov_spending - economy.taxes
    total_deficit = primary_deficit + economy.interest_payments

    max_new_debt = cal.MAX_NEW_DEBT_GDP * gdp
    if total_deficit > 0:
        new_borrowing = min(total_deficit, max_new_debt)
    else:
        new_borrowing = 0.0
        economy.public_debt = max(0.0, economy.public_debt + total_deficit)

    economy.public_debt += new_borrowing

    economy.rd_spending *= cal.RD_SPENDING_DECAY
