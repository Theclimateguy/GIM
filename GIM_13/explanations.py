from .types import GameResult, RISK_LABELS, ScenarioEvaluation


DRIVER_LABELS = {
    "debt_stress": "Debt stress",
    "social_stress": "Social stress",
    "resource_gap": "Resource gap",
    "energy_dependence": "Energy dependence",
    "conflict_stress": "Conflict stress",
    "sanctions_pressure": "Sanctions pressure",
    "military_posture": "Military posture",
    "climate_stress": "Climate stress",
    "policy_space": "Policy space",
    "negotiation_capacity": "Negotiation capacity",
    "tail_pressure": "Tail pressure",
    "multi_block_pressure": "Cross-block pressure",
    "actor_count_pressure": "Actor count pressure",
}


def _format_probability(value: float) -> str:
    return f"{100.0 * value:.1f}%"


def format_question_evaluation(evaluation: ScenarioEvaluation) -> str:
    scenario = evaluation.scenario
    lines = [
        f"Scenario: {scenario.title}",
        f"Template: {scenario.template_id}",
        f"Actors: {', '.join(scenario.actor_names) if scenario.actor_names else 'none'}",
        f"Horizon: {scenario.horizon_months} months from {scenario.base_year}",
        f"Criticality score: {evaluation.criticality_score:.2f}",
        f"Calibration score: {evaluation.calibration_score:.2f}",
        f"Physical consistency: {evaluation.physical_consistency_score:.2f}",
        "",
        "Top outcomes:",
    ]

    for risk_name in evaluation.dominant_outcomes:
        lines.append(
            f"- {RISK_LABELS[risk_name]}: {_format_probability(evaluation.risk_probabilities[risk_name])}"
        )

    lines.append("")
    lines.append("Strongest drivers:")
    for driver_name, driver_value in sorted(
        evaluation.driver_scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:5]:
        label = DRIVER_LABELS.get(driver_name, driver_name)
        lines.append(f"- {label}: {driver_value:.2f}")

    if scenario.unresolved_actor_names:
        lines.append("")
        lines.append(f"Unresolved actors: {', '.join(scenario.unresolved_actor_names)}")

    lines.append("")
    lines.append("Consistency notes:")
    for note in evaluation.consistency_notes:
        lines.append(f"- {note}")

    if evaluation.threshold_override_notes:
        lines.append("")
        lines.append("Soft-guardrail notes:")
        for note in evaluation.threshold_override_notes:
            lines.append(f"- {note}")

    return "\n".join(lines)


def format_game_result(result: GameResult) -> str:
    game = result.game
    best = result.best_combination
    lines = [
        f"Game: {game.title}",
        f"Scenario: {game.scenario.title}",
        f"Players: {', '.join(player.display_name for player in game.players)}",
    ]

    if result.truncated_action_space:
        lines.append("Action space was truncated to keep the MVP search bounded.")

    lines.extend(
        [
            "",
            "Best strategy profile:",
        ]
    )
    for player in game.players:
        lines.append(
            f"- {player.display_name}: {best.actions[player.player_id]} "
            f"(payoff {best.player_payoffs[player.player_id]:+.2f})"
        )

    lines.extend(
        [
            "",
            "Resulting top outcomes:",
        ]
    )
    for risk_name in best.evaluation.dominant_outcomes:
        lines.append(
            f"- {RISK_LABELS[risk_name]}: {_format_probability(best.evaluation.risk_probabilities[risk_name])}"
        )

    lines.extend(
        [
            "",
            "Top strategy profiles:",
        ]
    )
    for combination in result.combinations[:3]:
        strategy_line = ", ".join(
            f"{player.display_name}={combination.actions[player.player_id]}"
            for player in game.players
        )
        lines.append(f"- {strategy_line} -> total payoff {combination.total_payoff:+.2f}")

    return "\n".join(lines)
