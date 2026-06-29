from typing import Dict, Optional

from .core import (
    RESOURCE_NAMES,
    WORLD_ANNUAL_SUPPLY_CAP_ZJ,
    WORLD_PROVEN_RESERVES_ZJ,
    WorldState,
)
from .params import resolve_params


def allocate_energy_reserves_and_caps(world: WorldState) -> Dict[str, Dict[str, float]]:
    global_energy_reserves = world.global_state.global_reserves.get(
        "energy", WORLD_PROVEN_RESERVES_ZJ
    )

    keys: Dict[str, float] = {}
    total_key = 0.0
    for agent_id, agent in world.agents.items():
        energy = agent.resources.get("energy")
        key = max(energy.own_reserve, 0.0) if energy is not None else 0.0
        keys[agent_id] = key
        total_key += key

    allocation: Dict[str, Dict[str, float]] = {}

    if total_key <= 0.0:
        count = max(len(world.agents), 1)
        for agent_id in world.agents:
            allocation[agent_id] = {
                "reserve_zj": global_energy_reserves / count,
                "prod_cap_zj_per_year": WORLD_ANNUAL_SUPPLY_CAP_ZJ / count,
            }
        return allocation

    for agent_id, key in keys.items():
        share = key / total_key
        allocation[agent_id] = {
            "reserve_zj": share * global_energy_reserves,
            "prod_cap_zj_per_year": share * WORLD_ANNUAL_SUPPLY_CAP_ZJ,
        }

    return allocation


def update_resource_stocks(
    world: WorldState,
    energy_alloc: Optional[Dict[str, Dict[str, float]]] = None,
    regen_params: Optional[Dict[str, float]] = None,
    tech_expansion_params: Optional[Dict[str, float]] = None,
    metals_recycling_rate: float = 0.45,
    metals_substitution_elasticity: float = 0.3,
    metals_price_ref: float = 1.0,
) -> None:
    if regen_params is None:
        regen_params = {"energy": 0.0, "food": 0.02, "metals": 0.0}
    if tech_expansion_params is None:
        tech_expansion_params = {"energy": 0.01, "food": 0.0, "metals": 0.005}

    total_primary_production: Dict[str, float] = {name: 0.0 for name in RESOURCE_NAMES}

    # [E3.1] Cost-minimizing energy demand: energy use responds to the energy *price level* with the
    # capital-energy substitution elasticity (E ∝ p_E^(-sigma_KE)). Implemented as a year-over-year
    # price-change response (adjust = (p_t/p_{t-1})^(-sigma)) so a CONSTANT price leaves demand
    # unchanged -- equivalent to a level response anchored at the initial price, and (critically)
    # non-compounding: a permanent price level gives a one-time demand shift, not an exponential
    # ratchet. (Using a fixed reference here compounds a constant price into runaway decay.)
    # Switchable; golden-safe (the 2015-2023 energy price barely moves from its initial level).
    cal = resolve_params(world)
    energy_demand_response = bool(getattr(cal, "ENERGY_DEMAND_PRICE_RESPONSE", False))
    energy_sigma = max(0.0, getattr(cal, "CES_SIGMA_KE", 0.4))
    energy_price_now = max(1e-6, float(world.global_state.prices.get("energy", 1.0)))
    energy_price_prev = max(1e-6, float(getattr(world.global_state, "_energy_demand_price_prev", energy_price_now)))
    energy_demand_adjust = (energy_price_now / energy_price_prev) ** (-energy_sigma)
    if energy_demand_response:
        world.global_state._energy_demand_price_prev = energy_price_now

    for agent_id, agent in world.agents.items():
        for resource_name in RESOURCE_NAMES:
            resource = agent.resources.get(resource_name)
            if resource is None:
                continue

            if resource_name == "energy" and energy_demand_response:
                resource.consumption = max(0.0, resource.consumption * energy_demand_adjust)

            if resource_name == "metals":
                price = world.global_state.prices.get("metals", metals_price_ref)
                if metals_substitution_elasticity > 0.0 and price > 0.0:
                    # Price-based substitution reduces metals demand when prices rise.
                    adjust = (price / metals_price_ref) ** (-metals_substitution_elasticity)
                    resource.consumption = max(0.0, resource.consumption * adjust)

            if resource_name == "energy" and energy_alloc is not None:
                caps = energy_alloc.get(
                    agent_id,
                    {"prod_cap_zj_per_year": WORLD_ANNUAL_SUPPLY_CAP_ZJ},
                )
                desired = max(0.0, resource.production)
                cap_year = caps["prod_cap_zj_per_year"]
                max_from_reserve = max(0.0, resource.own_reserve)
                production = min(desired, cap_year, max_from_reserve)
            else:
                production = max(0.0, resource.production)

            primary_production = production
            if resource_name == "metals":
                # Recycling adds secondary supply without depleting ore reserves.
                recycle_rate = max(0.0, min(0.9, metals_recycling_rate))
                recycled = recycle_rate * max(0.0, resource.consumption)
                production = production + recycled

            regen = regen_params.get(resource_name, 0.0) * max(resource.own_reserve, 0.0)
            tech_expansion = tech_expansion_params.get(resource_name, 0.0) * max(
                resource.own_reserve,
                0.0,
            )

            if resource_name == "food":
                new_reserve = resource.own_reserve + regen + tech_expansion
            else:
                new_reserve = resource.own_reserve - primary_production + regen + tech_expansion

            resource.own_reserve = max(0.0, new_reserve)
            resource.production = production
            total_primary_production[resource_name] += primary_production

    # T1.2 (Finding C-1): the global reserve ledger is the coherent aggregate of the country
    # ledgers — global_reserves[r] == sum_i own_reserve[r] — so it tracks the per-country
    # production/regen/tech flows exactly instead of evolving on a separate, divergent path
    # (which made the food/metals global pools floor at 0 within one year). Behaviour-preserving:
    # global_reserves only feeds the unused `reserve_zj` allocation field, not any dynamics.
    sync_global_reserves_from_agents(world)


def sync_global_reserves_from_agents(world: WorldState) -> None:
    """Set global_reserves[r] = sum over agents of own_reserve[r] (coherent aggregate)."""
    reserves = getattr(world.global_state, "global_reserves", None)
    if reserves is None:
        return
    for resource_name in RESOURCE_NAMES:
        total = 0.0
        for agent in world.agents.values():
            resource = agent.resources.get(resource_name)
            if resource is not None:
                total += max(0.0, float(resource.own_reserve))
        reserves[resource_name] = total


def update_global_resource_prices(
    world: WorldState,
    alpha: float = 0.15,
    min_price: float = 0.3,
    max_price: float = 5.0,
) -> None:
    epsilon = 1e-6

    supply: Dict[str, float] = {name: 0.0 for name in RESOURCE_NAMES}
    demand: Dict[str, float] = {name: 0.0 for name in RESOURCE_NAMES}

    for agent in world.agents.values():
        for resource_name in RESOURCE_NAMES:
            resource = agent.resources.get(resource_name)
            if resource is None:
                continue
            supply[resource_name] += max(0.0, resource.production)
            demand[resource_name] += max(0.0, resource.consumption)

    cal = resolve_params(world)
    clearing = getattr(cal, "MARKET_CLEARING", False)
    alpha = getattr(cal, "PRICE_ADJUST_ALPHA", alpha)
    eps = max(0.05, getattr(cal, "MARKET_DEMAND_ELASTICITY", 0.4))

    for resource_name in RESOURCE_NAMES:
        current_price = world.global_state.prices.get(resource_name, 1.0)
        if clearing:
            # [F2.2] within-period clearing: set price so constant-elasticity demand == supply.
            # demand(p) = D0*(p/p_cur)^(-eps) == supply  ->  p* = p_cur*(D0/supply)^(1/eps).
            ratio = (demand[resource_name] + epsilon) / (supply[resource_name] + epsilon)
            next_price = current_price * (ratio ** (1.0 / eps))
        else:
            imbalance = (demand[resource_name] - supply[resource_name]) / (
                supply[resource_name] + epsilon
            )
            next_price = current_price * (1.0 + alpha * imbalance)
        world.global_state.prices[resource_name] = max(
            min_price,
            min(max_price, next_price),
        )
