from __future__ import annotations

import csv
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from .core.policy import make_policy_map
from .core.simulation import step_world
from .core.world_factory import make_world_from_csv


COMPILED_STATE_COLUMNS = (
    "id",
    "name",
    "region",
    "regime_type",
    "alliance_block",
    "gdp",
    "population",
    "fx_reserves",
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
    "trust_gov",
    "social_tension",
    "inequality_gini",
    "climate_risk",
    "co2_annual_emissions",
    "biodiversity_local",
    "pdi",
    "idv",
    "mas",
    "uai",
    "lto",
    "ind",
    "traditional_secular",
    "survival_self_expression",
    "tech_level",
    "security_index",
    "military_power",
    "water_stress",
    "regime_stability",
    "debt_crisis_prone",
    "conflict_proneness",
)


@dataclass(frozen=True)
class ProjectionSummary:
    source_state_csv: str
    output_state_csv: str
    baseline_year: int
    target_year: int
    simulated_years: int
    policy_mode: str
    enable_extreme_events: bool
    seed: int | None
    max_countries: int | None
    agent_count: int
    world_gdp_start: float
    world_gdp_end: float
    world_population_start: float
    world_population_end: float
    total_co2_start: float
    total_co2_end: float
    global_temp_start: float
    global_temp_end: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _resource_value(agent, resource_name: str, attr_name: str) -> float:
    resource = agent.resources.get(resource_name)
    if resource is None:
        return 0.0
    return float(getattr(resource, attr_name))


def _compiled_state_row(agent) -> dict[str, object]:
    gdp = float(agent.economy.gdp)
    public_debt_pct_gdp = 100.0 * float(agent.economy.public_debt) / max(gdp, 1e-12)
    return {
        "id": agent.id,
        "name": agent.name,
        "region": agent.region,
        "regime_type": agent.culture.regime_type,
        "alliance_block": agent.alliance_block,
        "gdp": gdp,
        "population": float(agent.economy.population),
        "fx_reserves": float(agent.economy.fx_reserves),
        "public_debt_pct_gdp": public_debt_pct_gdp,
        "energy_reserve": _resource_value(agent, "energy", "own_reserve"),
        "energy_production": _resource_value(agent, "energy", "production"),
        "energy_consumption": _resource_value(agent, "energy", "consumption"),
        "food_reserve": _resource_value(agent, "food", "own_reserve"),
        "food_production": _resource_value(agent, "food", "production"),
        "food_consumption": _resource_value(agent, "food", "consumption"),
        "metals_reserve": _resource_value(agent, "metals", "own_reserve"),
        "metals_production": _resource_value(agent, "metals", "production"),
        "metals_consumption": _resource_value(agent, "metals", "consumption"),
        "trust_gov": float(agent.society.trust_gov),
        "social_tension": float(agent.society.social_tension),
        "inequality_gini": float(agent.society.inequality_gini),
        "climate_risk": float(agent.climate.climate_risk),
        "co2_annual_emissions": float(agent.climate.co2_annual_emissions),
        "biodiversity_local": float(agent.climate.biodiversity_local),
        "pdi": float(agent.culture.pdi),
        "idv": float(agent.culture.idv),
        "mas": float(agent.culture.mas),
        "uai": float(agent.culture.uai),
        "lto": float(agent.culture.lto),
        "ind": float(agent.culture.ind),
        "traditional_secular": float(agent.culture.traditional_secular),
        "survival_self_expression": float(agent.culture.survival_self_expression),
        "tech_level": float(agent.technology.tech_level),
        "security_index": float(agent.technology.security_index),
        "military_power": float(agent.technology.military_power),
        "water_stress": float(agent.risk.water_stress),
        "regime_stability": float(agent.risk.regime_stability),
        "debt_crisis_prone": float(agent.risk.debt_crisis_prone),
        "conflict_proneness": float(agent.risk.conflict_proneness),
    }


def compiled_state_rows(world) -> list[dict[str, object]]:
    return [_compiled_state_row(agent) for agent in world.agents.values()]


def write_compiled_state_csv(world, output_path: str | Path) -> Path:
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(COMPILED_STATE_COLUMNS))
        writer.writeheader()
        for row in compiled_state_rows(world):
            writer.writerow(row)
    return output


def write_projection_metadata(summary: ProjectionSummary, metadata_path: str | Path) -> Path:
    output = Path(metadata_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def project_state_csv(
    *,
    state_csv: str | Path,
    output_csv: str | Path,
    years: int,
    state_year: int | None = None,
    policy_mode: str = "simple",
    enable_extreme_events: bool = False,
    seed: int | None = 0,
    max_countries: int | None = None,
) -> ProjectionSummary:
    if years < 0:
        raise ValueError(f"Projection horizon must be non-negative, got {years}")

    source_state_csv = Path(state_csv).expanduser().resolve()
    output_state_csv = Path(output_csv).expanduser().resolve()

    resolved_state_year = 2023 if state_year is None else int(state_year)
    world = make_world_from_csv(
        str(source_state_csv),
        max_agents=max_countries,
        base_year=resolved_state_year,
    )
    baseline_year = int(getattr(world.global_state, "_calendar_year_base", resolved_state_year))

    if seed is not None:
        random.seed(seed)
        world.global_state._temperature_variability_seed = seed

    policies = make_policy_map(world.agents.keys(), mode=policy_mode)

    world_gdp_start = sum(agent.economy.gdp for agent in world.agents.values())
    world_population_start = sum(agent.economy.population for agent in world.agents.values())
    total_co2_start = sum(agent.climate.co2_annual_emissions for agent in world.agents.values())
    global_temp_start = float(world.global_state.temperature_global)

    for _ in range(years):
        world = step_world(
            world,
            policies,
            enable_extreme_events=enable_extreme_events,
        )

    write_compiled_state_csv(world, output_state_csv)
    make_world_from_csv(str(output_state_csv), base_year=baseline_year + years)

    world_gdp_end = sum(agent.economy.gdp for agent in world.agents.values())
    world_population_end = sum(agent.economy.population for agent in world.agents.values())
    total_co2_end = sum(agent.climate.co2_annual_emissions for agent in world.agents.values())
    global_temp_end = float(world.global_state.temperature_global)

    return ProjectionSummary(
        source_state_csv=str(source_state_csv),
        output_state_csv=str(output_state_csv),
        baseline_year=baseline_year,
        target_year=baseline_year + years,
        simulated_years=years,
        policy_mode=policy_mode,
        enable_extreme_events=enable_extreme_events,
        seed=seed,
        max_countries=max_countries,
        agent_count=len(world.agents),
        world_gdp_start=world_gdp_start,
        world_gdp_end=world_gdp_end,
        world_population_start=world_population_start,
        world_population_end=world_population_end,
        total_co2_start=total_co2_start,
        total_co2_end=total_co2_end,
        global_temp_start=global_temp_start,
        global_temp_end=global_temp_end,
    )


__all__ = [
    "COMPILED_STATE_COLUMNS",
    "ProjectionSummary",
    "compiled_state_rows",
    "project_state_csv",
    "write_compiled_state_csv",
    "write_projection_metadata",
]
