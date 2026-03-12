from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from .decision_language import (
    OUTCOME_EXPLANATIONS,
    build_highlights,
    executive_summary_text,
    global_debt_ratio,
    global_emissions,
    global_social_tension,
    horizon_label,
    labelize,
    risk_label,
    select_glossary_keys,
    top_driver_entries,
    world_gdp,
)
from .explanations import DRIVER_LABELS
from .interpretive_summary import build_interpretive_summary
from .model_terms import TERM_EXPLANATIONS


@dataclass
class BriefConfig:
    output_path: str = "decision_brief.md"
    top_k_drivers: int = 5
    top_k_strategies: int = 5
    top_k_actors: int = 5
    include_trajectory: bool = True
    include_game_results: bool = True
    execution_label: str = "static"
    policy_mode_label: str = "snapshot"
    run_timestamp: str | None = None
    run_id: str | None = None
    n_runs: int = 1
    horizon_years: int = 0
    include_interpretive_summary: bool = True
    prefer_llm_interpretation: bool = True


class AnalyticsBriefRenderer:
    def render(
        self,
        *,
        evaluation: Any,
        game_result: Any | None,
        equilibrium_result: Any | None,
        trajectory: list[Any] | None,
        scenario_def: Any,
        config: BriefConfig,
    ) -> str:
        payload = {
            "scenario": asdict(scenario_def),
            "evaluation": asdict(evaluation),
            "game_result": asdict(game_result) if game_result is not None else None,
            "equilibrium_result": asdict(equilibrium_result) if equilibrium_result is not None else None,
            "trajectory": [asdict(state) for state in (trajectory or [])],
            "brief_config": asdict(config),
        }
        return self.render_payload(payload, config=config)

    def render_payload(self, payload: dict[str, Any], *, config: BriefConfig | None = None) -> str:
        scenario = payload["scenario"]
        evaluation = payload["evaluation"]
        game_result = payload.get("game_result")
        equilibrium_result = payload.get("equilibrium_result")
        trajectory = payload.get("trajectory") or []
        runtime_cfg = payload.get("dashboard_config") or payload.get("brief_config") or {}
        defaults = BriefConfig()
        if config is None:
            effective_config = BriefConfig(
                execution_label=str(runtime_cfg.get("execution_label", defaults.execution_label)),
                policy_mode_label=str(runtime_cfg.get("policy_mode_label", defaults.policy_mode_label)),
                run_timestamp=runtime_cfg.get("run_timestamp"),
                run_id=runtime_cfg.get("run_id"),
                n_runs=int(runtime_cfg.get("n_runs", defaults.n_runs) or defaults.n_runs),
                horizon_years=int(runtime_cfg.get("horizon_years", defaults.horizon_years) or defaults.horizon_years),
                include_interpretive_summary=bool(
                    runtime_cfg.get("include_interpretive_summary", defaults.include_interpretive_summary)
                ),
                prefer_llm_interpretation=bool(
                    runtime_cfg.get("prefer_llm_interpretation", defaults.prefer_llm_interpretation)
                ),
            )
        else:
            effective_config = BriefConfig(
                output_path=config.output_path,
                top_k_drivers=config.top_k_drivers,
                top_k_strategies=config.top_k_strategies,
                top_k_actors=config.top_k_actors,
                include_trajectory=config.include_trajectory,
                include_game_results=config.include_game_results,
                execution_label=(
                    config.execution_label
                    if config.execution_label != defaults.execution_label
                    else str(runtime_cfg.get("execution_label", defaults.execution_label))
                ),
                policy_mode_label=(
                    config.policy_mode_label
                    if config.policy_mode_label != defaults.policy_mode_label
                    else str(runtime_cfg.get("policy_mode_label", defaults.policy_mode_label))
                ),
                run_timestamp=config.run_timestamp or runtime_cfg.get("run_timestamp"),
                run_id=config.run_id or runtime_cfg.get("run_id"),
                n_runs=(
                    config.n_runs
                    if config.n_runs != defaults.n_runs
                    else int(runtime_cfg.get("n_runs", defaults.n_runs) or defaults.n_runs)
                ),
                horizon_years=(
                    config.horizon_years
                    if config.horizon_years != defaults.horizon_years
                    else int(runtime_cfg.get("horizon_years", defaults.horizon_years) or defaults.horizon_years)
                ),
                include_interpretive_summary=config.include_interpretive_summary,
                prefer_llm_interpretation=config.prefer_llm_interpretation,
            )

        initial_eval = self._baseline_evaluation(payload)
        actor_ids = self._resolve_actor_ids(scenario, evaluation, trajectory)
        actor_rows = self._actor_rows(trajectory, evaluation, actor_ids, limit=effective_config.top_k_actors)
        outcome_lines = self._outcome_lines(evaluation, initial_eval)
        driver_lines = self._driver_lines(evaluation, effective_config.top_k_drivers)
        crisis_lines = self._crisis_lines(evaluation)
        glossary_lines = self._glossary_lines(evaluation, actor_ids)
        trajectory_lines = self._trajectory_lines(trajectory) if effective_config.include_trajectory else []
        strategy_table = self._strategy_table(game_result, effective_config.top_k_strategies) if effective_config.include_game_results else ""
        equilibrium_lines = self._equilibrium_lines(equilibrium_result)
        highlight_lines = [
            f"- {item.title}: {item.body}"
            for item in build_highlights(
                evaluation=evaluation,
                initial_evaluation=initial_eval,
                game_result=game_result,
                trajectory=trajectory,
                actor_ids=actor_ids,
            )
        ]
        horizon_years = effective_config.horizon_years or max(len(trajectory) - 1, 0)
        executive_summary = executive_summary_text(
            scenario,
            evaluation,
            actor_names=list(scenario.get("actor_names") or []),
            horizon_years=horizon_years,
        )
        interpretive_summary = (
            build_interpretive_summary(
                payload,
                prefer_llm=effective_config.prefer_llm_interpretation,
            )
            if effective_config.include_interpretive_summary
            else None
        )

        parts = [
            f"# GIM13 Decision Brief: {scenario.get('source_prompt') or scenario.get('title')}",
            "",
            "## Scenario",
            f"- Template: `{scenario.get('template_id', 'n/a')}`",
            f"- Base year: `{scenario.get('base_year', 'n/a')}`",
            f"- Path: `{effective_config.execution_label} / {effective_config.policy_mode_label}`",
            f"- Actors: {', '.join(scenario.get('actor_names') or ['Auto-resolved'])}",
            f"- Horizon: {horizon_label(scenario, horizon_years)}",
            f"- Run: `{effective_config.run_timestamp or 'n/a'}`",
            f"- Run ID: `{effective_config.run_id or 'n/a'}`",
            f"- n_runs: `{effective_config.n_runs}`",
        ]
        if isinstance(game_result, dict) and game_result.get("game", {}).get("title"):
            parts.append(f"- Policy game: {game_result['game']['title']}")
        parts.extend(
            [
                "",
                "## Decision-Maker Interpretation",
                *(
                    self._interpretive_lines(interpretive_summary)
                    if interpretive_summary is not None
                    else ["Interpretive summary disabled."]
                ),
                "",
                "## Executive Summary",
                executive_summary,
                "",
                "## Outcome Distribution",
                *outcome_lines,
                "",
                "## Main Drivers",
                *driver_lines,
                "",
                "## Crisis Overview",
                *crisis_lines,
                "",
                "## Model Terms",
                *glossary_lines,
                "",
                "## Actor Snapshot",
                "| Actor | GDP Δ% | Debt/GDP | Social tension | Conflict pressure | Top crisis metrics |",
                "| --- | ---: | ---: | ---: | ---: | --- |",
                *actor_rows,
            ]
        )

        if trajectory_lines:
            parts.extend(
                [
                    "",
                    "## Global Trajectory",
                    *trajectory_lines,
                ]
            )

        if strategy_table:
            parts.extend(
                [
                    "",
                    "## Strategy Ranking",
                    strategy_table,
                ]
            )

        if equilibrium_lines:
            parts.extend(
                [
                    "",
                    "## Equilibrium Analysis",
                    *equilibrium_lines,
                ]
            )

        parts.extend(
            [
                "",
                "## Analyst Highlights",
                *highlight_lines,
                "",
                "## Method Note",
                "- Quantitative sections are derived directly from model outputs; the interpretation layer can be produced either by DeepSeek or by deterministic fallback rules.",
                "- It can be generated directly after `question/game` or post-facto from `evaluation.json`.",
            ]
        )

        return "\n".join(parts).strip() + "\n"

    def write(
        self,
        *,
        evaluation: Any,
        game_result: Any | None,
        equilibrium_result: Any | None,
        trajectory: list[Any] | None,
        scenario_def: Any,
        config: BriefConfig,
    ) -> str:
        text = self.render(
            evaluation=evaluation,
            game_result=game_result,
            equilibrium_result=equilibrium_result,
            trajectory=trajectory,
            scenario_def=scenario_def,
            config=config,
        )
        output_path = Path(config.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        return str(output_path)

    def write_from_json(self, *, input_path: str, config: BriefConfig) -> str:
        payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
        text = self.render_payload(payload, config=config)
        output_path = Path(config.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        return str(output_path)

    def _interpretive_lines(self, summary: Any) -> list[str]:
        lines = [f"Interpretation source: {summary.source_label}."]
        for paragraph in summary.paragraphs:
            lines.extend(["", paragraph])
        if summary.note:
            lines.extend(["", f"_Note: {summary.note}_"])
        return lines

    def _baseline_evaluation(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        game_result = payload.get("game_result")
        if isinstance(game_result, dict):
            baseline = game_result.get("baseline_evaluation")
            if isinstance(baseline, dict):
                return baseline
        trajectory = payload.get("trajectory") or []
        scenario = payload.get("scenario")
        if len(trajectory) <= 1 or not scenario:
            return None
        return None

    def _resolve_actor_ids(
        self,
        scenario: dict[str, Any],
        evaluation: dict[str, Any],
        trajectory: list[dict[str, Any]],
    ) -> list[str]:
        scenario_ids = [
            actor_id
            for actor_id in scenario.get("actor_ids", [])
            if trajectory and actor_id in trajectory[-1].get("agents", {})
        ]
        if scenario_ids:
            return scenario_ids
        dashboard_agents = list((evaluation.get("crisis_dashboard") or {}).get("agents", {}).keys())
        if dashboard_agents:
            return dashboard_agents[:5]
        if trajectory:
            return list((trajectory[-1].get("agents") or {}).keys())[:5]
        return []

    def _actor_rows(
        self,
        trajectory: list[dict[str, Any]],
        evaluation: dict[str, Any],
        actor_ids: list[str],
        *,
        limit: int,
    ) -> list[str]:
        if not trajectory:
            return []
        initial_world = trajectory[0]
        terminal_world = trajectory[-1]
        dashboard_agents = (evaluation.get("crisis_dashboard") or {}).get("agents", {})
        rows: list[tuple[float, str]] = []
        for actor_id in actor_ids[:limit]:
            init_agent = (initial_world.get("agents") or {}).get(actor_id)
            term_agent = (terminal_world.get("agents") or {}).get(actor_id)
            report = dashboard_agents.get(actor_id)
            if not init_agent or not term_agent or not report:
                continue
            gdp_delta = self._pct_change(
                init_agent["economy"].get("gdp", 0.0),
                term_agent["economy"].get("gdp", 0.0),
            )
            debt_ratio = self._safe_div(
                term_agent["economy"].get("public_debt", 0.0),
                term_agent["economy"].get("gdp", 0.0),
            )
            social_tension = term_agent["society"].get("social_tension", 0.0)
            conflict_pressure = report["metrics"]["conflict_escalation_pressure"]["severity"]
            top_metrics = ", ".join(labelize(name) for name in report.get("top_metric_names", [])[:3])
            markdown = (
                f"| {term_agent['name']} | {gdp_delta:+.1f}% | {debt_ratio:.2f} | "
                f"{social_tension:.2f} | {conflict_pressure:.2f} | {top_metrics} |"
            )
            rows.append((max(conflict_pressure, social_tension, min(debt_ratio, 2.0)), markdown))
        rows.sort(key=lambda item: item[0], reverse=True)
        return [row for _score, row in rows]

    def _outcome_lines(
        self,
        evaluation: dict[str, Any],
        initial_eval: dict[str, Any] | None,
    ) -> list[str]:
        lines = []
        ranked = sorted(
            evaluation["risk_probabilities"].items(),
            key=lambda item: item[1],
            reverse=True,
        )
        for index, (risk_name, probability) in enumerate(ranked[:5], start=1):
            line = (
                f"- {index}. **{risk_label(risk_name)}**: {100.0 * probability:.1f}%"
            )
            if initial_eval is not None:
                start_prob = initial_eval.get("risk_probabilities", {}).get(risk_name, probability)
                line += f" (Δ {100.0 * (probability - start_prob):+.1f}pp vs baseline)"
            line += f" — {OUTCOME_EXPLANATIONS.get(risk_name, 'model-defined risk state')}."
            lines.append(line)
        return lines

    def _driver_lines(self, evaluation: dict[str, Any], limit: int) -> list[str]:
        ranked = top_driver_entries(evaluation, limit)
        return [
            f"- **{DRIVER_LABELS.get(name, labelize(name))}**: {value:.2f} — {TERM_EXPLANATIONS.get(name, 'Model-defined driver term.')}"
            for name, value in ranked
        ]

    def _crisis_lines(self, evaluation: dict[str, Any]) -> list[str]:
        summary = evaluation.get("crisis_signal_summary", {})
        lines = [
            f"- Net crisis shift: `{summary.get('net_crisis_shift', 0.0):+.2f}`",
            f"- Macro stress shift: `{summary.get('macro_stress_shift', 0.0):+.2f}`",
            f"- Stability stress shift: `{summary.get('stability_stress_shift', 0.0):+.2f}`",
            f"- Geopolitical stress shift: `{summary.get('geopolitical_stress_shift', 0.0):+.2f}`",
        ]
        top_changes = self._top_crisis_changes(evaluation, limit=5)
        if top_changes:
            lines.append(f"- Largest metric shifts: {', '.join(top_changes)}")
        return lines

    def _trajectory_lines(self, trajectory: list[dict[str, Any]]) -> list[str]:
        if len(trajectory) <= 1:
            return ["- Static path: no simulated trajectory was produced."]
        start = trajectory[0]
        end = trajectory[-1]
        world_gdp_0 = world_gdp(start)
        world_gdp_n = world_gdp(end)
        debt_0 = global_debt_ratio(start)
        debt_n = global_debt_ratio(end)
        social_0 = global_social_tension(start)
        social_n = global_social_tension(end)
        energy_0 = (start.get("global_state") or {}).get("prices", {}).get("energy", 1.0)
        energy_n = (end.get("global_state") or {}).get("prices", {}).get("energy", 1.0)
        emissions_0 = global_emissions(start)
        emissions_n = global_emissions(end)
        return [
            f"- World GDP: `{world_gdp_0:.2f}` → `{world_gdp_n:.2f}` ({self._pct_change(world_gdp_0, world_gdp_n):+.1f}%)",
            f"- Global debt / GDP: `{debt_0:.2f}` → `{debt_n:.2f}` ({debt_n - debt_0:+.2f})",
            f"- Global social tension: `{social_0:.2f}` → `{social_n:.2f}` ({social_n - social_0:+.2f})",
            f"- Energy price index: `{energy_0:.2f}` → `{energy_n:.2f}` ({energy_n - energy_0:+.2f})",
            f"- Global annual emissions: `{emissions_0:.2f}` → `{emissions_n:.2f}` ({emissions_n - emissions_0:+.2f})",
        ]

    def _glossary_lines(self, evaluation: dict[str, Any], actor_ids: list[str]) -> list[str]:
        lines = []
        for key in select_glossary_keys(evaluation, actor_ids):
            description = TERM_EXPLANATIONS.get(key)
            if not description:
                continue
            lines.append(f"- **{labelize(key)}**: {description}")
        return lines or ["- No additional glossary terms were required for this run."]

    def _strategy_table(self, game_result: dict[str, Any] | None, top_k: int) -> str:
        if not game_result:
            return ""
        baseline = game_result.get("baseline_evaluation") or {}
        baseline_criticality = baseline.get("criticality_score", 0.0)
        players = game_result.get("game", {}).get("players", [])
        rows = [
            "| Rank | Strategy profile | Total payoff | Criticality Δ |",
            "| --- | --- | ---: | ---: |",
        ]
        for index, combination in enumerate(game_result.get("combinations", [])[:top_k], start=1):
            profile = []
            for player in players:
                action = combination.get("actions", {}).get(player["player_id"], "n/a")
                profile.append(f"{player['display_name']}: {labelize(action)}")
            crit_delta = combination["evaluation"]["criticality_score"] - baseline_criticality
            rows.append(
                f"| {index} | {'; '.join(profile)} | {combination['total_payoff']:+.2f} | {crit_delta:+.2f} |"
            )
        if game_result.get("truncated_action_space"):
            rows.append("")
            rows.append("> Action space was truncated before evaluation.")
        return "\n".join(rows)

    def _equilibrium_lines(self, equilibrium_result: dict[str, Any] | None) -> list[str]:
        if not equilibrium_result:
            return []
        game = equilibrium_result.get("game", {})
        player_names = {
            player.get("player_id"): player.get("display_name", player.get("player_id", "n/a"))
            for player in game.get("players", [])
        }

        lines = [
            f"- Episodes: `{equilibrium_result.get('episodes', 0)}`",
            f"- Converged: `{'yes' if equilibrium_result.get('converged') else 'no'}`",
        ]

        ce = equilibrium_result.get("correlated_equilibrium") or {}
        lines.extend(
            [
                f"- CE solver: `{ce.get('solver_status', 'n/a')}`",
                f"- Max incentive deviation: `{ce.get('max_incentive_deviation', 0.0):.6f}`",
            ]
        )

        mean_external = equilibrium_result.get("mean_external_regret") or {}
        if mean_external:
            lines.append("- Mean external regret:")
            for player_id, value in mean_external.items():
                lines.append(f"  {player_names.get(player_id, player_id)}: `{value:.4f}`")

        mean_coalition = equilibrium_result.get("mean_coalition_regret") or {}
        if mean_coalition:
            lines.append("- Mean coalition regret:")
            for block, value in mean_coalition.items():
                lines.append(f"  {block}: `{value:.4f}`")

        recommended = equilibrium_result.get("recommended_profile") or {}
        if recommended:
            lines.append("- Recommended profile:")
            for player_id, action_name in recommended.items():
                lines.append(
                    f"  {player_names.get(player_id, player_id)}: `{labelize(action_name)}`"
                )

        welfare = equilibrium_result.get("welfare") or {}
        if welfare:
            lines.extend(
                [
                    f"- Trust alpha: `{welfare.get('alpha', 0.0):.2f}`",
                    f"- Utilitarian welfare: `{welfare.get('utilitarian_sw', 0.0):+.3f}`",
                    f"- Trust-weighted welfare: `{welfare.get('trust_weighted_sw', 0.0):+.3f}`",
                    f"- Payoff Gini: `{welfare.get('payoff_gini', 0.0):.4f}`",
                ]
            )
            if welfare.get("positive_normative_kl") is not None:
                lines.append(
                    f"- Positive vs normative KL gap: `{welfare.get('positive_normative_kl', 0.0):.6f}`"
                )

        if equilibrium_result.get("price_of_anarchy") is not None:
            lines.append(f"- Price of anarchy: `{equilibrium_result.get('price_of_anarchy', 0.0):.4f}`")

        top_ce = sorted((ce.get("distribution") or {}).items(), key=lambda item: item[1], reverse=True)[:3]
        if top_ce:
            lines.append("- Top CE support:")
            for key, probability in top_ce:
                lines.append(f"  {self._profile_label(key, player_names)}: `{100.0 * probability:.1f}%`")

        top_cce = sorted((equilibrium_result.get("ccE_empirical") or {}).items(), key=lambda item: item[1], reverse=True)[:3]
        if top_cce:
            lines.append("- Empirical CCE support:")
            for key, probability in top_cce:
                lines.append(f"  {self._profile_label(key, player_names)}: `{100.0 * probability:.1f}%`")

        return lines

    def _highlight_lines(
        self,
        *,
        scenario: dict[str, Any],
        evaluation: dict[str, Any],
        initial_eval: dict[str, Any] | None,
        trajectory: list[dict[str, Any]],
        actor_ids: list[str],
        actor_rows: list[str],
        game_result: dict[str, Any] | None,
    ) -> list[str]:
        lines = []
        top_outcome = evaluation["dominant_outcomes"][0]
        top_prob = evaluation["risk_probabilities"].get(top_outcome, 0.0)
        baseline_top_prob = 0.0
        if initial_eval is not None:
            baseline_top_prob = initial_eval.get("risk_probabilities", {}).get(top_outcome, top_prob)
        criticality_delta = 0.0
        if initial_eval is not None:
            criticality_delta = evaluation["criticality_score"] - initial_eval.get("criticality_score", evaluation["criticality_score"])

        if top_outcome in ESCALATORY_OUTCOMES:
            lines.append(
                f"- Escalation remains the dominant reading: **{self._risk_label(top_outcome)}** leads at `{100.0 * top_prob:.1f}%`."
            )
        if criticality_delta > 0.05:
            lines.append(
                f"- Criticality increased by `{criticality_delta:+.2f}` over the trajectory, which indicates worsening systemic pressure."
            )
        if top_outcome == "maritime_chokepoint_crisis":
            lines.append(
                "- Route and energy exposure are central in this run: the model is treating disruption of maritime flows as the main risk transmission channel."
            )
        elif self._global_energy_stress_increasing(trajectory, evaluation):
            lines.append(
                "- Global energy and route stress are rising: the crisis layer shows widening oil-market and volume-gap pressure even without a full maritime-break outcome."
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
                    f"- A negotiation window exists: the top strategy improves criticality by `{best_delta:+.2f}` and negotiation capacity remains `{negotiation_capacity:.2f}`."
                )
        worst_debt = self._worst_debt_actor(trajectory, actor_ids=actor_ids)
        if worst_debt is not None:
            lines.append(
                f"- Debt fragility is material: **{worst_debt['name']}** ends the run at debt/GDP `{worst_debt['debt_ratio']:.2f}`."
            )
        if not self._climate_events_count(trajectory):
            lines.append("- Climate feedback stays secondary in this run: no explicit climate shock events were detected in the simulated years.")
        if len(lines) < 2:
            top_drivers = sorted(
                evaluation["driver_scores"].items(),
                key=lambda item: item[1],
                reverse=True,
            )[:3]
            lines.append(
                "- Primary stress pattern: "
                + ", ".join(DRIVER_LABELS.get(name, self._labelize(name)) for name, _value in top_drivers)
                + "."
            )
        return lines[:5]

    def _top_crisis_changes(self, evaluation: dict[str, Any], limit: int) -> list[str]:
        dashboard_agents = (evaluation.get("crisis_dashboard") or {}).get("agents", {})
        changes: list[tuple[float, str]] = []
        for agent_id, metrics in (evaluation.get("crisis_delta_by_agent") or {}).items():
            if agent_id == "__global__":
                prefix = "global"
            else:
                prefix = dashboard_agents.get(agent_id, {}).get("agent_name", agent_id)
            for metric_name, delta in metrics.items():
                weighted_shift = delta.get("weighted_shift", 0.0)
                if abs(weighted_shift) < 1e-6:
                    continue
                direction = "up" if weighted_shift > 0 else "down"
                changes.append(
                    (
                        abs(weighted_shift),
                        f"{prefix}: {self._labelize(metric_name)} {direction} {weighted_shift:+.2f}",
                    )
                )
        changes.sort(key=lambda item: item[0], reverse=True)
        return [label for _score, label in changes[:limit]]

    def _world_gdp(self, world: dict[str, Any]) -> float:
        return sum(agent["economy"].get("gdp", 0.0) for agent in (world.get("agents") or {}).values())

    def _global_debt_ratio(self, world: dict[str, Any]) -> float:
        total_debt = sum(agent["economy"].get("public_debt", 0.0) for agent in (world.get("agents") or {}).values())
        total_gdp = self._world_gdp(world)
        return self._safe_div(total_debt, total_gdp)

    def _global_social_tension(self, world: dict[str, Any]) -> float:
        agents = list((world.get("agents") or {}).values())
        total_population = sum(max(agent["economy"].get("population", 0.0), 0.0) for agent in agents)
        if total_population <= 1e-9:
            return 0.0
        weighted = sum(
            max(agent["economy"].get("population", 0.0), 0.0) * agent["society"].get("social_tension", 0.0)
            for agent in agents
        )
        return weighted / total_population

    def _global_emissions(self, world: dict[str, Any]) -> float:
        return sum(agent["climate"].get("co2_annual_emissions", 0.0) for agent in (world.get("agents") or {}).values())

    def _worst_debt_actor(
        self,
        trajectory: list[dict[str, Any]],
        *,
        actor_ids: list[str] | None = None,
    ) -> dict[str, Any] | None:
        if not trajectory:
            return None
        worst: dict[str, Any] | None = None
        worst_ratio = 1.0
        terminal_agents = trajectory[-1].get("agents") or {}
        relevant_agents = (
            [terminal_agents[actor_id] for actor_id in actor_ids if actor_id in terminal_agents]
            if actor_ids
            else list(terminal_agents.values())
        )
        for agent in relevant_agents:
            debt_ratio = self._safe_div(agent["economy"].get("public_debt", 0.0), agent["economy"].get("gdp", 0.0))
            if debt_ratio > worst_ratio:
                worst_ratio = debt_ratio
                worst = {"name": agent["name"], "debt_ratio": debt_ratio}
        return worst

    def _global_energy_stress_increasing(
        self,
        trajectory: list[dict[str, Any]],
        evaluation: dict[str, Any],
    ) -> bool:
        if len(trajectory) <= 1:
            return False
        start_price = (trajectory[0].get("global_state") or {}).get("prices", {}).get("energy", 1.0)
        end_price = (trajectory[-1].get("global_state") or {}).get("prices", {}).get("energy", 1.0)
        global_metrics = (evaluation.get("crisis_dashboard") or {}).get("global_context", {}).get("metrics", {})
        oil_stress = global_metrics.get("global_oil_market_stress", {}).get("level", 0.0)
        return (end_price - start_price) > 0.10 or oil_stress > 0.45

    def _climate_events_count(self, trajectory: list[dict[str, Any]]) -> int:
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

    def _risk_label(self, risk_name: str) -> str:
        return RISK_LABELS.get(risk_name, self._labelize(risk_name))

    def _labelize(self, value: str) -> str:
        return value.replace("_", " ").strip().title()

    def _pct_change(self, start: float, end: float) -> float:
        if abs(start) <= 1e-9:
            return 0.0
        return 100.0 * (end / start - 1.0)

    def _safe_div(self, numerator: float, denominator: float) -> float:
        if abs(denominator) <= 1e-9:
            return 0.0
        return numerator / denominator

    def _profile_label(self, key: str, player_names: dict[str, str]) -> str:
        parts = []
        for part in key.split("|"):
            player_id, action_name = part.split(":", 1)
            parts.append(f"{player_names.get(player_id, player_id)}={labelize(action_name)}")
        return "; ".join(parts)

    def _horizon_label(self, scenario: dict[str, Any], horizon_years: int) -> str:
        if horizon_years > 0:
            base_year = scenario.get("base_year")
            return f"{horizon_years} years ({base_year}->{base_year + horizon_years})"
        return f"{scenario.get('horizon_months', 0)} months"

    def _horizon_phrase(self, scenario: dict[str, Any], horizon_years: int) -> str:
        if horizon_years > 0:
            return f"over the next {horizon_years} years"
        months = scenario.get("horizon_months", 0)
        if months:
            return f"over the next {months} months"
        return "in the current snapshot"

    def _actor_phrase(self, actor_names: list[str]) -> str:
        if not actor_names:
            return "the selected actors"
        if len(actor_names) == 1:
            return actor_names[0]
        if len(actor_names) == 2:
            return f"{actor_names[0]} and {actor_names[1]}"
        return ", ".join(actor_names[:-1]) + f", and {actor_names[-1]}"


def write_brief_artifact(
    *,
    renderer: AnalyticsBriefRenderer,
    evaluation: Any,
    game_result: Any | None,
    equilibrium_result: Any | None,
    trajectory: list[Any] | None,
    scenario_def: Any,
    config: BriefConfig,
) -> str:
    return renderer.write(
        evaluation=evaluation,
        game_result=game_result,
        equilibrium_result=equilibrium_result,
        trajectory=trajectory,
        scenario_def=scenario_def,
        config=config,
    )
