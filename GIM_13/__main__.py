from argparse import ArgumentParser
from dataclasses import asdict
import json
from pathlib import Path

from .calibration import (
    CalibrationRunConfig,
    DEFAULT_CALIBRATION_SUITE,
    format_calibration_suite_result,
    run_operational_calibration,
)
from .console_app import run_console
from .crisis_metrics import CrisisMetricsEngine
from .explanations import format_crisis_dashboard, format_game_result, format_question_evaluation
from .game_runner import GameRunner
from .runtime import load_world
from .scenario_compiler import compile_question, load_game_definition, resolve_actor_names
from .sim_bridge import SimBridge


def _resolve_case_path(raw_value: str) -> Path:
    candidate = Path(raw_value)
    if candidate.exists():
        return candidate
    packaged = Path(__file__).resolve().parent / "cases" / raw_value
    if packaged.exists():
        return packaged
    return candidate


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="GIM_13 policy-gaming MVP")
    subparsers = parser.add_subparsers(dest="command", required=True)

    question_parser = subparsers.add_parser("question", help="Compile and evaluate a question-driven scenario")
    question_parser.add_argument("--question", required=True)
    question_parser.add_argument("--actors", nargs="*")
    question_parser.add_argument("--base-year", type=int)
    question_parser.add_argument("--horizon-months", type=int, default=24)
    question_parser.add_argument("--template")
    question_parser.add_argument("--state-csv")
    question_parser.add_argument("--max-countries", type=int)
    question_parser.add_argument("--json", dest="json_output", action="store_true")
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
    game_parser.add_argument("--case", required=True)
    game_parser.add_argument("--state-csv")
    game_parser.add_argument("--max-countries", type=int)
    game_parser.add_argument("--json", dest="json_output", action="store_true")
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

    return parser


def _should_use_simulation(args) -> bool:
    use_sim = bool(getattr(args, "sim", False) or (getattr(args, "horizon", 0) > 0 and not getattr(args, "no_sim", False)))
    if getattr(args, "sim", False) and getattr(args, "horizon", 0) <= 0:
        raise SystemExit("--sim requires --horizon > 0")
    return use_sim


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "console":
        run_console(state_csv=args.state_csv, max_countries=args.max_countries)
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
        scenario = compile_question(
            question=args.question,
            world=world,
            base_year=args.base_year,
            actors=args.actors,
            horizon_months=args.horizon_months,
            template_id=args.template,
        )
        if _should_use_simulation(args):
            bridge = SimBridge()
            evaluation, _trajectory = bridge.evaluate_scenario(
                world,
                scenario,
                n_years=args.horizon,
                default_mode="llm",
            )
        else:
            evaluation = runner.evaluate_scenario(scenario)
        if args.json_output:
            print(json.dumps(asdict(evaluation), indent=2, ensure_ascii=False))
            return
        print(format_question_evaluation(evaluation))
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

    case_path = _resolve_case_path(args.case)
    game = load_game_definition(case_path, world)
    if _should_use_simulation(args):
        bridge = SimBridge()
        result = bridge.run_game(
            world,
            game,
            n_years=args.horizon,
            default_mode="llm",
        )
    else:
        result = runner.run_game(game)
    if args.json_output:
        print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
        return
    print(format_game_result(result))


if __name__ == "__main__":
    main()
