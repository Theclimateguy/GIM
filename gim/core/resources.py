from typing import Dict, Optional

from .core import (
    RESOURCE_NAMES,
    WORLD_ANNUAL_SUPPLY_CAP_ZJ,
    WORLD_PROVEN_RESERVES_ZJ,
    WorldState,
)


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

    for agent_id, agent in world.agents.items():
        for resource_name in RESOURCE_NAMES:
            resource = agent.resources.get(resource_name)
            if resource is None:
                continue

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

    if (
        not hasattr(world.global_state, "global_reserves")
        or world.global_state.global_reserves is None
    ):
        return

    for resource_name in RESOURCE_NAMES:
        global_reserve = world.global_state.global_reserves.get(resource_name, 0.0)
        total_production = total_primary_production.get(resource_name, 0.0)

        regen_global = regen_params.get(resource_name, 0.0) * max(global_reserve, 0.0)
        tech_global = tech_expansion_params.get(resource_name, 0.0) * max(global_reserve, 0.0)
        world.global_state.global_reserves[resource_name] = max(
            0.0,
            global_reserve - total_production + regen_global + tech_global,
        )


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

    for resource_name in RESOURCE_NAMES:
        current_price = world.global_state.prices.get(resource_name, 1.0)
        imbalance = (demand[resource_name] - supply[resource_name]) / (
            supply[resource_name] + epsilon
        )
        next_price = current_price * (1.0 + alpha * imbalance)
        world.global_state.prices[resource_name] = max(
            min_price,
            min(max_price, next_price),
        )
