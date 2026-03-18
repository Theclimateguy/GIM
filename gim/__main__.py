from argparse import ArgumentParser
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from typing import Callable

from .briefing import AnalyticsBriefRenderer, BriefConfig, write_brief_artifact
from . import __version__
from .core.cli import main as core_main
from .case_builder import build_case_from_text, write_case_payload
from .calibration import (
    CalibrationRunConfig,
    DEFAULT_CALIBRATION_SUITE,
    format_calibration_suite_result,
    run_operational_calibration,
)
from .calibration_validator import run_sanity_suite
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
from .results import build_run_artifacts, resolve_run_output_path, write_json_artifact, write_run_manifest
from .runtime import MISC_ROOT, load_world
from .scenario_compiler import compile_question, load_game_definition, resolve_actor_names
from .sim_bridge import SimBridge, SimProgress
from .ui_server import run_ui_server

BACKGROUND_POLICY_CHOICES = ("compiled-llm", "llm", "simple", "growth")
LLM_REFRESH_CHOICES = ("trigger", "periodic", "never")


def _resolve_case_path(raw_value: str) -> Path:
    candidate = Path(raw_value)
    if candidate.exists():
        return candidate
    packaged = MISC_ROOT / "cases" / raw_value
    if packaged.exists():
        return packaged
    return candidate


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="GIM15 scenario, game and reporting layer")
    parser.add_argument("--version", action="version", version=f"GIM15 {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    question_parser = subparsers.add_parser("question", help="Compile and evaluate a question-driven scenario")
    question_parser.add_argument("question_text", nargs="?")
    question_parser.add_argument("--question")
    question_parser.add_argument("--actors", nargs="*")
    question_parser.add_argument("--base-year", type=int)
    question_parser.add_argument("--horizon-months", type=int, default=24)
    question_parser.add_argument("--template")
    question_parser.add_argument("--state-csv")
    question_parser.add_argument("--state-year", type=int)
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
    question_parser.add_argument(
        "--background-policy",
        choices=BACKGROUND_POLICY_CHOICES,
        default="compiled-llm",
        help="Autonomous policy mode for non-player countries on the sim path.",
    )
    question_parser.add_argument(
        "--llm-refresh",
        choices=LLM_REFRESH_CHOICES,
        default="trigger",
        help="How often compiled-llm doctrines are refreshed.",
    )
    question_parser.add_argument(
        "--llm-refresh-years",
        type=int,
        default=2,
        help="Periodic doctrine refresh interval in years when --llm-refresh=periodic.",
    )

    game_parser = subparsers.add_parser("game", help="Run a policy-gaming case")
    game_input_group = game_parser.add_mutually_exclusive_group(required=True)
    game_input_group.add_argument("--case")
    game_input_group.add_argument("--description", help="Build a case from free text before running the game")
    game_parser.add_argument("--save-case", help="Optional path to save the generated case JSON")
    game_parser.add_argument("--state-csv")
    game_parser.add_argument("--state-year", type=int)
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
    game_parser.add_argument(
        "--background-policy",
        choices=BACKGROUND_POLICY_CHOICES,
        default="compiled-llm",
        help="Autonomous policy mode for non-player countries on the sim path.",
    )
    game_parser.add_argument(
        "--llm-refresh",
        choices=LLM_REFRESH_CHOICES,
        default="trigger",
        help="How often compiled-llm doctrines are refreshed.",
    )
    game_parser.add_argument(
        "--llm-refresh-years",
        type=int,
        default=2,
        help="Periodic doctrine refresh interval in years when --llm-refresh=periodic.",
    )

    metrics_parser = subparsers.add_parser("metrics", help="Build a crisis metrics dashboard")
    metrics_parser.add_argument("--agents", nargs="*")
    metrics_parser.add_argument("--state-csv")
    metrics_parser.add_argument("--state-year", type=int)
    metrics_parser.add_argument("--max-countries", type=int)
    metrics_parser.add_argument("--json", dest="json_output", action="store_true")

    console_parser = subparsers.add_parser("console", help="Launch the interactive console menu")
    console_parser.add_argument("--state-csv")
    console_parser.add_argument("--state-year", type=int)
    console_parser.add_argument("--max-countries", type=int)

    calibrate_parser = subparsers.add_parser(
        "calibrate",
        help="Run the bundled historical calibration suite against the current model",
    )
    calibrate_parser.add_argument("--suite", default=DEFAULT_CALIBRATION_SUITE)
    calibrate_parser.add_argument("--state-csv")
    calibrate_parser.add_argument("--state-year", type=int)
    calibrate_parser.add_argument("--max-countries", type=int)
    calibrate_parser.add_argument("--json", dest="json_output", action="store_true")
    calibrate_parser.add_argument("--runs", type=int, default=1)
    calibrate_parser.add_argument("--horizon", type=int, default=0)
    calibrate_mode_group = calibrate_parser.add_mutually_exclusive_group()
    calibrate_mode_group.add_argument("--sim", action="store_true")
    calibrate_mode_group.add_argument("--no-sim", action="store_true")
    calibrate_parser.add_argument(
        "--background-policy",
        choices=BACKGROUND_POLICY_CHOICES,
        default="compiled-llm",
        help="Autonomous policy mode for non-player countries on the sim path.",
    )
    calibrate_parser.add_argument(
        "--llm-refresh",
        choices=LLM_REFRESH_CHOICES,
        default="trigger",
        help="How often compiled-llm doctrines are refreshed.",
    )
    calibrate_parser.add_argument(
        "--llm-refresh-years",
        type=int,
        default=2,
        help="Periodic doctrine refresh interval in years when --llm-refresh=periodic.",
    )

    brief_parser = subparsers.add_parser(
        "brief",
        help="Generate a Markdown analytical brief from a saved evaluation JSON artifact",
    )
    brief_parser.add_argument("--from-json", required=True)
    brief_parser.add_argument("--output", default="decision_brief.md")

    ui_parser = subparsers.add_parser(
        "ui",
        help="Launch local web UI bound to the current repository and local model runtime",
    )
    ui_parser.add_argument("--host", default="127.0.0.1")
    ui_parser.add_argument("--port", type=int, default=8090)

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
    output_path: str,
    use_sim: bool,
    show_game_results: bool,
    run_timestamp: str,
    run_id: str,
) -> DashboardConfig:
    return DashboardConfig(
        output_path=output_path,
        show_trajectory=use_sim and getattr(args, "horizon", 0) > 0,
        show_game_results=show_game_results,
        show_narrative=bool(getattr(args, "narrative", False)),
        execution_label="sim" if use_sim else "static",
        policy_mode_label=_policy_mode_label(args, use_sim),
        run_timestamp=run_timestamp,
        run_id=run_id,
        n_runs=1,
        horizon_years=getattr(args, "horizon", 0),
    )


def _brief_config(
    args,
    *,
    output_path: str,
    use_sim: bool,
    include_game_results: bool,
    run_timestamp: str,
    run_id: str,
) -> BriefConfig:
    return BriefConfig(
        output_path=output_path,
        include_trajectory=use_sim and getattr(args, "horizon", 0) > 0,
        include_game_results=include_game_results,
        execution_label="sim" if use_sim else "static",
        policy_mode_label=_policy_mode_label(args, use_sim),
        run_timestamp=run_timestamp,
        run_id=run_id,
        n_runs=1,
        horizon_years=getattr(args, "horizon", 0),
    )


def _terminal_progress_logger() -> Callable[[SimProgress], None]:
    def _log(update: SimProgress) -> None:
        print(
            f"[sim] {update.percent:>3}%  {update.message}",
            file=sys.stderr,
            flush=True,
        )

    return _log


def _policy_mode_label(args, use_sim: bool) -> str:
    if not use_sim:
        return "snapshot"
    return getattr(args, "background_policy", "compiled-llm")


def _serialize_game_output(game_result, equilibrium_result) -> dict:
    payload = {"game_result": asdict(game_result)}
    if equilibrium_result is not None:
        payload["equilibrium_result"] = asdict(equilibrium_result)
    return payload


def _emit_sanity_suite(json_output: bool) -> None:
    suite = run_sanity_suite()
    stream = sys.stderr if json_output else sys.stdout
    sections = (
        ("Outcome warnings", suite["outcome_warnings"]),
        ("Action warnings", suite["action_warnings"]),
        ("Crisis warnings", suite["crisis_warnings"]),
    )
    for label, warnings in sections:
        if not warnings:
            continue
        print(f"{label}:", file=stream)
        for warning in warnings:
            print(f"  - {warning}", file=stream)
    if not suite["pass"]:
        print("Sanity suite reported fatal calibration issues.", file=stream)


def _artifact_stream(json_output: bool):
    return sys.stderr if json_output else sys.stdout


def _emit_artifact_notice(message: str, *, json_output: bool) -> None:
    print(message, file=_artifact_stream(json_output))


def _apply_world_cli_overrides(argv: list[str]) -> None:
    parser = ArgumentParser(add_help=False)
    parser.add_argument("--state-csv")
    parser.add_argument("--state-year", type=int)
    parser.add_argument("--max-countries", type=int)
    known_args, _ = parser.parse_known_args(argv)
    if known_args.state_csv:
        os.environ["STATE_CSV"] = known_args.state_csv
    if known_args.state_year is not None:
        os.environ["STATE_YEAR"] = str(known_args.state_year)
    if known_args.max_countries is not None:
        os.environ["MAX_COUNTRIES"] = str(known_args.max_countries)


def main() -> None:
    orchestration_commands = {"question", "game", "metrics", "console", "calibrate", "brief", "ui"}
    argv = sys.argv[1:]
    if not argv:
        core_main()
        return
    if argv[0] == "world":
        _apply_world_cli_overrides(argv[1:])
        sys.argv = [sys.argv[0], *argv[1:]]
        core_main()
        return
    if argv[0] not in orchestration_commands and not argv[0].startswith("-"):
        core_main()
        return

    parser = build_parser()
    args = parser.parse_args()
    if args.command == "console":
        run_console(
            state_csv=args.state_csv,
            max_countries=args.max_countries,
            state_year=args.state_year,
        )
        return
    if args.command == "ui":
        run_ui_server(host=args.host, port=args.port)
        return
    if args.command == "brief":
        run_artifacts = build_run_artifacts(args.command)
        output_path = resolve_run_output_path(run_artifacts.run_dir, args.output, "decision_brief.md")
        output_path = AnalyticsBriefRenderer().write_from_json(
            input_path=args.from_json,
            config=BriefConfig(output_path=str(output_path)),
        )
        manifest_path = write_run_manifest(
            {
                "command": args.command,
                "run_id": run_artifacts.run_id,
                "run_timestamp": run_artifacts.run_timestamp,
                "artifacts_dir": str(run_artifacts.run_dir),
                "inputs": {
                    "from_json": str(Path(args.from_json).expanduser().resolve()),
                },
                "outputs": {
                    "brief_markdown": str(Path(output_path).resolve()),
                },
            },
            run_artifacts.run_dir,
        )
        print(f"Analytical brief written to {output_path}")
        print(f"Run manifest written to {manifest_path}")
        return
    if args.command == "calibrate":
        _emit_sanity_suite(args.json_output)
        result = run_operational_calibration(
            suite_id=args.suite,
            state_csv=args.state_csv,
            max_countries=args.max_countries,
            state_year=args.state_year,
            config=CalibrationRunConfig(
                n_runs=args.runs,
                horizon_years=args.horizon,
                use_sim=_should_use_simulation(args),
                default_mode=args.background_policy,
                llm_refresh=args.llm_refresh,
                llm_refresh_years=args.llm_refresh_years,
            ),
        )
        if args.json_output:
            print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
            return
        print(format_calibration_suite_result(result))
        return
    world = load_world(
        state_csv=args.state_csv,
        max_agents=args.max_countries,
        state_year=args.state_year,
    )
    runner = GameRunner(world)
    metrics_engine = CrisisMetricsEngine()

    if args.command == "question":
        use_sim = _should_use_simulation(args)
        run_artifacts = build_run_artifacts(args.command)
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
                default_mode=args.background_policy,
                llm_refresh=args.llm_refresh,
                llm_refresh_years=args.llm_refresh_years,
                progress_callback=_terminal_progress_logger(),
            )
        else:
            evaluation = runner.evaluate_scenario(scenario)
        evaluation_json_path = write_json_artifact(
            {
                "scenario": asdict(scenario),
                "evaluation": asdict(evaluation),
                "game_result": None,
                "equilibrium_result": None,
                "trajectory": [asdict(state) for state in trajectory],
                "dashboard_config": {
                    "execution_label": "sim" if use_sim else "static",
                    "policy_mode_label": _policy_mode_label(args, use_sim),
                    "run_timestamp": run_artifacts.run_timestamp,
                    "run_id": run_artifacts.run_id,
                    "n_runs": 1,
                    "horizon_years": getattr(args, "horizon", 0),
                },
            },
            run_artifacts.run_dir / "evaluation.json",
        )
        written = None
        brief_path = None
        if args.dashboard:
            dashboard_output = resolve_run_output_path(run_artifacts.run_dir, args.dashboard_output, "dashboard.html")
            written = write_dashboard_artifacts(
                renderer=DashboardRenderer(),
                evaluation=evaluation,
                game_result=None,
                equilibrium_result=None,
                trajectory=trajectory,
                scenario_def=scenario,
                config=_dashboard_config(
                    args,
                    output_path=str(dashboard_output),
                    use_sim=use_sim,
                    show_game_results=False,
                    run_timestamp=run_artifacts.run_timestamp,
                    run_id=run_artifacts.run_id,
                ),
                save_json=False,
            )
        if args.brief:
            brief_output = resolve_run_output_path(run_artifacts.run_dir, args.brief_output, "decision_brief.md")
            brief_path = write_brief_artifact(
                renderer=AnalyticsBriefRenderer(),
                evaluation=evaluation,
                game_result=None,
                equilibrium_result=None,
                trajectory=trajectory,
                scenario_def=scenario,
                config=_brief_config(
                    args,
                    output_path=str(brief_output),
                    use_sim=use_sim,
                    include_game_results=False,
                    run_timestamp=run_artifacts.run_timestamp,
                    run_id=run_artifacts.run_id,
                ),
            )
        manifest_path = write_run_manifest(
            {
                "command": args.command,
                "run_id": run_artifacts.run_id,
                "run_timestamp": run_artifacts.run_timestamp,
                "artifacts_dir": str(run_artifacts.run_dir),
                "inputs": {
                    "question": _resolve_question_text(args),
                    "actors": list(args.actors or []),
                    "base_year": args.base_year,
                    "horizon_months": args.horizon_months,
                    "template": args.template,
                    "state_csv": args.state_csv,
                    "state_year": args.state_year,
                    "max_countries": args.max_countries,
                    "use_sim": use_sim,
                    "horizon_years": args.horizon,
                    "background_policy": getattr(args, "background_policy", None),
                    "llm_refresh": getattr(args, "llm_refresh", None),
                    "llm_refresh_years": getattr(args, "llm_refresh_years", None),
                },
                "outputs": {
                    "evaluation_json": str(evaluation_json_path.resolve()),
                    "dashboard_html": written["html"] if written is not None else None,
                    "brief_markdown": str(Path(brief_path).resolve()) if brief_path is not None else None,
                },
            },
            run_artifacts.run_dir,
        )
        if args.json_output:
            print(json.dumps(asdict(evaluation), indent=2, ensure_ascii=False))
            _emit_artifact_notice(f"JSON artifact written to {evaluation_json_path}", json_output=True)
            if written is not None:
                _emit_artifact_notice(f"Dashboard written to {written['html']}", json_output=True)
            if brief_path is not None:
                _emit_artifact_notice(f"Analytical brief written to {brief_path}", json_output=True)
            _emit_artifact_notice(f"Run manifest written to {manifest_path}", json_output=True)
            return
        print(format_question_evaluation(evaluation))
        print(f"\nJSON artifact written to {evaluation_json_path}")
        if written is not None:
            print(f"\nDashboard written to {written['html']}")
        if brief_path is not None:
            print(f"Analytical brief written to {brief_path}")
        print(f"Run manifest written to {manifest_path}")
        return

    if args.command == "metrics":
        run_artifacts = build_run_artifacts(args.command)
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
        metrics_json_path = write_json_artifact(asdict(dashboard), run_artifacts.run_dir / "metrics.json")
        manifest_path = write_run_manifest(
            {
                "command": args.command,
                "run_id": run_artifacts.run_id,
                "run_timestamp": run_artifacts.run_timestamp,
                "artifacts_dir": str(run_artifacts.run_dir),
                "inputs": {
                    "agents": list(args.agents or []),
                    "state_csv": args.state_csv,
                    "state_year": args.state_year,
                    "max_countries": args.max_countries,
                },
                "outputs": {
                    "metrics_json": str(metrics_json_path.resolve()),
                },
            },
            run_artifacts.run_dir,
        )
        if args.json_output:
            print(json.dumps(asdict(dashboard), indent=2, ensure_ascii=False))
            _emit_artifact_notice(f"Metrics JSON written to {metrics_json_path}", json_output=True)
            _emit_artifact_notice(f"Run manifest written to {manifest_path}", json_output=True)
            return
        print(format_crisis_dashboard(dashboard))
        print(f"\nMetrics JSON written to {metrics_json_path}")
        print(f"Run manifest written to {manifest_path}")
        return

    run_artifacts = build_run_artifacts(args.command)
    built_case_path = None
    if getattr(args, "description", None):
        build = build_case_from_text(args.description, world, prefer_llm=True)
        game = build.game
        if build.note:
            print(build.note, file=sys.stderr)
        case_output = resolve_run_output_path(run_artifacts.run_dir, args.save_case, "generated_case.json")
        built_case_path = write_case_payload(build.payload, case_output)
    else:
        case_path = _resolve_case_path(args.case)
        game = load_game_definition(case_path, world)
    use_sim = _should_use_simulation(args)
    if use_sim:
        bridge = SimBridge()
        result = bridge.run_game(
            world,
            game,
            n_years=args.horizon,
            default_mode=args.background_policy,
            llm_refresh=args.llm_refresh,
            llm_refresh_years=args.llm_refresh_years,
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
    game_json_path = write_json_artifact(
        {
            "game_result": asdict(result),
            "equilibrium_result": asdict(equilibrium_result) if equilibrium_result is not None else None,
        },
        run_artifacts.run_dir / "game_result.json",
    )
    written = None
    brief_path = None
    if args.dashboard:
        dashboard_output = resolve_run_output_path(run_artifacts.run_dir, args.dashboard_output, "dashboard.html")
        written = write_dashboard_artifacts(
            renderer=DashboardRenderer(),
            evaluation=result.best_combination.evaluation,
            game_result=result,
            equilibrium_result=equilibrium_result,
            trajectory=trajectory,
            scenario_def=game.scenario,
            config=_dashboard_config(
                args,
                output_path=str(dashboard_output),
                use_sim=use_sim,
                show_game_results=True,
                run_timestamp=run_artifacts.run_timestamp,
                run_id=run_artifacts.run_id,
            ),
            save_json=False,
        )
    if args.brief:
        brief_output = resolve_run_output_path(run_artifacts.run_dir, args.brief_output, "decision_brief.md")
        brief_path = write_brief_artifact(
            renderer=AnalyticsBriefRenderer(),
            evaluation=result.best_combination.evaluation,
            game_result=result,
            equilibrium_result=equilibrium_result,
            trajectory=trajectory,
            scenario_def=game.scenario,
            config=_brief_config(
                args,
                output_path=str(brief_output),
                use_sim=use_sim,
                include_game_results=True,
                run_timestamp=run_artifacts.run_timestamp,
                run_id=run_artifacts.run_id,
            ),
        )
    manifest_path = write_run_manifest(
        {
            "command": args.command,
            "run_id": run_artifacts.run_id,
            "run_timestamp": run_artifacts.run_timestamp,
            "artifacts_dir": str(run_artifacts.run_dir),
            "inputs": {
                "case": args.case,
                "description": args.description,
                "save_case": args.save_case,
                "state_csv": args.state_csv,
                "state_year": args.state_year,
                "max_countries": args.max_countries,
                "use_sim": use_sim,
                "horizon_years": args.horizon,
                "background_policy": getattr(args, "background_policy", None),
                "llm_refresh": getattr(args, "llm_refresh", None),
                "llm_refresh_years": getattr(args, "llm_refresh_years", None),
                "equilibrium": args.equilibrium,
                "episodes": args.episodes,
                "threshold": args.threshold,
                "trust_alpha": args.trust_alpha,
                "max_combinations": args.max_combinations,
            },
            "outputs": {
                "generated_case_json": str(Path(built_case_path).resolve()) if built_case_path is not None else None,
                "game_result_json": str(game_json_path.resolve()),
                "dashboard_html": written["html"] if written is not None else None,
                "brief_markdown": str(Path(brief_path).resolve()) if brief_path is not None else None,
            },
        },
        run_artifacts.run_dir,
    )
    if args.json_output:
        print(json.dumps(_serialize_game_output(result, equilibrium_result), indent=2, ensure_ascii=False))
        _emit_artifact_notice(f"Game JSON artifact written to {game_json_path}", json_output=True)
        if built_case_path is not None:
            _emit_artifact_notice(f"Generated case written to {built_case_path}", json_output=True)
        if written is not None:
            _emit_artifact_notice(f"Dashboard written to {written['html']}", json_output=True)
        if brief_path is not None:
            _emit_artifact_notice(f"Analytical brief written to {brief_path}", json_output=True)
        _emit_artifact_notice(f"Run manifest written to {manifest_path}", json_output=True)
        return
    print(format_game_result(result))
    if equilibrium_result is not None:
        print()
        print(format_equilibrium_result(equilibrium_result))
    print(f"\nGame JSON artifact written to {game_json_path}")
    if written is not None:
        print(f"\nDashboard written to {written['html']}")
    if brief_path is not None:
        print(f"Analytical brief written to {brief_path}")
    if built_case_path is not None:
        print(f"Generated case written to {built_case_path}")
    print(f"Run manifest written to {manifest_path}")


if __name__ == "__main__":
    main()
