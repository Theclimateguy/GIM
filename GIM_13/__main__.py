from argparse import ArgumentParser
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Callable

from .briefing import AnalyticsBriefRenderer, BriefConfig, write_brief_artifact
from .case_builder import build_case_from_text, write_case_payload
from .calibration import (
    CalibrationRunConfig,
    DEFAULT_CALIBRATION_SUITE,
    format_calibration_suite_result,
    run_operational_calibration,
)
from .console_app import run_console
from .crisis_metrics import CrisisMetricsEngine
from .dashboard import DashboardConfig, DashboardRenderer, write_dashboard_artifacts
from .explanations import (
    format_crisis_dashboard,
    format_equilibrium_result,
    format_game_result,
    format_question_evaluation,
)
from .game_theory.equilibrium_runner import run_equilibrium_search
from .game_runner import GameRunner
from .runtime import MISC_ROOT, load_world
from .scenario_compiler import compile_question, load_game_definition, resolve_actor_names
from .sim_bridge import SimBridge, SimProgress


def _resolve_case_path(raw_value: str) -> Path:
    candidate = Path(raw_value)
    if candidate.exists():
        return candidate
    packaged = MISC_ROOT / "cases" / raw_value
    if packaged.exists():
        return packaged
    return candidate


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="GIM_13 policy-gaming MVP")
    subparsers = parser.add_subparsers(dest="command", required=True)

    question_parser = subparsers.add_parser("question", help="Compile and evaluate a question-driven scenario")
    question_parser.add_argument("question_text", nargs="?")
    question_parser.add_argument("--question")
    question_parser.add_argument("--actors", nargs="*")
    question_parser.add_argument("--base-year", type=int)
    question_parser.add_argument("--horizon-months", type=int, default=24)
    question_parser.add_argument("--template")
    question_parser.add_argument("--state-csv")
    question_parser.add_argument("--max-countries", type=int)
    question_parser.add_argument("--json", dest="json_output", action="store_true")
    question_parser.add_argument("--dashboard", action="store_true")
    question_parser.add_argument("--dashboard-output", default="dashboard.html")
    question_parser.add_argument("--brief", action="store_true")
    question_parser.add_argument("--brief-output", default="decision_brief.md")
    question_parser.add_argument("--narrative", action="store_true")
    question_parser.add_argument(
        "--horizon",
        type=int,
        default=0,
        help="Years to simulate via step_world. 0 keeps the static scorer.",
    )
    question_mode_group = question_parser.add_mutually_exclusive_group()
    question_mode_group.add_argument("--sim", action="store_true")
    question_mode_group.add_argument("--no-sim", action="store_true")

    game_parser = subparsers.add_parser("game", help="Run a policy-gaming case")
    game_input_group = game_parser.add_mutually_exclusive_group(required=True)
    game_input_group.add_argument("--case")
    game_input_group.add_argument("--description", help="Build a case from free text before running the game")
    game_parser.add_argument("--save-case", help="Optional path to save the generated case JSON")
    game_parser.add_argument("--state-csv")
    game_parser.add_argument("--max-countries", type=int)
    game_parser.add_argument("--json", dest="json_output", action="store_true")
    game_parser.add_argument("--dashboard", action="store_true")
    game_parser.add_argument("--dashboard-output", default="dashboard.html")
    game_parser.add_argument("--brief", action="store_true")
    game_parser.add_argument("--brief-output", default="decision_brief.md")
    game_parser.add_argument("--narrative", action="store_true")
    game_parser.add_argument(
        "--equilibrium",
        action="store_true",
        help="Run regret minimization and trust-weighted CE on top of the evaluated game matrix",
    )
    game_parser.add_argument("--episodes", type=int, default=50)
    game_parser.add_argument("--threshold", type=float, default=0.02)
    game_parser.add_argument("--trust-alpha", type=float, default=0.5)
    game_parser.add_argument("--max-combinations", type=int, default=256)
    game_parser.add_argument(
        "--horizon",
        type=int,
        default=0,
        help="Years to simulate via step_world. 0 keeps the static scorer.",
    )
    game_mode_group = game_parser.add_mutually_exclusive_group()
    game_mode_group.add_argument("--sim", action="store_true")
    game_mode_group.add_argument("--no-sim", action="store_true")

    metrics_parser = subparsers.add_parser("metrics", help="Build a crisis metrics dashboard")
    metrics_parser.add_argument("--agents", nargs="*")
    metrics_parser.add_argument("--state-csv")
    metrics_parser.add_argument("--max-countries", type=int)
    metrics_parser.add_argument("--json", dest="json_output", action="store_true")

    console_parser = subparsers.add_parser("console", help="Launch the interactive console menu")
    console_parser.add_argument("--state-csv")
    console_parser.add_argument("--max-countries", type=int)

    calibrate_parser = subparsers.add_parser(
        "calibrate",
        help="Run the bundled historical calibration suite against the current model",
    )
    calibrate_parser.add_argument("--suite", default=DEFAULT_CALIBRATION_SUITE)
    calibrate_parser.add_argument("--state-csv")
    calibrate_parser.add_argument("--max-countries", type=int)
    calibrate_parser.add_argument("--json", dest="json_output", action="store_true")
    calibrate_parser.add_argument("--runs", type=int, default=1)
    calibrate_parser.add_argument("--horizon", type=int, default=0)
    calibrate_mode_group = calibrate_parser.add_mutually_exclusive_group()
    calibrate_mode_group.add_argument("--sim", action="store_true")
    calibrate_mode_group.add_argument("--no-sim", action="store_true")

    brief_parser = subparsers.add_parser(
        "brief",
        help="Generate a Markdown analytical brief from a saved evaluation JSON artifact",
    )
    brief_parser.add_argument("--from-json", required=True)
    brief_parser.add_argument("--output", default="decision_brief.md")

    return parser


def _should_use_simulation(args) -> bool:
    use_sim = bool(getattr(args, "sim", False) or (getattr(args, "horizon", 0) > 0 and not getattr(args, "no_sim", False)))
    if getattr(args, "sim", False) and getattr(args, "horizon", 0) <= 0:
        raise SystemExit("--sim requires --horizon > 0")
    return use_sim


def _resolve_question_text(args) -> str:
    question_text = getattr(args, "question", None) or getattr(args, "question_text", None)
    if not question_text:
        raise SystemExit("question requires either a positional question or --question")
    return question_text


def _dashboard_config(
    args,
    *,
    use_sim: bool,
    show_game_results: bool,
    run_timestamp: str,
    run_id: str,
) -> DashboardConfig:
    return DashboardConfig(
        output_path=args.dashboard_output,
        show_trajectory=use_sim and getattr(args, "horizon", 0) > 0,
        show_game_results=show_game_results,
        show_narrative=bool(getattr(args, "narrative", False)),
        execution_label="sim" if use_sim else "static",
        policy_mode_label="llm" if use_sim else "snapshot",
        run_timestamp=run_timestamp,
        run_id=run_id,
        n_runs=1,
        horizon_years=getattr(args, "horizon", 0),
    )


def _brief_config(
    args,
    *,
    use_sim: bool,
    include_game_results: bool,
    run_timestamp: str,
    run_id: str,
) -> BriefConfig:
    return BriefConfig(
        output_path=args.brief_output,
        include_trajectory=use_sim and getattr(args, "horizon", 0) > 0,
        include_game_results=include_game_results,
        execution_label="sim" if use_sim else "static",
        policy_mode_label="llm" if use_sim else "snapshot",
        run_timestamp=run_timestamp,
        run_id=run_id,
        n_runs=1,
        horizon_years=getattr(args, "horizon", 0),
    )


def _build_run_metadata(command: str) -> tuple[str, str]:
    stamp = datetime.now()
    run_timestamp = stamp.strftime("%Y-%m-%d %H:%M")
    run_id = f"{command}-{stamp.strftime('%Y%m%d-%H%M%S')}"
    return run_timestamp, run_id


def _terminal_progress_logger() -> Callable[[SimProgress], None]:
    def _log(update: SimProgress) -> None:
        print(
            f"[sim] {update.percent:>3}%  {update.message}",
            file=sys.stderr,
            flush=True,
        )

    return _log


def _serialize_game_output(game_result, equilibrium_result) -> dict:
    payload = {"game_result": asdict(game_result)}
    if equilibrium_result is not None:
        payload["equilibrium_result"] = asdict(equilibrium_result)
    return payload


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "console":
        run_console(state_csv=args.state_csv, max_countries=args.max_countries)
        return
    if args.command == "brief":
        output_path = AnalyticsBriefRenderer().write_from_json(
            input_path=args.from_json,
            config=BriefConfig(output_path=args.output),
        )
        print(f"Analytical brief written to {output_path}")
        return
    if args.command == "calibrate":
        result = run_operational_calibration(
            suite_id=args.suite,
            state_csv=args.state_csv,
            max_countries=args.max_countries,
            config=CalibrationRunConfig(
                n_runs=args.runs,
                horizon_years=args.horizon,
                use_sim=_should_use_simulation(args),
            ),
        )
        if args.json_output:
            print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
            return
        print(format_calibration_suite_result(result))
        return
    world = load_world(state_csv=args.state_csv, max_agents=args.max_countries)
    runner = GameRunner(world)
    metrics_engine = CrisisMetricsEngine()

    if args.command == "question":
        use_sim = _should_use_simulation(args)
        run_timestamp, run_id = _build_run_metadata(args.command)
        scenario = compile_question(
            question=_resolve_question_text(args),
            world=world,
            base_year=args.base_year,
            actors=args.actors,
            horizon_months=args.horizon_months,
            template_id=args.template,
        )
        trajectory = [world]
        if use_sim:
            bridge = SimBridge()
            evaluation, trajectory = bridge.evaluate_scenario(
                world,
                scenario,
                n_years=args.horizon,
                default_mode="llm",
                progress_callback=_terminal_progress_logger(),
            )
        else:
            evaluation = runner.evaluate_scenario(scenario)
        written = None
        brief_path = None
        if args.dashboard:
            written = write_dashboard_artifacts(
                renderer=DashboardRenderer(),
                evaluation=evaluation,
                game_result=None,
                equilibrium_result=None,
                trajectory=trajectory,
                scenario_def=scenario,
                config=_dashboard_config(
                    args,
                    use_sim=use_sim,
                    show_game_results=False,
                    run_timestamp=run_timestamp,
                    run_id=run_id,
                ),
                save_json=args.json_output,
            )
        if args.brief:
            brief_path = write_brief_artifact(
                renderer=AnalyticsBriefRenderer(),
                evaluation=evaluation,
                game_result=None,
                equilibrium_result=None,
                trajectory=trajectory,
                scenario_def=scenario,
                config=_brief_config(
                    args,
                    use_sim=use_sim,
                    include_game_results=False,
                    run_timestamp=run_timestamp,
                    run_id=run_id,
                ),
            )
        if args.json_output:
            print(json.dumps(asdict(evaluation), indent=2, ensure_ascii=False))
            return
        print(format_question_evaluation(evaluation))
        if written is not None:
            print(f"\nDashboard written to {written['html']}")
            if "json" in written:
                print(f"JSON artifact written to {written['json']}")
        if brief_path is not None:
            print(f"Analytical brief written to {brief_path}")
        return

    if args.command == "metrics":
        if args.agents:
            actor_ids, _actor_names, unresolved = resolve_actor_names(world, args.agents)
            if unresolved:
                raise SystemExit(f"Unresolved agent names: {', '.join(unresolved)}")
        else:
            actor_ids = [
                agent.id
                for agent in sorted(
                    world.agents.values(),
                    key=lambda current: current.economy.gdp,
                    reverse=True,
                )[:5]
            ]
        dashboard = metrics_engine.compute_dashboard(world, agent_ids=actor_ids)
        if args.json_output:
            print(json.dumps(asdict(dashboard), indent=2, ensure_ascii=False))
            return
        print(format_crisis_dashboard(dashboard))
        return

    built_case_path = None
    if getattr(args, "description", None):
        build = build_case_from_text(args.description, world, prefer_llm=True)
        game = build.game
        if build.note:
            print(build.note, file=sys.stderr)
        if args.save_case:
            built_case_path = write_case_payload(build.payload, args.save_case)
    else:
        case_path = _resolve_case_path(args.case)
        game = load_game_definition(case_path, world)
    use_sim = _should_use_simulation(args)
    run_timestamp, run_id = _build_run_metadata(args.command)
    if use_sim:
        bridge = SimBridge()
        result = bridge.run_game(
            world,
            game,
            n_years=args.horizon,
            default_mode="llm",
            max_combinations=args.max_combinations,
            progress_callback=_terminal_progress_logger(),
        )
        trajectory = result.trajectory
    else:
        result = runner.run_game(game, max_combinations=args.max_combinations)
        trajectory = [world]
    equilibrium_result = None
    if args.equilibrium:
        equilibrium_result = run_equilibrium_search(
            runner=GameRunner(trajectory[-1]) if trajectory else runner,
            game=game,
            world=trajectory[-1] if trajectory else world,
            max_episodes=args.episodes,
            convergence_threshold=args.threshold,
            max_combinations=args.max_combinations,
            trust_alpha=args.trust_alpha,
            stage_game=result,
        )
    written = None
    brief_path = None
    if args.dashboard:
        written = write_dashboard_artifacts(
            renderer=DashboardRenderer(),
            evaluation=result.best_combination.evaluation,
            game_result=result,
            equilibrium_result=equilibrium_result,
            trajectory=trajectory,
            scenario_def=game.scenario,
            config=_dashboard_config(
                args,
                use_sim=use_sim,
                show_game_results=True,
                run_timestamp=run_timestamp,
                run_id=run_id,
            ),
            save_json=args.json_output,
        )
    if args.brief:
        brief_path = write_brief_artifact(
            renderer=AnalyticsBriefRenderer(),
            evaluation=result.best_combination.evaluation,
            game_result=result,
            equilibrium_result=equilibrium_result,
            trajectory=trajectory,
            scenario_def=game.scenario,
            config=_brief_config(
                args,
                use_sim=use_sim,
                include_game_results=True,
                run_timestamp=run_timestamp,
                run_id=run_id,
            ),
        )
    if args.json_output:
        print(json.dumps(_serialize_game_output(result, equilibrium_result), indent=2, ensure_ascii=False))
        return
    print(format_game_result(result))
    if equilibrium_result is not None:
        print()
        print(format_equilibrium_result(equilibrium_result))
    if written is not None:
        print(f"\nDashboard written to {written['html']}")
        if "json" in written:
            print(f"JSON artifact written to {written['json']}")
    if brief_path is not None:
        print(f"Analytical brief written to {brief_path}")
    if built_case_path is not None:
        print(f"Generated case written to {built_case_path}")


if __name__ == "__main__":
    main()
