from __future__ import annotations

"""
Crisis persistence calibration.

This helper calibrates the crisis-persistence family against two operational_v2
historical anchors:

- Argentina 2001-2005: long debt crisis with regime stress
- South Korea 1997-1999: short debt crisis with fast exit and no regime collapse

The packaged operational_v2 cases are outcome-layer anchors, so this script adds
minimal historical replay overrides to activate the physical debt-crisis layer
before searching over persistence and exit parameters.
"""

import copy
import itertools
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gim.calibration import (
    apply_state_overrides,
    load_calibration_cases,
)
from gim.core import calibration_params as cal
from gim.core.core import Action, DomesticPolicy, FinancePolicy, ForeignPolicy, WorldState
from gim.historical_backtest import run_historical_backtest
from gim.core.simulation import step_world
from gim.runtime import load_world


OUTPUT_PATH = REPO_ROOT / "misc" / "calibration" / "crisis_persistence_calibration.json"
SIM_STEPS = 6
SUITE_ID = "operational_v2"
TARGET_CASE_IDS = ("argentina_default_2001", "south_korea_imf_1997")
BACKTEST_TOLERANCE = 0.005
BACKTEST_GOLDEN = {
    "gdp_rmse_trillions": 1.053,
    "global_co2_rmse_gtco2": 1.630,
    "temperature_rmse_c": 0.136,
}

# Historical replay overrides needed to activate the physical crisis layer.
# The operational_v2 YAMLs are tuned for the scenario/outcome layer and do not
# by themselves trigger a debt-crisis path in the yearly physics loop.
ANCHOR_REPLAY_OVERRIDES: dict[str, dict[str, dict[str, float | str]]] = {
    "argentina_default_2001": {
        "Argentina": {
            "economy.public_debt_gdp": 1.35,
            "credit_zone": "sub_investment",
            "society.trust_gov": 0.45,
            "society.social_tension": 0.60,
        }
    },
    "south_korea_imf_1997": {
        "Korea, Rep.": {
            "economy.public_debt_gdp": 1.18,
            "credit_zone": "distressed",
            "society.trust_gov": 0.55,
            "society.social_tension": 0.40,
        }
    },
}

TARGETS: dict[str, dict[str, float | bool]] = {
    "argentina_default_2001": {
        "debt_crisis_years_min": 3,
        "debt_crisis_years_max": 5,
        "gdp_drop_year1_min": 0.08,
        "gdp_drop_year1_max": 0.14,
        "regime_crisis_triggered": True,
    },
    "south_korea_imf_1997": {
        "debt_crisis_years_min": 1,
        "debt_crisis_years_max": 2,
        "gdp_drop_year1_min": 0.03,
        "gdp_drop_year1_max": 0.08,
        "regime_crisis_triggered": False,
    },
}

CORE_GRID: dict[str, list[float | int]] = {
    "DEBT_CRISIS_PERSIST_GDP_MULT": [0.955, 0.965, 0.970, 0.975, 0.980],
    "DEBT_CRISIS_PERSIST_TRUST_HIT": [0.020, 0.025, 0.030, 0.035],
    "DEBT_CRISIS_PERSIST_TENSION_HIT": [0.015, 0.020, 0.025],
    "DEBT_CRISIS_MAX_YEARS": [6, 7, 8],
    "REGIME_CRISIS_PERSIST_GDP_MULT": [0.950, 0.960, 0.970],
    "REGIME_CRISIS_PERSIST_CAPITAL_MULT": [0.965, 0.975, 0.985],
}

REFINEMENT_GRID: dict[str, list[float | int]] = {
    "DEBT_CRISIS_EXIT_THRESHOLD": [0.68, 0.70, 0.72],
    "DEBT_CRISIS_EXIT_RATE": [0.07, 0.08, 0.09],
    "REGIME_CRISIS_MAX_YEARS": [4, 5, 6],
}

PARAM_KEYS = list(CORE_GRID) + list(REFINEMENT_GRID)


def _noop_policy(agent_id: str):
    def _policy(obs, memory_summary=None):  # noqa: ANN001, ARG001
        return Action(
            agent_id=agent_id,
            time=obs.time,
            domestic_policy=DomesticPolicy(0.0, 0.0, 0.0, 0.0, "none"),
            foreign_policy=ForeignPolicy(),
            finance=FinancePolicy(0.0, 0.0),
            explanation="crisis-persistence replay noop",
        )

    return _policy


def _current_param_values() -> dict[str, float | int]:
    return {name: getattr(cal, name) for name in PARAM_KEYS}


def _load_anchor_worlds() -> dict[str, tuple[WorldState, str]]:
    cases = {case.id: case for case in load_calibration_cases(SUITE_ID)}
    anchor_worlds: dict[str, tuple[WorldState, str]] = {}
    for case_id in TARGET_CASE_IDS:
        case = cases[case_id]
        world = load_world()
        apply_state_overrides(world, case.scenario.initial_state_overrides)
        apply_state_overrides(world, ANCHOR_REPLAY_OVERRIDES[case_id])
        agent_name = case.scenario.actors[0]
        agent_id = next(
            current_id
            for current_id, agent in world.agents.items()
            if agent.name == agent_name or agent.id == agent_name
        )
        anchor_worlds[case_id] = (world, agent_id)
    return anchor_worlds


def _set_params(params: dict[str, float | int]) -> dict[str, float | int]:
    originals = {}
    for key, value in params.items():
        originals[key] = getattr(cal, key)
        setattr(cal, key, value)
    return originals


def _restore_params(originals: dict[str, float | int]) -> None:
    for key, value in originals.items():
        setattr(cal, key, value)


def score_run(case_id: str, result: dict[str, Any]) -> float:
    target = TARGETS[case_id]
    penalties: list[float] = []

    years = int(result["debt_crisis_active_years_max"])
    years_min = int(target["debt_crisis_years_min"])
    years_max = int(target["debt_crisis_years_max"])
    if years < years_min:
        penalties.append((years_min - years) * 0.25)
    elif years > years_max:
        penalties.append((years - years_max) * 0.25)

    drop = abs(float(result["gdp_change_year1"]))
    drop_min = float(target["gdp_drop_year1_min"])
    drop_max = float(target["gdp_drop_year1_max"])
    if drop < drop_min:
        penalties.append((drop_min - drop) * 2.0)
    elif drop > drop_max:
        penalties.append((drop - drop_max) * 2.0)

    if bool(result["regime_crisis_triggered"]) != bool(target["regime_crisis_triggered"]):
        penalties.append(0.40)

    return min(1.0, sum(penalties))


def run_case_with_params(
    *,
    case_id: str,
    anchor_worlds: dict[str, tuple[WorldState, str]],
    params: dict[str, float | int],
    n_steps: int = SIM_STEPS,
) -> dict[str, Any]:
    originals = _set_params(params)
    try:
        base_world, agent_id = anchor_worlds[case_id]
        world = copy.deepcopy(base_world)
        gdp_start = world.agents[agent_id].economy.gdp
        policies = {current_id: _noop_policy(current_id) for current_id in world.agents}

        max_debt_years = 0
        max_regime_years = 0
        regime_triggered = False
        gdp_year1 = 0.0

        for step in range(n_steps):
            step_world(
                world,
                policies,
                enable_extreme_events=False,
                apply_political_filters=False,
                apply_institutions=False,
            )
            agent = world.agents[agent_id]
            max_debt_years = max(max_debt_years, agent.risk.debt_crisis_active_years)
            max_regime_years = max(max_regime_years, agent.risk.regime_crisis_active_years)
            regime_triggered = regime_triggered or agent.risk.regime_crisis_active_years > 0
            if step == 0:
                gdp_year1 = (agent.economy.gdp - gdp_start) / max(gdp_start, 1e-6)

        return {
            "debt_crisis_active_years_max": max_debt_years,
            "regime_crisis_active_years_max": max_regime_years,
            "gdp_change_year1": gdp_year1,
            "regime_crisis_triggered": regime_triggered,
        }
    finally:
        _restore_params(originals)


def _rank_key(item: dict[str, Any]) -> tuple[float, float, float]:
    arg = item["cases"]["argentina_default_2001"]
    kor = item["cases"]["south_korea_imf_1997"]
    duration_error = abs(arg["debt_crisis_active_years_max"] - 4) + abs(
        kor["debt_crisis_active_years_max"] - 2
    )
    gdp_error = abs(abs(arg["gdp_change_year1"]) - 0.109) + abs(abs(kor["gdp_change_year1"]) - 0.051)
    return (item["total_score"], duration_error, gdp_error)


def _enumerate(grid: dict[str, list[float | int]]) -> list[dict[str, float | int]]:
    keys = list(grid)
    combos = []
    for values in itertools.product(*(grid[key] for key in keys)):
        combos.append(dict(zip(keys, values)))
    return combos


def run_grid_search() -> list[dict[str, Any]]:
    anchor_worlds = _load_anchor_worlds()
    ranked: list[dict[str, Any]] = []

    for core_params in _enumerate(CORE_GRID):
        case_results = {}
        total_score = 0.0
        for case_id in TARGET_CASE_IDS:
            result = run_case_with_params(
                case_id=case_id,
                anchor_worlds=anchor_worlds,
                params=core_params,
            )
            score = score_run(case_id, result)
            total_score += score
            case_results[case_id] = {"score": score, **result}
        ranked.append(
            {
                "params": dict(core_params),
                "total_score": total_score,
                "cases": case_results,
                "search_stage": "core",
            }
        )

    ranked.sort(key=_rank_key)

    refined: list[dict[str, Any]] = []
    for base_result in ranked[:12]:
        for refine_params in _enumerate(REFINEMENT_GRID):
            params = dict(base_result["params"])
            params.update(refine_params)
            case_results = {}
            total_score = 0.0
            for case_id in TARGET_CASE_IDS:
                result = run_case_with_params(
                    case_id=case_id,
                    anchor_worlds=anchor_worlds,
                    params=params,
                )
                score = score_run(case_id, result)
                total_score += score
                case_results[case_id] = {"score": score, **result}
            refined.append(
                {
                    "params": params,
                    "total_score": total_score,
                    "cases": case_results,
                    "search_stage": "refined",
                }
            )

    refined.sort(key=_rank_key)
    return refined


def _median_distance(candidate: dict[str, Any], medians: dict[str, float]) -> float:
    distance = 0.0
    for key in PARAM_KEYS:
        distance += abs(float(candidate["params"][key]) - medians[key])
    return distance


def _prior_distance(candidate: dict[str, Any], priors: dict[str, float | int]) -> float:
    distance = 0.0
    for key in PARAM_KEYS:
        distance += abs(float(candidate["params"][key]) - float(priors[key]))
    return distance


def choose_plateau_center(
    ranked: list[dict[str, Any]],
    priors: dict[str, float | int],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, float]]:
    best_score = ranked[0]["total_score"]
    plateau = [item for item in ranked if abs(item["total_score"] - best_score) < 1e-9]
    medians = {}
    for key in PARAM_KEYS:
        values = sorted(float(item["params"][key]) for item in plateau)
        medians[key] = values[len(values) // 2]
    selected = min(
        plateau,
        key=lambda item: (_median_distance(item, medians), 0.10 * _prior_distance(item, priors)),
    )
    return selected, plateau, medians


def _backtest_metrics_for_candidate(candidate: dict[str, Any]) -> dict[str, float]:
    originals = _set_params(candidate["params"])
    try:
        result = run_historical_backtest()
    finally:
        _restore_params(originals)
    return {
        "gdp_rmse_trillions": result.gdp_rmse_trillions,
        "global_co2_rmse_gtco2": result.global_co2_rmse_gtco2,
        "temperature_rmse_c": result.temperature_rmse_c,
    }


def select_backtest_guardrailed_candidate(
    *,
    plateau: list[dict[str, Any]],
    medians: dict[str, float],
    priors: dict[str, float | int],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], dict[str, float]]:
    shortlist_by_median = sorted(
        plateau,
        key=lambda item: (_median_distance(item, medians), _prior_distance(item, priors)),
    )[:24]
    shortlist_by_prior = sorted(
        plateau,
        key=lambda item: (_prior_distance(item, priors), _median_distance(item, medians)),
    )[:24]
    seen = set()
    shortlist = []
    for candidate in shortlist_by_median + shortlist_by_prior:
        key = tuple((name, candidate["params"][name]) for name in PARAM_KEYS)
        if key in seen:
            continue
        seen.add(key)
        shortlist.append(candidate)

    viable: list[dict[str, Any]] = []
    for candidate in shortlist:
        probe = copy.deepcopy(candidate)
        probe["backtest_metrics"] = _backtest_metrics_for_candidate(candidate)
        metrics = probe["backtest_metrics"]
        gdp_ok = abs(metrics["gdp_rmse_trillions"] - BACKTEST_GOLDEN["gdp_rmse_trillions"]) <= BACKTEST_TOLERANCE
        co2_ok = (
            abs(metrics["global_co2_rmse_gtco2"] - BACKTEST_GOLDEN["global_co2_rmse_gtco2"])
            <= BACKTEST_TOLERANCE
        )
        temp_ok = abs(metrics["temperature_rmse_c"] - BACKTEST_GOLDEN["temperature_rmse_c"]) <= BACKTEST_TOLERANCE
        probe["backtest_guardrail_pass"] = gdp_ok and co2_ok and temp_ok
        viable.append(probe)

    passing = [probe for probe in viable if probe["backtest_guardrail_pass"]]
    if not passing:
        return None, viable, dict(BACKTEST_GOLDEN)

    selected = min(
        passing,
        key=lambda item: (_median_distance(item, medians), _prior_distance(item, priors)),
    )
    return selected, viable, dict(BACKTEST_GOLDEN)


def main() -> None:
    priors = _current_param_values()
    print("Running crisis persistence grid search...")
    print(f"Core combinations: {len(_enumerate(CORE_GRID))}")
    print(f"Refinement combinations per shortlisted candidate: {len(_enumerate(REFINEMENT_GRID))}")

    ranked = run_grid_search()
    raw_plateau_center, plateau, medians = choose_plateau_center(ranked, priors)
    selected, backtest_probe, baseline_metrics = select_backtest_guardrailed_candidate(
        plateau=plateau,
        medians=medians,
        priors=priors,
    )
    if selected is None:
        selected = raw_plateau_center

    payload = {
        "suite_id": SUITE_ID,
        "simulation_steps": SIM_STEPS,
        "targets": TARGETS,
        "anchor_replay_overrides": ANCHOR_REPLAY_OVERRIDES,
        "core_grid": CORE_GRID,
        "refinement_grid": REFINEMENT_GRID,
        "prior_params": priors,
        "best_score": ranked[0]["total_score"],
        "plateau_size": len(plateau),
        "raw_plateau_center": raw_plateau_center,
        "selected_plateau_center": selected,
        "plateau_medians": medians,
        "historical_backtest_baseline": baseline_metrics,
        "plateau_backtest_probe": backtest_probe,
        "top_20": ranked[:20],
        "notes": [
            "Historical replay uses minimal case-specific stress overrides because operational_v2 cases are outcome-layer anchors.",
            "South Korea year-1 GDP residual remains onset-dominated in this model family; persistence search mainly identifies duration and exit behavior.",
        ],
    }

    OUTPUT_PATH.write_text(json.dumps(payload, indent=2))

    print(f"\nBest score: {ranked[0]['total_score']:.4f}")
    print(f"Plateau size at best score: {len(plateau)}")
    if "backtest_metrics" in selected:
        metrics = selected["backtest_metrics"]
        print(
            "Selected candidate backtest: "
            f"GDP={metrics['gdp_rmse_trillions']:.3f}, "
            f"CO2={metrics['global_co2_rmse_gtco2']:.3f}, "
            f"Temp={metrics['temperature_rmse_c']:.3f}"
        )
    print("\nSelected plateau-center params:")
    for key in PARAM_KEYS:
        print(f"  {key} = {selected['params'][key]}")

    print("\nSelected case results:")
    for case_id, result in selected["cases"].items():
        print(
            f"  {case_id}: score={result['score']:.3f}, "
            f"debt_years={result['debt_crisis_active_years_max']}, "
            f"gdp_year1={result['gdp_change_year1']:.3f}, "
            f"regime={result['regime_crisis_triggered']}"
        )

    print(f"\nTop-20 saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
