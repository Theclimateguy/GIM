import math
from typing import Dict, Optional

from .core import (
    RESOURCE_NAMES,
    WORLD_ANNUAL_SUPPLY_CAP_ZJ,
    WORLD_PROVEN_RESERVES_ZJ,
    WorldState,
)
from .params import resolve_params


# The physical world annual-supply cap (WORLD_ANNUAL_SUPPLY_CAP_ZJ, in ZJ) is anchored
# to the model's energy *index* by the base-year world production, so the cap acts as a
# real growth ceiling sitting this multiple above current output. Before this, the ZJ
# cap was min()-compared directly against index-scale production (~1e4), collapsing
# effective supply to ~0.65 and slamming the energy price into its cap on step 1 — a
# units bug, not a calibration choice. Reserves still bind long-run via `own_reserve`.
ENERGY_ANNUAL_CAP_HEADROOM = 1.5


def normalize_resource_scales_forward(world: WorldState) -> None:
    """Forward-projection init: correct two resource-block scale issues in the state so the
    forward markets are functional. Called ONLY on the forward member path (not the raw loader,
    the game/geo calibration, or the historical backtest) and only ever scales UP — so the
    validated surfaces stay byte-identical. Idempotent.

    1) ENERGY reserves imply only ~7 yr of cover at the index production rate; scale them to the
       physical proven-reserves / annual-supply horizon (~50 yr), else the stock binds production
       within a decade -> supply collapses -> the energy price hits its cap -> a near-term GDP dip.
    2) METALS production is understated ~4.7x vs consumption (a top producer like China shows
       prod << cons), so the market never clears: price slams to the floor, production runs away,
       and resource-stress climbs. Scale metals production AND reserve to the consumption scale so
       the market balances and reserve-cover (years) is preserved.
    """
    # 1) Energy reserves -> PER-AGENT physical horizon. The state lists ~7 yr of cover globally,
    #    but most importers only ~2-3 yr — and a single *global* scale factor (the global ratio is
    #    dominated by a few big reserve-holders) leaves those importers short. Within a decade an
    #    importer's reserve then binds its production (production = min(desired, cap, own_reserve));
    #    supply falls below demand, the energy price spikes mid-horizon, forward emissions drop, CO2
    #    draws down and the temperature fan's lower tail cools. Lift EACH agent to the proven-reserves
    #    horizon (scale UP only) so no agent depletes in-horizon and forward energy supply stays put.
    horizon_years = WORLD_PROVEN_RESERVES_ZJ / max(WORLD_ANNUAL_SUPPLY_CAP_ZJ, 1e-9)
    for agent in world.agents.values():
        energy = agent.resources.get("energy")
        if energy is not None and energy.production > 0.0:
            target = energy.production * horizon_years
            if energy.own_reserve < target:
                energy.own_reserve = target

    # 2) Metals production/reserve -> balance the market with consumption.
    m_prod = m_cons = 0.0
    for agent in world.agents.values():
        metals = agent.resources.get("metals")
        if metals is not None:
            m_prod += max(0.0, metals.production)
            m_cons += max(0.0, metals.consumption)
    if m_prod > 0.0 and m_cons > m_prod:
        factor = m_cons / m_prod
        for agent in world.agents.values():
            metals = agent.resources.get("metals")
            if metals is not None:
                metals.production *= factor
                metals.own_reserve *= factor

    # 3) FOOD consumption -> balance the market with production. Base-year food consumption is
    #    understated ~0.64x vs production (a frozen base demand that never tracked population), so the
    #    food market is permanently over-supplied and its price pins to the floor. Scale EVERY agent's
    #    food consumption up by the single global prod/cons ratio (mirrors the metals balance above,
    #    inverted) so the global market clears at the base year while each agent's importer/exporter
    #    position is preserved; demand growth then tracks population from a balanced start. Scale UP
    #    only, so the validated base-year production surface is untouched.
    f_prod = f_cons = 0.0
    for agent in world.agents.values():
        food = agent.resources.get("food")
        if food is not None:
            f_prod += max(0.0, food.production)
            f_cons += max(0.0, food.consumption)
    if f_cons > 0.0 and f_prod > f_cons:
        factor = f_prod / f_cons
        for agent in world.agents.values():
            food = agent.resources.get("food")
            if food is not None:
                food.consumption *= factor

    sync_global_reserves_from_agents(world)


def allocate_energy_reserves_and_caps(world: WorldState) -> Dict[str, Dict[str, float]]:
    global_energy_reserves = world.global_state.global_reserves.get(
        "energy", WORLD_PROVEN_RESERVES_ZJ
    )

    # Base-year world energy production (index units), captured once. The physical ZJ
    # annual cap is expressed as this many index-units so it is commensurate with the
    # production it constrains.
    base_prod = getattr(world.global_state, "_energy_base_production_index", None)
    if base_prod is None:
        base_prod = sum(
            max(0.0, energy.production)
            for agent in world.agents.values()
            if (energy := agent.resources.get("energy")) is not None
        )
        world.global_state._energy_base_production_index = base_prod
    global_cap_index = max(base_prod, 1e-9) * ENERGY_ANNUAL_CAP_HEADROOM

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
                "prod_cap_zj_per_year": global_cap_index / count,
            }
        return allocation

    for agent_id, key in keys.items():
        share = key / total_key
        # Reserve-share of the global ceiling, but never below the agent's current
        # output, so the cap can only constrain *growth*, never throttle current supply.
        energy = world.agents[agent_id].resources.get("energy")
        current_prod = max(0.0, energy.production) if energy is not None else 0.0
        allocation[agent_id] = {
            "reserve_zj": share * global_energy_reserves,
            "prod_cap_zj_per_year": max(share * global_cap_index, current_prod),
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

    # Metals substitution, made NON-COMPOUNDING (year-over-year, like energy above): a
    # constant price now leaves demand unchanged. The previous fixed-reference form
    # (p/p_ref)^(-e) compounded a constant off-reference price into an exponential demand
    # ratchet — exactly the runaway the energy comment warns about — which, combined with the
    # understated metals supply, blew metals consumption/production up ~30x over a decade.
    metals_price_now = max(1e-6, float(world.global_state.prices.get("metals", metals_price_ref)))
    metals_price_prev = max(1e-6, float(getattr(world.global_state, "_metals_demand_price_prev", metals_price_now)))
    metals_demand_adjust = (metals_price_now / metals_price_prev) ** (-metals_substitution_elasticity)
    world.global_state._metals_demand_price_prev = metals_price_now

    # [F2.4] Resource demand growth. Consumption tracks realized population and per-capita income
    # growth (per-resource elasticities) instead of sitting frozen at its base-year level, which
    # otherwise permanently over-supplied food (demand never grew with population) and understated
    # metals demand -> prices pinned to the floor. Growth is realized with a one-year lag (economy
    # and population update later in the step) and uses per-agent prev pop/income kept on
    # global_state; the first year has no prior -> factor 1, so the base year is unchanged.
    demand_pop_elas = {
        "energy": getattr(cal, "ENERGY_DEMAND_POP_ELASTICITY", 0.0),
        "food": getattr(cal, "FOOD_DEMAND_POP_ELASTICITY", 0.0),
        "metals": getattr(cal, "METALS_DEMAND_POP_ELASTICITY", 0.0),
    }
    demand_income_elas = {
        "energy": getattr(cal, "ENERGY_DEMAND_INCOME_ELASTICITY", 0.0),
        "food": getattr(cal, "FOOD_DEMAND_INCOME_ELASTICITY", 0.0),
        "metals": getattr(cal, "METALS_DEMAND_INCOME_ELASTICITY", 0.0),
    }
    demand_growth_on = any(v != 0.0 for v in demand_pop_elas.values()) or any(
        v != 0.0 for v in demand_income_elas.values()
    )
    growth_min = getattr(cal, "RESOURCE_DEMAND_GROWTH_MIN", 0.8)
    growth_max = getattr(cal, "RESOURCE_DEMAND_GROWTH_MAX", 1.25)
    pop_prev = getattr(world.global_state, "_resource_demand_pop_prev", {})
    gdppc_prev = getattr(world.global_state, "_resource_demand_gdppc_prev", {})
    next_pop_prev: Dict[str, float] = {}
    next_gdppc_prev: Dict[str, float] = {}

    for agent_id, agent in world.agents.items():
        # [F2.4] realized per-agent pop / per-capita-income growth since the last step.
        pop = max(0.0, float(getattr(agent.economy, "population", 0.0)))
        gdp = max(0.0, float(getattr(agent.economy, "gdp", 0.0)))
        gdp_pc = gdp / pop if pop > 0.0 else 0.0
        prev_pop = pop_prev.get(agent_id)
        prev_gdppc = gdppc_prev.get(agent_id)
        if demand_growth_on and prev_pop and prev_pop > 0.0 and prev_gdppc and prev_gdppc > 0.0:
            pop_growth = pop / prev_pop
            income_growth = gdp_pc / prev_gdppc
        else:
            pop_growth = 1.0
            income_growth = 1.0
        next_pop_prev[agent_id] = pop
        next_gdppc_prev[agent_id] = gdp_pc

        for resource_name in RESOURCE_NAMES:
            resource = agent.resources.get(resource_name)
            if resource is None:
                continue

            # [F2.4] grow base demand with realized population + per-capita income (clamped band).
            if demand_growth_on:
                growth_factor = (pop_growth ** demand_pop_elas[resource_name]) * (
                    income_growth ** demand_income_elas[resource_name]
                )
                growth_factor = min(growth_max, max(growth_min, growth_factor))
                resource.consumption = max(0.0, resource.consumption * growth_factor)

            if resource_name == "energy" and energy_demand_response:
                resource.consumption = max(0.0, resource.consumption * energy_demand_adjust)

            if resource_name == "metals" and metals_substitution_elasticity > 0.0:
                # Price-based substitution reduces metals demand when prices rise (non-compounding).
                resource.consumption = max(0.0, resource.consumption * metals_demand_adjust)

            # [F2.4b] Desired PRIMARY production carried forward is last year's primary output only,
            # NOT the total output including recycled secondary supply. Storing the recycled-inclusive
            # total as the desired base (as before) let recycling compound into the primary base every
            # year -> metals supply ran away ~20x over the horizon -> D/S collapsed -> price pinned to
            # the floor. First year has no stored primary, so fall back to the loaded production
            # (== base-year primary, no recycling yet) -> base year unchanged.
            prev_primary = getattr(resource, "_primary_production", None)
            desired_base = prev_primary if prev_primary is not None else max(0.0, resource.production)

            if resource_name == "energy" and energy_alloc is not None:
                caps = energy_alloc.get(
                    agent_id,
                    {"prod_cap_zj_per_year": WORLD_ANNUAL_SUPPLY_CAP_ZJ},
                )
                cap_year = caps["prod_cap_zj_per_year"]
                max_from_reserve = max(0.0, resource.own_reserve)
                production = min(desired_base, cap_year, max_from_reserve)
            else:
                production = desired_base

            primary_production = production
            if resource_name == "metals":
                # Recycling adds secondary supply without depleting ore reserves. It boosts THIS
                # year's market supply only; it must not feed back into next year's primary base.
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
            # [F2.4b] carry PRIMARY production forward as next year's desired base; keep the
            # recycled-inclusive total as the reported output the market/economy consume.
            resource._primary_production = primary_production
            resource.production = production
            total_primary_production[resource_name] += primary_production

    # [F2.4] carry this step's pop / per-capita income forward as the base for next year's growth.
    world.global_state._resource_demand_pop_prev = next_pop_prev
    world.global_state._resource_demand_gdppc_prev = next_gdppc_prev

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


def _resource_price_anchors(world: WorldState) -> Dict[str, float]:
    """Per-resource anchor price for the equilibrium pull: the calibration reference price,
    captured once the first time prices are updated (the base year, where prices are ~1.0)."""
    anchors = getattr(world.global_state, "_resource_price_anchors", None)
    if anchors is None:
        anchors = {
            name: max(1e-6, float(world.global_state.prices.get(name, 1.0)))
            for name in RESOURCE_NAMES
        }
        world.global_state._resource_price_anchors = anchors
    return anchors


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
    reserves = getattr(world.global_state, "global_reserves", {})
    anchor_pull = float(getattr(cal, "PRICE_ANCHOR_PULL", 0.0))
    anchors = _resource_price_anchors(world) if anchor_pull > 0.0 else {}

    for resource_name in RESOURCE_NAMES:
        current_price = world.global_state.prices.get(resource_name, 1.0)
        if clearing:
            # [F2.2] within-period clearing: set price so constant-elasticity demand == supply.
            # demand(p) = D0*(p/p_cur)^(-eps) == supply  ->  p* = p_cur*(D0/supply)^(1/eps).
            #
            # [reserve buffer] A flow-only clearing price assumes this year's production must
            # equal this year's consumption, which is a fair approximation for a near-zero-storage
            # good but not for one with a large standing stock: metals carry several years of
            # above-ground/recycled inventory, energy several years of proven reserves, so a
            # flow imbalance is mostly absorbed by drawing down (or building) that stock rather
            # than requiring price alone to clear it in one step. food carries very little
            # buffer (perishable), so it keeps clearing close to the pure flow rule, correctly
            # staying the most price-volatile of the three. buffer_ratio -> 1 when reserves dwarf
            # the imbalance (price barely moves this year); -> 0 when reserves are thin relative
            # to the imbalance (recovers the original pure flow-clearing rule).
            raw_ratio = (demand[resource_name] + epsilon) / (supply[resource_name] + epsilon)
            imbalance = abs(demand[resource_name] - supply[resource_name])
            reserve = max(0.0, float(reserves.get(resource_name, 0.0)))
            buffer_ratio = reserve / (reserve + imbalance + epsilon)
            damped_ratio = 1.0 + (1.0 - buffer_ratio) * (raw_ratio - 1.0)
            next_price = current_price * (damped_ratio ** (1.0 / eps))
        else:
            imbalance = (demand[resource_name] - supply[resource_name]) / (
                supply[resource_name] + epsilon
            )
            next_price = current_price * (1.0 + alpha * imbalance)

        # [F2.3] weak log-space mean-reversion toward the calibration anchor, applied AFTER the
        # walk step so a persistent imbalance settles at a finite level instead of pinning to a
        # clamp. Zero pull, or a price already at its anchor, leaves next_price untouched.
        if anchor_pull > 0.0:
            anchor = max(1e-6, float(anchors.get(resource_name, 1.0)))
            log_next = math.log(max(next_price, 1e-9))
            next_price = math.exp(log_next + anchor_pull * (math.log(anchor) - log_next))

        world.global_state.prices[resource_name] = max(
            min_price,
            min(max_price, next_price),
        )
