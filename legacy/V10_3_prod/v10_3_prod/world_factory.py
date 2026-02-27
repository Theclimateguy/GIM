import csv
from typing import Dict

from .core import (
    AgentState,
    ClimateSubState,
    CO2_STOCK_2023_GT,
    CulturalState,
    EconomyState,
    GlobalState,
    RelationState,
    ResourceSubState,
    RiskState,
    SocietyState,
    TGLOBAL_2023_C,
    TechnologyState,
    WorldState,
    BIODIVERSITY_2023,
)


def make_world_from_csv(path: str = "agent_states.csv") -> WorldState:
    agents: Dict[str, AgentState] = {}

    with open(path, newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        for row in reader:
            agent_id = row["id"]
            gdp_val = float(row["gdp"])
            population_val = float(row["population"])

            economy = EconomyState(
                gdp=gdp_val,
                capital=3.0 * gdp_val,
                population=population_val,
                public_debt=float(row["public_debt"]) if row["public_debt"] else 0.0,
                fx_reserves=float(row["fx_reserves"]),
                gdp_per_capita=gdp_val * 1e12 / population_val if population_val > 0 else 0.0,
            )

            resources = {
                "energy": ResourceSubState(
                    own_reserve=float(row.get("energy_reserve", 20.0)),
                    production=float(row.get("energy_production", 100.0)),
                    consumption=float(row.get("energy_consumption", 100.0)),
                ),
                "food": ResourceSubState(
                    own_reserve=float(row.get("food_reserve", 10.0)),
                    production=float(row.get("food_production", 50.0)),
                    consumption=float(row.get("food_consumption", 50.0)),
                ),
                "metals": ResourceSubState(
                    own_reserve=float(row.get("metals_reserve", 30.0)),
                    production=float(row.get("metals_production", 20.0)),
                    consumption=float(row.get("metals_consumption", 20.0)),
                ),
            }

            society = SocietyState(
                trust_gov=float(row["trust_gov"]),
                social_tension=float(row["social_tension"]),
                inequality_gini=float(row["inequality_gini"]),
            )

            climate = ClimateSubState(
                climate_risk=float(row["climate_risk"]),
                co2_annual_emissions=float(row.get("co2_annual_emissions", 0.0)),
                biodiversity_local=float(row.get("biodiversity_local", 0.8)),
            )

            risk = RiskState(
                water_stress=float(row.get("water_stress", 0.5)),
                regime_stability=float(row.get("regime_stability", 0.6)),
                debt_crisis_prone=float(row.get("debt_crisis_prone", 0.5)),
                conflict_proneness=float(row.get("conflict_proneness", 0.4)),
            )

            culture = CulturalState(
                pdi=float(row["pdi"]),
                idv=float(row["idv"]),
                mas=float(row["mas"]),
                uai=float(row["uai"]),
                lto=float(row["lto"]),
                ind=float(row["ind"]),
                survival_self_expression=float(row["survival_self_expression"]),
                traditional_secular=float(row["traditional_secular"]),
                regime_type=row["regime_type"],
            )

            technology = TechnologyState(
                tech_level=float(row.get("tech_level", 1.0)),
                military_power=float(row.get("military_power", 1.0)),
                security_index=float(row.get("security_index", 0.5)),
            )

            agents[agent_id] = AgentState(
                id=agent_id,
                type="country",
                name=row["name"],
                region=row["region"],
                economy=economy,
                resources=resources,
                society=society,
                climate=climate,
                culture=culture,
                technology=technology,
                risk=risk,
                alliance_block=row.get("alliance_block", "NonAligned"),
                memory_id=f"mem_{agent_id}",
            )

    relations: Dict[str, Dict[str, RelationState]] = {}
    ids = list(agents.keys())
    for left in ids:
        relations[left] = {}
        for right in ids:
            if left == right:
                continue
            relations[left][right] = RelationState(
                trade_intensity=0.5,
                trust=0.6,
                conflict_level=0.1,
            )

    total_pop = sum(a.economy.population for a in agents.values())
    total_gdp = sum(a.economy.gdp for a in agents.values())
    total_weight = 0.0
    weighted_bio = 0.0
    for agent in agents.values():
        weight = agent.economy.population ** 0.3
        total_weight += weight
        weighted_bio += agent.climate.biodiversity_local * weight
    if total_pop > 0:
        baseline_gdp_pc = total_gdp * 1e12 / total_pop
    else:
        baseline_gdp_pc = 10000.0
    if total_weight > 0:
        biodiversity_init = weighted_bio / total_weight
    else:
        biodiversity_init = BIODIVERSITY_2023

    global_state = GlobalState(
        co2=CO2_STOCK_2023_GT,
        temperature_global=TGLOBAL_2023_C,
        biodiversity_index=biodiversity_init,
        baseline_gdp_pc=baseline_gdp_pc,
    )

    return WorldState(time=0, agents=agents, global_state=global_state, relations=relations)
