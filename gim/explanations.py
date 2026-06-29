from .crisis_metrics import CrisisDashboard
from .game_theory.equilibrium_runner import EquilibriumResult
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


def _top_crisis_changes(evaluation: ScenarioEvaluation, limit: int = 5) -> list[str]:
    changes: list[tuple[float, str]] = []
    for agent_id, metrics in evaluation.crisis_delta_by_agent.items():
        if agent_id == "__global__":
            prefix = "global"
        else:
            report = evaluation.crisis_dashboard.agents.get(agent_id)
            prefix = report.agent_name if report is not None else agent_id
        for metric_name, delta in metrics.items():
            weighted_shift = delta.get("weighted_shift", 0.0)
            if abs(weighted_shift) < 1e-6:
                continue
            direction = "up" if weighted_shift > 0 else "down"
            changes.append(
                (
                    abs(weighted_shift),
                    f"{prefix}: {metric_name} {direction} by {weighted_shift:+.2f}",
                )
            )
    changes.sort(key=lambda item: item[0], reverse=True)
    return [line for _score, line in changes[:limit]]


def format_question_evaluation(evaluation: ScenarioEvaluation) -> str:
    scenario = evaluation.scenario
    display_year = scenario.display_year or scenario.base_year
    lines = [
        f"Scenario: {scenario.title}",
        f"Template: {scenario.template_id}",
        f"Actors: {', '.join(scenario.actor_names) if scenario.actor_names else 'none'}",
        f"Horizon: {scenario.horizon_months} months from {display_year}",
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

    lines.append("")
    lines.append("Crisis layer:")
    lines.append(f"- Net crisis shift: {evaluation.crisis_signal_summary['net_crisis_shift']:+.2f}")
    lines.append(
        f"- Macro stress shift: {evaluation.crisis_signal_summary['macro_stress_shift']:+.2f}"
    )
    lines.append(
        f"- Stability stress shift: {evaluation.crisis_signal_summary['stability_stress_shift']:+.2f}"
    )
    lines.append(
        f"- Geopolitical stress shift: {evaluation.crisis_signal_summary['geopolitical_stress_shift']:+.2f}"
    )
    for report in evaluation.crisis_dashboard.agents.values():
        lines.append(f"- {report.agent_name} top crisis metrics: {', '.join(report.top_metric_names[:3])}")

    top_changes = _top_crisis_changes(evaluation, limit=4)
    if top_changes:
        lines.append("")
        lines.append("Largest crisis shifts:")
        for line in top_changes:
            lines.append(f"- {line}")

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
            "Crisis delta vs baseline:",
            f"- Net crisis shift: {best.evaluation.crisis_signal_summary['net_crisis_shift']:+.2f}",
            f"- Macro stress shift: {best.evaluation.crisis_signal_summary['macro_stress_shift']:+.2f}",
            f"- Stability stress shift: {best.evaluation.crisis_signal_summary['stability_stress_shift']:+.2f}",
            f"- Geopolitical stress shift: {best.evaluation.crisis_signal_summary['geopolitical_stress_shift']:+.2f}",
        ]
    )

    top_changes = _top_crisis_changes(best.evaluation, limit=5)
    if top_changes:
        lines.append("- Largest metric shifts:")
        for line in top_changes:
            lines.append(f"- {line}")

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

    lines.extend(
        [
            "",
            "Baseline top outcomes:",
        ]
    )
    for risk_name in result.baseline_evaluation.dominant_outcomes:
        lines.append(
            f"- {RISK_LABELS[risk_name]}: {_format_probability(result.baseline_evaluation.risk_probabilities[risk_name])}"
        )

    return "\n".join(lines)


def format_crisis_dashboard(dashboard: CrisisDashboard) -> str:
    lines = ["Global crisis context:"]
    for metric_name, metric in sorted(
        dashboard.global_context.metrics.items(),
        key=lambda item: item[1].severity,
        reverse=True,
    ):
        label = metric_name.replace("_", " ")
        lines.append(
            f"- {label}: value={metric.value:.3f} {metric.unit}, severity={metric.severity:.2f}"
        )

    for report in dashboard.agents.values():
        lines.extend(
            [
                "",
                f"{report.agent_name} [{report.archetype}]",
            ]
        )
        for metric_name in report.top_metric_names:
            metric = report.metrics[metric_name]
            lines.append(
                f"- {metric_name}: severity={metric.severity:.2f}, relevance={metric.relevance:.2f}, "
                f"value={metric.value:.3f} {metric.unit}"
            )

    return "\n".join(lines)


def format_equilibrium_result(result: EquilibriumResult) -> str:
    game = result.game
    name_map = {player.player_id: player.display_name for player in game.players}

    def _pretty_profile(key: str) -> str:
        parts = []
        for part in key.split("|"):
            player_id, action_name = part.split(":", 1)
            parts.append(f"{name_map.get(player_id, player_id)}={action_name}")
        return ", ".join(parts)

    def _pretty_pair(pair_key: str) -> str:
        left, right = pair_key.split(" || ", 1)
        return f"{_pretty_profile(left)} || {_pretty_profile(right)}"

    lines = [
        f"Equilibrium analysis: {game.title}",
        f"Scenario: {game.scenario.title}",
        f"Players: {', '.join(player.display_name for player in game.players)}",
        f"Episodes: {result.episodes}",
        f"Trust alpha: {result.trust_alpha:.2f}",
        f"Converged: {'yes' if result.converged else 'no'}",
        f"CE solver: {result.correlated_equilibrium.solver_status}",
        f"Max incentive deviation: {result.correlated_equilibrium.max_incentive_deviation:.6f}",
        f"Normative CE objective: {result.correlated_equilibrium.objective_description}",
        "",
        "Mean external regret:",
    ]

    if result.warnings:
        lines.extend(["", "Warnings:"])
        for warning in result.warnings:
            lines.append(f"- {warning}")

    for player in game.players:
        lines.append(
            f"- {player.display_name}: {result.mean_external_regret.get(player.player_id, 0.0):.4f}"
        )

    if result.mean_coalition_regret:
        lines.extend(["", "Mean coalition regret:"])
        for block, value in sorted(result.mean_coalition_regret.items()):
            lines.append(f"- {block}: {value:.4f}")

    lines.extend(["", "Recommended profile (argmax CE support):"])
    for player in game.players:
        action_name = result.recommended_profile.get(player.player_id, "n/a")
        lines.append(f"- {player.display_name}: {action_name}")

    if result.welfare is not None:
        welfare = result.welfare
        lines.extend(
            [
                "",
                "Welfare diagnostics:",
                f"- trust alpha: {welfare.alpha:.2f}",
                f"- utilitarian welfare: {welfare.utilitarian_sw:+.3f}",
                f"- trust-weighted welfare: {welfare.trust_weighted_sw:+.3f}",
                f"- payoff gini: {welfare.payoff_gini:.4f}",
            ]
        )
        if welfare.positive_normative_kl is not None:
            lines.append(f"- positive vs normative gap (KL): {welfare.positive_normative_kl:.6f}")
        if result.price_of_anarchy is not None:
            lines.append(f"- price of anarchy: {result.price_of_anarchy:.4f}")
        if welfare.action_correlations:
            lines.append("- top action correlations:")
            for pair_key, probability in welfare.action_correlations.items():
                lines.append(f"  {_pretty_pair(pair_key)}: {100.0 * probability:.1f}%")

    top_ce = sorted(
        result.correlated_equilibrium.distribution.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:5]
    if top_ce:
        lines.extend(["", "Top CE support:"])
        for key, probability in top_ce:
            lines.append(f"- {_pretty_profile(key)}: {100.0 * probability:.1f}%")

    top_cce = sorted(result.ccE_empirical.items(), key=lambda item: item[1], reverse=True)[:5]
    if top_cce:
        lines.extend(["", "Empirical CCE support:"])
        for key, probability in top_cce:
            lines.append(f"- {_pretty_profile(key)}: {100.0 * probability:.1f}%")

    if result.regret_history.records:
        swap_regret = result.regret_history.records[-1].swap_regret
        top_swap: list[tuple[float, str]] = []
        for player in game.players:
            for edge, value in swap_regret.get(player.player_id, {}).items():
                top_swap.append((value, f"{player.display_name}: {edge} -> {value:.4f}"))
        top_swap.sort(key=lambda item: item[0], reverse=True)
        if top_swap:
            lines.extend(["", "Largest swap-regret edges:"])
            for _value, label in top_swap[:5]:
                lines.append(f"- {label}")

    return "\n".join(lines)
