from __future__ import annotations

from . import geo_calibration as geo


def _all_weights_within_ci() -> list[str]:
    warnings: list[str] = []
    for path, weight in geo.collect_geo_weight_paths().items():
        lo, hi = weight.ci95
        if not (lo <= weight.value <= hi):
            warnings.append(
                f"[fatal] {path} value {weight.value:.3f} is outside ci95=({lo:.3f}, {hi:.3f})."
            )
    return warnings


def validate_outcome_weights() -> list[str]:
    warnings = _all_weights_within_ci()
    status_quo = geo.OUTCOME_INTERCEPTS["status_quo"].value
    others = [
        weight.value
        for key, weight in geo.OUTCOME_INTERCEPTS.items()
        if key != "status_quo"
    ]
    if others and status_quo <= max(others):
        warnings.append("[fatal] status_quo should remain the largest outcome intercept.")

    for outcome_name, drivers in geo.OUTCOME_DRIVERS.items():
        total = sum(abs(weight.value) for weight in drivers.values())
        if total > 2.0:
            warnings.append(
                f"[fatal] {outcome_name} driver mass is {total:.2f}, above the 2.0 sanity ceiling."
            )
    return warnings


def validate_action_shifts() -> list[str]:
    warnings: list[str] = []
    for action_name, shifts in geo.ACTION_RISK_SHIFTS.items():
        for outcome_name, weight in shifts.items():
            if abs(weight.value) > 0.25:
                warnings.append(
                    f"[warn] {action_name}->{outcome_name} shift {weight.value:.2f} exceeds the soft 0.25 bound."
                )

    for action_name in geo.ESCALATORY_ACTIONS:
        shifts = geo.ACTION_RISK_SHIFTS.get(action_name, {})
        for outcome_name in ("direct_strike_exchange", "broad_regional_escalation"):
            weight = shifts.get(outcome_name)
            if weight is not None and weight.value < 0.0:
                warnings.append(
                    f"[warn] escalatory action {action_name} lowers {outcome_name} by {weight.value:.2f}."
                )
    return warnings


def validate_crisis_weights() -> list[str]:
    warnings = _all_weights_within_ci()
    if abs(
        geo.CRISIS_METRIC_WEIGHTS["severity_level_weight"].value
        + geo.CRISIS_METRIC_WEIGHTS["severity_momentum_weight"].value
        + geo.CRISIS_METRIC_WEIGHTS["severity_buffer_weight"].value
        + geo.CRISIS_METRIC_WEIGHTS["severity_trigger_weight"].value
        - 1.0
    ) > 1e-9:
        warnings.append("[fatal] Crisis severity weights should sum to 1.0.")

    if abs(
        geo.CRISIS_METRIC_WEIGHTS["import_dependency_energy_weight"].value
        + geo.CRISIS_METRIC_WEIGHTS["import_dependency_food_weight"].value
        + geo.CRISIS_METRIC_WEIGHTS["import_dependency_metals_weight"].value
        - 1.0
    ) > 1e-9:
        warnings.append("[fatal] Import-dependency weights should sum to 1.0.")

    if abs(
        geo.CRISIS_METRIC_WEIGHTS["basket_food_weight"].value
        + geo.CRISIS_METRIC_WEIGHTS["basket_energy_weight"].value
        + geo.CRISIS_METRIC_WEIGHTS["basket_metals_weight"].value
        - 1.0
    ) > 1e-9:
        warnings.append("[fatal] Basket-price weights should sum to 1.0.")

    for archetype_name, relevance_map in geo.ARCHETYPE_RELEVANCE.items():
        for metric_name, weight in relevance_map.items():
            if not (0.0 <= weight.value <= 1.0):
                warnings.append(
                    f"[fatal] {archetype_name}.{metric_name} relevance {weight.value:.2f} is outside [0, 1]."
                )
    return warnings


def run_sanity_suite() -> dict:
    outcome_warnings = validate_outcome_weights()
    action_warnings = validate_action_shifts()
    crisis_warnings = validate_crisis_weights()
    fatal_count = sum(
        1
        for warning in outcome_warnings + action_warnings + crisis_warnings
        if warning.startswith("[fatal]")
    )
    return {
        "outcome_warnings": outcome_warnings,
        "action_warnings": action_warnings,
        "crisis_warnings": crisis_warnings,
        "pass": fatal_count == 0,
    }
