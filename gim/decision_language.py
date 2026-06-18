from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .explanations import DRIVER_LABELS
from .model_terms import TERM_EXPLANATIONS
from .types import RISK_LABELS


OUTCOME_EXPLANATIONS = {
    "status_quo": "the system remains tense but broadly within the current political order",
    "controlled_suppression": "authorities contain instability through coercive control rather than settlement",
    "internal_destabilization": "domestic economic and political stress becomes the main source of instability",
    "social_unrest_without_military": "domestic unrest rises and spreads without crossing into a military confrontation",
    "sovereign_financial_crisis": "sovereign debt, inflation and liquidity stress become the primary crisis transmission channel",
    "limited_proxy_escalation": "competition intensifies indirectly through proxies, covert pressure or local clashes",
    "maritime_chokepoint_crisis": "trade and energy routes become the central stress channel, pushing up disruption risk",
    "direct_strike_exchange": "actors move from signaling into overt military exchange",
    "broad_regional_escalation": "the crisis spreads across multiple actors and theaters into a wider regional shock",
    "negotiated_deescalation": "the system shifts toward bargaining, mediation and partial stabilization",
}

ESCALATORY_OUTCOMES = {
    "controlled_suppression",
    "internal_destabilization",
    "social_unrest_without_military",
    "sovereign_financial_crisis",
    "limited_proxy_escalation",
    "maritime_chokepoint_crisis",
    "direct_strike_exchange",
    "broad_regional_escalation",
}


@dataclass(frozen=True)
class DecisionHighlight:
    kind: str
    title: str
    body: str


def risk_label(risk_name: str) -> str:
    return RISK_LABELS.get(risk_name, labelize(risk_name))


def labelize(value: str) -> str:
    return value.replace("_", " ").strip().title()


def actor_phrase(actor_names: list[str]) -> str:
    if not actor_names:
        return "the selected actors"
    if len(actor_names) == 1:
        return actor_names[0]
    if len(actor_names) == 2:
        return f"{actor_names[0]} and {actor_names[1]}"
    return ", ".join(actor_names[:-1]) + f", and {actor_names[-1]}"


def horizon_label(scenario: dict[str, Any], horizon_years: int) -> str:
    if horizon_years > 0:
        display_year = scenario.get("display_year", scenario.get("base_year"))
        return f"{horizon_years} years ({display_year}->{display_year + horizon_years})"
    return f"{scenario.get('horizon_months', 0)} months"


def horizon_phrase(scenario: dict[str, Any], horizon_years: int) -> str:
    if horizon_years > 0:
        return f"over the next {horizon_years} years"
    months = scenario.get("horizon_months", 0)
    if months:
        return f"over the next {months} months"
    return "in the current snapshot"


def top_driver_entries(evaluation: dict[str, Any], limit: int = 5) -> list[tuple[str, float]]:
    return sorted(
        (evaluation.get("driver_scores") or {}).items(),
        key=lambda item: item[1],
        reverse=True,
    )[:limit]


def select_glossary_keys(
    evaluation: dict[str, Any],
    actor_ids: list[str],
    *,
    top_driver_count: int = 4,
    top_actor_metric_count: int = 2,
) -> list[str]:
    keys: list[str] = [name for name, _value in top_driver_entries(evaluation, top_driver_count)]
    dashboard_agents = (evaluation.get("crisis_dashboard") or {}).get("agents", {})
    for actor_id in actor_ids[:3]:
        report = dashboard_agents.get(actor_id)
        if not report:
            continue
        keys.extend(report.get("top_metric_names", [])[:top_actor_metric_count])

    deduped: list[str] = []
    seen: set[str] = set()
    for key in keys:
        if key in seen:
            continue
        if key not in TERM_EXPLANATIONS:
            continue
        seen.add(key)
        deduped.append(key)
    return deduped


def scenario_summary_text(
    scenario: dict[str, Any],
    evaluation: dict[str, Any],
    *,
    actor_names: list[str] | None = None,
    horizon_years: int,
) -> str:
    top_outcome = evaluation["dominant_outcomes"][0]
    second_outcome = evaluation["dominant_outcomes"][1] if len(evaluation["dominant_outcomes"]) > 1 else top_outcome
    actors = actor_names or list(scenario.get("actor_names") or [])
    return (
        f"This run asks whether tensions involving {actor_phrase(actors)} "
        f"{horizon_phrase(scenario, horizon_years)} move the system toward "
        f"{risk_label(top_outcome).lower()} rather than {risk_label(second_outcome).lower()}. "
        f"The current leading answer is {100.0 * evaluation['risk_probabilities'].get(top_outcome, 0.0):.1f}% "
        f"for {risk_label(top_outcome).lower()}, meaning "
        f"{OUTCOME_EXPLANATIONS.get(top_outcome, 'the model sees it as the dominant system trajectory')}."
    )


def executive_summary_text(
    scenario: dict[str, Any],
    evaluation: dict[str, Any],
    *,
    actor_names: list[str] | None = None,
    horizon_years: int,
) -> str:
    top_outcome = evaluation["dominant_outcomes"][0]
    second_outcome = evaluation["dominant_outcomes"][1] if len(evaluation["dominant_outcomes"]) > 1 else top_outcome
    actors = actor_names or list(scenario.get("actor_names") or [])
    return (
        f"This run tests whether tensions involving {actor_phrase(actors)} "
        f"{horizon_phrase(scenario, horizon_years)} move the system toward "
        f"{risk_label(top_outcome).lower()} rather than {risk_label(second_outcome).lower()}. "
        f"The leading outcome is {risk_label(top_outcome).lower()} at "
        f"{100.0 * evaluation['risk_probabilities'].get(top_outcome, 0.0):.1f}%, which means "
        f"{OUTCOME_EXPLANATIONS.get(top_outcome, 'the model sees it as the dominant system trajectory')}. "
        f"Criticality is {evaluation['criticality_score']:.2f}, calibration is {evaluation['calibration_score']:.2f}, "
        f"and physical consistency is {evaluation['physical_consistency_score']:.2f}."
    )


def current_reading_text(evaluation: dict[str, Any]) -> str:
    top_outcome = evaluation["dominant_outcomes"][0]
    return (
        f"Leading scenario: {risk_label(top_outcome)}. "
        f"{OUTCOME_EXPLANATIONS.get(top_outcome, 'This is the dominant model reading.')}"
    )


def build_highlights(
    *,
    evaluation: dict[str, Any],
    initial_evaluation: dict[str, Any] | None,
    game_result: dict[str, Any] | None,
    trajectory: list[dict[str, Any]],
    actor_ids: list[str],
) -> list[DecisionHighlight]:
    lines: list[DecisionHighlight] = []
    top_outcome = evaluation["dominant_outcomes"][0]
    top_prob = evaluation["risk_probabilities"].get(top_outcome, 0.0)

    criticality_delta = 0.0
    initial_criticality = evaluation["criticality_score"]
    if initial_evaluation is not None:
        initial_criticality = initial_evaluation.get("criticality_score", initial_criticality)
        criticality_delta = evaluation["criticality_score"] - initial_criticality

    if top_outcome in ESCALATORY_OUTCOMES:
        lines.append(
            DecisionHighlight(
                kind="k-up",
                title="Escalation remains the dominant reading",
                body=f"{risk_label(top_outcome)} leads at {100.0 * top_prob:.1f}%.",
            )
        )
    if criticality_delta > 0.05:
        lines.append(
            DecisionHighlight(
                kind="k-up",
                title="Criticality is worsening",
                body=f"Criticality moved from {initial_criticality:.2f} to {evaluation['criticality_score']:.2f}.",
            )
        )
    if top_outcome == "maritime_chokepoint_crisis":
        lines.append(
            DecisionHighlight(
                kind="k-flat",
                title="Route and energy exposure are central",
                body="The model is treating disruption of maritime flows as the main risk transmission channel.",
            )
        )
    elif global_energy_stress_increasing(trajectory, evaluation):
        lines.append(
            DecisionHighlight(
                kind="k-flat",
                title="Global energy stress is rising",
                body="Oil-market and volume-gap pressure are widening even without a full maritime-break outcome.",
            )
        )

    negotiation_capacity = max(
        (
            profile.get("negotiation_capacity", 0.0)
            for profile in (evaluation.get("actor_profiles") or {}).values()
        ),
        default=0.0,
    )
    if game_result is not None:
        best = game_result.get("best_combination") or {}
        best_delta = (best.get("evaluation") or {}).get("criticality_score", 0.0) - (
            (game_result.get("baseline_evaluation") or {}).get("criticality_score", 0.0)
        )
        if best_delta < -0.03 and negotiation_capacity > 0.55:
            lines.append(
                DecisionHighlight(
                    kind="k-down",
                    title="A negotiation window exists",
                    body=f"The top strategy improves criticality by {best_delta:+.2f} and negotiation capacity remains {negotiation_capacity:.2f}.",
                )
            )

    worst_debt = worst_debt_actor(trajectory, actor_ids=actor_ids)
    if worst_debt is not None:
        lines.append(
            DecisionHighlight(
                kind="k-flat",
                title="Debt fragility remains material",
                body=f"{worst_debt['name']} ends the run at debt/GDP {worst_debt['debt_ratio']:.2f}.",
            )
        )

    if climate_events_count(trajectory) == 0:
        lines.append(
            DecisionHighlight(
                kind="k-down",
                title="Climate feedback stays secondary",
                body="No explicit climate shock events were detected in the simulated years.",
            )
        )

    if len(lines) < 2:
        top_drivers = ", ".join(DRIVER_LABELS.get(name, labelize(name)) for name, _value in top_driver_entries(evaluation, 3))
        lines.append(
            DecisionHighlight(
                kind="k-flat",
                title="Primary stress pattern",
                body=f"The scenario is still driven mainly by {top_drivers}.",
            )
        )
    return lines[:5]


def global_energy_stress_increasing(trajectory: list[dict[str, Any]], evaluation: dict[str, Any]) -> bool:
    if len(trajectory) <= 1:
        return False
    start_price = (trajectory[0].get("global_state") or {}).get("prices", {}).get("energy", 1.0)
    end_price = (trajectory[-1].get("global_state") or {}).get("prices", {}).get("energy", 1.0)
    global_metrics = (evaluation.get("crisis_dashboard") or {}).get("global_context", {}).get("metrics", {})
    oil_stress = global_metrics.get("global_oil_market_stress", {}).get("level", 0.0)
    return (end_price - start_price) > 0.10 or oil_stress > 0.45


def worst_debt_actor(
    trajectory: list[dict[str, Any]],
    *,
    actor_ids: list[str] | None = None,
) -> dict[str, Any] | None:
    if not trajectory:
        return None
    terminal_agents = trajectory[-1].get("agents") or {}
    relevant_agents = (
        [terminal_agents[actor_id] for actor_id in actor_ids if actor_id in terminal_agents]
        if actor_ids
        else list(terminal_agents.values())
    )
    worst: dict[str, Any] | None = None
    worst_ratio = 1.0
    for agent in relevant_agents:
        debt_ratio = safe_div(agent["economy"].get("public_debt", 0.0), agent["economy"].get("gdp", 0.0))
        if debt_ratio > worst_ratio:
            worst_ratio = debt_ratio
            worst = {"name": agent["name"], "debt_ratio": debt_ratio}
    return worst


def climate_events_count(trajectory: list[dict[str, Any]]) -> int:
    if len(trajectory) <= 1:
        return 0
    count = 0
    for index in range(1, len(trajectory)):
        previous = trajectory[index - 1]
        current = trajectory[index]
        for agent_id, agent in (current.get("agents") or {}).items():
            previous_agent = (previous.get("agents") or {}).get(agent_id)
            if previous_agent is None:
                continue
            if (
                agent["economy"].get("climate_shock_years", 0.0) > previous_agent["economy"].get("climate_shock_years", 0.0)
                or agent["economy"].get("climate_shock_penalty", 0.0) > previous_agent["economy"].get("climate_shock_penalty", 0.0) + 1e-9
            ):
                count += 1
    return count


def world_gdp(world: dict[str, Any]) -> float:
    return sum(agent["economy"].get("gdp", 0.0) for agent in (world.get("agents") or {}).values())


def global_debt_ratio(world: dict[str, Any]) -> float:
    total_debt = sum(agent["economy"].get("public_debt", 0.0) for agent in (world.get("agents") or {}).values())
    total_gdp = world_gdp(world)
    return safe_div(total_debt, total_gdp)


def global_social_tension(world: dict[str, Any]) -> float:
    agents = list((world.get("agents") or {}).values())
    total_population = sum(max(agent["economy"].get("population", 0.0), 0.0) for agent in agents)
    if total_population <= 1e-9:
        return 0.0
    weighted = sum(
        max(agent["economy"].get("population", 0.0), 0.0) * agent["society"].get("social_tension", 0.0)
        for agent in agents
    )
    return weighted / total_population


def global_emissions(world: dict[str, Any]) -> float:
    return sum(agent["climate"].get("co2_annual_emissions", 0.0) for agent in (world.get("agents") or {}).values())


def safe_div(numerator: float, denominator: float) -> float:
    if abs(denominator) <= 1e-9:
        return 0.0
    return numerator / denominator
