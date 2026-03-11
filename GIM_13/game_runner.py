from __future__ import annotations

from itertools import product
import math

from .runtime import AgentState, WorldState
from .types import (
    GameCombinationResult,
    GameDefinition,
    GameResult,
    ScenarioDefinition,
    ScenarioEvaluation,
    TAIL_RISK_CLASSES,
)


ACTION_RISK_SHIFTS = {
    "signal_deterrence": {
        "direct_strike_exchange": 0.15,
        "broad_regional_escalation": 0.05,
        "negotiated_deescalation": -0.05,
    },
    "signal_restraint": {
        "direct_strike_exchange": -0.20,
        "broad_regional_escalation": -0.15,
        "negotiated_deescalation": 0.20,
    },
    "arm_proxy": {
        "limited_proxy_escalation": 0.40,
        "broad_regional_escalation": 0.15,
    },
    "restrain_proxy": {
        "limited_proxy_escalation": -0.30,
        "negotiated_deescalation": 0.15,
    },
    "covert_disruption": {
        "limited_proxy_escalation": 0.20,
        "maritime_chokepoint_crisis": 0.10,
        "negotiated_deescalation": -0.05,
    },
    "maritime_interdiction": {
        "maritime_chokepoint_crisis": 0.55,
        "direct_strike_exchange": 0.15,
        "broad_regional_escalation": 0.15,
    },
    "partial_mobilization": {
        "direct_strike_exchange": 0.35,
        "broad_regional_escalation": 0.15,
    },
    "targeted_strike": {
        "direct_strike_exchange": 0.60,
        "broad_regional_escalation": 0.30,
        "negotiated_deescalation": -0.20,
    },
    "backchannel_offer": {
        "direct_strike_exchange": -0.10,
        "broad_regional_escalation": -0.10,
        "negotiated_deescalation": 0.30,
    },
    "accept_mediation": {
        "direct_strike_exchange": -0.15,
        "broad_regional_escalation": -0.15,
        "negotiated_deescalation": 0.40,
    },
    "information_campaign": {
        "controlled_suppression": 0.05,
        "internal_destabilization": 0.05,
    },
    "domestic_crackdown": {
        "controlled_suppression": 0.35,
        "internal_destabilization": 0.10,
        "negotiated_deescalation": -0.05,
    },
}

SHOCK_RISK_SHIFTS = {
    "sanctions": {
        "internal_destabilization": 0.22,
        "limited_proxy_escalation": 0.10,
        "controlled_suppression": 0.12,
    },
    "proxy": {
        "limited_proxy_escalation": 0.25,
        "broad_regional_escalation": 0.10,
    },
    "maritime": {
        "maritime_chokepoint_crisis": 0.35,
        "broad_regional_escalation": 0.08,
    },
    "domestic": {
        "controlled_suppression": 0.18,
        "internal_destabilization": 0.25,
    },
}

OBJECTIVE_TO_RISK_UTILITY = {
    "regime_retention": {
        "status_quo": 0.60,
        "controlled_suppression": 0.45,
        "negotiated_deescalation": 0.35,
        "internal_destabilization": -1.00,
        "broad_regional_escalation": -0.80,
    },
    "reduce_war_risk": {
        "status_quo": 0.35,
        "negotiated_deescalation": 1.00,
        "limited_proxy_escalation": -0.55,
        "maritime_chokepoint_crisis": -0.55,
        "direct_strike_exchange": -0.90,
        "broad_regional_escalation": -1.00,
    },
    "regional_influence": {
        "status_quo": 0.15,
        "limited_proxy_escalation": 0.40,
        "direct_strike_exchange": 0.10,
        "negotiated_deescalation": 0.25,
        "broad_regional_escalation": -0.30,
    },
    "sanctions_resilience": {
        "status_quo": 0.50,
        "negotiated_deescalation": 0.70,
        "internal_destabilization": -0.50,
        "maritime_chokepoint_crisis": -0.35,
        "direct_strike_exchange": -0.55,
        "broad_regional_escalation": -0.80,
    },
    "resource_access": {
        "status_quo": 0.50,
        "negotiated_deescalation": 0.70,
        "maritime_chokepoint_crisis": -1.00,
        "broad_regional_escalation": -0.55,
    },
    "bargaining_power": {
        "status_quo": 0.10,
        "limited_proxy_escalation": 0.20,
        "direct_strike_exchange": 0.10,
        "negotiated_deescalation": 0.40,
        "broad_regional_escalation": -0.20,
    },
}

ACTION_OBJECTIVE_BONUS = {
    "signal_deterrence": {"bargaining_power": 0.12, "regional_influence": 0.08},
    "signal_restraint": {"reduce_war_risk": 0.12},
    "arm_proxy": {"regional_influence": 0.18},
    "restrain_proxy": {"reduce_war_risk": 0.08},
    "maritime_interdiction": {"regional_influence": 0.08},
    "backchannel_offer": {"reduce_war_risk": 0.10, "bargaining_power": 0.06},
    "accept_mediation": {"reduce_war_risk": 0.15},
    "domestic_crackdown": {"regime_retention": 0.10},
}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _softmax(scores: dict[str, float]) -> dict[str, float]:
    max_score = max(scores.values()) if scores else 0.0
    shifted = {key: math.exp(value - max_score) for key, value in scores.items()}
    total = sum(shifted.values()) or 1.0
    return {key: value / total for key, value in shifted.items()}


class GameRunner:
    def __init__(self, world: WorldState):
        self.world = world

    def _profile_agent(self, agent: AgentState) -> dict[str, float]:
        debt_ratio = agent.economy.public_debt / max(agent.economy.gdp, 0.25)
        resource_gaps = []
        for resource in agent.resources.values():
            gap = max(resource.consumption - resource.production, 0.0) / max(resource.consumption, 1e-6)
            resource_gaps.append(gap)

        energy = agent.resources.get("energy")
        energy_dependence = 0.0
        if energy is not None:
            energy_dependence = max(energy.consumption - energy.production, 0.0) / max(
                energy.consumption, 1e-6
            )

        debt_stress = max(agent.risk.debt_crisis_prone, max(0.0, debt_ratio - 0.3))
        social_stress = (
            0.45 * agent.society.social_tension
            + 0.25 * (1.0 - agent.society.trust_gov)
            + 0.30 * (1.0 - agent.risk.regime_stability)
        )
        conflict_stress = (
            0.30 * agent.risk.conflict_proneness
            + 0.25 * agent.political.hawkishness
            + 0.20 * max(agent.technology.military_power - 0.75, 0.0)
            + 0.15 * (1.0 - agent.technology.security_index)
            + 0.10 * (1.0 - agent.political.coalition_openness)
        )
        sanctions_pressure = 0.18 * len(agent.active_sanctions) + max(0.0, debt_ratio - 0.5)
        military_posture = 0.55 * agent.technology.military_power + 0.45 * agent.technology.security_index
        climate_stress = 0.60 * agent.climate.climate_risk + 0.40 * agent.risk.water_stress
        policy_space = agent.political.policy_space
        negotiation_capacity = (
            0.40 * agent.political.coalition_openness
            + 0.30 * agent.society.trust_gov
            + 0.30 * agent.risk.regime_stability
        )
        tail_pressure = (
            social_stress
            + conflict_stress
            + _mean(resource_gaps)
            + 0.40 * debt_stress
            + 0.20 * climate_stress
        )

        return {
            "debt_stress": debt_stress,
            "social_stress": social_stress,
            "resource_gap": _mean(resource_gaps),
            "energy_dependence": energy_dependence,
            "conflict_stress": conflict_stress,
            "sanctions_pressure": sanctions_pressure,
            "military_posture": military_posture,
            "climate_stress": climate_stress,
            "policy_space": policy_space,
            "negotiation_capacity": negotiation_capacity,
            "tail_pressure": tail_pressure,
        }

    def _aggregate_profiles(self, actor_ids: list[str]) -> dict[str, float]:
        profiles = [self._profile_agent(self.world.agents[actor_id]) for actor_id in actor_ids]
        aggregate = {
            key: _mean([profile[key] for profile in profiles])
            for key in profiles[0]
        }
        blocks = {self.world.agents[actor_id].alliance_block for actor_id in actor_ids}
        aggregate["multi_block_pressure"] = max(0.0, (len(blocks) - 1) / 3.0)
        aggregate["actor_count_pressure"] = max(0.0, (len(actor_ids) - 1) / 3.0)
        return aggregate

    def _base_scores(
        self,
        scenario: ScenarioDefinition,
        aggregate: dict[str, float],
    ) -> dict[str, float]:
        bias = scenario.risk_biases
        scores = {
            "status_quo": (
                0.65
                + 0.35 * (1.0 - aggregate["social_stress"])
                + 0.20 * (1.0 - aggregate["conflict_stress"])
                + 0.20 * aggregate["policy_space"]
                - 0.15 * aggregate["resource_gap"]
            ),
            "controlled_suppression": (
                0.05
                + 0.75 * aggregate["social_stress"]
                + 0.35 * aggregate["military_posture"]
                - 0.20 * aggregate["negotiation_capacity"]
            ),
            "internal_destabilization": (
                -0.05
                + 0.95 * aggregate["social_stress"]
                + 0.45 * aggregate["debt_stress"]
                + 0.35 * aggregate["resource_gap"]
                - 0.20 * aggregate["policy_space"]
            ),
            "limited_proxy_escalation": (
                0.00
                + 0.85 * aggregate["conflict_stress"]
                + 0.25 * aggregate["sanctions_pressure"]
                + 0.15 * aggregate["actor_count_pressure"]
            ),
            "maritime_chokepoint_crisis": (
                -0.15
                + 1.10 * aggregate["energy_dependence"]
                + 0.40 * aggregate["conflict_stress"]
                + 0.25 * aggregate["resource_gap"]
            ),
            "direct_strike_exchange": (
                -0.10
                + 0.90 * aggregate["conflict_stress"]
                + 0.50 * aggregate["military_posture"]
                + 0.20 * aggregate["sanctions_pressure"]
            ),
            "broad_regional_escalation": (
                -0.35
                + 0.30 * aggregate["actor_count_pressure"]
                + 0.25 * aggregate["multi_block_pressure"]
                + 0.35 * aggregate["conflict_stress"]
            ),
            "negotiated_deescalation": (
                0.10
                + 0.80 * aggregate["negotiation_capacity"]
                + 0.15 * (1.0 - aggregate["conflict_stress"])
                - 0.20 * aggregate["tail_pressure"]
            ),
        }

        for risk_name, shift in bias.items():
            scores[risk_name] = scores.get(risk_name, 0.0) + shift

        scores["broad_regional_escalation"] += 0.30 * max(scores["direct_strike_exchange"], 0.0)
        scores["broad_regional_escalation"] += 0.20 * max(scores["limited_proxy_escalation"], 0.0)
        return scores

    def _apply_shocks(self, scores: dict[str, float], scenario: ScenarioDefinition) -> None:
        for shock in scenario.shocks:
            for risk_name, shift in SHOCK_RISK_SHIFTS.get(shock.channel, {}).items():
                scores[risk_name] = scores.get(risk_name, 0.0) + shift * shock.magnitude

    def _apply_actions(self, scores: dict[str, float], selected_actions: dict[str, str]) -> None:
        escalation_count = 0
        deescalation_count = 0
        for action_name in selected_actions.values():
            for risk_name, shift in ACTION_RISK_SHIFTS.get(action_name, {}).items():
                scores[risk_name] = scores.get(risk_name, 0.0) + shift
            if action_name in {
                "arm_proxy",
                "covert_disruption",
                "maritime_interdiction",
                "partial_mobilization",
                "targeted_strike",
            }:
                escalation_count += 1
            if action_name in {
                "signal_restraint",
                "restrain_proxy",
                "backchannel_offer",
                "accept_mediation",
            }:
                deescalation_count += 1

        if escalation_count:
            scores["direct_strike_exchange"] += 0.06 * escalation_count
            scores["broad_regional_escalation"] += 0.04 * escalation_count
        if deescalation_count:
            scores["negotiated_deescalation"] += 0.08 * deescalation_count
            scores["broad_regional_escalation"] -= 0.04 * deescalation_count

    def _expand_tail_risk(self, scores: dict[str, float], scenario: ScenarioDefinition, aggregate: dict[str, float]) -> None:
        critical_pressure = max(0.0, aggregate["tail_pressure"] - 1.25)
        additive_shift = (0.18 if scenario.critical_focus else 0.0) + 0.35 * critical_pressure
        for risk_name in TAIL_RISK_CLASSES:
            scores[risk_name] = scores.get(risk_name, 0.0) + additive_shift
        scores["status_quo"] -= 0.10 * critical_pressure

    def _assess_consistency(
        self,
        scenario: ScenarioDefinition,
        aggregate: dict[str, float],
        probabilities: dict[str, float],
        selected_actions: dict[str, str],
    ) -> tuple[float, list[str], list[str]]:
        physical_consistency = 1.0
        notes: list[str] = []
        threshold_notes: list[str] = []
        chosen_actions = set(selected_actions.values())

        if (
            probabilities["broad_regional_escalation"] > 0.20
            and aggregate["conflict_stress"] < 0.45
        ):
            notes.append(
                "Broad regional escalation was penalized because conflict stress is too low to support a regional cascade."
            )
            physical_consistency -= 0.20

        if (
            probabilities["maritime_chokepoint_crisis"] > 0.18
            and aggregate["energy_dependence"] < 0.08
            and "maritime_interdiction" not in chosen_actions
            and scenario.template_id != "maritime_deterrence"
        ):
            notes.append(
                "Maritime chokepoint risk was penalized because the actor set does not show enough route dependence."
            )
            physical_consistency -= 0.20

        if (
            probabilities["internal_destabilization"] > 0.18
            and aggregate["social_stress"] < 0.35
        ):
            notes.append(
                "Internal destabilization was penalized because domestic stress is too low for systemic breakdown."
            )
            physical_consistency -= 0.20

        if (
            probabilities["direct_strike_exchange"] > 0.18
            and aggregate["military_posture"] < 0.55
            and not chosen_actions.intersection({"partial_mobilization", "targeted_strike"})
        ):
            notes.append(
                "Direct strike risk was penalized because military posture is too weak for a sustained exchange."
            )
            physical_consistency -= 0.15

        if not notes:
            notes.append(
                "High-impact outcomes remain causally grounded in observable stress channels, shocks and selected actions."
            )

        if aggregate["energy_dependence"] > 0.12 or aggregate["resource_gap"] > 0.12:
            threshold_notes.append(
                "Soft threshold override: energy and resource imbalances are carried as shortage pressure instead of being clipped by hard demand caps."
            )
        if aggregate["debt_stress"] > 0.75:
            threshold_notes.append(
                "Soft threshold override: GDP contraction is allowed to exceed legacy comfort thresholds when fiscal and political stress reinforce each other."
            )
        if aggregate["tail_pressure"] > 1.60:
            threshold_notes.append(
                "Tail expansion is active: rare but explainable critical states stay in the distribution because several stress channels point in the same direction."
            )
        if scenario.unresolved_actor_names:
            threshold_notes.append(
                "Calibration note: unresolved actors stay outside the numeric core and should be added to the state CSV before operational use."
            )

        return max(0.0, min(1.0, physical_consistency)), notes, threshold_notes

    def evaluate_scenario(
        self,
        scenario: ScenarioDefinition,
        selected_actions: dict[str, str] | None = None,
    ) -> ScenarioEvaluation:
        actor_ids = scenario.actor_ids or list(self.world.agents)[:3]
        actor_profiles = {
            actor_id: self._profile_agent(self.world.agents[actor_id])
            for actor_id in actor_ids
        }
        aggregate = self._aggregate_profiles(actor_ids)
        scores = self._base_scores(scenario, aggregate)
        self._apply_shocks(scores, scenario)
        self._apply_actions(scores, selected_actions or {})
        self._expand_tail_risk(scores, scenario, aggregate)
        probabilities = _softmax(scores)
        physical_consistency_score, notes, threshold_notes = self._assess_consistency(
            scenario=scenario,
            aggregate=aggregate,
            probabilities=probabilities,
            selected_actions=selected_actions or {},
        )

        calibration_score = 1.0
        if scenario.unresolved_actor_names:
            calibration_score -= min(0.25, 0.05 * len(scenario.unresolved_actor_names))
        if scenario.calibration_guardrails.preserve_baseline_calibration:
            extreme_mass = (
                probabilities["internal_destabilization"]
                + probabilities["limited_proxy_escalation"]
                + probabilities["maritime_chokepoint_crisis"]
                + probabilities["direct_strike_exchange"]
                + probabilities["broad_regional_escalation"]
            )
            if extreme_mass > 0.85 and aggregate["tail_pressure"] < 1.40:
                calibration_score -= 0.15
        calibration_score = max(
            0.0,
            min(1.0, 0.50 * calibration_score + 0.50 * physical_consistency_score),
        )

        dominant_outcomes = sorted(
            probabilities,
            key=lambda risk_name: probabilities[risk_name],
            reverse=True,
        )[:3]
        criticality_score = (
            probabilities["controlled_suppression"] * 0.50
            + probabilities["internal_destabilization"] * 0.80
            + probabilities["limited_proxy_escalation"] * 0.60
            + probabilities["maritime_chokepoint_crisis"] * 0.70
            + probabilities["direct_strike_exchange"] * 0.85
            + probabilities["broad_regional_escalation"] * 1.00
        )

        return ScenarioEvaluation(
            scenario=scenario,
            raw_risk_scores=scores,
            risk_probabilities=probabilities,
            driver_scores=aggregate,
            actor_profiles=actor_profiles,
            dominant_outcomes=dominant_outcomes,
            criticality_score=criticality_score,
            calibration_score=calibration_score,
            physical_consistency_score=physical_consistency_score,
            consistency_notes=notes,
            threshold_override_notes=threshold_notes,
        )

    def _score_player(
        self,
        player,
        evaluation: ScenarioEvaluation,
        action_name: str,
    ) -> float:
        score = 0.0
        for objective_name, weight in player.objectives.items():
            utilities = OBJECTIVE_TO_RISK_UTILITY.get(objective_name, {})
            objective_value = sum(
                evaluation.risk_probabilities[risk_name] * utility
                for risk_name, utility in utilities.items()
            )
            objective_value += ACTION_OBJECTIVE_BONUS.get(action_name, {}).get(objective_name, 0.0)
            score += weight * objective_value

        score -= 0.25 * (1.0 - evaluation.calibration_score)
        score -= 0.25 * (1.0 - evaluation.physical_consistency_score)
        return score

    def run_game(self, game: GameDefinition, max_combinations: int = 256) -> GameResult:
        action_spaces = [player.allowed_actions or ["signal_restraint"] for player in game.players]
        combination_count = 1
        for action_space in action_spaces:
            combination_count *= max(1, len(action_space))

        truncated_action_space = False
        if combination_count > max_combinations:
            action_spaces = [action_space[:3] for action_space in action_spaces]
            truncated_action_space = True

        combinations: list[GameCombinationResult] = []
        for choice_tuple in product(*action_spaces):
            selected_actions = {
                player.player_id: action_name
                for player, action_name in zip(game.players, choice_tuple)
            }
            evaluation = self.evaluate_scenario(game.scenario, selected_actions=selected_actions)
            player_payoffs = {
                player.player_id: self._score_player(
                    player,
                    evaluation=evaluation,
                    action_name=selected_actions[player.player_id],
                )
                for player in game.players
            }
            combinations.append(
                GameCombinationResult(
                    actions=selected_actions,
                    evaluation=evaluation,
                    player_payoffs=player_payoffs,
                    total_payoff=sum(player_payoffs.values()),
                )
            )

        combinations.sort(key=lambda combo: combo.total_payoff, reverse=True)
        return GameResult(
            game=game,
            best_combination=combinations[0],
            combinations=combinations,
            truncated_action_space=truncated_action_space,
        )
