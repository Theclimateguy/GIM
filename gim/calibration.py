from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from .game_runner import GameRunner
from .runtime import MISC_ROOT, REPO_ROOT, default_state_csv, load_world
from .scenario_compiler import compile_question
from .sim_bridge import SimBridge


CALIBRATION_CASES_DIR = MISC_ROOT / "calibration_cases"
DEFAULT_CALIBRATION_SUITE = "operational_v1"
DEFAULT_TOP_DRIVER_LIMIT = 4
DEFAULT_TOP_METRIC_LIMIT = 3

COMPONENT_WEIGHTS = {
    "top_outcome": 0.30,
    "dominant_outcomes": 0.25,
    "drivers": 0.20,
    "actor_metrics": 0.15,
    "quality": 0.10,
}


@dataclass
class CalibrationScenarioSpec:
    question: str
    actors: list[str]
    template: str | None = None
    base_year: int | None = None
    horizon_months: int = 24


@dataclass
class CalibrationExpectationSpec:
    top_outcomes: list[str]
    dominant_outcomes: list[str] = field(default_factory=list)
    drivers: list[str] = field(default_factory=list)
    actor_metrics: dict[str, list[str]] = field(default_factory=dict)
    min_calibration_score: float = 0.85
    min_physical_consistency_score: float = 0.85
    min_criticality_score: float = 0.50
    minimum_case_score: float = 0.65


@dataclass
class CalibrationCaseSpec:
    id: str
    title: str
    description: str
    reference_period: str
    scenario: CalibrationScenarioSpec
    expectations: CalibrationExpectationSpec
    historical_signals: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class CalibrationRunConfig:
    n_runs: int = 1
    horizon_years: int = 0
    use_sim: bool = False
    default_mode: str = "compiled-llm"
    llm_refresh: str = "trigger"
    llm_refresh_years: int = 2


@dataclass
class CalibrationCaseSnapshot:
    dominant_outcomes: list[str]
    dominant_probabilities: dict[str, float]
    top_drivers: list[str]
    actor_top_metrics: dict[str, list[str]]
    calibration_score: float
    physical_consistency_score: float
    criticality_score: float


@dataclass
class CalibrationCaseResult:
    case_id: str
    title: str
    reference_period: str
    passed: bool
    total_score: float
    component_scores: dict[str, float]
    quality_checks: dict[str, bool]
    snapshot: CalibrationCaseSnapshot
    std_score: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass
class CalibrationSuiteResult:
    suite_id: str
    state_csv: str
    case_count: int
    pass_count: int
    average_score: float
    average_calibration_score: float
    average_physical_consistency_score: float
    average_criticality_score: float
    results: list[CalibrationCaseResult]


def discover_calibration_suites() -> list[str]:
    if not CALIBRATION_CASES_DIR.exists():
        return []
    return sorted(path.name for path in CALIBRATION_CASES_DIR.iterdir() if path.is_dir())


def discover_calibration_cases(suite_id: str = DEFAULT_CALIBRATION_SUITE) -> list[Path]:
    suite_dir = CALIBRATION_CASES_DIR / suite_id
    if not suite_dir.exists():
        raise FileNotFoundError(f"Calibration suite '{suite_id}' does not exist: {suite_dir}")
    return sorted(path for path in suite_dir.glob("*.json") if path.is_file())


def _default_calibration_state_csv() -> str:
    return default_state_csv()


def _load_case(path: Path) -> CalibrationCaseSpec:
    raw = json.loads(path.read_text())
    return CalibrationCaseSpec(
        id=str(raw["id"]),
        title=str(raw["title"]),
        description=str(raw["description"]),
        reference_period=str(raw["reference_period"]),
        scenario=CalibrationScenarioSpec(
            question=str(raw["scenario"]["question"]),
            actors=list(raw["scenario"].get("actors", [])),
            template=raw["scenario"].get("template"),
            base_year=raw["scenario"].get("base_year"),
            horizon_months=int(raw["scenario"].get("horizon_months", 24)),
        ),
        expectations=CalibrationExpectationSpec(
            top_outcomes=list(raw["expectations"].get("top_outcomes", [])),
            dominant_outcomes=list(raw["expectations"].get("dominant_outcomes", [])),
            drivers=list(raw["expectations"].get("drivers", [])),
            actor_metrics={
                str(actor_name): list(metric_names)
                for actor_name, metric_names in raw["expectations"].get("actor_metrics", {}).items()
            },
            min_calibration_score=float(raw["expectations"].get("min_calibration_score", 0.85)),
            min_physical_consistency_score=float(
                raw["expectations"].get("min_physical_consistency_score", 0.85)
            ),
            min_criticality_score=float(raw["expectations"].get("min_criticality_score", 0.50)),
            minimum_case_score=float(raw["expectations"].get("minimum_case_score", 0.65)),
        ),
        historical_signals=list(raw.get("historical_signals", [])),
        tags=list(raw.get("tags", [])),
    )


def _overlap_ratio(expected: list[str], actual: list[str]) -> float:
    if not expected:
        return 1.0
    actual_set = set(actual)
    hits = sum(1 for item in expected if item in actual_set)
    return hits / len(expected)


def _driver_names(evaluation: Any, limit: int = DEFAULT_TOP_DRIVER_LIMIT) -> list[str]:
    return [
        driver_name
        for driver_name, _value in sorted(
            evaluation.driver_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:limit]
    ]


def _actor_metric_names(evaluation: Any, limit: int = DEFAULT_TOP_METRIC_LIMIT) -> dict[str, list[str]]:
    return {
        report.agent_name: list(report.top_metric_names[:limit])
        for report in evaluation.crisis_dashboard.agents.values()
    }


def _quality_checks(expectations: CalibrationExpectationSpec, evaluation: Any) -> dict[str, bool]:
    return {
        "calibration_score": evaluation.calibration_score >= expectations.min_calibration_score,
        "physical_consistency_score": (
            evaluation.physical_consistency_score >= expectations.min_physical_consistency_score
        ),
        "criticality_score": evaluation.criticality_score >= expectations.min_criticality_score,
    }


def _score_case(case: CalibrationCaseSpec, evaluation: Any) -> CalibrationCaseResult:
    actual_dominant = list(evaluation.dominant_outcomes)
    actual_top_drivers = _driver_names(evaluation)
    actual_actor_metrics = _actor_metric_names(evaluation)

    top_outcome_score = 1.0 if actual_dominant and actual_dominant[0] in case.expectations.top_outcomes else 0.0
    dominant_score = _overlap_ratio(case.expectations.dominant_outcomes, actual_dominant)
    driver_score = _overlap_ratio(case.expectations.drivers, actual_top_drivers)

    actor_metric_scores: list[float] = []
    missing_actor_expectations: list[str] = []
    for actor_name, expected_metrics in case.expectations.actor_metrics.items():
        actual_metrics = actual_actor_metrics.get(actor_name)
        if actual_metrics is None:
            missing_actor_expectations.append(actor_name)
            actor_metric_scores.append(0.0)
            continue
        actor_metric_scores.append(_overlap_ratio(expected_metrics, actual_metrics))
    actor_metric_score = (
        sum(actor_metric_scores) / len(actor_metric_scores) if actor_metric_scores else 1.0
    )

    quality_checks = _quality_checks(case.expectations, evaluation)
    quality_score = sum(1.0 for passed in quality_checks.values() if passed) / max(
        len(quality_checks), 1
    )

    component_scores = {
        "top_outcome": COMPONENT_WEIGHTS["top_outcome"] * top_outcome_score,
        "dominant_outcomes": COMPONENT_WEIGHTS["dominant_outcomes"] * dominant_score,
        "drivers": COMPONENT_WEIGHTS["drivers"] * driver_score,
        "actor_metrics": COMPONENT_WEIGHTS["actor_metrics"] * actor_metric_score,
        "quality": COMPONENT_WEIGHTS["quality"] * quality_score,
    }
    total_score = sum(component_scores.values())

    notes: list[str] = []
    if top_outcome_score == 0.0 and actual_dominant:
        notes.append(
            f"Top outcome mismatch: got '{actual_dominant[0]}', expected one of {case.expectations.top_outcomes}."
        )
    if dominant_score < 1.0 and case.expectations.dominant_outcomes:
        notes.append(
            f"Dominant outcome overlap {dominant_score:.2f}: actual {actual_dominant}, expected {case.expectations.dominant_outcomes}."
        )
    if driver_score < 1.0 and case.expectations.drivers:
        notes.append(
            f"Driver overlap {driver_score:.2f}: actual {actual_top_drivers}, expected {case.expectations.drivers}."
        )
    if actor_metric_score < 1.0 and case.expectations.actor_metrics:
        notes.append(
            f"Actor metric overlap {actor_metric_score:.2f}: actual {actual_actor_metrics}."
        )
    for actor_name in missing_actor_expectations:
        notes.append(f"Expected actor metrics for '{actor_name}' could not be evaluated.")
    for check_name, passed in quality_checks.items():
        if not passed:
            notes.append(f"Quality floor failed: {check_name}.")

    snapshot = CalibrationCaseSnapshot(
        dominant_outcomes=actual_dominant,
        dominant_probabilities={
            risk_name: evaluation.risk_probabilities[risk_name] for risk_name in actual_dominant
        },
        top_drivers=actual_top_drivers,
        actor_top_metrics=actual_actor_metrics,
        calibration_score=evaluation.calibration_score,
        physical_consistency_score=evaluation.physical_consistency_score,
        criticality_score=evaluation.criticality_score,
    )
    passed = total_score >= case.expectations.minimum_case_score and all(quality_checks.values())

    return CalibrationCaseResult(
        case_id=case.id,
        title=case.title,
        reference_period=case.reference_period,
        passed=passed,
        total_score=total_score,
        std_score=0.0,
        component_scores=component_scores,
        quality_checks=quality_checks,
        snapshot=snapshot,
        notes=notes,
    )


def _run_single_case(
    case: CalibrationCaseSpec,
    *,
    world: Any,
    runner: GameRunner,
    bridge: SimBridge | None,
    config: CalibrationRunConfig,
) -> Any:
    scenario = compile_question(
        question=case.scenario.question,
        world=world,
        base_year=case.scenario.base_year,
        actors=case.scenario.actors,
        horizon_months=case.scenario.horizon_months,
        template_id=case.scenario.template,
    )
    if config.use_sim and config.horizon_years > 0:
        assert bridge is not None
        evaluation, _trajectory = bridge.evaluate_scenario(
            world,
            scenario,
            n_years=config.horizon_years,
            default_mode=config.default_mode,
            llm_refresh=config.llm_refresh,
            llm_refresh_years=config.llm_refresh_years,
        )
        return evaluation
    return runner.evaluate_scenario(scenario)


def _aggregate_case_results(
    case: CalibrationCaseSpec,
    run_results: list[CalibrationCaseResult],
) -> CalibrationCaseResult:
    if not run_results:
        raise ValueError(f"No calibration results available for case {case.id}")

    total_scores = [result.total_score for result in run_results]
    mean_score = mean(total_scores)
    std_score = pstdev(total_scores) if len(total_scores) > 1 else 0.0
    representative = min(run_results, key=lambda result: abs(result.total_score - mean_score))

    mean_component_scores = {
        key: mean(result.component_scores[key] for result in run_results)
        for key in representative.component_scores
    }
    mean_calibration_score = mean(result.snapshot.calibration_score for result in run_results)
    mean_physical_consistency_score = mean(
        result.snapshot.physical_consistency_score for result in run_results
    )
    mean_criticality_score = mean(result.snapshot.criticality_score for result in run_results)
    quality_checks = {
        "calibration_score": mean_calibration_score >= case.expectations.min_calibration_score,
        "physical_consistency_score": (
            mean_physical_consistency_score >= case.expectations.min_physical_consistency_score
        ),
        "criticality_score": mean_criticality_score >= case.expectations.min_criticality_score,
    }

    notes = list(representative.notes)
    if std_score > 0.0:
        notes.append(f"Run dispersion std={std_score:.3f} over {len(run_results)} runs.")

    snapshot = CalibrationCaseSnapshot(
        dominant_outcomes=list(representative.snapshot.dominant_outcomes),
        dominant_probabilities=dict(representative.snapshot.dominant_probabilities),
        top_drivers=list(representative.snapshot.top_drivers),
        actor_top_metrics=dict(representative.snapshot.actor_top_metrics),
        calibration_score=mean_calibration_score,
        physical_consistency_score=mean_physical_consistency_score,
        criticality_score=mean_criticality_score,
    )
    passed = (
        mean_score >= case.expectations.minimum_case_score
        and std_score < 0.15
        and all(quality_checks.values())
    )
    return CalibrationCaseResult(
        case_id=case.id,
        title=case.title,
        reference_period=case.reference_period,
        passed=passed,
        total_score=mean_score,
        std_score=std_score,
        component_scores=mean_component_scores,
        quality_checks=quality_checks,
        snapshot=snapshot,
        notes=notes,
    )


def run_operational_calibration(
    suite_id: str = DEFAULT_CALIBRATION_SUITE,
    *,
    state_csv: str | None = None,
    max_countries: int | None = None,
    config: CalibrationRunConfig | None = None,
    case_ids: set[str] | None = None,
) -> CalibrationSuiteResult:
    active_config = config or CalibrationRunConfig()
    if active_config.n_runs < 1:
        raise ValueError("CalibrationRunConfig.n_runs must be at least 1")
    resolved_state_csv = state_csv or _default_calibration_state_csv()
    world = load_world(state_csv=resolved_state_csv, max_agents=max_countries)
    runner = GameRunner(world)
    bridge = SimBridge() if active_config.use_sim and active_config.horizon_years > 0 else None

    case_specs = [_load_case(path) for path in discover_calibration_cases(suite_id)]
    if case_ids is not None:
        case_specs = [case for case in case_specs if case.id in case_ids]
    results: list[CalibrationCaseResult] = []

    for case in case_specs:
        run_results = []
        for _run_index in range(active_config.n_runs):
            evaluation = _run_single_case(
                case,
                world=world,
                runner=runner,
                bridge=bridge,
                config=active_config,
            )
            run_results.append(_score_case(case, evaluation))
        results.append(_aggregate_case_results(case, run_results))

    case_count = len(results)
    pass_count = sum(1 for result in results if result.passed)
    average_score = sum(result.total_score for result in results) / max(case_count, 1)
    average_calibration_score = sum(
        result.snapshot.calibration_score for result in results
    ) / max(case_count, 1)
    average_physical_consistency_score = sum(
        result.snapshot.physical_consistency_score for result in results
    ) / max(case_count, 1)
    average_criticality_score = sum(
        result.snapshot.criticality_score for result in results
    ) / max(case_count, 1)

    return CalibrationSuiteResult(
        suite_id=suite_id,
        state_csv=resolved_state_csv,
        case_count=case_count,
        pass_count=pass_count,
        average_score=average_score,
        average_calibration_score=average_calibration_score,
        average_physical_consistency_score=average_physical_consistency_score,
        average_criticality_score=average_criticality_score,
        results=results,
    )


def format_calibration_suite_result(result: CalibrationSuiteResult) -> str:
    lines = [
        f"Calibration suite: {result.suite_id}",
        f"State CSV: {result.state_csv}",
        f"Cases passed: {result.pass_count}/{result.case_count}",
        f"Average score: {result.average_score:.2f}",
        f"Average calibration score: {result.average_calibration_score:.2f}",
        f"Average physical consistency: {result.average_physical_consistency_score:.2f}",
        f"Average criticality: {result.average_criticality_score:.2f}",
        "",
        "Case results:",
    ]

    for case_result in result.results:
        status = "PASS" if case_result.passed else "FAIL"
        top_outcome = case_result.snapshot.dominant_outcomes[0] if case_result.snapshot.dominant_outcomes else "n/a"
        lines.append(
            f"- {case_result.case_id} [{status}] score={case_result.total_score:.2f} "
            f"std={case_result.std_score:.2f} top={top_outcome} period={case_result.reference_period}"
        )
        lines.append(
            "  "
            + (
                f"drivers={', '.join(case_result.snapshot.top_drivers[:4])}; "
                f"criticality={case_result.snapshot.criticality_score:.2f}"
            )
        )
        if case_result.notes:
            lines.append("  " + "notes: " + " | ".join(case_result.notes[:3]))

    return "\n".join(lines)


def suite_result_as_json(result: CalibrationSuiteResult) -> str:
    return json.dumps(asdict(result), indent=2, ensure_ascii=False)
