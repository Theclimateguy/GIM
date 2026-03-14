import csv
import datetime
import os
from typing import Any, Dict, Iterable, List

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
        "credit_rating",
        "credit_zone",
        "credit_risk_score",
        "credit_financial_risk",
        "credit_war_risk",
        "credit_social_risk",
        "credit_sanctions_risk",
        "credit_macro_risk",
        "credit_next_year_revolution_risk",
        "credit_sanction_risk_next",
        "credit_inbound_sanctions_mild",
        "credit_inbound_sanctions_strong",
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
                        "credit_rating": agent.credit_rating,
                        "credit_zone": agent.credit_zone,
                        "credit_risk_score": agent.credit_risk_score,
                        "credit_financial_risk": agent.credit_rating_details.get("financial_risk"),
                        "credit_war_risk": agent.credit_rating_details.get("war_risk"),
                        "credit_social_risk": agent.credit_rating_details.get("social_risk"),
                        "credit_sanctions_risk": agent.credit_rating_details.get("sanctions_risk"),
                        "credit_macro_risk": agent.credit_rating_details.get("macro_risk"),
                        "credit_next_year_revolution_risk": agent.credit_rating_details.get(
                            "next_year_revolution_risk"
                        ),
                        "credit_sanction_risk_next": agent.credit_rating_details.get("sanction_next"),
                        "credit_inbound_sanctions_mild": agent.credit_rating_details.get(
                            "inbound_sanctions_mild"
                        ),
                        "credit_inbound_sanctions_strong": agent.credit_rating_details.get(
                            "inbound_sanctions_strong"
                        ),
                    }
                )

    return filepath


def log_actions_to_csv(
    action_records: Iterable[Dict[str, Any]],
    sim_id: str,
    base_dir: str = "logs",
) -> str:
    records = list(action_records)
    os.makedirs(base_dir, exist_ok=True)
    filepath = os.path.join(base_dir, f"{sim_id}_actions.csv")
    if not records:
        with open(filepath, "w", newline="") as file_obj:
            writer = csv.writer(file_obj)
            writer.writerow(["time", "agent_id"])
        return filepath

    fieldnames = [
        "time",
        "agent_id",
        "agent_name",
        "alliance_block",
        "gdp",
        "trust_gov",
        "social_tension",
        "inequality_gini",
        "political_legitimacy",
        "political_protest_pressure",
        "political_hawkishness",
        "political_protectionism",
        "political_coalition_openness",
        "political_sanction_propensity",
        "political_policy_space",
        "dom_tax_fuel_change",
        "dom_social_spending_change",
        "dom_military_spending_change",
        "dom_rd_investment_change",
        "dom_climate_policy",
        "trade_deals",
        "trade_realized",
        "sanctions_intent",
        "trade_restrictions_intent",
        "security_intent_type",
        "security_intent_target",
        "security_applied_type",
        "security_applied_target",
        "active_sanctions",
        "avg_trade_barrier",
        "avg_trade_intensity",
        "avg_relation_trust",
        "avg_relation_conflict",
        "explanation",
    ]

    extra_fields = []
    for record in records:
        for key in record.keys():
            if key not in fieldnames and key not in extra_fields:
                extra_fields.append(key)
    fieldnames = fieldnames + extra_fields

    with open(filepath, "w", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(record)

    return filepath


def log_institutions_to_csv(
    reports: Iterable[Dict[str, Any]],
    sim_id: str,
    base_dir: str = "logs",
) -> str:
    records = list(reports)
    os.makedirs(base_dir, exist_ok=True)
    filepath = os.path.join(base_dir, f"{sim_id}_institutions.csv")
    if not records:
        with open(filepath, "w", newline="") as file_obj:
            writer = csv.writer(file_obj)
            writer.writerow(["time", "org_id"])
        return filepath

    fieldnames = [
        "time",
        "org_id",
        "org_type",
        "legitimacy",
        "budget",
        "members",
        "measures",
        "global_gdp",
        "global_trust",
        "global_tension",
        "global_rel_trust",
        "global_rel_conflict",
        "global_trade_intensity",
        "global_co2",
        "global_temp",
    ]

    extra_fields = []
    for record in records:
        for key in record.keys():
            if key not in fieldnames and key not in extra_fields:
                extra_fields.append(key)
    fieldnames = fieldnames + extra_fields

    with open(filepath, "w", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(record)

    return filepath
