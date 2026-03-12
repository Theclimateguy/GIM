from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from math import prod
from pathlib import Path
from time import perf_counter
from typing import Callable

from .briefing import AnalyticsBriefRenderer, BriefConfig, write_brief_artifact
from .dashboard import DashboardConfig, DashboardRenderer, write_dashboard_artifacts
from .explanations import format_game_result, format_question_evaluation
from .game_runner import GameRunner
from .runtime import MISC_ROOT, default_state_csv, load_world
from .scenario_compiler import compile_question, load_game_definition
from .sim_bridge import SimBridge, SimProgress
from .types import GameDefinition


CASES_DIR = MISC_ROOT / "cases"


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
    evaluation,
    game_result,
    trajectory,
    scenario_def,
    horizon_years: int,
    use_sim: bool,
    run_timestamp: str,
    run_id: str,
) -> None:
    if not _prompt_yes_no("Write dashboard (includes Decision Brief)", default=False):
        return
    output_path = _prompt("Dashboard output [dashboard.html]: ").strip() or "dashboard.html"
    written = write_dashboard_artifacts(
        renderer=DashboardRenderer(),
        evaluation=evaluation,
        game_result=game_result,
        trajectory=trajectory,
        scenario_def=scenario_def,
        config=DashboardConfig(
            output_path=output_path,
            show_trajectory=use_sim and len(trajectory or []) > 1,
            show_game_results=game_result is not None,
            execution_label="sim" if use_sim else "static",
            policy_mode_label="llm" if use_sim else "snapshot",
            run_timestamp=run_timestamp,
            run_id=run_id,
            n_runs=1,
            horizon_years=horizon_years,
        ),
        save_json=False,
    )
    _log(f"Dashboard written to {written['html']}")


def _maybe_write_brief(
    *,
    evaluation,
    game_result,
    trajectory,
    scenario_def,
    horizon_years: int,
    use_sim: bool,
    run_timestamp: str,
    run_id: str,
) -> None:
    if not _prompt_yes_no("Write standalone analytical brief", default=False):
        return
    output_path = _prompt("Brief output [decision_brief.md]: ").strip() or "decision_brief.md"
    written = write_brief_artifact(
        renderer=AnalyticsBriefRenderer(),
        evaluation=evaluation,
        game_result=game_result,
        trajectory=trajectory,
        scenario_def=scenario_def,
        config=BriefConfig(
            output_path=output_path,
            include_trajectory=use_sim and len(trajectory or []) > 1,
            include_game_results=game_result is not None,
            execution_label="sim" if use_sim else "static",
            policy_mode_label="llm" if use_sim else "snapshot",
            run_timestamp=run_timestamp,
            run_id=run_id,
            n_runs=1,
            horizon_years=horizon_years,
        ),
    )
    _log(f"Analytical brief written to {written}")


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
        _log(f"Running simulation bridge for {horizon_years} yearly steps")
        bridge = SimBridge()
        evaluation, trajectory = bridge.evaluate_scenario(
            session.world,
            scenario,
            n_years=horizon_years,
            default_mode="llm",
            progress_callback=_progress_logger(),
        )
    else:
        _log("Evaluating scenario with static scorer")
        evaluation = runner.evaluate_scenario(scenario)
        trajectory = [session.world]
    elapsed = perf_counter() - started
    _log(f"Evaluation complete in {elapsed:.2f}s")
    run_stamp = datetime.now()
    run_timestamp = run_stamp.strftime("%Y-%m-%d %H:%M")
    run_id = f"question-{run_stamp.strftime('%Y%m%d-%H%M%S')}"

    print()
    print(format_question_evaluation(evaluation))
    _maybe_write_dashboard(
        evaluation=evaluation,
        game_result=None,
        trajectory=trajectory,
        scenario_def=scenario,
        horizon_years=horizon_years,
        use_sim=horizon_years > 0,
        run_timestamp=run_timestamp,
        run_id=run_id,
    )
    _maybe_write_brief(
        evaluation=evaluation,
        game_result=None,
        trajectory=trajectory,
        scenario_def=scenario,
        horizon_years=horizon_years,
        use_sim=horizon_years > 0,
        run_timestamp=run_timestamp,
        run_id=run_id,
    )


def _select_case() -> Path | None:
    cases = discover_cases()
    if not cases:
        print("No bundled cases found.")
        return None

    print()
    print("Available cases:")
    for index, (path, title) in enumerate(cases, start=1):
        print(f"[{index}] {title} ({path.name})")
    print("[p] Enter custom path")
    print("[b] Back")

    while True:
        raw = _prompt("Choose case [1]: ").strip().lower()
        if not raw:
            return cases[0][0]
        if raw == "b":
            return None
        if raw == "p":
            custom = _prompt_required("Case path: ")
            return _resolve_case_path(custom)
        if raw.isdigit():
            index = int(raw)
            if 1 <= index <= len(cases):
                return cases[index - 1][0]
        print("Choose a case number, `p`, or `b`.")


def _run_game_flow(session: ConsoleSession) -> None:
    runner = session.ensure_runner()
    assert session.world is not None

    case_path = _select_case()
    if case_path is None:
        return

    started = perf_counter()
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
        _log(f"Running policy game through simulation bridge for {horizon_years} yearly steps")
        bridge = SimBridge()
        result = bridge.run_game(
            session.world,
            game,
            n_years=horizon_years,
            default_mode="llm",
            progress_callback=_progress_logger(),
        )
        trajectory = result.trajectory
    else:
        _log("Running policy game with static scorer")
        result = runner.run_game(game)
        trajectory = [session.world]
    elapsed = perf_counter() - started
    _log(f"Game evaluation complete in {elapsed:.2f}s")
    run_stamp = datetime.now()
    run_timestamp = run_stamp.strftime("%Y-%m-%d %H:%M")
    run_id = f"game-{run_stamp.strftime('%Y%m%d-%H%M%S')}"

    print()
    print(format_game_result(result))
    _maybe_write_dashboard(
        evaluation=result.best_combination.evaluation,
        game_result=result,
        trajectory=trajectory,
        scenario_def=game.scenario,
        horizon_years=horizon_years,
        use_sim=horizon_years > 0,
        run_timestamp=run_timestamp,
        run_id=run_id,
    )
    _maybe_write_brief(
        evaluation=result.best_combination.evaluation,
        game_result=result,
        trajectory=trajectory,
        scenario_def=game.scenario,
        horizon_years=horizon_years,
        use_sim=horizon_years > 0,
        run_timestamp=run_timestamp,
        run_id=run_id,
    )


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
