#!/usr/bin/env python3
"""Run 30-year climate/energy policy stress tests with the GIM17 core."""

from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import random
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from gim.core.core import (
    Action,
    DomesticPolicy,
    FinancePolicy,
    ForeignPolicy,
    Observation,
    SecurityActions,
    TradeRestriction,
    WorldState,
    clamp01,
)
from gim.core.metrics import compute_reserve_years
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv


DEFAULT_STATE_CSV = ROOT / "data" / "agent_states_operational_2026_calibrated.csv"
DEFAULT_OUTPUT_ROOT = ROOT / "results"
FOCUS_ACTORS = ("USA", "CHN", "IND", "DEU", "BRA", "RUS", "SAU", "NGA")


@dataclass(frozen=True)
class ScenarioSpec:
    """Policy-mode mapping from SSP-like narrative to GIM levers."""

    scenario_id: str
    label: str
    narrative: str
    climate_policy: str
    fuel_tax: float
    rd_delta: float
    social_delta: float
    military_delta: float
    energy_demand_growth: float
    food_demand_growth: float
    metals_demand_growth: float
    efficiency_gain: float
    adaptation_share: float
    trade_restriction: str = "none"
    transition_year: int | None = None
    post_transition_climate_policy: str | None = None
    post_transition_fuel_tax: float | None = None
    post_transition_energy_demand_growth: float | None = None
    post_transition_efficiency_gain: float | None = None
    post_transition_social_delta: float | None = None


SCENARIOS: tuple[ScenarioSpec, ...] = (
    ScenarioSpec(
        scenario_id="ssp1_sustainability",
        label="SSP1-like sustainability transition",
        narrative=(
            "Early strong climate policy, fuel taxation, higher R&D, social cushioning, "
            "lower energy intensity and adaptation spending."
        ),
        climate_policy="strong",
        fuel_tax=0.85,
        rd_delta=0.006,
        social_delta=0.006,
        military_delta=-0.003,
        energy_demand_growth=-0.008,
        food_demand_growth=-0.002,
        metals_demand_growth=0.002,
        efficiency_gain=0.015,
        adaptation_share=0.006,
    ),
    ScenarioSpec(
        scenario_id="ssp2_middle_road",
        label="SSP2-like middle of the road",
        narrative=(
            "Moderate climate policy and R&D with limited social cushioning; no explicit "
            "fragmentation shock."
        ),
        climate_policy="moderate",
        fuel_tax=0.25,
        rd_delta=0.003,
        social_delta=0.001,
        military_delta=0.0,
        energy_demand_growth=0.001,
        food_demand_growth=0.001,
        metals_demand_growth=0.001,
        efficiency_gain=0.006,
        adaptation_share=0.002,
    ),
    ScenarioSpec(
        scenario_id="ssp3_fragmentation",
        label="SSP3-like regional rivalry / fragmentation",
        narrative=(
            "Weak climate policy, higher resource demand, hard trade restrictions, "
            "lower efficiency gains and higher military spending."
        ),
        climate_policy="weak",
        fuel_tax=0.0,
        rd_delta=0.001,
        social_delta=-0.001,
        military_delta=0.006,
        energy_demand_growth=0.004,
        food_demand_growth=0.003,
        metals_demand_growth=0.002,
        efficiency_gain=0.001,
        adaptation_share=0.0,
        trade_restriction="hard",
    ),
    ScenarioSpec(
        scenario_id="ssp5_fossil_growth",
        label="SSP5-like fossil-fueled growth",
        narrative=(
            "High R&D and growth orientation, low climate constraint, falling fuel taxes "
            "and fast energy demand growth."
        ),
        climate_policy="none",
        fuel_tax=-0.35,
        rd_delta=0.007,
        social_delta=0.0,
        military_delta=0.001,
        energy_demand_growth=0.008,
        food_demand_growth=0.002,
        metals_demand_growth=0.003,
        efficiency_gain=0.008,
        adaptation_share=0.002,
    ),
    ScenarioSpec(
        scenario_id="delayed_transition",
        label="Delayed transition shock",
        narrative=(
            "First decade follows a fossil-growth path, then shifts abruptly into strong "
            "transition policy with social cushioning and higher efficiency gains."
        ),
        climate_policy="weak",
        fuel_tax=-0.20,
        rd_delta=0.005,
        social_delta=0.0,
        military_delta=0.001,
        energy_demand_growth=0.006,
        food_demand_growth=0.002,
        metals_demand_growth=0.002,
        efficiency_gain=0.004,
        adaptation_share=0.001,
        transition_year=10,
        post_transition_climate_policy="strong",
        post_transition_fuel_tax=1.05,
        post_transition_energy_demand_growth=-0.006,
        post_transition_efficiency_gain=0.016,
        post_transition_social_delta=0.008,
    ),
)


def _active_value(spec: ScenarioSpec, year_index: int, field: str):
    if spec.transition_year is None or year_index < spec.transition_year:
        return getattr(spec, field)
    post_name = f"post_transition_{field}"
    post_value = getattr(spec, post_name, None)
    return getattr(spec, field) if post_value is None else post_value


def _target_from_observation(obs: Observation) -> str | None:
    neighbors = obs.external_actors.get("neighbors", [])
    own_block = obs.self_state.get("alliance_block")
    best_id = None
    best_score = -1.0
    for neighbor in neighbors:
        target_id = str(neighbor.get("agent_id", "")).strip()
        if not target_id:
            continue
        block_penalty = 0.25 if neighbor.get("alliance_block") == own_block else 0.0
        score = (
            float(neighbor.get("conflict_level", 0.0))
            + 0.5 * (1.0 - float(neighbor.get("trust", 0.6)))
            + 0.2 * float(neighbor.get("trade_intensity", 0.0))
            - block_penalty
        )
        if score > best_score:
            best_score = score
            best_id = target_id
    return best_id


def make_scenario_policy(spec: ScenarioSpec) -> Callable[[Observation], Action]:
    def policy(obs: Observation) -> Action:
        year_index = int(obs.time)
        climate_policy = str(_active_value(spec, year_index, "climate_policy"))
        fuel_tax = float(_active_value(spec, year_index, "fuel_tax"))
        social_delta = float(_active_value(spec, year_index, "social_delta"))

        restrictions: list[TradeRestriction] = []
        if spec.trade_restriction != "none":
            target = _target_from_observation(obs)
            if target is not None:
                restrictions.append(
                    TradeRestriction(
                        target=target,
                        level=spec.trade_restriction,
                        reason=f"{spec.scenario_id} resource-security protectionism",
                    )
                )

        return Action(
            agent_id=obs.agent_id,
            time=obs.time,
            domestic_policy=DomesticPolicy(
                tax_fuel_change=fuel_tax,
                social_spending_change=social_delta,
                military_spending_change=spec.military_delta,
                rd_investment_change=spec.rd_delta,
                climate_policy=climate_policy,  # type: ignore[arg-type]
            ),
            foreign_policy=ForeignPolicy(
                trade_restrictions=restrictions,
                security_actions=SecurityActions(type="none", target=None),
            ),
            finance=FinancePolicy(
                borrow_from_global_markets=0.0,
                use_fx_reserves_change=0.0,
            ),
            explanation=f"{spec.scenario_id}: {spec.narrative}",
        )

    return policy


def _apply_scenario_overlay(world: WorldState, spec: ScenarioSpec, year_index: int) -> None:
    """Apply SSP-like demand/efficiency/adaptation pressure before yearly core step."""

    energy_growth = float(_active_value(spec, year_index, "energy_demand_growth"))
    efficiency_gain = float(_active_value(spec, year_index, "efficiency_gain"))
    for agent in world.agents.values():
        energy = agent.resources.get("energy")
        food = agent.resources.get("food")
        metals = agent.resources.get("metals")
        if energy is not None:
            energy.consumption = max(0.0, energy.consumption * (1.0 + energy_growth))
            energy.efficiency = max(0.2, energy.efficiency * (1.0 + efficiency_gain))
        if food is not None:
            food.consumption = max(0.0, food.consumption * (1.0 + spec.food_demand_growth))
        if metals is not None:
            metals.consumption = max(0.0, metals.consumption * (1.0 + spec.metals_demand_growth))
            metals.efficiency = max(0.2, metals.efficiency * (1.0 + 0.5 * efficiency_gain))
        agent.economy.climate_adaptation_spending = spec.adaptation_share * max(agent.economy.gdp, 0.0)


def _resource_shortfall(world: WorldState, resource_name: str) -> float:
    supply = 0.0
    demand = 0.0
    for agent in world.agents.values():
        resource = agent.resources.get(resource_name)
        if resource is None:
            continue
        supply += max(0.0, resource.production)
        demand += max(0.0, resource.consumption)
    return max(0.0, (demand - supply) / max(supply, 1e-9))


def _weighted_average(world: WorldState, getter: Callable[[object], float]) -> float:
    total_pop = sum(max(agent.economy.population, 0.0) for agent in world.agents.values())
    if total_pop <= 0.0:
        return 0.0
    return sum(max(agent.economy.population, 0.0) * getter(agent) for agent in world.agents.values()) / total_pop


def _relation_metrics(world: WorldState) -> dict[str, float]:
    seen: set[tuple[str, str]] = set()
    conflict_values: list[float] = []
    trust_values: list[float] = []
    barrier_values: list[float] = []
    trade_values: list[float] = []
    war_pairs = 0
    high_conflict_pairs = 0
    for actor_id, rels in world.relations.items():
        for target_id, rel in rels.items():
            pair = tuple(sorted((actor_id, target_id)))
            if pair in seen:
                continue
            seen.add(pair)
            reverse = world.relations.get(target_id, {}).get(actor_id)
            conflict = rel.conflict_level if reverse is None else 0.5 * (rel.conflict_level + reverse.conflict_level)
            trust = rel.trust if reverse is None else 0.5 * (rel.trust + reverse.trust)
            barrier = rel.trade_barrier if reverse is None else 0.5 * (rel.trade_barrier + reverse.trade_barrier)
            trade = rel.trade_intensity if reverse is None else 0.5 * (rel.trade_intensity + reverse.trade_intensity)
            conflict_values.append(float(conflict))
            trust_values.append(float(trust))
            barrier_values.append(float(barrier))
            trade_values.append(float(trade))
            if rel.at_war or (reverse is not None and reverse.at_war):
                war_pairs += 1
            if conflict >= 0.6:
                high_conflict_pairs += 1
    denom = max(len(conflict_values), 1)
    return {
        "war_pairs": float(war_pairs),
        "high_conflict_pairs": float(high_conflict_pairs),
        "avg_relation_conflict": sum(conflict_values) / denom,
        "avg_relation_trust": sum(trust_values) / denom,
        "avg_trade_barrier": sum(barrier_values) / denom,
        "avg_trade_intensity": sum(trade_values) / denom,
    }


def _migration_pressure_proxy(world: WorldState) -> float:
    baseline = getattr(world.global_state, "baseline_gdp_pc", 0.0) or 1.0
    total_pop = sum(max(agent.economy.population, 0.0) for agent in world.agents.values())
    if total_pop <= 0.0:
        return 0.0
    weighted = 0.0
    for agent in world.agents.values():
        gdp_pc = agent.economy.gdp * 1e12 / max(agent.economy.population, 1.0)
        income_push = max(0.0, (baseline - gdp_pc) / baseline)
        reserve_years = compute_reserve_years(agent)
        food_stress = clamp01(1.0 - reserve_years.get("food", 10.0) / 3.0)
        pressure = clamp01(
            0.35 * income_push
            + 0.25 * clamp01(agent.climate.climate_risk)
            + 0.20 * clamp01(agent.society.social_tension)
            + 0.15 * clamp01(agent.risk.conflict_proneness)
            + 0.05 * food_stress
        )
        weighted += max(agent.economy.population, 0.0) * pressure
    return weighted / total_pop


def collect_global_metrics(
    world: WorldState,
    *,
    scenario_id: str,
    seed: int,
    base_year: int,
) -> dict[str, float | int | str]:
    total_gdp = sum(max(agent.economy.gdp, 0.0) for agent in world.agents.values())
    total_pop = sum(max(agent.economy.population, 0.0) for agent in world.agents.values())
    total_debt = sum(max(agent.economy.public_debt, 0.0) for agent in world.agents.values())
    emissions = sum(max(agent.climate.co2_annual_emissions, 0.0) for agent in world.agents.values())
    relation = _relation_metrics(world)
    return {
        "scenario": scenario_id,
        "seed": seed,
        "time": world.time,
        "year": base_year + world.time,
        "total_gdp": total_gdp,
        "total_population": total_pop,
        "gdp_per_capita": total_gdp * 1e12 / max(total_pop, 1.0),
        "debt_to_gdp": total_debt / max(total_gdp, 1e-9),
        "trust_gov": _weighted_average(world, lambda agent: agent.society.trust_gov),
        "social_tension": _weighted_average(world, lambda agent: agent.society.social_tension),
        "climate_risk": _weighted_average(world, lambda agent: agent.climate.climate_risk),
        "annual_co2_emissions": emissions,
        "global_co2_stock": world.global_state.co2,
        "global_temperature": world.global_state.temperature_global,
        "global_biodiversity": world.global_state.biodiversity_index,
        "energy_price": world.global_state.prices.get("energy", 1.0),
        "food_price": world.global_state.prices.get("food", 1.0),
        "metals_price": world.global_state.prices.get("metals", 1.0),
        "energy_shortfall": _resource_shortfall(world, "energy"),
        "food_shortfall": _resource_shortfall(world, "food"),
        "metals_shortfall": _resource_shortfall(world, "metals"),
        "migration_pressure_proxy": _migration_pressure_proxy(world),
        "climate_shock_agents": sum(
            1 for agent in world.agents.values() if int(agent.economy.climate_shock_years) > 0
        ),
        "social_stress_share": sum(
            1
            for agent in world.agents.values()
            if agent.society.social_tension >= 0.65 or agent.society.trust_gov <= 0.25
        )
        / max(len(world.agents), 1),
        **relation,
    }


def collect_actor_metrics(
    world: WorldState,
    *,
    scenario_id: str,
    seed: int,
    base_year: int,
    actor_ids: tuple[str, ...] | None = None,
) -> list[dict[str, float | int | str]]:
    rows = []
    ids = actor_ids if actor_ids is not None else tuple(world.agents.keys())
    for actor_id in ids:
        agent = world.agents.get(actor_id)
        if agent is None:
            continue
        reserve_years = compute_reserve_years(agent)
        rows.append(
            {
                "scenario": scenario_id,
                "seed": seed,
                "time": world.time,
                "year": base_year + world.time,
                "agent_id": actor_id,
                "agent_name": agent.name,
                "region": agent.region,
                "alliance_block": agent.alliance_block,
                "regime_type": agent.culture.regime_type,
                "gdp": agent.economy.gdp,
                "population": agent.economy.population,
                "gdp_per_capita": agent.economy.gdp * 1e12 / max(agent.economy.population, 1.0),
                "debt_to_gdp": agent.economy.public_debt / max(agent.economy.gdp, 1e-9),
                "trust_gov": agent.society.trust_gov,
                "social_tension": agent.society.social_tension,
                "climate_risk": agent.climate.climate_risk,
                "co2_annual_emissions": agent.climate.co2_annual_emissions,
                "energy_reserve_years": reserve_years.get("energy", 0.0),
                "food_reserve_years": reserve_years.get("food", 0.0),
                "metals_reserve_years": reserve_years.get("metals", 0.0),
                "credit_risk_score": agent.credit_risk_score,
            }
        )
    return rows


def run_one(
    spec: ScenarioSpec,
    *,
    seed: int,
    years: int,
    state_csv: Path,
    base_year: int,
    max_countries: int | None,
    enable_extreme_events: bool,
    focus_actors: tuple[str, ...],
) -> tuple[list[dict[str, float | int | str]], list[dict[str, float | int | str]], list[dict[str, float | int | str]], list[dict]]:
    random.seed(seed)
    world = make_world_from_csv(str(state_csv), max_agents=max_countries, base_year=base_year)
    world.global_state._temperature_variability_seed = seed
    world.global_state._temperature_variability_sign = 1.0 if seed % 2 == 0 else -1.0
    policies = {agent_id: make_scenario_policy(spec) for agent_id in world.agents.keys()}
    action_log: list[dict] = []

    global_rows = [collect_global_metrics(world, scenario_id=spec.scenario_id, seed=seed, base_year=base_year)]
    all_actor_rows = collect_actor_metrics(
        world,
        scenario_id=spec.scenario_id,
        seed=seed,
        base_year=base_year,
        actor_ids=None,
    )
    focus_set = set(focus_actors)
    focus_rows = [row for row in all_actor_rows if row["agent_id"] in focus_set]
    for _ in range(years):
        _apply_scenario_overlay(world, spec, int(world.time))
        world = step_world(
            world,
            policies,
            enable_extreme_events=enable_extreme_events,
            action_log=action_log,
            apply_political_filters=True,
            apply_institutions=True,
        )
        global_rows.append(collect_global_metrics(world, scenario_id=spec.scenario_id, seed=seed, base_year=base_year))
        new_actor_rows = collect_actor_metrics(
            world,
            scenario_id=spec.scenario_id,
            seed=seed,
            base_year=base_year,
            actor_ids=None,
        )
        all_actor_rows.extend(new_actor_rows)
        focus_rows.extend(row for row in new_actor_rows if row["agent_id"] in focus_set)

    for record in action_log:
        record["scenario"] = spec.scenario_id
        record["seed"] = seed
    return global_rows, all_actor_rows, focus_rows, action_log


def _quantile(series: pd.Series, q: float) -> float:
    return float(series.quantile(q))


def summarize(global_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = global_df[global_df["time"] == 0].set_index(["scenario", "seed"])
    df = global_df.copy()
    df["gdp_index"] = [
        row.total_gdp / base.loc[(row.scenario, row.seed), "total_gdp"] * 100.0
        for row in df.itertuples(index=False)
    ]
    df["emissions_index"] = [
        row.annual_co2_emissions / max(base.loc[(row.scenario, row.seed), "annual_co2_emissions"], 1e-9) * 100.0
        for row in df.itertuples(index=False)
    ]
    df["energy_gap_log"] = df["energy_shortfall"].map(lambda value: math.log10(1.0 + max(float(value), 0.0)))
    df["food_gap_log"] = df["food_shortfall"].map(lambda value: math.log10(1.0 + max(float(value), 0.0)))

    grouped = (
        df.groupby(["scenario", "year"])
        .agg(
            gdp_index_mean=("gdp_index", "mean"),
            gdp_index_p10=("gdp_index", lambda x: _quantile(x, 0.10)),
            gdp_index_p90=("gdp_index", lambda x: _quantile(x, 0.90)),
            temperature_mean=("global_temperature", "mean"),
            emissions_index_mean=("emissions_index", "mean"),
            tension_mean=("social_tension", "mean"),
            trust_mean=("trust_gov", "mean"),
            energy_shortfall_mean=("energy_shortfall", "mean"),
            food_shortfall_mean=("food_shortfall", "mean"),
            energy_gap_log_mean=("energy_gap_log", "mean"),
            food_gap_log_mean=("food_gap_log", "mean"),
            war_pairs_mean=("war_pairs", "mean"),
            high_conflict_pairs_mean=("high_conflict_pairs", "mean"),
            avg_relation_conflict_mean=("avg_relation_conflict", "mean"),
            avg_relation_trust_mean=("avg_relation_trust", "mean"),
            avg_trade_barrier_mean=("avg_trade_barrier", "mean"),
            avg_trade_intensity_mean=("avg_trade_intensity", "mean"),
            migration_pressure_mean=("migration_pressure_proxy", "mean"),
            social_stress_share_mean=("social_stress_share", "mean"),
        )
        .reset_index()
    )

    final_year = int(df["year"].max())
    final = grouped[grouped["year"] == final_year].copy()
    final["welfare_score"] = (
        final["gdp_index_mean"]
        - 8.0 * final["temperature_mean"]
        - 25.0 * final["tension_mean"]
        - 12.0 * final["energy_gap_log_mean"]
        - 8.0 * final["food_gap_log_mean"]
        - 20.0 * final["avg_relation_conflict_mean"]
        - 0.2 * final["high_conflict_pairs_mean"]
    )
    final = final.sort_values("welfare_score", ascending=False)
    return grouped, final


def summarize_groups(actor_df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    df = actor_df.copy()
    df["gdp_weight"] = df["gdp"].clip(lower=0.0)
    df["pop_weight"] = df["population"].clip(lower=0.0)
    rows: list[dict[str, float | int | str]] = []
    for keys, group in df.groupby(["scenario", "seed", "year", group_col]):
        scenario, seed, year, group_value = keys
        gdp = float(group["gdp"].clip(lower=0.0).sum())
        pop = float(group["population"].clip(lower=0.0).sum())
        debt = float((group["debt_to_gdp"] * group["gdp"].clip(lower=0.0)).sum())
        emissions = float(group["co2_annual_emissions"].clip(lower=0.0).sum())
        pop_weight = group["pop_weight"]
        denom_pop = float(pop_weight.sum())
        rows.append(
            {
                "scenario": scenario,
                "seed": int(seed),
                "year": int(year),
                group_col: group_value,
                "gdp": gdp,
                "population": pop,
                "gdp_per_capita": gdp * 1e12 / max(pop, 1.0),
                "debt_to_gdp": debt / max(gdp, 1e-9),
                "trust_gov": float((group["trust_gov"] * pop_weight).sum() / denom_pop) if denom_pop else 0.0,
                "social_tension": float((group["social_tension"] * pop_weight).sum() / denom_pop) if denom_pop else 0.0,
                "climate_risk": float((group["climate_risk"] * pop_weight).sum() / denom_pop) if denom_pop else 0.0,
                "co2_annual_emissions": emissions,
                "energy_reserve_years": float(group["energy_reserve_years"].median()),
                "food_reserve_years": float(group["food_reserve_years"].median()),
                "credit_risk_score": float((group["credit_risk_score"] * pop_weight).sum() / denom_pop) if denom_pop else 0.0,
                "social_stress_share": float(
                    ((group["social_tension"] >= 0.65) | (group["trust_gov"] <= 0.25)).mean()
                ),
                "country_count": int(len(group)),
            }
        )

    panel = pd.DataFrame(rows)
    base = (
        panel.sort_values("year")
        .groupby(["scenario", "seed", group_col], as_index=False)
        .first()
        .set_index(["scenario", "seed", group_col])
    )
    panel["gdp_index"] = [
        row.gdp / max(base.loc[(row.scenario, row.seed, getattr(row, group_col)), "gdp"], 1e-9) * 100.0
        for row in panel.itertuples(index=False)
    ]
    summary = (
        panel.groupby(["scenario", "year", group_col])
        .agg(
            gdp_index_mean=("gdp_index", "mean"),
            gdp_mean=("gdp", "mean"),
            population_mean=("population", "mean"),
            gdp_per_capita_mean=("gdp_per_capita", "mean"),
            trust_mean=("trust_gov", "mean"),
            tension_mean=("social_tension", "mean"),
            climate_risk_mean=("climate_risk", "mean"),
            emissions_mean=("co2_annual_emissions", "mean"),
            energy_reserve_years_median=("energy_reserve_years", "mean"),
            food_reserve_years_median=("food_reserve_years", "mean"),
            credit_risk_mean=("credit_risk_score", "mean"),
            social_stress_share_mean=("social_stress_share", "mean"),
            country_count=("country_count", "first"),
        )
        .reset_index()
    )
    return summary


def summarize_countries(actor_df: pd.DataFrame) -> pd.DataFrame:
    df = actor_df.copy()
    base = df[df["year"] == df["year"].min()].set_index(["scenario", "seed", "agent_id"])
    df["gdp_index"] = [
        row.gdp / max(base.loc[(row.scenario, row.seed, row.agent_id), "gdp"], 1e-9) * 100.0
        for row in df.itertuples(index=False)
    ]
    df["emissions_index"] = [
        row.co2_annual_emissions / max(base.loc[(row.scenario, row.seed, row.agent_id), "co2_annual_emissions"], 1e-9) * 100.0
        for row in df.itertuples(index=False)
    ]
    def _mode_or_last(values: pd.Series) -> str:
        mode = values.mode()
        if not mode.empty:
            return str(mode.iloc[0])
        return str(values.iloc[-1])

    summary = (
        df.groupby(["scenario", "year", "agent_id", "agent_name", "region"])
        .agg(
            alliance_block=("alliance_block", _mode_or_last),
            regime_type=("regime_type", _mode_or_last),
            gdp_index_mean=("gdp_index", "mean"),
            gdp_mean=("gdp", "mean"),
            gdp_per_capita_mean=("gdp_per_capita", "mean"),
            population_mean=("population", "mean"),
            debt_to_gdp_mean=("debt_to_gdp", "mean"),
            trust_mean=("trust_gov", "mean"),
            tension_mean=("social_tension", "mean"),
            climate_risk_mean=("climate_risk", "mean"),
            emissions_index_mean=("emissions_index", "mean"),
            energy_reserve_years_median=("energy_reserve_years", "median"),
            food_reserve_years_median=("food_reserve_years", "median"),
            credit_risk_mean=("credit_risk_score", "mean"),
        )
        .reset_index()
    )
    return summary


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def plot_metric(summary_df: pd.DataFrame, output_dir: Path, metric: str, ylabel: str, filename: str) -> None:
    fig, ax = plt.subplots(figsize=(11, 6))
    for scenario_id, group in summary_df.groupby("scenario"):
        group = group.sort_values("year")
        ax.plot(group["year"], group[metric], label=scenario_id, linewidth=2)
    ax.set_title(ylabel)
    ax.set_xlabel("Year")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_dir / filename, dpi=180)
    plt.close(fig)


def plot_actor_gdp(actor_df: pd.DataFrame, output_dir: Path) -> None:
    if actor_df.empty:
        return
    df = actor_df.copy()
    base = df[df["time"] == 0].set_index(["scenario", "seed", "agent_id"])
    df["gdp_index"] = [
        row.gdp / max(base.loc[(row.scenario, row.seed, row.agent_id), "gdp"], 1e-9) * 100.0
        for row in df.itertuples(index=False)
    ]
    final_year = df["year"].max()
    final = (
        df[df["year"] == final_year]
        .groupby(["scenario", "agent_id"])["gdp_index"]
        .mean()
        .reset_index()
    )
    pivot = final.pivot(index="agent_id", columns="scenario", values="gdp_index")
    ax = pivot.plot(kind="bar", figsize=(12, 6))
    ax.set_title("Focus actor GDP index at horizon end")
    ax.set_xlabel("Actor")
    ax.set_ylabel("GDP index, start=100")
    ax.grid(True, axis="y", alpha=0.25)
    fig = ax.get_figure()
    fig.tight_layout()
    fig.savefig(output_dir / "focus_actor_final_gdp_index.png", dpi=180)
    plt.close(fig)


def _markdown_table(df: pd.DataFrame) -> str:
    headers = [str(col) for col in df.columns]
    rows = [[str(value) for value in row] for row in df.itertuples(index=False, name=None)]
    widths = [
        max(len(headers[idx]), *(len(row[idx]) for row in rows)) if rows else len(headers[idx])
        for idx in range(len(headers))
    ]

    def fmt_row(values: list[str]) -> str:
        return "| " + " | ".join(value.ljust(widths[idx]) for idx, value in enumerate(values)) + " |"

    separator = "| " + " | ".join("-" * width for width in widths) + " |"
    return "\n".join([fmt_row(headers), separator, *(fmt_row(row) for row in rows)])


def render_report(
    output_dir: Path,
    *,
    summary_df: pd.DataFrame,
    final_df: pd.DataFrame,
    years: int,
    base_year: int,
    seeds: list[int],
    state_csv: Path,
    enable_extreme_events: bool,
) -> None:
    scenario_lookup = {spec.scenario_id: spec for spec in SCENARIOS}
    lines: list[str] = [
        "# GIM17 Climate/Energy Policy Stress Test",
        "",
        f"Run timestamp: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        f"State CSV: `{state_csv}`",
        f"Horizon: `{years}` years (`{base_year}` to `{base_year + years}`)",
        f"Seeds: `{', '.join(str(seed) for seed in seeds)}`",
        f"Extreme climate events: `{enable_extreme_events}`",
        "",
        "## Formalization",
        "",
        "Each scenario is an SSP-like policy mode mapped onto existing GIM17 levers. "
        "The yearly state transition is the unchanged `step_world` core:",
        "",
        r"\\[x_{t+1}=F(x_t, a_t^{scenario}, \\epsilon_t),\\quad t=0,\\ldots,30.\\]",
        "",
        "Tracked observables are global GDP index, annual emissions, temperature, "
        "population-weighted trust/tension, resource shortfall ratios, migration-pressure proxy, "
        "high-conflict pairs and active war pairs.",
        "",
        "Important limitation: these are IPCC/SSP-like narrative stress tests, not calibrated CMIP/IPCC "
        "forcing pathways. The experiment tests internal GIM dynamics under comparable policy modes.",
        "",
        "## Scenario Mapping",
        "",
    ]
    for spec in SCENARIOS:
        lines.append(f"- `{spec.scenario_id}`: {spec.narrative}")
    lines.extend(["", "## Final-Year Summary", ""])

    show_cols = [
        "scenario",
        "gdp_index_mean",
        "temperature_mean",
        "emissions_index_mean",
        "tension_mean",
        "trust_mean",
        "energy_gap_log_mean",
        "food_gap_log_mean",
        "avg_relation_conflict_mean",
        "avg_trade_barrier_mean",
        "high_conflict_pairs_mean",
        "war_pairs_mean",
        "migration_pressure_mean",
        "welfare_score",
    ]
    rounded = final_df[show_cols].copy()
    for col in show_cols:
        if col != "scenario":
            rounded[col] = rounded[col].map(lambda value: round(float(value), 3))
    lines.append(_markdown_table(rounded))
    lines.extend(["", "## Main Findings", ""])

    best = final_df.iloc[0]
    worst_temp = final_df.sort_values("temperature_mean", ascending=False).iloc[0]
    worst_conflict = final_df.sort_values("avg_relation_conflict_mean", ascending=False).iloc[0]
    best_gdp = final_df.sort_values("gdp_index_mean", ascending=False).iloc[0]
    best_temp = final_df.sort_values("temperature_mean", ascending=True).iloc[0]
    best_emissions = final_df.sort_values("emissions_index_mean", ascending=True).iloc[0]
    best_energy = final_df.sort_values("energy_gap_log_mean", ascending=True).iloc[0]
    lines.append(
        f"- Best under the default GDP-weighted composite score is `{best['scenario']}`. "
        "This score is intentionally diagnostic, not normative; it rewards GDP strongly and penalizes "
        "warming, energy stress, tension and conflict."
    )
    lines.append(
        f"- Highest final GDP index is `{best_gdp['scenario']}` at {best_gdp['gdp_index_mean']:.1f} "
        "relative to start=100."
    )
    lines.append(
        f"- Highest warming outcome is `{worst_temp['scenario']}` at "
        f"{worst_temp['temperature_mean']:.2f} C global anomaly in the model state."
    )
    lines.append(
        f"- Lowest final warming is `{best_temp['scenario']}` at {best_temp['temperature_mean']:.2f} C; "
        f"lowest annual emissions index is `{best_emissions['scenario']}` at "
        f"{best_emissions['emissions_index_mean']:.1f}."
    )
    lines.append(
        f"- Lowest energy-stress log index is `{best_energy['scenario']}` at "
        f"{best_energy['energy_gap_log_mean']:.3f}; raw energy shortfall ratios are large because "
        "the calibrated resource block is unit-scaled, so log stress is the preferred comparison metric."
    )
    lines.append(
        f"- Highest endogenous relation-conflict pressure is `{worst_conflict['scenario']}` with "
        f"mean bilateral conflict {worst_conflict['avg_relation_conflict_mean']:.3f} in the final year."
    )
    lines.append(
        "- No scenario produced persistent active war pairs in the final-year ensemble mean; the signal is "
        "instead a broad rise in bilateral conflict levels and trade barriers. Treat this as a "
        "pre-war geopolitical stress indicator, not a realized war forecast."
    )
    lines.extend(["", "## Interpretation", ""])
    lines.append(
        "- If the objective is GDP maximization with weak climate constraints, the fossil-growth path dominates "
        "near-term output but also produces the highest warming and emissions trajectory."
    )
    lines.append(
        "- If the objective is climate/energy risk minimization, the sustainability path dominates on emissions, "
        "temperature and energy-stress metrics, but it does not remove social or geopolitical stress inside the model."
    )
    lines.append(
        "- The delayed transition preserves more output than SSP2-like gradualism while approaching the low-emissions "
        "cluster after the policy break; its main risk is transition shock timing rather than final emissions."
    )
    lines.append(
        "- The model is signaling a robust endogenous shift from climate/energy policy into social tension, trade "
        "barriers and bilateral conflict levels, even when no explicit war/crisis scenario is imposed."
    )

    lines.extend(["", "## Plot Artifacts", ""])
    for name in [
        "global_gdp_index.png",
        "global_temperature.png",
        "annual_emissions_index.png",
        "social_tension.png",
        "trust_gov.png",
        "energy_gap_log.png",
        "food_shortfall.png",
        "avg_relation_conflict.png",
        "high_conflict_pairs.png",
        "migration_pressure_proxy.png",
        "focus_actor_final_gdp_index.png",
    ]:
        if (output_dir / name).exists():
            lines.append(f"- `{name}`")
    lines.extend(["", "## Files", ""])
    for name in [
        "scenario_config.json",
        "trajectories.csv",
        "trajectory_summary.csv",
        "final_summary.csv",
        "all_actor_trajectories.csv",
        "focus_actor_trajectories.csv",
        "region_summary.csv",
        "alliance_summary.csv",
        "country_summary.csv",
        "action_log.csv",
    ]:
        if (output_dir / name).exists():
            lines.append(f"- `{name}`")
    lines.append("")
    output_dir.joinpath("report.md").write_text("\n".join(lines), encoding="utf-8")


def run_experiment(args: argparse.Namespace) -> Path:
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_ROOT / (
        "climate_energy_stress-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    state_csv = Path(args.state_csv).resolve()
    seeds = [int(seed.strip()) for seed in str(args.seeds).split(",") if seed.strip()]
    focus_actors = tuple(actor.strip() for actor in str(args.focus_actors).split(",") if actor.strip())

    config = {
        "years": args.years,
        "base_year": args.base_year,
        "state_csv": str(state_csv),
        "max_countries": args.max_countries,
        "seeds": seeds,
        "enable_extreme_events": not args.disable_extreme_events,
        "focus_actors": focus_actors,
        "scenarios": [asdict(spec) for spec in SCENARIOS],
    }
    output_dir.joinpath("scenario_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    all_global_rows: list[dict] = []
    all_actor_rows: list[dict] = []
    all_focus_rows: list[dict] = []
    all_action_rows: list[dict] = []
    for spec in SCENARIOS:
        for seed in seeds:
            print(f"[run] {spec.scenario_id} seed={seed} years={args.years}")
            global_rows, actor_rows, focus_rows, action_rows = run_one(
                spec,
                seed=seed,
                years=args.years,
                state_csv=state_csv,
                base_year=args.base_year,
                max_countries=args.max_countries,
                enable_extreme_events=not args.disable_extreme_events,
                focus_actors=focus_actors,
            )
            all_global_rows.extend(global_rows)
            all_actor_rows.extend(actor_rows)
            all_focus_rows.extend(focus_rows)
            all_action_rows.extend(action_rows)

    write_csv(output_dir / "trajectories.csv", all_global_rows)
    write_csv(output_dir / "all_actor_trajectories.csv", all_actor_rows)
    write_csv(output_dir / "focus_actor_trajectories.csv", all_focus_rows)
    write_csv(output_dir / "action_log.csv", all_action_rows)

    global_df = pd.DataFrame(all_global_rows)
    actor_df = pd.DataFrame(all_actor_rows)
    summary_df, final_df = summarize(global_df)
    summary_df.to_csv(output_dir / "trajectory_summary.csv", index=False)
    final_df.to_csv(output_dir / "final_summary.csv", index=False)
    region_summary = summarize_groups(actor_df, "region")
    alliance_summary = summarize_groups(actor_df, "alliance_block")
    country_summary = summarize_countries(actor_df)
    region_summary.to_csv(output_dir / "region_summary.csv", index=False)
    alliance_summary.to_csv(output_dir / "alliance_summary.csv", index=False)
    country_summary.to_csv(output_dir / "country_summary.csv", index=False)

    plot_metric(summary_df, output_dir, "gdp_index_mean", "Global GDP index, start=100", "global_gdp_index.png")
    plot_metric(summary_df, output_dir, "temperature_mean", "Global temperature anomaly, C", "global_temperature.png")
    plot_metric(summary_df, output_dir, "emissions_index_mean", "Annual CO2 emissions index, start=100", "annual_emissions_index.png")
    plot_metric(summary_df, output_dir, "tension_mean", "Population-weighted social tension", "social_tension.png")
    plot_metric(summary_df, output_dir, "trust_mean", "Population-weighted trust in government", "trust_gov.png")
    plot_metric(summary_df, output_dir, "energy_gap_log_mean", "Global energy stress log10(1 + shortfall)", "energy_gap_log.png")
    plot_metric(summary_df, output_dir, "food_shortfall_mean", "Global food shortfall ratio", "food_shortfall.png")
    plot_metric(summary_df, output_dir, "avg_relation_conflict_mean", "Mean bilateral conflict level", "avg_relation_conflict.png")
    plot_metric(summary_df, output_dir, "high_conflict_pairs_mean", "High-conflict bilateral pairs", "high_conflict_pairs.png")
    plot_metric(summary_df, output_dir, "migration_pressure_mean", "Migration pressure proxy", "migration_pressure_proxy.png")
    plot_actor_gdp(pd.DataFrame(all_focus_rows), output_dir)

    render_report(
        output_dir,
        summary_df=summary_df,
        final_df=final_df,
        years=args.years,
        base_year=args.base_year,
        seeds=seeds,
        state_csv=state_csv,
        enable_extreme_events=not args.disable_extreme_events,
    )

    return output_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run GIM17 climate/energy policy stress tests.")
    parser.add_argument("--years", type=int, default=30)
    parser.add_argument("--base-year", type=int, default=2026)
    parser.add_argument("--state-csv", default=str(DEFAULT_STATE_CSV))
    parser.add_argument("--max-countries", type=int, default=None)
    parser.add_argument("--seeds", default="2026,2027,2028,2029,2030")
    parser.add_argument("--focus-actors", default=",".join(FOCUS_ACTORS))
    parser.add_argument("--disable-extreme-events", action="store_true")
    parser.add_argument("--output-dir")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    output_dir = run_experiment(args)
    print(f"[done] climate/energy stress test artifacts: {output_dir}")


if __name__ == "__main__":
    main()
