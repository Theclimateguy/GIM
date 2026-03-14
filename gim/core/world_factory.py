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
    "capital",
    "public_debt",
    "public_debt_pct_gdp",
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

POSITIVE_NUMERIC_COLUMNS = {
    "gdp",
    "population",
}

NONNEGATIVE_NUMERIC_COLUMNS = {
    "capital",
    "fx_reserves",
    "public_debt",
    "public_debt_pct_gdp",
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
    "military_power",
    "tech_level",
}

UNIT_INTERVAL_COLUMNS = {
    "trust_gov",
    "social_tension",
    "climate_risk",
    "biodiversity_local",
    "water_stress",
    "regime_stability",
    "debt_crisis_prone",
    "conflict_proneness",
    "security_index",
}

PERCENTILE_COLUMNS = {
    "inequality_gini",
    "pdi",
    "idv",
    "mas",
    "uai",
    "lto",
    "ind",
}

WVS_SCALE_COLUMNS = {
    "traditional_secular",
    "survival_self_expression",
}


def _raw_value(row: dict[str, str], key: str) -> str:
    return row.get(key, "") or ""


def _parse_optional_float(row: dict[str, str], key: str) -> float | None:
    raw = _raw_value(row, key).strip()
    if not raw:
        return None
    return float(raw)


def _parse_with_default(row: dict[str, str], key: str, default: float) -> float:
    value = _parse_optional_float(row, key)
    return default if value is None else value


def _resolve_capital(row: dict[str, str], gdp_val: float) -> float:
    capital_val = _parse_optional_float(row, "capital")
    if capital_val is None:
        return 3.0 * gdp_val
    return capital_val


def _resolve_public_debt(row: dict[str, str], gdp_val: float) -> float:
    public_debt = _parse_optional_float(row, "public_debt")
    if public_debt is not None:
        return public_debt

    debt_ratio = _parse_optional_float(row, "public_debt_pct_gdp")
    if debt_ratio is not None:
        return gdp_val * debt_ratio / 100.0

    return 0.0


def _validate_bounds(value: float, lower: float, upper: float, *, col: str, row_num: int, path: str) -> None:
    if lower <= value <= upper:
        return
    raise ValueError(
        f"CSV validation error in {path} at row {row_num}: "
        f"field '{col}' must be in [{lower}, {upper}], got '{value}'"
    )


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

    for col in POSITIVE_NUMERIC_COLUMNS:
        value = _parse_optional_float(row, col)
        if value is None:
            continue
        if value <= 0.0:
            raise ValueError(
                f"CSV validation error in {path} at row {row_num}: "
                f"field '{col}' must be > 0, got '{value}'"
            )

    for col in NONNEGATIVE_NUMERIC_COLUMNS:
        value = _parse_optional_float(row, col)
        if value is None:
            continue
        if value < 0.0:
            raise ValueError(
                f"CSV validation error in {path} at row {row_num}: "
                f"field '{col}' must be >= 0, got '{value}'"
            )

    for col in UNIT_INTERVAL_COLUMNS:
        value = _parse_optional_float(row, col)
        if value is None:
            continue
        _validate_bounds(value, 0.0, 1.0, col=col, row_num=row_num, path=path)

    for col in PERCENTILE_COLUMNS:
        value = _parse_optional_float(row, col)
        if value is None:
            continue
        _validate_bounds(value, 0.0, 100.0, col=col, row_num=row_num, path=path)

    for col in WVS_SCALE_COLUMNS:
        value = _parse_optional_float(row, col)
        if value is None:
            continue
        _validate_bounds(value, 0.0, 10.0, col=col, row_num=row_num, path=path)


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
                capital=_resolve_capital(row, gdp_val),
                population=population_val,
                public_debt=_resolve_public_debt(row, gdp_val),
                fx_reserves=float(row["fx_reserves"]),
                gdp_per_capita=gdp_val * 1e12 / population_val if population_val > 0 else 0.0,
            )

            resources = {
                "energy": ResourceSubState(
                    own_reserve=_parse_with_default(row, "energy_reserve", 20.0),
                    production=_parse_with_default(row, "energy_production", 100.0),
                    consumption=_parse_with_default(row, "energy_consumption", 100.0),
                ),
                "food": ResourceSubState(
                    own_reserve=_parse_with_default(row, "food_reserve", 10.0),
                    production=_parse_with_default(row, "food_production", 50.0),
                    consumption=_parse_with_default(row, "food_consumption", 50.0),
                ),
                "metals": ResourceSubState(
                    own_reserve=_parse_with_default(row, "metals_reserve", 30.0),
                    production=_parse_with_default(row, "metals_production", 20.0),
                    consumption=_parse_with_default(row, "metals_consumption", 20.0),
                ),
            }

            society = SocietyState(
                trust_gov=float(row["trust_gov"]),
                social_tension=float(row["social_tension"]),
                inequality_gini=float(row["inequality_gini"]),
            )

            climate = ClimateSubState(
                climate_risk=float(row["climate_risk"]),
                co2_annual_emissions=_parse_with_default(row, "co2_annual_emissions", 0.0),
                biodiversity_local=_parse_with_default(row, "biodiversity_local", 0.8),
            )

            risk = RiskState(
                water_stress=_parse_with_default(row, "water_stress", 0.5),
                regime_stability=_parse_with_default(row, "regime_stability", 0.6),
                debt_crisis_prone=_parse_with_default(row, "debt_crisis_prone", 0.5),
                conflict_proneness=_parse_with_default(row, "conflict_proneness", 0.4),
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
                tech_level=_parse_with_default(row, "tech_level", 1.0),
                military_power=_parse_with_default(row, "military_power", 1.0),
                security_index=_parse_with_default(row, "security_index", 0.5),
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
                alliance_block=(row.get("alliance_block") or "NonAligned").strip() or "NonAligned",
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
    global_state._calendar_year_base = 2023
    global_state._enable_temperature_variability = True
    global_state._temperature_variability_seed = 0
    global_state._temperature_variability_sign = 1.0

    world = WorldState(time=0, agents=agents, global_state=global_state, relations=relations)

    from .political_dynamics import update_political_states
    from .institutions import build_default_institutions
    from .credit_rating import update_credit_ratings

    update_political_states(world)
    world.institutions = build_default_institutions(world)
    update_credit_ratings(world, memory={})
    return world
