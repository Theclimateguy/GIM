from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from itertools import product
from typing import Callable

from gim_11_1.core import (
    Action,
    DomesticPolicy,
    FinancePolicy,
    ForeignPolicy,
    Observation,
    SanctionsAction,
    SecurityActions,
    TradeDeal,
    TradeRestriction,
    WorldState,
)
from gim_11_1.policy import make_policy_map
from gim_11_1.simulation import step_world

from .crisis_metrics import CrisisDashboard, CrisisMetricsEngine
from .game_runner import ACTION_RISK_SHIFTS, GameRunner
from .types import GameCombinationResult, GameDefinition, GameResult, ScenarioDefinition, ScenarioEvaluation


ACTION_TO_POLICY: dict[str, dict] = {
    "signal_deterrence": {
        "domestic": {"military_spending_change": 0.004},
        "security": {"type": "military_exercise", "target_mode": "primary_peer"},
        "trade_restrictions": [
            {"level": "soft", "target_mode": "primary_peer", "reason": "deterrence signaling"}
        ],
        "description": "Visible deterrence posture with limited coercive spillovers.",
    },
    "signal_restraint": {
        "domestic": {"social_spending_change": 0.001, "military_spending_change": -0.001},
        "description": "De-escalatory posture with lower force signaling.",
    },
    "arm_proxy": {
        "domestic": {"military_spending_change": 0.005},
        "security": {"type": "arms_buildup", "target_mode": "primary_peer"},
        "trade_restrictions": [
            {"level": "soft", "target_mode": "primary_peer", "reason": "proxy pressure"}
        ],
        "description": "Indirect escalation through proxy and force posture.",
    },
    "restrain_proxy": {
        "domestic": {"social_spending_change": 0.001, "military_spending_change": -0.001},
        "description": "Restraint stance that avoids proxy escalation.",
    },
    "covert_disruption": {
        "domestic": {"rd_investment_change": 0.001},
        "sanctions": [
            {"type": "mild", "target_mode": "primary_peer", "reason": "covert disruption"}
        ],
        "trade_restrictions": [
            {"level": "soft", "target_mode": "primary_peer", "reason": "covert disruption"}
        ],
        "description": "Gray-zone pressure short of overt force.",
    },
    "maritime_interdiction": {
        "domestic": {"military_spending_change": 0.006},
        "sanctions": [
            {"type": "strong", "target_mode": "primary_peer", "reason": "maritime interdiction"}
        ],
        "trade_restrictions": [
            {"level": "hard", "target_mode": "primary_peer", "reason": "maritime interdiction"}
        ],
        "security": {"type": "border_incident", "target_mode": "primary_peer"},
        "description": "Route denial posture with high trade disruption.",
    },
    "partial_mobilization": {
        "domestic": {"military_spending_change": 0.008},
        "security": {"type": "arms_buildup", "target_mode": "primary_peer"},
        "description": "General military mobilization without immediate open conflict.",
    },
    "targeted_strike": {
        "domestic": {"military_spending_change": 0.007},
        "security": {"type": "conflict", "target_mode": "primary_peer"},
        "description": "Direct kinetic escalation against the primary counterpart.",
    },
    "backchannel_offer": {
        "domestic": {"social_spending_change": 0.001, "military_spending_change": -0.001},
        "trade_deals": [
            {
                "resource_selector": "largest_gap",
                "direction": "import",
                "partner_mode": "primary_peer",
                "volume_scale": 0.03,
                "price_preference": "fair",
            }
        ],
        "description": "Quiet de-escalation channel backed by limited economic normalization.",
    },
    "accept_mediation": {
        "domestic": {"social_spending_change": 0.0015, "military_spending_change": -0.0015},
        "trade_deals": [
            {
                "resource_selector": "largest_gap",
                "direction": "import",
                "partner_mode": "primary_peer",
                "volume_scale": 0.04,
                "price_preference": "fair",
            }
        ],
        "description": "Explicit acceptance of mediation and partial normalization.",
    },
    "information_campaign": {
        "domestic": {"rd_investment_change": 0.001},
        "description": "Narrative competition without hard external moves.",
    },
    "domestic_crackdown": {
        "domestic": {
            "tax_fuel_change": 0.25,
            "social_spending_change": -0.004,
            "military_spending_change": 0.003,
        },
        "description": "Domestic repression posture that trades legitimacy for control.",
    },
}

MACRO_METRICS = {"inflation", "fx_stress", "sovereign_stress", "food_affordability_stress"}
STABILITY_METRICS = {"protest_pressure", "regime_fragility"}
GEOPOLITICAL_METRICS = {
    "oil_vulnerability",
    "sanctions_strangulation",
    "conflict_escalation_pressure",
    "strategic_dependency",
    "chokepoint_exposure",
}


@dataclass(frozen=True)
class SimProgress:
    phase: str
    percent: int
    completed_units: int
    total_units: int
    message: str


class _ProgressTracker:
    def __init__(
        self,
        *,
        phase: str,
        total_units: int,
        callback: Callable[[SimProgress], None] | None,
        percent_step: int = 5,
    ) -> None:
        self.phase = phase
        self.total_units = max(total_units, 1)
        self.callback = callback
        self.percent_step = max(percent_step, 1)
        self.completed_units = 0
        self._next_percent = 0

    def start(self, message: str) -> None:
        self._emit(percent=0, message=message)
        self._next_percent = self.percent_step

    def advance(self, *, units: int = 1, message: str) -> None:
        self.completed_units = min(self.total_units, self.completed_units + max(units, 0))
        percent = int((100 * self.completed_units) / self.total_units)
        if self.completed_units >= self.total_units or percent >= self._next_percent:
            self._emit(percent=percent, message=message)
            while self._next_percent <= percent:
                self._next_percent += self.percent_step

    def complete(self, message: str) -> None:
        self.completed_units = self.total_units
        self._emit(percent=100, message=message)

    def _emit(self, *, percent: int, message: str) -> None:
        if self.callback is None:
            return
        self.callback(
            SimProgress(
                phase=self.phase,
                percent=max(0, min(100, percent)),
                completed_units=self.completed_units,
                total_units=self.total_units,
                message=message,
            )
        )


class SimBridge:
    """
    Wires GIM13 scenario/game definitions into a GIM11_1 simulation run.
    Translates GIM13 action labels to deterministic GIM11_1 Action callables.
    Runs step_world N times and returns trajectory snapshots.
    """

    ACTION_TO_POLICY = ACTION_TO_POLICY

    def __init__(self) -> None:
        self.metrics_engine = CrisisMetricsEngine()

    @classmethod
    def unmapped_actions(cls) -> list[str]:
        return sorted(set(ACTION_RISK_SHIFTS) - set(cls.ACTION_TO_POLICY))

    @classmethod
    def validate_action_mapping(cls) -> None:
        missing = cls.unmapped_actions()
        if missing:
            raise ValueError(f"Unmapped GIM13 actions: {', '.join(missing)}")

    def build_policy_map(
        self,
        world: WorldState,
        game_def: GameDefinition | None,
        default_mode: str = "llm",
        selected_actions: dict[str, str] | None = None,
    ) -> dict[str, Callable[..., Action]]:
        """
        For each agent in world:
        - if agent is a named player in selected_actions: inject a deterministic forced action policy
        - else: assign the requested autonomous mode via the legacy policy map
        """

        self.validate_action_mapping()
        policy_map = make_policy_map(world.agents.keys(), mode=default_mode)
        action_selection = dict(selected_actions or {})
        if not game_def:
            if action_selection:
                for agent_id, action_name in action_selection.items():
                    if agent_id not in world.agents:
                        raise ValueError(f"Unknown player agent id: {agent_id}")
                    if action_name not in self.ACTION_TO_POLICY:
                        raise ValueError(f"Unmapped action label: {action_name}")
                    policy_map[agent_id] = self._make_forced_policy(
                        world=world,
                        agent_id=agent_id,
                        action_name=action_name,
                        scenario_actor_ids=[],
                    )
            return policy_map

        for player in game_def.players:
            for action_name in player.allowed_actions:
                if action_name not in self.ACTION_TO_POLICY:
                    raise ValueError(
                        f"Unmapped action label in game definition for {player.display_name}: {action_name}"
                    )

        scenario_actor_ids = list(game_def.scenario.actor_ids)
        for agent_id, action_name in action_selection.items():
            if action_name not in self.ACTION_TO_POLICY:
                raise ValueError(f"Unmapped action label: {action_name}")
            if agent_id not in world.agents:
                raise ValueError(f"Unknown player agent id: {agent_id}")
            policy_map[agent_id] = self._make_forced_policy(
                world=world,
                agent_id=agent_id,
                action_name=action_name,
                scenario_actor_ids=scenario_actor_ids,
            )

        return policy_map

    def run_trajectory(
        self,
        world: WorldState,
        policy_map: dict[str, Callable[..., Action]],
        n_years: int,
        *,
        progress_tracker: _ProgressTracker | None = None,
        trajectory_label: str = "simulation",
    ) -> list[WorldState]:
        """
        Deep-copy the world and run step_world n_years times.
        """

        if n_years < 0:
            raise ValueError("n_years must be non-negative")

        sim_world = copy.deepcopy(world)
        trajectory = [copy.deepcopy(sim_world)]
        memory = {}
        agent_count = max(len(sim_world.agents), 1)
        for year_index in range(n_years):
            resolved_in_year = {"count": 0}

            def _policy_progress(agent_id: str) -> None:
                if progress_tracker is None:
                    return
                resolved_in_year["count"] += 1
                progress_tracker.advance(
                    message=(
                        f"{trajectory_label}: year {year_index + 1}/{n_years}, "
                        f"resolved {resolved_in_year['count']}/{agent_count} agents"
                    )
                )

            sim_world = step_world(
                sim_world,
                policy_map,
                memory=memory,
                policy_progress=_policy_progress if progress_tracker is not None else None,
            )
            trajectory.append(copy.deepcopy(sim_world))
        return trajectory

    def score_trajectory(
        self,
        trajectory: list[WorldState],
        scenario_def: ScenarioDefinition,
    ) -> ScenarioEvaluation:
        """
        Score the terminal state with the existing GameRunner and replace crisis metrics with
        dashboard/deltas computed against the actual simulated trajectory.
        """

        if not trajectory:
            raise ValueError("trajectory must contain at least one world snapshot")

        initial_world = trajectory[0]
        terminal_world = trajectory[-1]
        terminal_runner = GameRunner(terminal_world)
        evaluation = terminal_runner.evaluate_scenario(scenario_def, selected_actions={})

        agent_ids = self._selected_agent_ids(initial_world, scenario_def)
        baseline_dashboard = self.metrics_engine.compute_dashboard(initial_world, agent_ids=agent_ids)
        terminal_dashboard = self.metrics_engine.compute_dashboard(
            terminal_world,
            agent_ids=agent_ids,
            history=trajectory,
        )
        delta_by_agent, crisis_signal_summary = self._compute_crisis_delta(
            baseline_dashboard=baseline_dashboard,
            terminal_dashboard=terminal_dashboard,
        )

        notes = list(evaluation.consistency_notes)
        notes.append(
            f"Scenario was scored on the terminal state after {max(len(trajectory) - 1, 0)} simulated yearly steps."
        )
        return replace(
            evaluation,
            crisis_dashboard=terminal_dashboard,
            crisis_delta_by_agent=delta_by_agent,
            crisis_signal_summary=crisis_signal_summary,
            consistency_notes=notes,
        )

    def evaluate_scenario(
        self,
        world: WorldState,
        scenario_def: ScenarioDefinition,
        *,
        n_years: int,
        default_mode: str = "llm",
        progress_callback: Callable[[SimProgress], None] | None = None,
    ) -> tuple[ScenarioEvaluation, list[WorldState]]:
        policy_map = self.build_policy_map(world, game_def=None, default_mode=default_mode)
        tracker = None
        if progress_callback is not None and n_years > 0:
            tracker = _ProgressTracker(
                phase="question",
                total_units=max(len(world.agents), 1) * n_years,
                callback=progress_callback,
            )
            tracker.start(
                f"Starting scenario simulation for {n_years} yearly steps across {len(world.agents)} agents"
            )
        trajectory = self.run_trajectory(
            world,
            policy_map,
            n_years,
            progress_tracker=tracker,
            trajectory_label="scenario simulation",
        )
        if tracker is not None:
            tracker.complete("Scenario simulation complete")
        return self.score_trajectory(trajectory, scenario_def), trajectory

    def run_game(
        self,
        world: WorldState,
        game_def: GameDefinition,
        *,
        n_years: int,
        default_mode: str = "llm",
        max_combinations: int = 256,
        progress_callback: Callable[[SimProgress], None] | None = None,
    ) -> GameResult:
        action_spaces = [player.allowed_actions or ["signal_restraint"] for player in game_def.players]
        combination_count = 1
        for action_space in action_spaces:
            combination_count *= max(1, len(action_space))

        truncated_action_space = False
        if combination_count > max_combinations:
            action_spaces = [action_space[:3] for action_space in action_spaces]
            truncated_action_space = True

        effective_combination_count = 1
        for action_space in action_spaces:
            effective_combination_count *= max(1, len(action_space))

        tracker = None
        if progress_callback is not None and n_years > 0:
            tracker = _ProgressTracker(
                phase="game",
                total_units=max(len(world.agents), 1) * n_years * (1 + effective_combination_count),
                callback=progress_callback,
            )
            tracker.start(
                "Starting policy game simulation "
                f"(baseline + {effective_combination_count} strategy profiles)"
            )

        baseline_policy_map = self.build_policy_map(
            world,
            game_def=game_def,
            default_mode=default_mode,
            selected_actions={},
        )
        baseline_trajectory = self.run_trajectory(
            world,
            baseline_policy_map,
            n_years,
            progress_tracker=tracker,
            trajectory_label="baseline profile",
        )
        baseline_evaluation = self.score_trajectory(baseline_trajectory, game_def.scenario)

        scoring_runner = GameRunner(world)
        combinations: list[GameCombinationResult] = []
        trajectories_by_actions: dict[tuple[tuple[str, str], ...], list[WorldState]] = {}

        for combo_index, choice_tuple in enumerate(product(*action_spaces), start=1):
            selected_actions = {
                player.player_id: action_name
                for player, action_name in zip(game_def.players, choice_tuple)
            }
            policy_map = self.build_policy_map(
                world,
                game_def=game_def,
                default_mode=default_mode,
                selected_actions=selected_actions,
            )
            trajectory = self.run_trajectory(
                world,
                policy_map,
                n_years,
                progress_tracker=tracker,
                trajectory_label=f"strategy {combo_index}/{effective_combination_count}",
            )
            evaluation = self.score_trajectory(trajectory, game_def.scenario)
            player_payoffs = {
                player.player_id: scoring_runner._score_player(
                    player,
                    evaluation=evaluation,
                    action_name=selected_actions[player.player_id],
                )
                for player in game_def.players
            }
            signature = tuple(sorted(selected_actions.items()))
            trajectories_by_actions[signature] = trajectory
            combinations.append(
                GameCombinationResult(
                    actions=selected_actions,
                    evaluation=evaluation,
                    player_payoffs=player_payoffs,
                    total_payoff=sum(player_payoffs.values()),
                )
            )

        combinations.sort(key=lambda combo: combo.total_payoff, reverse=True)
        best_signature = tuple(sorted(combinations[0].actions.items()))
        if tracker is not None:
            tracker.complete("Policy game simulation complete")
        return GameResult(
            game=game_def,
            baseline_evaluation=baseline_evaluation,
            best_combination=combinations[0],
            combinations=combinations,
            truncated_action_space=truncated_action_space,
            trajectory=trajectories_by_actions.get(best_signature),
            baseline_trajectory=baseline_trajectory,
        )

    def _selected_agent_ids(self, world: WorldState, scenario_def: ScenarioDefinition) -> list[str] | None:
        actor_ids = [agent_id for agent_id in scenario_def.actor_ids if agent_id in world.agents]
        if actor_ids:
            return actor_ids
        return [
            agent.id
            for agent in sorted(
                world.agents.values(),
                key=lambda current: current.economy.gdp,
                reverse=True,
            )[:5]
        ]

    def _compute_crisis_delta(
        self,
        *,
        baseline_dashboard: CrisisDashboard,
        terminal_dashboard: CrisisDashboard,
    ) -> tuple[dict[str, dict[str, dict[str, float]]], dict[str, float]]:
        delta_by_agent: dict[str, dict[str, dict[str, float]]] = {}
        worst_agent_shift = 0.0
        macro_shift_total = 0.0
        stability_shift_total = 0.0
        geopolitical_shift_total = 0.0
        macro_count = 0
        stability_count = 0
        geopolitical_count = 0
        net_shift_total = 0.0

        for agent_id, baseline_report in baseline_dashboard.agents.items():
            terminal_report = terminal_dashboard.agents.get(agent_id)
            if terminal_report is None:
                continue
            delta_by_agent[agent_id] = {}
            weighted_agent_shift = 0.0

            for metric_name, baseline_metric in baseline_report.metrics.items():
                terminal_metric = terminal_report.metrics[metric_name]
                level_delta = terminal_metric.level - baseline_metric.level
                severity_delta = terminal_metric.severity - baseline_metric.severity
                weighted_shift = severity_delta * terminal_metric.relevance
                delta_by_agent[agent_id][metric_name] = {
                    "level_delta": level_delta,
                    "severity_delta": severity_delta,
                    "weighted_shift": weighted_shift,
                }
                weighted_agent_shift += weighted_shift
                net_shift_total += weighted_shift

                if metric_name in MACRO_METRICS:
                    macro_shift_total += weighted_shift
                    macro_count += 1
                if metric_name in STABILITY_METRICS:
                    stability_shift_total += weighted_shift
                    stability_count += 1
                if metric_name in GEOPOLITICAL_METRICS:
                    geopolitical_shift_total += weighted_shift
                    geopolitical_count += 1

            worst_agent_shift = max(worst_agent_shift, weighted_agent_shift)

        delta_by_agent["__global__"] = {}
        global_net_shift = 0.0
        for metric_name, baseline_metric in baseline_dashboard.global_context.metrics.items():
            terminal_metric = terminal_dashboard.global_context.metrics[metric_name]
            level_delta = terminal_metric.level - baseline_metric.level
            severity_delta = terminal_metric.severity - baseline_metric.severity
            delta_by_agent["__global__"][metric_name] = {
                "level_delta": level_delta,
                "severity_delta": severity_delta,
                "weighted_shift": severity_delta,
            }
            global_net_shift += severity_delta

        crisis_signal_summary = {
            "net_crisis_shift": net_shift_total,
            "macro_stress_shift": macro_shift_total / max(macro_count, 1),
            "stability_stress_shift": stability_shift_total / max(stability_count, 1),
            "geopolitical_stress_shift": geopolitical_shift_total / max(geopolitical_count, 1),
            "global_context_shift": global_net_shift / max(len(delta_by_agent["__global__"]), 1),
            "worst_actor_shift": worst_agent_shift,
        }
        return delta_by_agent, crisis_signal_summary

    def _make_forced_policy(
        self,
        *,
        world: WorldState,
        agent_id: str,
        action_name: str,
        scenario_actor_ids: list[str],
    ) -> Callable[..., Action]:
        spec = self.ACTION_TO_POLICY[action_name]
        primary_peer = self._primary_peer(world, agent_id, scenario_actor_ids)

        sanctions = [
            SanctionsAction(
                target=self._resolve_target(agent_id, primary_peer, item.get("target_mode", "primary_peer")),
                type=item["type"],
                reason=item.get("reason", action_name.replace("_", " ")),
            )
            for item in spec.get("sanctions", [])
            if self._resolve_target(agent_id, primary_peer, item.get("target_mode", "primary_peer"))
        ]
        trade_restrictions = [
            TradeRestriction(
                target=self._resolve_target(agent_id, primary_peer, item.get("target_mode", "primary_peer")),
                level=item["level"],
                reason=item.get("reason", action_name.replace("_", " ")),
            )
            for item in spec.get("trade_restrictions", [])
            if self._resolve_target(agent_id, primary_peer, item.get("target_mode", "primary_peer"))
        ]
        security_target = None
        security_spec = spec.get("security")
        if security_spec is not None:
            security_target = self._resolve_target(
                agent_id,
                primary_peer,
                security_spec.get("target_mode", "primary_peer"),
            )

        trade_deals = self._build_trade_deals(
            world=world,
            agent_id=agent_id,
            primary_peer=primary_peer,
            trade_specs=spec.get("trade_deals", []),
        )
        domestic = spec.get("domestic", {})
        explanation = spec.get("description", action_name.replace("_", " "))
        if primary_peer and primary_peer in world.agents:
            explanation = f"{explanation} Target={world.agents[primary_peer].name}."

        def forced_policy(obs: Observation, memory_summary: dict | None = None) -> Action:
            del memory_summary
            return Action(
                agent_id=obs.agent_id,
                time=obs.time,
                domestic_policy=DomesticPolicy(
                    tax_fuel_change=float(domestic.get("tax_fuel_change", 0.0)),
                    social_spending_change=float(domestic.get("social_spending_change", 0.0)),
                    military_spending_change=float(domestic.get("military_spending_change", 0.0)),
                    rd_investment_change=float(domestic.get("rd_investment_change", 0.0)),
                    climate_policy=domestic.get("climate_policy", "none"),
                ),
                foreign_policy=ForeignPolicy(
                    proposed_trade_deals=copy.deepcopy(trade_deals),
                    sanctions_actions=copy.deepcopy(sanctions),
                    trade_restrictions=copy.deepcopy(trade_restrictions),
                    security_actions=SecurityActions(
                        type=security_spec["type"] if security_spec else "none",
                        target=security_target,
                    ),
                ),
                finance=FinancePolicy(
                    borrow_from_global_markets=0.0,
                    use_fx_reserves_change=0.0,
                ),
                explanation=f"forced_gim13_action:{action_name}; {explanation}",
            )

        return forced_policy

    def _build_trade_deals(
        self,
        *,
        world: WorldState,
        agent_id: str,
        primary_peer: str | None,
        trade_specs: list[dict],
    ) -> list[TradeDeal]:
        if not trade_specs or primary_peer is None or primary_peer not in world.agents:
            return []

        agent = world.agents[agent_id]
        deals: list[TradeDeal] = []
        for spec in trade_specs:
            resource_name = self._choose_trade_resource(agent, spec.get("resource_selector", "largest_gap"))
            baseline = max(agent.resources[resource_name].consumption, 1e-6)
            volume_change = max(0.01, float(spec.get("volume_scale", 0.03)) * baseline)
            deals.append(
                TradeDeal(
                    partner=primary_peer,
                    resource=resource_name,
                    direction=spec.get("direction", "import"),
                    volume_change=volume_change,
                    price_preference=spec.get("price_preference", "fair"),
                )
            )
        return deals

    def _choose_trade_resource(self, agent, selector: str) -> str:
        if selector != "largest_gap":
            return "energy"

        best_name = "energy"
        best_gap = -1.0
        for resource_name in ("energy", "food", "metals"):
            resource = agent.resources[resource_name]
            gap = max(resource.consumption - resource.production, 0.0)
            if gap > best_gap:
                best_gap = gap
                best_name = resource_name
        return best_name

    def _primary_peer(
        self,
        world: WorldState,
        agent_id: str,
        scenario_actor_ids: list[str],
    ) -> str | None:
        candidate_ids = [
            target_id
            for target_id in scenario_actor_ids
            if target_id != agent_id and target_id in world.agents
        ]
        if not candidate_ids:
            candidate_ids = [
                target_id for target_id in world.relations.get(agent_id, {}) if target_id in world.agents
            ]
        best_target = None
        best_score = float("-inf")
        for target_id in candidate_ids:
            relation = world.relations.get(agent_id, {}).get(target_id)
            if relation is None:
                score = 0.0
            else:
                score = relation.conflict_level + 0.5 * (1.0 - relation.trust) + 0.2 * relation.trade_barrier
            if score > best_score:
                best_score = score
                best_target = target_id
        return best_target

    def _resolve_target(
        self,
        agent_id: str,
        primary_peer: str | None,
        target_mode: str,
    ) -> str | None:
        if target_mode == "self":
            return agent_id
        if target_mode == "primary_peer":
            return primary_peer
        return None
