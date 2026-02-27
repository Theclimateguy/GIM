import csv
import datetime
import os
from typing import List

from .core import WorldState


def make_sim_id(name: str) -> str:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_name = name.replace(" ", "_")
    return f"{safe_name}_{timestamp}"


def log_world_to_csv(
    world_history: List[WorldState],
    sim_id: str,
    base_dir: str = "logs",
) -> str:
    t_start = world_history[0].time
    t_end = world_history[-1].time

    os.makedirs(base_dir, exist_ok=True)
    filepath = os.path.join(base_dir, f"{sim_id}_t{t_start}-t{t_end}.csv")

    fieldnames = [
        "time",
        "agent_id",
        "gdp",
        "capital",
        "population",
        "public_debt",
        "fx_reserves",
        "energy_own_reserve",
        "energy_production",
        "energy_consumption",
        "food_own_reserve",
        "food_production",
        "food_consumption",
        "metals_own_reserve",
        "metals_production",
        "metals_consumption",
        "trust_gov",
        "social_tension",
        "inequality_gini",
        "climate_risk",
        "co2_annual_emissions",
        "biodiversity_local",
        "global_co2",
        "global_temperature",
        "global_biodiversity",
        "net_exports",
        "birth_rate",
        "death_rate",
    ]

    with open(filepath, "w", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()

        for world in world_history:
            for agent_id, agent in world.agents.items():
                energy = agent.resources.get("energy")
                food = agent.resources.get("food")
                metals = agent.resources.get("metals")

                writer.writerow(
                    {
                        "time": world.time,
                        "agent_id": agent_id,
                        "gdp": agent.economy.gdp,
                        "capital": agent.economy.capital,
                        "population": agent.economy.population,
                        "public_debt": agent.economy.public_debt,
                        "fx_reserves": agent.economy.fx_reserves,
                        "energy_own_reserve": energy.own_reserve if energy else None,
                        "energy_production": energy.production if energy else None,
                        "energy_consumption": energy.consumption if energy else None,
                        "food_own_reserve": food.own_reserve if food else None,
                        "food_production": food.production if food else None,
                        "food_consumption": food.consumption if food else None,
                        "metals_own_reserve": metals.own_reserve if metals else None,
                        "metals_production": metals.production if metals else None,
                        "metals_consumption": metals.consumption if metals else None,
                        "trust_gov": agent.society.trust_gov,
                        "social_tension": agent.society.social_tension,
                        "inequality_gini": agent.society.inequality_gini,
                        "climate_risk": agent.climate.climate_risk,
                        "co2_annual_emissions": agent.climate.co2_annual_emissions,
                        "biodiversity_local": agent.climate.biodiversity_local,
                        "global_co2": world.global_state.co2,
                        "global_temperature": world.global_state.temperature_global,
                        "global_biodiversity": world.global_state.biodiversity_index,
                        "net_exports": agent.economy.net_exports,
                        "birth_rate": agent.economy.birth_rate,
                        "death_rate": agent.economy.death_rate,
                    }
                )

    return filepath
