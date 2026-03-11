from argparse import ArgumentParser
from dataclasses import asdict
import json
from pathlib import Path

from .explanations import format_game_result, format_question_evaluation
from .game_runner import GameRunner
from .runtime import load_world
from .scenario_compiler import compile_question, load_game_definition


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

    game_parser = subparsers.add_parser("game", help="Run a policy-gaming case")
    game_parser.add_argument("--case", required=True)
    game_parser.add_argument("--state-csv")
    game_parser.add_argument("--max-countries", type=int)
    game_parser.add_argument("--json", dest="json_output", action="store_true")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    world = load_world(state_csv=args.state_csv, max_agents=args.max_countries)
    runner = GameRunner(world)

    if args.command == "question":
        scenario = compile_question(
            question=args.question,
            world=world,
            base_year=args.base_year,
            actors=args.actors,
            horizon_months=args.horizon_months,
            template_id=args.template,
        )
        evaluation = runner.evaluate_scenario(scenario)
        if args.json_output:
            print(json.dumps(asdict(evaluation), indent=2, ensure_ascii=False))
            return
        print(format_question_evaluation(evaluation))
        return

    case_path = _resolve_case_path(args.case)
    game = load_game_definition(case_path, world)
    result = runner.run_game(game)
    if args.json_output:
        print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
        return
    print(format_game_result(result))


if __name__ == "__main__":
    main()
