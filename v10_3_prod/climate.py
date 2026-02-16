import math
import random

from .core import CO2_PREINDUSTRIAL_GT, TGLOBAL_2023_C, AgentState, WorldState, clamp01


def update_global_climate(
    world: WorldState,
    co2_absorption_base: float = 20.0,
    co2_absorption_slope: float = 0.0,
    airborne_fraction: float = 0.5,
    climate_sensitivity: float = 0.00001,
    temp_inertia: float = 0.0,
) -> None:
    total_emissions = sum(agent.climate.co2_annual_emissions for agent in world.agents.values())

    co2_stock = world.global_state.co2
    sink_capacity = co2_absorption_base + co2_absorption_slope * max(
        0.0, co2_stock - CO2_PREINDUSTRIAL_GT
    )
    sink_capacity = max(0.0, sink_capacity)
    # Enforce an approximate airborne fraction: at least this share of emissions remains in the atmosphere.
    absorption_cap = max(0.0, total_emissions * (1.0 - airborne_fraction))
    absorption = min(sink_capacity, absorption_cap) if sink_capacity > 0.0 else absorption_cap
    world.global_state.co2 = max(
        co2_stock + total_emissions - absorption,
        CO2_PREINDUSTRIAL_GT,
    )

    delta_co2 = world.global_state.co2 - CO2_PREINDUSTRIAL_GT
    world.global_state.temperature_global += climate_sensitivity * delta_co2 - temp_inertia

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
        degradation = 0.01 * max(0.0, temp_increase) * agent.climate.climate_risk
        agent.climate.biodiversity_local = max(0.0, agent.climate.biodiversity_local - degradation)


def update_climate_risks(world: WorldState) -> None:
    delta_t = max(0.0, world.global_state.temperature_global - TGLOBAL_2023_C)
    for agent in world.agents.values():
        agent.climate.climate_risk = max(0.0, min(1.0, agent.climate.climate_risk + 0.05 * delta_t))


def apply_climate_extreme_events(
    world: WorldState,
    base_prob: float = 0.008,
    max_extra_prob: float = 0.04,
) -> None:
    temperature = world.global_state.temperature_global

    for agent in world.agents.values():
        risk = agent.climate.climate_risk
        if risk <= 0.0:
            continue

        # Endogenous resilience dampens both event likelihood and impact.
        # Better institutions, higher tech, and stronger trust improve coping capacity.
        tech_res = clamp01(agent.technology.tech_level / 2.0)
        resilience = clamp01(
            0.45 * agent.risk.regime_stability
            + 0.35 * tech_res
            + 0.20 * agent.society.trust_gov
        )

        extra_warming = max(0.0, temperature - TGLOBAL_2023_C)
        temp_factor = 1.0 + 0.15 * extra_warming
        event_prob = (base_prob + max_extra_prob * risk) * temp_factor
        event_prob *= 1.0 - 0.40 * resilience
        event_prob = min(0.5, max(0.0, event_prob))

        if random.random() >= event_prob:
            continue

        severity = 0.025 + 0.10 * risk
        severity *= 1.0 - 0.50 * resilience
        agent.economy.capital *= max(0.0, 1.0 - severity)

        pop_loss = (0.004 + 0.015 * risk) * (1.0 - 0.35 * resilience)
        agent.economy.population *= max(0.0, 1.0 - pop_loss)

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

    benefit_peak = 0.5
    max_benefit = 0.01
    benefit = max_benefit * math.exp(-((delta_t - benefit_peak) ** 2) / (2 * 0.5**2))

    loss = 0.003 * (temperature**2)
    return max(0.0, 1.0 + benefit - loss)


def effective_damage_multiplier(agent: AgentState, world: WorldState) -> float:
    base = climate_damage_multiplier(world.global_state.temperature_global)
    risk = agent.climate.climate_risk
    adjustment = 1.0 + 0.005 * (1.0 - risk)
    return max(0.0, base * adjustment)
