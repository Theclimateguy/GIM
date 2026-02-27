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


REQUIRED_COLUMNS = {
    "id",
    "name",
    "region",
    "regime_type",
    "gdp",
    "population",
    "fx_reserves",
    "trust_gov",
    "social_tension",
    "inequality_gini",
    "climate_risk",
    "pdi",
    "idv",
    "mas",
    "uai",
    "lto",
    "ind",
    "survival_self_expression",
    "traditional_secular",
}

REQUIRED_NUMERIC_COLUMNS = {
    "gdp",
    "population",
    "fx_reserves",
    "trust_gov",
    "social_tension",
    "inequality_gini",
    "climate_risk",
    "pdi",
    "idv",
    "mas",
    "uai",
    "lto",
    "ind",
    "survival_self_expression",
    "traditional_secular",
}

OPTIONAL_NUMERIC_COLUMNS = {
    "public_debt",
    "energy_reserve",
    "energy_production",
    "energy_consumption",
    "food_reserve",
    "food_production",
    "food_consumption",
    "metals_reserve",
    "metals_production",
    "metals_consumption",
    "co2_annual_emissions",
    "biodiversity_local",
    "water_stress",
    "regime_stability",
    "debt_crisis_prone",
    "conflict_proneness",
    "tech_level",
    "military_power",
    "security_index",
}


def _validate_csv_schema(reader: csv.DictReader, path: str) -> None:
    fieldnames = reader.fieldnames or []
    field_set = set(fieldnames)
    missing = sorted(REQUIRED_COLUMNS - field_set)
    if missing:
        raise ValueError(
            f"CSV validation error in {path}: missing required columns: {', '.join(missing)}"
        )


def _validate_row_values(row: dict[str, str], row_num: int, path: str) -> None:
    for col in REQUIRED_COLUMNS:
        if not (row.get(col) or "").strip():
            raise ValueError(
                f"CSV validation error in {path} at row {row_num}: empty required field '{col}'"
            )

    for col in REQUIRED_NUMERIC_COLUMNS:
        raw = (row.get(col) or "").strip()
        try:
            float(raw)
        except ValueError:
            raise ValueError(
                f"CSV validation error in {path} at row {row_num}: "
                f"field '{col}' must be numeric, got '{raw}'"
            ) from None

    for col in OPTIONAL_NUMERIC_COLUMNS:
        raw = (row.get(col) or "").strip()
        if not raw:
            continue
        try:
            float(raw)
        except ValueError:
            raise ValueError(
                f"CSV validation error in {path} at row {row_num}: "
                f"field '{col}' must be numeric when provided, got '{raw}'"
            ) from None


def make_world_from_csv(path: str = "agent_states.csv", max_agents: int | None = None) -> WorldState:
    agents: Dict[str, AgentState] = {}

    with open(path, newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        _validate_csv_schema(reader, path)
        for row_num, row in enumerate(reader, start=2):
            if max_agents is not None and len(agents) >= max_agents:
                break

            _validate_row_values(row, row_num, path)
            agent_id = row["id"]
            if not agent_id:
                continue
            if agent_id in agents:
                # Keep the first occurrence to avoid accidental duplicate IDs.
                continue
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

    if not agents:
        raise ValueError(f"CSV validation error in {path}: no valid country rows found")

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
                trade_barrier=0.0,
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
        temperature_ocean=TGLOBAL_2023_C - 0.4,
        baseline_gdp_pc=baseline_gdp_pc,
    )

    world = WorldState(time=0, agents=agents, global_state=global_state, relations=relations)

    from .political_dynamics import update_political_states
    from .institutions import build_default_institutions
    from .credit_rating import update_credit_ratings

    update_political_states(world)
    world.institutions = build_default_institutions(world)
    update_credit_ratings(world, memory={})
    return world
