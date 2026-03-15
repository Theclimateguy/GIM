from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from math import prod
from pathlib import Path
from time import perf_counter
from typing import Callable

from .briefing import AnalyticsBriefRenderer, BriefConfig, write_brief_artifact
from .case_builder import build_case_from_text, write_case_payload
from .dashboard import DashboardConfig, DashboardRenderer, write_dashboard_artifacts
from .explanations import format_equilibrium_result, format_game_result, format_question_evaluation
from .game_theory.equilibrium_runner import run_equilibrium_search
from .game_runner import GameRunner
from .results import build_run_artifacts, resolve_run_output_path, write_json_artifact, write_run_manifest
from .runtime import MISC_ROOT, default_state_csv, load_world
from .scenario_compiler import compile_question, load_game_definition
from .sim_bridge import SimBridge, SimProgress
from .types import GameDefinition


CASES_DIR = MISC_ROOT / "cases"
BUILD_NEW_GAME = "__build_new_game__"
BACKGROUND_POLICY_CHOICES = ("compiled-llm", "llm", "simple", "growth")
LLM_REFRESH_CHOICES = ("trigger", "periodic", "never")


def _log(message: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] {message}")


def _progress_logger() -> Callable[[SimProgress], None]:
    def _log_progress(update: SimProgress) -> None:
        _log(f"Simulation {update.percent:>3}% - {update.message}")

    return _log_progress


def _prompt(text: str) -> str:
    try:
        return input(text)
    except EOFError:
        return "q"


def _prompt_required(text: str) -> str:
    while True:
        value = _prompt(text).strip()
        if value:
            return value
        print("Value is required.")


def _prompt_optional_int(text: str, *, default: int | None = None) -> int | None:
    while True:
        raw = _prompt(text).strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            print("Enter an integer or leave blank.")


def _prompt_optional_float(text: str, *, default: float | None = None) -> float | None:
    while True:
        raw = _prompt(text).strip()
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            print("Enter a number or leave blank.")


def _prompt_non_negative_int(text: str, *, default: int = 0) -> int:
    while True:
        value = _prompt_optional_int(text, default=default)
        if value is None:
            return default
        if value >= 0:
            return value
        print("Enter a non-negative integer.")


def _prompt_yes_no(text: str, *, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        raw = _prompt(f"{text} {suffix}: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Enter yes or no.")


def _prompt_choice(text: str, choices: tuple[str, ...], *, default: str) -> str:
    choice_set = {choice.lower(): choice for choice in choices}
    prompt_text = "/".join(choices)
    while True:
        raw = _prompt(f"{text} [{prompt_text}] [{default}]: ").strip().lower()
        if not raw:
            return default
        if raw in choice_set:
            return choice_set[raw]
        print(f"Choose one of: {', '.join(choices)}.")


def _prompt_actor_list(text: str) -> list[str]:
    raw = _prompt(text).strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _resolve_case_path(raw_value: str) -> Path:
    candidate = Path(raw_value)
    if candidate.exists():
        return candidate
    packaged = CASES_DIR / raw_value
    if packaged.exists():
        return packaged
    return candidate


def discover_cases() -> list[tuple[Path, str]]:
    records: list[tuple[Path, str]] = []
    for path in sorted(CASES_DIR.glob("*.json")):
        title = path.stem
        try:
            payload = json.loads(path.read_text())
            title = str(payload.get("title") or title)
        except Exception:
            pass
        records.append((path, title))
    return records


def count_action_combinations(game: GameDefinition) -> int:
    if not game.players:
        return 0
    return prod(max(1, len(player.allowed_actions or ["signal_restraint"])) for player in game.players)


def _maybe_write_dashboard(
    *,
    run_dir: Path,
    evaluation,
    game_result,
    equilibrium_result,
    trajectory,
    scenario_def,
    horizon_years: int,
    use_sim: bool,
    policy_mode_label: str,
    run_timestamp: str,
    run_id: str,
 ) -> str | None:
    if not _prompt_yes_no("Write dashboard (includes Decision Brief)", default=False):
        return None
    default_output = resolve_run_output_path(run_dir, None, "dashboard.html")
    output_path = _prompt(f"Dashboard output [{default_output}]: ").strip() or str(default_output)
    written = write_dashboard_artifacts(
        renderer=DashboardRenderer(),
        evaluation=evaluation,
        game_result=game_result,
        equilibrium_result=equilibrium_result,
        trajectory=trajectory,
        scenario_def=scenario_def,
        config=DashboardConfig(
            output_path=output_path,
            show_trajectory=use_sim and len(trajectory or []) > 1,
            show_game_results=game_result is not None,
            execution_label="sim" if use_sim else "static",
            policy_mode_label=policy_mode_label if use_sim else "snapshot",
            run_timestamp=run_timestamp,
            run_id=run_id,
            n_runs=1,
            horizon_years=horizon_years,
        ),
        save_json=False,
    )
    _log(f"Dashboard written to {written['html']}")
    return written["html"]


def _maybe_write_brief(
    *,
    run_dir: Path,
    evaluation,
    game_result,
    equilibrium_result,
    trajectory,
    scenario_def,
    horizon_years: int,
    use_sim: bool,
    policy_mode_label: str,
    run_timestamp: str,
    run_id: str,
 ) -> str | None:
    if not _prompt_yes_no("Write standalone analytical brief", default=False):
        return None
    default_output = resolve_run_output_path(run_dir, None, "decision_brief.md")
    output_path = _prompt(f"Brief output [{default_output}]: ").strip() or str(default_output)
    written = write_brief_artifact(
        renderer=AnalyticsBriefRenderer(),
        evaluation=evaluation,
        game_result=game_result,
        equilibrium_result=equilibrium_result,
        trajectory=trajectory,
        scenario_def=scenario_def,
        config=BriefConfig(
            output_path=output_path,
            include_trajectory=use_sim and len(trajectory or []) > 1,
            include_game_results=game_result is not None,
            execution_label="sim" if use_sim else "static",
            policy_mode_label=policy_mode_label if use_sim else "snapshot",
            run_timestamp=run_timestamp,
            run_id=run_id,
            n_runs=1,
            horizon_years=horizon_years,
        ),
    )
    _log(f"Analytical brief written to {written}")
    return written


@dataclass
class ConsoleSession:
    state_csv: str | None = None
    max_countries: int | None = None
    world: object | None = None
    runner: GameRunner | None = None

    def ensure_runner(self) -> GameRunner:
        if self.runner is not None:
            return self.runner
        state_csv = self.state_csv or default_state_csv()
        started = perf_counter()
        _log(f"Loading world from {state_csv}")
        self.world = load_world(state_csv=state_csv, max_agents=self.max_countries)
        self.runner = GameRunner(self.world)
        elapsed = perf_counter() - started
        _log(f"World loaded: {len(self.world.agents)} agents in {elapsed:.2f}s")
        return self.runner


def _render_menu() -> None:
    print()
    print("=== GIM_13 Console ===")
    print("[1] Policy Gaming")
    print("[2] Q&A")
    print("[q] Quit")
    print()


def _run_question_flow(session: ConsoleSession) -> None:
    runner = session.ensure_runner()
    assert session.world is not None

    print()
    print("Q&A mode")
    question = _prompt_required("Question: ")
    actors = _prompt_actor_list("Actors (comma separated, blank = auto): ")
    base_year = _prompt_optional_int("Base year [auto]: ")
    horizon_months = _prompt_optional_int("Horizon months [24]: ", default=24) or 24
    horizon_years = _prompt_non_negative_int("Simulation years [0 = static]: ", default=0)
    template = _prompt("Template [auto]: ").strip() or None
    run_artifacts = build_run_artifacts("question")

    started = perf_counter()
    _log("Compiling scenario from question")
    scenario = compile_question(
        question=question,
        world=session.world,
        base_year=base_year,
        actors=actors or None,
        horizon_months=horizon_months,
        template_id=template,
    )
    _log(
        "Scenario compiled: "
        f"template={scenario.template_id}, actors={', '.join(scenario.actor_names) if scenario.actor_names else 'none'}"
    )
    if scenario.unresolved_actor_names:
        _log(f"Unresolved actors: {', '.join(scenario.unresolved_actor_names)}")

    if horizon_years > 0:
        background_policy = _prompt_choice(
            "Background policy",
            BACKGROUND_POLICY_CHOICES,
            default="compiled-llm",
        )
        llm_refresh = _prompt_choice("LLM refresh mode", LLM_REFRESH_CHOICES, default="trigger")
        llm_refresh_years = _prompt_non_negative_int("LLM refresh years [2]: ", default=2) or 2
        _log(
            f"Running simulation bridge for {horizon_years} yearly steps "
            f"(background={background_policy}, refresh={llm_refresh})"
        )
        bridge = SimBridge()
        evaluation, trajectory = bridge.evaluate_scenario(
            session.world,
            scenario,
            n_years=horizon_years,
            default_mode=background_policy,
            llm_refresh=llm_refresh,
            llm_refresh_years=llm_refresh_years,
            progress_callback=_progress_logger(),
        )
        policy_mode_label = background_policy
    else:
        _log("Evaluating scenario with static scorer")
        evaluation = runner.evaluate_scenario(scenario)
        trajectory = [session.world]
        policy_mode_label = "snapshot"
    elapsed = perf_counter() - started
    _log(f"Evaluation complete in {elapsed:.2f}s")
    evaluation_json_path = write_json_artifact(
        {
            "scenario": asdict(scenario),
            "evaluation": asdict(evaluation),
            "game_result": None,
            "equilibrium_result": None,
            "trajectory": [asdict(state) for state in trajectory],
            "dashboard_config": {
                "execution_label": "sim" if horizon_years > 0 else "static",
                "policy_mode_label": policy_mode_label,
                "run_timestamp": run_artifacts.run_timestamp,
                "run_id": run_artifacts.run_id,
                "n_runs": 1,
                "horizon_years": horizon_years,
            },
        },
        run_artifacts.run_dir / "evaluation.json",
    )

    print()
    print(format_question_evaluation(evaluation))
    _log(f"JSON artifact written to {evaluation_json_path}")
    dashboard_path = _maybe_write_dashboard(
        run_dir=run_artifacts.run_dir,
        evaluation=evaluation,
        game_result=None,
        equilibrium_result=None,
        trajectory=trajectory,
        scenario_def=scenario,
        horizon_years=horizon_years,
        use_sim=horizon_years > 0,
        policy_mode_label=policy_mode_label,
        run_timestamp=run_artifacts.run_timestamp,
        run_id=run_artifacts.run_id,
    )
    brief_path = _maybe_write_brief(
        run_dir=run_artifacts.run_dir,
        evaluation=evaluation,
        game_result=None,
        equilibrium_result=None,
        trajectory=trajectory,
        scenario_def=scenario,
        horizon_years=horizon_years,
        use_sim=horizon_years > 0,
        policy_mode_label=policy_mode_label,
        run_timestamp=run_artifacts.run_timestamp,
        run_id=run_artifacts.run_id,
    )
    manifest_path = write_run_manifest(
        {
            "command": "question",
            "run_id": run_artifacts.run_id,
            "run_timestamp": run_artifacts.run_timestamp,
            "artifacts_dir": str(run_artifacts.run_dir),
            "inputs": {
                "question": question,
                "actors": actors,
                "base_year": base_year,
                "horizon_months": horizon_months,
                "template": template,
                "horizon_years": horizon_years,
            },
            "outputs": {
                "evaluation_json": str(evaluation_json_path.resolve()),
                "dashboard_html": str(Path(dashboard_path).resolve()) if dashboard_path is not None else None,
                "brief_markdown": str(Path(brief_path).resolve()) if brief_path is not None else None,
            },
        },
        run_artifacts.run_dir,
    )
    _log(f"Run manifest written to {manifest_path}")


def _select_case() -> Path | str | None:
    cases = discover_cases()
    if not cases:
        print("No bundled cases found.")
        return BUILD_NEW_GAME

    print()
    print("Available cases:")
    for index, (path, title) in enumerate(cases, start=1):
        print(f"[{index}] {title} ({path.name})")
    print("[n] Build a new case from free text")
    print("[p] Enter custom path")
    print("[b] Back")

    while True:
        raw = _prompt("Choose case [1]: ").strip().lower()
        if not raw:
            return cases[0][0]
        if raw == "b":
            return None
        if raw == "n":
            return BUILD_NEW_GAME
        if raw == "p":
            custom = _prompt_required("Case path: ")
            return _resolve_case_path(custom)
        if raw.isdigit():
            index = int(raw)
            if 1 <= index <= len(cases):
                return cases[index - 1][0]
        print("Choose a case number, `n`, `p`, or `b`.")


def _run_game_builder_flow(session: ConsoleSession, *, run_dir: Path) -> GameDefinition | None:
    runner = session.ensure_runner()
    assert session.world is not None
    del runner

    print()
    print("LLM case builder")
    description = _prompt_required("Describe scenario: ")
    _log("Building case from free text")
    build = build_case_from_text(description, session.world, prefer_llm=True)
    game = build.game
    _log(
        f"Case built via {build.source_label}: {game.title} "
        f"({len(game.players)} players, template={game.scenario.template_id})"
    )
    if build.note:
        _log(build.note)
    _log(f"Players: {', '.join(player.display_name for player in game.players)}")

    if _prompt_yes_no("Save generated case JSON", default=True):
        default_path = resolve_run_output_path(run_dir, None, f"{game.id}.json")
        output_path = _prompt(f"Case output [{default_path}]: ").strip() or str(default_path)
        saved_path = write_case_payload(build.payload, output_path)
        _log(f"Case JSON written to {saved_path}")

    return game


def _run_game_flow(session: ConsoleSession) -> None:
    runner = session.ensure_runner()
    assert session.world is not None

    case_selection = _select_case()
    if case_selection is None:
        return

    run_artifacts = build_run_artifacts("game")
    started = perf_counter()
    built_case_path = None
    if case_selection == BUILD_NEW_GAME:
        game = _run_game_builder_flow(session, run_dir=run_artifacts.run_dir)
        if game is None:
            return
        _log(f"Interactive game ready: {game.title}")
        default_case_path = run_artifacts.run_dir / f"{game.id}.json"
        if default_case_path.exists():
            built_case_path = default_case_path
    else:
        case_path = case_selection
        _log(f"Loading game case from {case_path}")
        game = load_game_definition(case_path, session.world)
    combination_count = count_action_combinations(game)
    _log(
        "Game loaded: "
        f"players={', '.join(player.display_name for player in game.players)}, combinations={combination_count}"
    )
    if combination_count > 256:
        _log("Action space exceeds 256 combinations; runner will truncate each player space to the first 3 actions.")
    horizon_years = _prompt_non_negative_int(
        "Horizon years [0 = static, 1-10 = simulate]: ",
        default=0,
    )

    if horizon_years > 0:
        background_policy = _prompt_choice(
            "Background policy",
            BACKGROUND_POLICY_CHOICES,
            default="compiled-llm",
        )
        llm_refresh = _prompt_choice("LLM refresh mode", LLM_REFRESH_CHOICES, default="trigger")
        llm_refresh_years = _prompt_non_negative_int("LLM refresh years [2]: ", default=2) or 2
        _log(
            f"Running policy game through simulation bridge for {horizon_years} yearly steps "
            f"(background={background_policy}, refresh={llm_refresh})"
        )
        bridge = SimBridge()
        result = bridge.run_game(
            session.world,
            game,
            n_years=horizon_years,
            default_mode=background_policy,
            llm_refresh=llm_refresh,
            llm_refresh_years=llm_refresh_years,
            progress_callback=_progress_logger(),
        )
        trajectory = result.trajectory
        policy_mode_label = background_policy
    else:
        _log("Running policy game with static scorer")
        result = runner.run_game(game)
        trajectory = [session.world]
        policy_mode_label = "snapshot"
    equilibrium_result = None
    if _prompt_yes_no("Run equilibrium analysis", default=False):
        episodes = _prompt_non_negative_int("Equilibrium episodes [50]: ", default=50)
        threshold = _prompt_optional_float("Convergence threshold [0.02]: ", default=0.02) or 0.02
        trust_alpha = _prompt_optional_float("Trust alpha [0.5]: ", default=0.5) or 0.5
        _log("Running equilibrium layer on top of the evaluated game matrix")
        equilibrium_result = run_equilibrium_search(
            runner=GameRunner(trajectory[-1]) if trajectory else runner,
            game=game,
            world=trajectory[-1] if trajectory else session.world,
            max_episodes=episodes,
            convergence_threshold=threshold,
            max_combinations=256,
            trust_alpha=trust_alpha,
            stage_game=result,
        )
    elapsed = perf_counter() - started
    _log(f"Game evaluation complete in {elapsed:.2f}s")
    game_json_path = write_json_artifact(
        {
            "game_result": asdict(result),
            "equilibrium_result": asdict(equilibrium_result) if equilibrium_result is not None else None,
        },
        run_artifacts.run_dir / "game_result.json",
    )

    print()
    print(format_game_result(result))
    if equilibrium_result is not None:
        print()
        print(format_equilibrium_result(equilibrium_result))
    _log(f"Game JSON artifact written to {game_json_path}")
    dashboard_path = _maybe_write_dashboard(
        run_dir=run_artifacts.run_dir,
        evaluation=result.best_combination.evaluation,
        game_result=result,
        equilibrium_result=equilibrium_result,
        trajectory=trajectory,
        scenario_def=game.scenario,
        horizon_years=horizon_years,
        use_sim=horizon_years > 0,
        policy_mode_label=policy_mode_label,
        run_timestamp=run_artifacts.run_timestamp,
        run_id=run_artifacts.run_id,
    )
    brief_path = _maybe_write_brief(
        run_dir=run_artifacts.run_dir,
        evaluation=result.best_combination.evaluation,
        game_result=result,
        equilibrium_result=equilibrium_result,
        trajectory=trajectory,
        scenario_def=game.scenario,
        horizon_years=horizon_years,
        use_sim=horizon_years > 0,
        policy_mode_label=policy_mode_label,
        run_timestamp=run_artifacts.run_timestamp,
        run_id=run_artifacts.run_id,
    )
    manifest_path = write_run_manifest(
        {
            "command": "game",
            "run_id": run_artifacts.run_id,
            "run_timestamp": run_artifacts.run_timestamp,
            "artifacts_dir": str(run_artifacts.run_dir),
            "inputs": {
                "selected_case": str(case_selection) if case_selection != BUILD_NEW_GAME else "generated",
                "horizon_years": horizon_years,
                "equilibrium": equilibrium_result is not None,
            },
            "outputs": {
                "generated_case_json": str(Path(built_case_path).resolve()) if built_case_path is not None else None,
                "game_result_json": str(game_json_path.resolve()),
                "dashboard_html": str(Path(dashboard_path).resolve()) if dashboard_path is not None else None,
                "brief_markdown": str(Path(brief_path).resolve()) if brief_path is not None else None,
            },
        },
        run_artifacts.run_dir,
    )
    _log(f"Run manifest written to {manifest_path}")


def run_console(state_csv: str | None = None, max_countries: int | None = None) -> None:
    session = ConsoleSession(state_csv=state_csv, max_countries=max_countries)
    while True:
        _render_menu()
        choice = _prompt("Mode: ").strip().lower()
        if choice in {"q", "quit", "exit"}:
            print("Exiting.")
            return
        if choice in {"1", "game", "policy", "policy gaming"}:
            _run_game_flow(session)
            continue
        if choice in {"2", "q&a", "qa", "question"}:
            _run_question_flow(session)
            continue
        print("Choose `1`, `2`, or `q`.")
