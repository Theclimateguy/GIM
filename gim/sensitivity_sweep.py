from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from .calibration import CalibrationRunConfig, load_calibration_cases, run_operational_calibration
from . import geo_calibration as geo


OUTCOME_SENSITIVITY_CATEGORIES = (
    "outcome_intercept",
    "outcome_driver",
    "outcome_link",
    "tail_risk",
)


@dataclass
class GeoWeightPerturbationResult:
    factor: float
    value: float
    average_score: float
    pass_count: int
    case_count: int
    changed_pass_fail_cases: list[str] = field(default_factory=list)
    changed_top_outcome_cases: list[str] = field(default_factory=list)


@dataclass
class GeoWeightSensitivityEntry:
    path: str
    baseline_value: float
    sensitivity_flag: str
    max_abs_average_score_delta: float
    perturbations: list[GeoWeightPerturbationResult]


@dataclass
class GeoWeightSensitivityReport:
    suite_id: str
    state_csv: str
    baseline_case_count: int
    baseline_pass_count: int
    baseline_average_score: float
    entries: list[GeoWeightSensitivityEntry]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def outcome_weight_paths(categories: Iterable[str] = OUTCOME_SENSITIVITY_CATEGORIES) -> list[str]:
    category_set = set(categories)
    return sorted(
        path
        for path in geo.collect_geo_weight_paths()
        if path.split(":", 1)[0] in category_set
    )


def discriminating_weight_paths(
    *,
    suite_id: str = "operational_v1",
    case_ids: set[str] | None = None,
) -> list[str]:
    selected = []
    for case in load_calibration_cases(suite_id):
        if case_ids is not None and case.id not in case_ids:
            continue
        selected.extend(case.discriminating_weights)
    return sorted(dict.fromkeys(path for path in selected if path))


def _case_result_map(result) -> dict[str, object]:
    return {case_result.case_id: case_result for case_result in result.results}


def run_geo_sensitivity_sweep(
    *,
    suite_id: str = "operational_v1",
    state_csv: str | None = None,
    weight_paths: list[str] | None = None,
    scale_factors: tuple[float, ...] = (0.8, 1.2),
    config: CalibrationRunConfig | None = None,
    case_ids: set[str] | None = None,
) -> GeoWeightSensitivityReport:
    active_case_ids = set(case_ids) if case_ids is not None else None
    active_paths = weight_paths
    if active_paths is None:
        active_paths = discriminating_weight_paths(suite_id=suite_id, case_ids=active_case_ids)
    active_paths = active_paths or outcome_weight_paths()
    active_config = config or CalibrationRunConfig()

    baseline = run_operational_calibration(
        suite_id=suite_id,
        state_csv=state_csv,
        config=active_config,
        case_ids=active_case_ids,
    )
    baseline_by_case = _case_result_map(baseline)
    baseline_weights = geo.collect_geo_weight_paths()

    entries: list[GeoWeightSensitivityEntry] = []
    for path in active_paths:
        original_weight = baseline_weights[path]
        perturbations: list[GeoWeightPerturbationResult] = []
        try:
            for factor in scale_factors:
                perturbed_value = original_weight.value * factor
                geo.set_geo_weight_value(path, perturbed_value, source="sensitivity_probe")
                perturbed = run_operational_calibration(
                    suite_id=suite_id,
                    state_csv=state_csv,
                    config=active_config,
                    case_ids=active_case_ids,
                )
                perturbed_by_case = _case_result_map(perturbed)
                changed_pass_fail_cases = sorted(
                    case_id
                    for case_id, baseline_case in baseline_by_case.items()
                    if baseline_case.passed != perturbed_by_case[case_id].passed
                )
                changed_top_outcome_cases = sorted(
                    case_id
                    for case_id, baseline_case in baseline_by_case.items()
                    if baseline_case.snapshot.dominant_outcomes[:1]
                    != perturbed_by_case[case_id].snapshot.dominant_outcomes[:1]
                )
                perturbations.append(
                    GeoWeightPerturbationResult(
                        factor=factor,
                        value=perturbed_value,
                        average_score=perturbed.average_score,
                        pass_count=perturbed.pass_count,
                        case_count=perturbed.case_count,
                        changed_pass_fail_cases=changed_pass_fail_cases,
                        changed_top_outcome_cases=changed_top_outcome_cases,
                    )
                )
        finally:
            geo.replace_geo_weight_path(path, original_weight)

        max_abs_average_score_delta = max(
            abs(entry.average_score - baseline.average_score) for entry in perturbations
        )
        sensitivity_flag = "high" if (
            any(entry.changed_pass_fail_cases for entry in perturbations)
            or any(entry.changed_top_outcome_cases for entry in perturbations)
            or max_abs_average_score_delta >= 0.03
        ) else "low"
        entries.append(
            GeoWeightSensitivityEntry(
                path=path,
                baseline_value=original_weight.value,
                sensitivity_flag=sensitivity_flag,
                max_abs_average_score_delta=max_abs_average_score_delta,
                perturbations=perturbations,
            )
        )

    return GeoWeightSensitivityReport(
        suite_id=suite_id,
        state_csv=baseline.state_csv,
        baseline_case_count=baseline.case_count,
        baseline_pass_count=baseline.pass_count,
        baseline_average_score=baseline.average_score,
        entries=entries,
    )


def format_geo_sensitivity_report(report: GeoWeightSensitivityReport, top_n: int = 12) -> str:
    lines = [
        f"Sensitivity sweep: suite={report.suite_id}",
        f"State CSV: {report.state_csv}",
        (
            f"Baseline: pass={report.baseline_pass_count}/{report.baseline_case_count} "
            f"avg_score={report.baseline_average_score:.3f}"
        ),
        "",
        "Most sensitive weights:",
    ]

    ranked = sorted(
        report.entries,
        key=lambda entry: (entry.sensitivity_flag == "high", entry.max_abs_average_score_delta),
        reverse=True,
    )
    for entry in ranked[:top_n]:
        lines.append(
            f"- {entry.path} [{entry.sensitivity_flag}] baseline={entry.baseline_value:.3f} "
            f"max_delta={entry.max_abs_average_score_delta:.3f}"
        )
        for perturbation in entry.perturbations:
            lines.append(
                "  "
                + (
                    f"x{perturbation.factor:.2f} -> avg={perturbation.average_score:.3f} "
                    f"pass={perturbation.pass_count}/{perturbation.case_count} "
                    f"pass_fail_flips={','.join(perturbation.changed_pass_fail_cases) or 'none'} "
                    f"top_flips={','.join(perturbation.changed_top_outcome_cases) or 'none'}"
                )
            )
    return "\n".join(lines)
