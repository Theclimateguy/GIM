import math
import random

from . import calibration_params as cal
from .core import (
    CO2_PREINDUSTRIAL_GT,
    F2XCO2_W_M2,
    GTCO2_PER_PPM,
    TGLOBAL_2023_C,
    AgentState,
    WorldState,
    clamp01,
)


def _climate_resilience(agent: AgentState) -> float:
    tech_res = clamp01(agent.technology.tech_level / cal.RESILIENCE_TECH_REF)
    gdp = max(agent.economy.gdp, 1e-6)
    adapt_spend = getattr(agent.economy, "climate_adaptation_spending", 0.0)
    adapt_share = max(0.0, adapt_spend) / gdp
    adapt_res = clamp01(adapt_share / cal.RESILIENCE_ADAPT_REF)
    return clamp01(
        cal.RESILIENCE_STABILITY_W * agent.risk.regime_stability
        + cal.RESILIENCE_TECH_W * tech_res
        + cal.RESILIENCE_TRUST_W * agent.society.trust_gov
        + cal.RESILIENCE_ADAPT_W * adapt_res
    )


def _structural_transition_multiplier(
    policy_reduction: float,
    fuel_tax_change: float,
) -> float:
    multiplier = 1.0 + cal.STRUCTURAL_TRANSITION_POLICY_SENS * max(0.0, policy_reduction)
    multiplier += cal.STRUCTURAL_TRANSITION_TAX_SENS * max(0.0, fuel_tax_change)
    return min(cal.STRUCTURAL_TRANSITION_MULT_MAX, max(cal.STRUCTURAL_TRANSITION_MULT_MIN, multiplier))


def update_emissions_from_economy(
    agent: AgentState,
    time: int,
    policy_reduction: float = 0.0,
    fuel_tax_change: float = 0.0,
) -> None:
    gdp = max(agent.economy.gdp, 1e-6)
    base_intensity = getattr(agent.climate, "_co2_intensity_base", None)
    if base_intensity is None or base_intensity <= 0.0:
        base_intensity = agent.climate.co2_annual_emissions / gdp
        if base_intensity <= 0.0:
            base_intensity = cal.CO2_INTENSITY_FLOOR
        agent.climate._co2_intensity_base = base_intensity

    tech = max(0.5, agent.technology.tech_level)
    tech_factor = math.exp(-cal.TECH_DECARB_K * max(0.0, tech - 1.0))
    energy = agent.resources.get("energy")
    efficiency = max(0.5, energy.efficiency) if energy is not None else 1.0
    efficiency_factor = 1.0 / efficiency

    stored_progress = getattr(agent.climate, "_structural_transition_progress", None)
    if stored_progress is None:
        structural_progress = max(0.0, float(time))
    else:
        structural_progress = max(max(0.0, float(time)), float(stored_progress))

    structural_multiplier = _structural_transition_multiplier(policy_reduction, fuel_tax_change)
    structural_transition = math.exp(-cal.DECARB_RATE_STRUCTURAL * structural_progress)
    tax_effect = 1.0 - cal.FUEL_TAX_EMISSIONS_SENS * fuel_tax_change
    tax_effect = min(cal.FUEL_TAX_EFFECT_MAX, max(cal.FUEL_TAX_EFFECT_MIN, tax_effect))
    intensity = base_intensity * tech_factor * efficiency_factor * structural_transition * tax_effect
    reduction = max(0.0, min(cal.POLICY_REDUCTION_MAX, policy_reduction))
    agent.climate.co2_annual_emissions = max(
        0.0,
        gdp * intensity * (1.0 - reduction) * cal.EMISSIONS_SCALE,
    )
    # Structural transition is cumulative and path-dependent: policy tools should
    # accelerate future decarbonization rather than retroactively rewrite past years.
    agent.climate._structural_transition_progress = structural_progress + structural_multiplier


def _normalize_fractions(fractions: tuple[float, ...]) -> list[float]:
    total = sum(fractions)
    if total <= 0.0:
        return [1.0]
    return [f / total for f in fractions]


def _init_carbon_pools(world: WorldState, fractions: list[float]) -> None:
    excess = max(0.0, world.global_state.co2 - CO2_PREINDUSTRIAL_GT)
    world.global_state.carbon_pools = [excess * frac for frac in fractions]


def _resolve_nonco2_forcing(world: WorldState, f_nonco2: float | None) -> float:
    if f_nonco2 is not None:
        return max(0.0, f_nonco2)
    base_year = getattr(world.global_state, "_calendar_year_base", 2023)
    year = base_year + max(0, int(world.time))
    year_offset = year - cal.F_NONCO2_BASE_YEAR
    forcing = cal.F_NONCO2_DEFAULT + cal.F_NONCO2_TREND * year_offset
    return max(0.0, forcing)


def _resolve_temperature_variability_sigma(world: WorldState) -> float:
    override = getattr(world.global_state, "_temperature_variability_sigma", None)
    if override is not None:
        return max(0.0, float(override))
    if not getattr(world.global_state, "_enable_temperature_variability", False):
        return 0.0
    return max(0.0, cal.TEMP_NATURAL_VARIABILITY_SIGMA)


def _sample_temperature_variability(world: WorldState, dt: float) -> float:
    if dt <= 0.0:
        return 0.0
    sigma = _resolve_temperature_variability_sigma(world)
    if sigma <= 0.0:
        return 0.0
    base_year = getattr(world.global_state, "_calendar_year_base", 2023)
    seed_base = int(getattr(world.global_state, "_temperature_variability_seed", 0))
    sign = float(getattr(world.global_state, "_temperature_variability_sign", 1.0))
    year = base_year + max(0, int(world.time))
    rng = random.Random(seed_base + year)
    return sign * rng.gauss(0.0, sigma * math.sqrt(dt))


def update_global_climate(
    world: WorldState,
    dt: float = 1.0,
    ecs: float | None = None,
    f_nonco2: float | None = None,
    heat_cap_surface: float | None = None,
    heat_cap_deep: float | None = None,
    ocean_exchange: float | None = None,
    carbon_pool_fractions: tuple[float, ...] | None = None,
    carbon_pool_timescales: tuple[float, ...] | None = None,
) -> None:
    if ecs is None:
        ecs = cal.ECS_DEFAULT
    if heat_cap_surface is None:
        heat_cap_surface = cal.HEAT_CAP_SURFACE
    if heat_cap_deep is None:
        heat_cap_deep = cal.HEAT_CAP_DEEP
    if ocean_exchange is None:
        ocean_exchange = cal.OCEAN_EXCHANGE
    if carbon_pool_fractions is None:
        carbon_pool_fractions = cal.CARBON_POOL_FRACTIONS
    if carbon_pool_timescales is None:
        carbon_pool_timescales = cal.CARBON_POOL_TIMESCALES

    total_emissions = sum(agent.climate.co2_annual_emissions for agent in world.agents.values())

    fractions = _normalize_fractions(carbon_pool_fractions)
    timescales = list(carbon_pool_timescales)
    if len(timescales) < len(fractions):
        timescales.extend([math.inf] * (len(fractions) - len(timescales)))
    elif len(timescales) > len(fractions):
        timescales = timescales[: len(fractions)]

    pools = world.global_state.carbon_pools
    if len(pools) != len(fractions):
        _init_carbon_pools(world, fractions)
        pools = world.global_state.carbon_pools

    new_pools = []
    for pool, frac, tau in zip(pools, fractions, timescales):
        if not math.isfinite(tau) or tau <= 0.0:
            decay = 1.0
        else:
            decay = math.exp(-dt / tau)
        new_pools.append(pool * decay + frac * total_emissions)
    world.global_state.carbon_pools = new_pools
    world.global_state.co2 = max(
        CO2_PREINDUSTRIAL_GT + sum(new_pools),
        CO2_PREINDUSTRIAL_GT,
    )

    c_ppm = max(1e-6, world.global_state.co2 / GTCO2_PER_PPM)
    c0_ppm = CO2_PREINDUSTRIAL_GT / GTCO2_PER_PPM
    f_co2 = cal.FORCING_LOG_COEFF * math.log(c_ppm / c0_ppm)
    f_nonco2 = _resolve_nonco2_forcing(world, f_nonco2)
    f_total = f_co2 + f_nonco2
    world.global_state.forcing_total = f_total

    ecs = min(max(cal.ECS_MIN, ecs), cal.ECS_MAX)
    climate_feedback = F2XCO2_W_M2 / ecs
    t_surface = world.global_state.temperature_global
    t_ocean = world.global_state.temperature_ocean
    dts = (f_total - climate_feedback * t_surface - ocean_exchange * (t_surface - t_ocean))
    dts *= dt / max(heat_cap_surface, 1e-6)
    dts += _sample_temperature_variability(world, dt)
    dtd = ocean_exchange * (t_surface - t_ocean) * dt / max(heat_cap_deep, 1e-6)
    world.global_state.temperature_global = t_surface + dts
    world.global_state.temperature_ocean = t_ocean + dtd

    total_weight = 0.0
    weighted_bio = 0.0
    for agent in world.agents.values():
        weight = agent.economy.population**0.3
        total_weight += weight
        weighted_bio += agent.climate.biodiversity_local * weight
    if total_weight > 0:
        world.global_state.biodiversity_index = weighted_bio / total_weight

    temp_increase = world.global_state.temperature_global - TGLOBAL_2023_C
    for agent in world.agents.values():
        resilience = _climate_resilience(agent)
        effective_risk = clamp01(agent.climate.climate_risk) * (
            1.0 - cal.BIODIVERSITY_RISK_DAMP * resilience
        )
        degradation = cal.BIODIVERSITY_TEMP_DAMAGE * max(0.0, temp_increase) * effective_risk
        agent.climate.biodiversity_local = max(0.0, agent.climate.biodiversity_local - degradation)


def update_climate_risks(
    world: WorldState,
    response_rate: float = cal.CRISK_RESPONSE_RATE,
    sensitivity: float = cal.CRISK_TEMP_SENSITIVITY,
    base_const: float = cal.CRISK_BASE_CONST,
    base_water: float = cal.CRISK_WATER_WEIGHT,
    base_gini: float = cal.CRISK_GINI_WEIGHT,
) -> None:
    delta_t = max(0.0, world.global_state.temperature_global - TGLOBAL_2023_C)
    for agent in world.agents.values():
        base = base_const + base_water * agent.risk.water_stress
        base += base_gini * (agent.society.inequality_gini / 100.0)
        base = clamp01(base)
        temp_component = 1.0 - math.exp(-sensitivity * delta_t)
        target = clamp01(base + (1.0 - base) * temp_component)
        agent.climate.climate_risk = clamp01(
            agent.climate.climate_risk + response_rate * (target - agent.climate.climate_risk)
        )


def apply_climate_extreme_events(
    world: WorldState,
    base_prob: float = cal.EVENT_BASE_PROB,
    max_extra_prob: float = cal.EVENT_MAX_EXTRA_PROB,
) -> None:
    # WRITES: economy.capital, economy.population, economy.climate_shock_years,
    # economy.climate_shock_penalty, society.social_tension, society.trust_gov
    temperature = world.global_state.temperature_global

    for agent in world.agents.values():
        risk = agent.climate.climate_risk
        if risk <= 0.0:
            continue

        # Endogenous resilience dampens both event likelihood and impact.
        # Better institutions, higher tech, and stronger trust improve coping capacity.
        resilience = _climate_resilience(agent)

        extra_warming = max(0.0, temperature - TGLOBAL_2023_C)
        temp_factor = 1.0 + cal.EVENT_TEMP_WARMING_SENS * extra_warming
        event_prob = (base_prob + max_extra_prob * risk) * temp_factor
        event_prob *= 1.0 - cal.EVENT_RESILIENCE_DAMP * resilience
        event_prob = min(cal.EVENT_PROB_MAX, max(0.0, event_prob))

        if random.random() >= event_prob:
            continue

        severity = cal.EVENT_SEVERITY_BASE + cal.EVENT_SEVERITY_RISK_SENS * risk
        severity *= 1.0 - cal.EVENT_SEVERITY_RESILIENCE_DAMP * resilience
        agent.economy.capital *= max(0.0, 1.0 - severity)

        pop_loss = (cal.EVENT_POP_LOSS_BASE + cal.EVENT_POP_LOSS_RISK_SENS * risk) * (
            1.0 - cal.EVENT_POP_RESILIENCE_DAMP * resilience
        )
        agent.economy.population *= max(0.0, 1.0 - pop_loss)

        shock_penalty = min(cal.EVENT_SHOCK_PENALTY_CAP, cal.EVENT_SHOCK_PENALTY_SEVERITY_SENS * severity)
        agent.economy.climate_shock_years = max(
            agent.economy.climate_shock_years,
            cal.EVENT_SHOCK_YEARS,
        )
        agent.economy.climate_shock_penalty = max(
            agent.economy.climate_shock_penalty,
            shock_penalty,
        )

        tension_jump = (cal.EVENT_TENSION_JUMP_BASE + cal.EVENT_TENSION_JUMP_RISK_SENS * risk) * (
            1.0 - cal.EVENT_POP_RESILIENCE_DAMP * resilience
        )
        agent.society.social_tension = min(1.0, agent.society.social_tension + tension_jump)
        if agent.risk.regime_stability > cal.EVENT_TRUST_STABILITY_THRESHOLD:
            trust_delta = cal.EVENT_TRUST_REWARD_BASE + cal.EVENT_TRUST_REWARD_RESILIENCE_SENS * resilience
            agent.society.trust_gov = min(1.0, agent.society.trust_gov + trust_delta)
        else:
            trust_delta = cal.EVENT_TRUST_PENALTY_BASE + cal.EVENT_TRUST_PENALTY_RISK_SENS * risk
            agent.society.trust_gov = max(0.0, agent.society.trust_gov - trust_delta)


def climate_damage_multiplier(temperature: float) -> float:
    delta_t = temperature - TGLOBAL_2023_C

    benefit = cal.DAMAGE_BENEFIT_MAX * math.exp(
        -((delta_t - cal.DAMAGE_BENEFIT_PEAK) ** 2) / (2 * cal.DAMAGE_BENEFIT_STDDEV**2)
    )

    loss = cal.DAMAGE_QUAD_COEFF * (temperature**2)
    return max(0.0, 1.0 + benefit - loss)


def effective_damage_multiplier(agent: AgentState, world: WorldState) -> float:
    base = climate_damage_multiplier(world.global_state.temperature_global)
    risk = agent.climate.climate_risk
    adjustment = 1.0 + cal.DAMAGE_RISK_ADJ * (1.0 - risk)
    return max(0.0, base * adjustment)
