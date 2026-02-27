import math
import random

from .core import (
    CO2_PREINDUSTRIAL_GT,
    F2XCO2_W_M2,
    GTCO2_PER_PPM,
    TGLOBAL_2023_C,
    AgentState,
    WorldState,
    clamp01,
)

CARBON_POOL_FRACTIONS = (0.2173, 0.2240, 0.2824, 0.2763)
CARBON_POOL_TIMESCALES = (math.inf, 394.4, 36.54, 4.304)
DEFAULT_ECS = 3.0
ECS_MIN = 1.5
ECS_MAX = 4.0
DEFAULT_F_NONCO2 = 0.0
DEFAULT_HEAT_CAP_SURFACE = 20.0
DEFAULT_HEAT_CAP_DEEP = 100.0
DEFAULT_OCEAN_EXCHANGE = 0.7
EMISSIONS_SCALE = 1.8
TECH_DECARB_K = 0.12
DECARB_RATE = 0.049


def _climate_resilience(agent: AgentState) -> float:
    tech_res = clamp01(agent.technology.tech_level / 2.0)
    gdp = max(agent.economy.gdp, 1e-6)
    adapt_spend = getattr(agent.economy, "climate_adaptation_spending", 0.0)
    adapt_share = max(0.0, adapt_spend) / gdp
    adapt_res = clamp01(adapt_share / 0.03)
    return clamp01(
        0.40 * agent.risk.regime_stability
        + 0.30 * tech_res
        + 0.15 * agent.society.trust_gov
        + 0.15 * adapt_res
    )


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
            base_intensity = 0.02
        agent.climate._co2_intensity_base = base_intensity

    tech = max(0.5, agent.technology.tech_level)
    tech_factor = math.exp(-TECH_DECARB_K * max(0.0, tech - 1.0))
    energy = agent.resources.get("energy")
    efficiency = max(0.5, energy.efficiency) if energy is not None else 1.0
    efficiency_factor = 1.0 / efficiency

    time_factor = math.exp(-DECARB_RATE * max(0.0, time))
    tax_effect = 1.0 - 0.12 * fuel_tax_change
    tax_effect = min(1.4, max(0.6, tax_effect))
    intensity = base_intensity * tech_factor * efficiency_factor * time_factor * tax_effect
    reduction = max(0.0, min(0.9, policy_reduction))
    agent.climate.co2_annual_emissions = max(
        0.0,
        gdp * intensity * (1.0 - reduction) * EMISSIONS_SCALE,
    )


def _normalize_fractions(fractions: tuple[float, ...]) -> list[float]:
    total = sum(fractions)
    if total <= 0.0:
        return [1.0]
    return [f / total for f in fractions]


def _init_carbon_pools(world: WorldState, fractions: list[float]) -> None:
    excess = max(0.0, world.global_state.co2 - CO2_PREINDUSTRIAL_GT)
    world.global_state.carbon_pools = [excess * frac for frac in fractions]


def update_global_climate(
    world: WorldState,
    dt: float = 1.0,
    ecs: float = DEFAULT_ECS,
    f_nonco2: float = DEFAULT_F_NONCO2,
    heat_cap_surface: float = DEFAULT_HEAT_CAP_SURFACE,
    heat_cap_deep: float = DEFAULT_HEAT_CAP_DEEP,
    ocean_exchange: float = DEFAULT_OCEAN_EXCHANGE,
    carbon_pool_fractions: tuple[float, ...] = CARBON_POOL_FRACTIONS,
    carbon_pool_timescales: tuple[float, ...] = CARBON_POOL_TIMESCALES,
) -> None:
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
    f_co2 = 5.35 * math.log(c_ppm / c0_ppm)
    f_total = f_co2 + f_nonco2
    world.global_state.forcing_total = f_total

    ecs = min(max(ECS_MIN, ecs), ECS_MAX)
    climate_feedback = F2XCO2_W_M2 / ecs
    t_surface = world.global_state.temperature_global
    t_ocean = world.global_state.temperature_ocean
    dts = (f_total - climate_feedback * t_surface - ocean_exchange * (t_surface - t_ocean))
    dts *= dt / max(heat_cap_surface, 1e-6)
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
        effective_risk = clamp01(agent.climate.climate_risk) * (1.0 - 0.60 * resilience)
        degradation = 0.004 * max(0.0, temp_increase) * effective_risk
        agent.climate.biodiversity_local = max(0.0, agent.climate.biodiversity_local - degradation)


def update_climate_risks(
    world: WorldState,
    response_rate: float = 0.06,
    sensitivity: float = 0.45,
    base_const: float = 0.3,
    base_water: float = 0.45,
    base_gini: float = 0.15,
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
    base_prob: float = 0.012,
    max_extra_prob: float = 0.07,
) -> None:
    temperature = world.global_state.temperature_global

    for agent in world.agents.values():
        risk = agent.climate.climate_risk
        if risk <= 0.0:
            continue

        # Endogenous resilience dampens both event likelihood and impact.
        # Better institutions, higher tech, and stronger trust improve coping capacity.
        resilience = _climate_resilience(agent)

        extra_warming = max(0.0, temperature - TGLOBAL_2023_C)
        temp_factor = 1.0 + 0.15 * extra_warming
        event_prob = (base_prob + max_extra_prob * risk) * temp_factor
        event_prob *= 1.0 - 0.40 * resilience
        event_prob = min(0.5, max(0.0, event_prob))

        if random.random() >= event_prob:
            continue

        severity = 0.03 + 0.15 * risk
        severity *= 1.0 - 0.50 * resilience
        agent.economy.capital *= max(0.0, 1.0 - severity)

        pop_loss = (0.004 + 0.015 * risk) * (1.0 - 0.35 * resilience)
        agent.economy.population *= max(0.0, 1.0 - pop_loss)

        shock_penalty = min(0.10, 0.5 * severity)
        agent.economy.climate_shock_years = max(agent.economy.climate_shock_years, 2)
        agent.economy.climate_shock_penalty = max(
            agent.economy.climate_shock_penalty,
            shock_penalty,
        )

        tension_jump = (0.03 + 0.10 * risk) * (1.0 - 0.35 * resilience)
        agent.society.social_tension = min(1.0, agent.society.social_tension + tension_jump)
        if agent.risk.regime_stability > 0.6:
            trust_delta = 0.02 + 0.02 * resilience
            agent.society.trust_gov = min(1.0, agent.society.trust_gov + trust_delta)
        else:
            trust_delta = 0.02 + 0.03 * risk
            agent.society.trust_gov = max(0.0, agent.society.trust_gov - trust_delta)


def climate_damage_multiplier(temperature: float) -> float:
    delta_t = temperature - TGLOBAL_2023_C

    benefit_peak = 0.3
    max_benefit = 0.006
    benefit = max_benefit * math.exp(-((delta_t - benefit_peak) ** 2) / (2 * 0.5**2))

    loss = 0.006 * (temperature**2)
    return max(0.0, 1.0 + benefit - loss)


def effective_damage_multiplier(agent: AgentState, world: WorldState) -> float:
    base = climate_damage_multiplier(world.global_state.temperature_global)
    risk = agent.climate.climate_risk
    adjustment = 1.0 + 0.005 * (1.0 - risk)
    return max(0.0, base * adjustment)
