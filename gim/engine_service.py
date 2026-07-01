"""GIM17 macOS engine sidecar.

A loopback HTTP+SSE service that wraps the *unchanged* in-process GIM17 API in
``gim/`` for the SwiftUI app. It adds **no model math** — every run orchestrates
existing functions (``compile_question``/``SimBridge``/``HybridSimulator``/
``run_equilibrium_search``) and projects their dataclasses into the stable JSON
shapes the Situation Room renders.

See ``docs/mac_app/ENGINE_BRIDGE_CONTRACT.md`` for the authoritative spec. The
parity test (``tests/test_engine_service.py``) guards against drift: a What-if
``result`` minus volatile fields must deep-equal the ``python3 -m gim question
--json`` output of the ``equiv_cli`` it reports.

Transport: binds ``127.0.0.1`` on an ephemeral port, requires a per-session
256-bit bearer token on every request, prints one ready-line of JSON on stdout,
logs to stderr, and self-exits if its parent process dies.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shlex
import sys
import threading
import time
import uuid
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from . import __version__
from .paths import RESULTS_ROOT
from .persona import augment_intent, get_persona, list_personas
from .ui_server import (
    ROOT,
    _analytics_payload_from_evaluation_path,
    _compare_payload,
    _doctrine_preview_payload,
    _intents_feed_payload,
    _list_actor_options,
    _load_world_cached,
    _safe_join,
)

SCHEMA = "gim-engine/1"

# The 8-phase pipeline progress markers, mirroring ui_server._update_progress.
_PHASE_MARKERS = (
    "baseline",
    "resolve_foreign_policy",
    "sanctions",
    "resource",
    "economy",
    "migration",
    "reconcile",
    "credit",
)
_STEP_TOTAL = len(_PHASE_MARKERS)

# Negative / positive outcome hints reused for weather-forecast valence colors.
_BAD_OUTCOME_HINTS = (
    "destabilization",
    "direct_strike",
    "proxy_escalation",
    "regional_escalation",
    "crisis",
    "unrest",
    "chokepoint",
    "conflict",
    "escalation",
    "strangulation",
    "default",
)
_GOOD_OUTCOME_HINTS = (
    "status_quo",
    "deescalation",
    "de_escalation",
    "suppression",
    "stable",
    "normalization",
    "mediation",
)


class RunCancelled(Exception):
    """Raised inside a run's progress_callback when its cancel flag is set."""


# --------------------------------------------------------------------------- #
# Run registry
# --------------------------------------------------------------------------- #


class EngineRun:
    """In-memory state for one streaming/async run, including its cancel flag."""

    def __init__(self, run_id: str, mode: str) -> None:
        self.run_id = run_id
        self.mode = mode
        self.cancelled = threading.Event()
        self.status = "queued"
        self.error: dict[str, Any] | None = None
        self.result: dict[str, Any] | None = None
        self.artifacts_dir: str | None = None
        self.started_at = time.time()


_RUNS: dict[str, EngineRun] = {}
_RUNS_LOCK = threading.Lock()


def _new_run(mode: str) -> EngineRun:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_id = f"{mode}-{stamp}-{uuid.uuid4().hex[:6]}"
    run = EngineRun(run_id, mode)
    with _RUNS_LOCK:
        _RUNS[run_id] = run
    return run


def _get_run(run_id: str) -> EngineRun | None:
    with _RUNS_LOCK:
        return _RUNS.get(run_id)


# --------------------------------------------------------------------------- #
# World handles (LRU over the shared ui_server cache)
# --------------------------------------------------------------------------- #

# world_key -> (state_csv, state_year, max_countries). The actual WorldState objects
# live in ui_server._WORLD_CACHE, so light calls stay sub-second and the app only
# ever passes the opaque handle around.
_WORLD_KEYS: dict[str, tuple[str | None, int | None, int | None]] = {}
_WORLD_KEYS_LOCK = threading.Lock()


def _world_key_for(state_csv: str | None, state_year: int | None, max_countries: int | None) -> str:
    raw = f"{state_csv or ''}|{int(state_year or 0)}|{int(max_countries or 0)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    key = f"w_{digest}"
    with _WORLD_KEYS_LOCK:
        _WORLD_KEYS[key] = (state_csv, state_year, max_countries)
    return key


def _resolve_world_key(world_key: str) -> tuple[str | None, int | None, int | None]:
    with _WORLD_KEYS_LOCK:
        spec = _WORLD_KEYS.get(world_key)
    if spec is None:
        raise KeyError(world_key)
    return spec


def _world_for_key(world_key: str):
    state_csv, state_year, max_countries = _resolve_world_key(world_key)
    return _load_world_cached(state_csv, state_year, max_countries)


# --------------------------------------------------------------------------- #
# Result projection (contract §5)
# --------------------------------------------------------------------------- #


def _valence_for(name: str) -> str:
    lower = name.lower()
    if any(hint in lower for hint in _BAD_OUTCOME_HINTS):
        return "bad"
    if any(hint in lower for hint in _GOOD_OUTCOME_HINTS):
        return "good"
    return "warn"


def _verdict_from_analytics(analytics: dict[str, Any]) -> str:
    dist = analytics.get("scenario_distribution") or []
    if not dist:
        return "Недостаточно данных для вердикта."
    top = dist[0]
    valence = _valence_for(str(top.get("name", "")))
    pct = 100.0 * float(top.get("value", 0.0))
    name = str(top.get("name", ""))
    if valence == "good":
        return f"Скорее устойчивый сценарий: «{name}» доминирует ({pct:.0f}%)."
    if valence == "bad":
        return f"Скорее срыв, чем стабилизация: «{name}» доминирует ({pct:.0f}%)."
    return f"Смешанный исход: «{name}» наиболее вероятен ({pct:.0f}%)."


def _paired_series(
    baseline_evaluation_path: Path,
    policy_evaluation_path: Path,
    series_key: str,
) -> list[dict[str, Any]]:
    """Zip a baseline analytics series with a policy series by actor id.

    Both inputs are produced by the same ``_analytics_payload_from_evaluation_path``
    projection, so the per-actor ``values`` lists are directly comparable.
    """
    baseline = _analytics_payload_from_evaluation_path(baseline_evaluation_path)
    policy = _analytics_payload_from_evaluation_path(policy_evaluation_path)
    base_by_id = {s["id"]: s for s in baseline.get(series_key, [])}
    out: list[dict[str, Any]] = []
    for series in policy.get(series_key, []):
        base = base_by_id.get(series["id"], {})
        out.append(
            {
                "id": series["id"],
                "name": series.get("name", series["id"]),
                "baseline": list(base.get("values", series.get("values", []))),
                "policy": list(series.get("values", [])),
            }
        )
    return out


def _price_series(evaluation_path: Path) -> dict[str, list[float]]:
    """Per-year global energy/food/metals price paths from the trajectory."""
    try:
        data = json.loads(evaluation_path.read_text(encoding="utf-8"))
    except Exception:
        return {"energy": [], "food": [], "metals": []}
    trajectory = data.get("trajectory") if isinstance(data.get("trajectory"), list) else []
    energy: list[float] = []
    food: list[float] = []
    metals: list[float] = []
    last = (1.0, 1.0, 1.0)
    for state in trajectory:
        g = state.get("global_state", {}) if isinstance(state, dict) else {}
        prices = g.get("prices", {}) if isinstance(g, dict) else {}
        e = float(prices.get("energy", last[0]))
        f = float(prices.get("food", last[1]))
        m = float(prices.get("metals", last[2]))
        last = (e, f, m)
        energy.append(e)
        food.append(f)
        metals.append(m)
    return {"energy": energy, "food": food, "metals": metals}


def _projection_from_evaluation(
    mode: str,
    evaluation_path: Path,
    *,
    baseline_evaluation_path: Path | None = None,
    intents_feed: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the stable UI projection from a saved evaluation.json.

    Reuses ``ui_server._analytics_payload_from_evaluation_path`` for the heavy
    lifting (criticality, outcome distribution, drivers, per-actor series), then
    reshapes into the contract §5 envelope. When a baseline evaluation is given,
    GDP/social series carry both ``baseline`` and ``policy`` paths.
    """
    analytics = _analytics_payload_from_evaluation_path(evaluation_path)

    outcomes = [
        {
            "name": item["name"],
            "value": float(item["value"]),
            "valence": _valence_for(str(item["name"])),
        }
        for item in analytics.get("scenario_distribution", [])
    ]
    drivers = []
    for line in analytics.get("brief_drivers", []):
        # brief_drivers lines look like "Debt Rollover: 0.91"
        if ":" in line:
            name, _, value = line.rpartition(":")
            try:
                drivers.append({"name": name.strip(), "value": float(value.strip())})
            except ValueError:
                drivers.append({"name": line.strip(), "value": 0.0})
    if not drivers:
        for card in analytics.get("quant", []):
            drivers.append({"name": card.get("name", ""), "value": float(card.get("raw_value", 0.0))})

    base_path = baseline_evaluation_path or evaluation_path
    gdp_series = _paired_series(base_path, evaluation_path, "gdp_series")
    social_series = _paired_series(base_path, evaluation_path, "social_tension_series")

    projection: dict[str, Any] = {
        "mode": mode,
        "schema": SCHEMA,
        "verdict": _verdict_from_analytics(analytics),
        "criticality": float(analytics.get("criticality", 0.0)),
        "outcomes": outcomes,
        "drivers": drivers[:6],
        "years": analytics.get("years", []),
        "series": {
            "gdp": gdp_series,
            "social_tension": social_series,
            "prices": _price_series(evaluation_path),
        },
    }
    if intents_feed is not None:
        projection["intents_feed"] = intents_feed
    return projection


# --------------------------------------------------------------------------- #
# Progress callback bridge (SSE)
# --------------------------------------------------------------------------- #


def _make_progress_callback(
    run: EngineRun,
    emit: Callable[[str, dict[str, Any]], None] | None,
) -> Callable[[Any], None]:
    """Adapt ``SimProgress`` updates into SSE ``progress`` events.

    ``step_index/step_total`` mirror the 8-phase pipeline using the same marker
    scan as ``ui_server._update_progress``. The callback also enforces cooperative
    cancellation: if the run's flag is set it raises ``RunCancelled``, which the
    bridge surfaces and we convert into a terminal ``error{code:"cancelled"}``.
    """

    def _callback(update: Any) -> None:
        if run.cancelled.is_set():
            raise RunCancelled(run.run_id)
        percent = int(getattr(update, "percent", 0))
        message = str(getattr(update, "message", ""))
        lowered = message.lower()
        step_index = 0
        for idx, marker in enumerate(_PHASE_MARKERS, start=1):
            if marker in lowered:
                step_index = idx
                break
        if step_index == 0:
            step_index = max(0, min(_STEP_TOTAL, int(round((percent / 100.0) * _STEP_TOTAL))))
        if emit is not None:
            emit(
                "progress",
                {
                    "run_id": run.run_id,
                    "percent": percent,
                    "step_index": step_index,
                    "step_total": _STEP_TOTAL,
                    "message": message,
                },
            )

    return _callback


# --------------------------------------------------------------------------- #
# Run orchestration (wraps existing in-process API; no model math here)
# --------------------------------------------------------------------------- #


def _trace_block(run: EngineRun, equiv_cli: str, seed: int | None) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "equiv_cli": equiv_cli,
        "seed": seed,
        "artifacts_dir": run.artifacts_dir,
        "elapsed_ms": int((time.time() - run.started_at) * 1000),
    }


def _world_cli_flags(world_key: str) -> list[str]:
    state_csv, state_year, max_countries = _resolve_world_key(world_key)
    flags: list[str] = []
    if state_csv:
        flags += ["--state-csv", str(state_csv)]
    if state_year:
        flags += ["--state-year", str(int(state_year))]
    if max_countries:
        flags += ["--max-countries", str(int(max_countries))]
    return flags


def run_whatif(
    run: EngineRun,
    payload: dict[str, Any],
    emit: Callable[[str, dict[str, Any]], None] | None,
) -> dict[str, Any]:
    """What-if mode: compile_question -> SimBridge.evaluate_scenario (or static).

    Mirrors ``__main__.py``'s question branch exactly so the result is parity-equal
    to ``python3 -m gim question --json``.
    """
    from .game_runner import GameRunner
    from .results import build_run_artifacts, write_json_artifact, write_run_manifest
    from .scenario_compiler import compile_question
    from .sim_bridge import SimBridge

    world_key = payload["world_key"]
    world = _world_for_key(world_key)
    question = str(payload.get("question") or "").strip()
    if not question:
        raise ValueError("whatif requires a non-empty 'question'")
    actors = payload.get("actors") or None
    if isinstance(actors, str):
        actors = shlex.split(actors) if actors.strip() else None
    template = payload.get("template") or None
    horizon = int(payload.get("horizon", 0) or 0)
    background_policy = str(payload.get("background_policy", "compiled-llm"))
    llm_refresh = str(payload.get("llm_refresh", "trigger"))
    llm_refresh_years = int(payload.get("llm_refresh_years", 2) or 2)
    use_sim = horizon > 0

    run_artifacts = build_run_artifacts("question")
    run.artifacts_dir = str(run_artifacts.run_dir.relative_to(ROOT)) if _under_root(run_artifacts.run_dir) else str(run_artifacts.run_dir)

    scenario = compile_question(
        question=question,
        world=world,
        actors=actors,
        template_id=template,
    )

    trajectory = [world]
    if use_sim:
        bridge = SimBridge()
        evaluation, trajectory = bridge.evaluate_scenario(
            world,
            scenario,
            n_years=horizon,
            default_mode=background_policy,
            llm_refresh=llm_refresh,
            llm_refresh_years=llm_refresh_years,
            progress_callback=_make_progress_callback(run, emit),
        )
    else:
        evaluation = GameRunner(world).evaluate_scenario(scenario)

    evaluation_json_path = write_json_artifact(
        {
            "scenario": asdict(scenario),
            "evaluation": asdict(evaluation),
            "game_result": None,
            "equilibrium_result": None,
            "trajectory": [asdict(state) for state in trajectory],
        },
        run_artifacts.run_dir / "evaluation.json",
    )
    write_run_manifest(
        {
            "command": "question",
            "run_id": run_artifacts.run_id,
            "run_timestamp": run_artifacts.run_timestamp,
            "artifacts_dir": str(run_artifacts.run_dir),
            "outputs": {"evaluation_json": str(evaluation_json_path.resolve())},
        },
        run_artifacts.run_dir,
    )

    # equiv_cli: the exact CLI that reproduces this run.
    cli = ["python3", "-m", "gim", "question", "--question", question]
    if actors:
        cli += ["--actors", *actors]
    if template:
        cli += ["--template", template]
    cli += _world_cli_flags(world_key)
    if use_sim:
        cli += ["--horizon", str(horizon), "--sim", "--background-policy", background_policy,
                "--llm-refresh", llm_refresh, "--llm-refresh-years", str(llm_refresh_years)]
    cli += ["--json"]
    equiv_cli = " ".join(shlex.quote(part) for part in cli)

    projection = _projection_from_evaluation("whatif", evaluation_json_path)
    projection["trace"] = _trace_block(run, equiv_cli, payload.get("seed"))
    # Embed the raw evaluation for the parity guarantee (contract §6): this is the
    # exact object `--json` prints. Kept under a dedicated key so the UI projection
    # stays clean while the parity test can compare math 1:1.
    projection["evaluation"] = asdict(evaluation)
    return projection


def run_play(
    run: EngineRun,
    payload: dict[str, Any],
    emit: Callable[[str, dict[str, Any]], None] | None,
) -> dict[str, Any]:
    """Play-as-a-country mode: HybridSimulator.run_round + intents feed.

    The persona biases (not overrides) the table intent via ``augment_intent``;
    background countries run the configured ``background_policy``.
    """
    from .hybrid_simulator import (
        HUMAN_MODE_ACTION,
        HUMAN_MODE_WHAT_IF,
        HybridSimulator,
        hybrid_result_payload,
    )
    from .results import build_run_artifacts, write_json_artifact, write_run_manifest

    world_key = payload["world_key"]
    world = _world_for_key(world_key)
    country = str(payload.get("country") or "").strip()
    if not country:
        raise ValueError("play requires a 'country'")
    persona = get_persona(payload.get("persona"))
    goal = str(payload.get("goal") or "").strip()
    intent_text = augment_intent(goal, persona)
    mode = str(payload.get("mode", HUMAN_MODE_WHAT_IF)).upper()
    if mode not in {HUMAN_MODE_ACTION, HUMAN_MODE_WHAT_IF}:
        mode = HUMAN_MODE_WHAT_IF
    round_years = int(payload.get("round_years", 4) or 4)
    ensemble_size = int(payload.get("ensemble_size", 3) or 3)
    seed = int(payload.get("seed", 2026) or 2026)
    background_policy = str(payload.get("background_policy", "compiled-llm"))
    llm_refresh = str(payload.get("llm_refresh", "trigger"))
    llm_refresh_years = int(payload.get("llm_refresh_years", 2) or 2)

    run_artifacts = build_run_artifacts("hybrid")
    run.artifacts_dir = str(run_artifacts.run_dir.relative_to(ROOT)) if _under_root(run_artifacts.run_dir) else str(run_artifacts.run_dir)

    # Coarse progress: HybridSimulator does not take a progress_callback, but we
    # still honour cooperative cancellation between the heavy phases.
    def _checkpoint(percent: int, message: str) -> None:
        if run.cancelled.is_set():
            raise RunCancelled(run.run_id)
        if emit is not None:
            emit("progress", {
                "run_id": run.run_id, "percent": percent,
                "step_index": max(0, min(_STEP_TOTAL, round(percent / 100.0 * _STEP_TOTAL))),
                "step_total": _STEP_TOTAL, "message": message,
            })

    _checkpoint(5, "compiling persona-biased intent")
    simulator = HybridSimulator()
    hybrid_result = simulator.run_round(
        world,
        intents_by_actor={country: intent_text},
        mode=mode,
        round_years=round_years,
        ensemble_size=ensemble_size,
        seed=seed,
        default_mode=background_policy,
        llm_refresh=llm_refresh,
        llm_refresh_years=llm_refresh_years,
        artifact_dir=str(run_artifacts.run_dir),
    )
    _checkpoint(90, "scoring policy vs baseline")

    full_payload = hybrid_result_payload(hybrid_result)
    evaluation_json_path = write_json_artifact(full_payload, run_artifacts.run_dir / "evaluation.json")
    hybrid_json_path = write_json_artifact(full_payload, run_artifacts.run_dir / "hybrid_result.json")
    # A baseline-only evaluation.json so the projection can show baseline vs policy paths.
    baseline_only = {
        "scenario": full_payload["scenario"],
        "evaluation": full_payload["baseline_evaluation"],
        "trajectory": full_payload["baseline_trajectory"],
    }
    baseline_path = write_json_artifact(baseline_only, run_artifacts.run_dir / "baseline_evaluation.json")
    write_run_manifest(
        {
            "command": "hybrid",
            "run_id": run_artifacts.run_id,
            "run_timestamp": run_artifacts.run_timestamp,
            "artifacts_dir": str(run_artifacts.run_dir),
            "outputs": {
                "evaluation_json": str(evaluation_json_path.resolve()),
                "hybrid_result_json": str(hybrid_json_path.resolve()),
            },
        },
        run_artifacts.run_dir,
    )

    intents_feed = _intents_feed_payload(hybrid_json_path).get("feed", [])
    if emit is not None:
        for item in intents_feed:
            emit("intent", item)

    cli = ["python3", "-m", "gim", "hybrid", "--tables", country, "--intent", f"{country}={intent_text}",
           "--mode", mode, "--round-years", str(round_years), "--ensemble-size", str(ensemble_size),
           "--seed", str(seed)]
    cli += _world_cli_flags(world_key)
    cli += ["--background-policy", background_policy, "--llm-refresh", llm_refresh,
            "--llm-refresh-years", str(llm_refresh_years), "--json"]
    equiv_cli = " ".join(shlex.quote(part) for part in cli)

    projection = _projection_from_evaluation(
        "play",
        evaluation_json_path,
        baseline_evaluation_path=baseline_path,
        intents_feed=intents_feed,
    )
    projection["trace"] = _trace_block(run, equiv_cli, seed)
    return projection


def run_game(
    run: EngineRun,
    payload: dict[str, Any],
    emit: Callable[[str, dict[str, Any]], None] | None,
) -> dict[str, Any]:
    """Game / equilibrium mode: SimBridge.run_game + optional run_equilibrium_search."""
    from .case_builder import build_case_from_text, write_case_payload
    from .game_runner import GameRunner
    from .game_theory.equilibrium_runner import run_equilibrium_search
    from .results import build_run_artifacts, resolve_run_output_path, write_json_artifact, write_run_manifest
    from .runtime import SCENARIOS_ROOT
    from .scenario_compiler import load_game_definition
    from .sim_bridge import SimBridge

    world_key = payload["world_key"]
    world = _world_for_key(world_key)
    case = payload.get("case") or None
    description = payload.get("description") or None
    if not case and not description:
        raise ValueError("game requires either 'case' or 'description'")
    horizon = int(payload.get("horizon", 0) or 0)
    want_equilibrium = bool(payload.get("equilibrium", False))
    episodes = int(payload.get("episodes", 50) or 50)
    threshold = float(payload.get("threshold", 0.02) or 0.02)
    trust_alpha = float(payload.get("trust_alpha", 0.5) or 0.5)
    max_combinations = int(payload.get("max_combinations", 256) or 256)
    background_policy = str(payload.get("background_policy", "compiled-llm"))
    llm_refresh = str(payload.get("llm_refresh", "trigger"))
    llm_refresh_years = int(payload.get("llm_refresh_years", 2) or 2)
    seed = payload.get("seed")
    use_sim = horizon > 0

    run_artifacts = build_run_artifacts("game")
    run.artifacts_dir = str(run_artifacts.run_dir.relative_to(ROOT)) if _under_root(run_artifacts.run_dir) else str(run_artifacts.run_dir)

    built_case_path = None
    if description:
        build = build_case_from_text(description, world, prefer_llm=True)
        game = build.game
        case_output = resolve_run_output_path(run_artifacts.run_dir, None, "generated_case.json")
        built_case_path = write_case_payload(build.payload, case_output)
    else:
        candidate = Path(str(case))
        case_path = candidate if candidate.exists() else SCENARIOS_ROOT / str(case)
        game = load_game_definition(case_path, world)

    runner = GameRunner(world)
    if use_sim:
        bridge = SimBridge()
        result = bridge.run_game(
            world,
            game,
            n_years=horizon,
            default_mode=background_policy,
            llm_refresh=llm_refresh,
            llm_refresh_years=llm_refresh_years,
            max_combinations=max_combinations,
            progress_callback=_make_progress_callback(run, emit),
        )
        trajectory = result.trajectory
    else:
        result = runner.run_game(game, max_combinations=max_combinations)
        trajectory = [world]

    equilibrium_result = None
    if want_equilibrium:
        if run.cancelled.is_set():
            raise RunCancelled(run.run_id)
        equilibrium_result = run_equilibrium_search(
            runner=GameRunner(trajectory[-1]) if trajectory else runner,
            game=game,
            world=trajectory[-1] if trajectory else world,
            max_episodes=episodes,
            convergence_threshold=threshold,
            max_combinations=max_combinations,
            trust_alpha=trust_alpha,
            stage_game=result,
        )

    game_json_path = write_json_artifact(
        {
            "game_result": asdict(result),
            "equilibrium_result": asdict(equilibrium_result) if equilibrium_result is not None else None,
        },
        run_artifacts.run_dir / "game_result.json",
    )
    # Best-combination evaluation drives the same projection the question path uses.
    best_evaluation = result.best_combination.evaluation
    evaluation_json_path = write_json_artifact(
        {
            "scenario": asdict(game.scenario),
            "evaluation": asdict(best_evaluation),
            "trajectory": [asdict(state) for state in trajectory],
        },
        run_artifacts.run_dir / "evaluation.json",
    )
    baseline_path = None
    if result.baseline_trajectory:
        baseline_path = write_json_artifact(
            {
                "scenario": asdict(game.scenario),
                "evaluation": asdict(result.baseline_evaluation),
                "trajectory": [asdict(state) for state in result.baseline_trajectory],
            },
            run_artifacts.run_dir / "baseline_evaluation.json",
        )
    write_run_manifest(
        {
            "command": "game",
            "run_id": run_artifacts.run_id,
            "run_timestamp": run_artifacts.run_timestamp,
            "artifacts_dir": str(run_artifacts.run_dir),
            "outputs": {
                "game_result_json": str(game_json_path.resolve()),
                "evaluation_json": str(evaluation_json_path.resolve()),
                "generated_case_json": str(Path(built_case_path).resolve()) if built_case_path else None,
            },
        },
        run_artifacts.run_dir,
    )

    cli = ["python3", "-m", "gim", "game"]
    if case:
        cli += ["--case", str(case)]
    else:
        cli += ["--description", str(description)]
    cli += _world_cli_flags(world_key)
    if use_sim:
        cli += ["--horizon", str(horizon), "--sim", "--background-policy", background_policy]
    if want_equilibrium:
        cli += ["--equilibrium", "--episodes", str(episodes), "--threshold", str(threshold),
                "--trust-alpha", str(trust_alpha)]
    cli += ["--max-combinations", str(max_combinations), "--json"]
    equiv_cli = " ".join(shlex.quote(part) for part in cli)

    projection = _projection_from_evaluation("game", evaluation_json_path, baseline_evaluation_path=baseline_path)
    projection["trace"] = _trace_block(run, equiv_cli, seed)
    projection["best_actions"] = dict(result.best_combination.actions)
    projection["truncated_action_space"] = bool(result.truncated_action_space)
    if equilibrium_result is not None:
        projection["equilibrium"] = asdict(equilibrium_result)
    return projection


_RUN_DISPATCH: dict[str, Callable[[EngineRun, dict[str, Any], Any], dict[str, Any]]] = {
    "whatif": run_whatif,
    "play": run_play,
    "game": run_game,
}


# --------------------------------------------------------------------------- #
# Export helpers
# --------------------------------------------------------------------------- #

_EXPORT_FILES = {
    "brief": ("decision_brief.md", "hybrid_report.md"),
    "dashboard": ("dashboard.html",),
    "evaluation": ("evaluation.json",),
}

_CSV_KINDS = {
    "world": ("hybrid_policy_round_world", "world"),
    "actions": ("hybrid_policy_round_actions", "actions"),
    "institutions": ("hybrid_policy_round_institutions", "institutions"),
}


def _run_dir_for(run_id: str) -> Path | None:
    run = _get_run(run_id)
    if run is not None and run.artifacts_dir:
        candidate = (ROOT / run.artifacts_dir).resolve()
        if candidate.is_dir():
            return candidate
    candidate = (RESULTS_ROOT / run_id).resolve()
    return candidate if candidate.is_dir() else None


def _export_file(run_id: str, kind: str) -> Path | None:
    run_dir = _run_dir_for(run_id)
    if run_dir is None:
        return None
    for name in _EXPORT_FILES.get(kind, ()):  # first existing wins
        candidate = run_dir / name
        if candidate.exists():
            return candidate
    return None


def _export_csv(run_id: str, kind: str) -> Path | None:
    run_dir = _run_dir_for(run_id)
    if run_dir is None:
        return None
    prefixes = _CSV_KINDS.get(kind)
    if prefixes is None:
        return None
    for candidate in sorted(run_dir.glob("*.csv")):
        if any(token in candidate.name for token in prefixes):
            return candidate
    return None


# --------------------------------------------------------------------------- #
# Misc
# --------------------------------------------------------------------------- #


def _under_root(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT)
        return True
    except ValueError:
        return False


def _ready_payload(port: int, token: str) -> dict[str, Any]:
    return {
        "ready": True,
        "schema": SCHEMA,
        "port": port,
        "token": token,
        "pid": os.getpid(),
        "gim_version": __version__,
        "offline": True,
    }


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #


class EngineHandler(BaseHTTPRequestHandler):
    server_version = "GIM17Engine/1.0"

    # Set by run_engine_service via the server instance.
    @property
    def _token(self) -> str:
        return self.server.session_token  # type: ignore[attr-defined]

    @property
    def _ready(self) -> dict[str, Any]:
        return self.server.ready_payload  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        # Logs to stderr (never stdout — stdout carries only the ready-line).
        sys.stderr.write("[engine] " + (fmt % args) + "\n")

    # -- helpers ----------------------------------------------------------- #

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return False
        return secrets.compare_digest(header[len("Bearer "):].strip(), self._token)

    def _send_json(self, payload: Any, status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_error(self, code: str, message: str, status: int, detail: Any = None) -> None:
        self._send_json(
            {"error": {"code": code, "message": message, "detail": detail}, "schema": SCHEMA},
            status=status,
        )

    def _send_file(self, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}

    def _wants_sse(self) -> bool:
        return "text/event-stream" in (self.headers.get("Accept", "") or "")

    def _sse_start(self) -> None:
        # SSE carries no Content-Length and we do not chunk-encode, so the stream
        # must be close-delimited: the client reads to EOF after the terminal
        # event. Force the connection closed (BaseHTTPRequestHandler keep-alive
        # for HTTP/1.1 clients would otherwise leave the reader blocked on the
        # next line indefinitely).
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

    def _sse_emit(self, event: str, data: dict[str, Any]) -> None:
        chunk = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        self.wfile.write(chunk.encode("utf-8"))
        self.wfile.flush()

    # -- request entry points --------------------------------------------- #

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/healthz":
            # Liveness — still token-gated per contract §1 (every request).
            if not self._authorized():
                self._send_error("unauthorized", "missing or invalid bearer token", 401)
                return
            self._send_json(self._ready)
            return

        if not self._authorized():
            self._send_error("unauthorized", "missing or invalid bearer token", 401)
            return

        try:
            if path == "/actors":
                world_key = query.get("world_key", [""])[0]
                state_csv, state_year, max_countries = _resolve_world_key(world_key)
                payload = _list_actor_options(str(state_csv) if state_csv else None)
                payload["schema"] = SCHEMA
                payload["world_key"] = world_key
                self._send_json(payload)
                return

            if path == "/personas":
                self._send_json({"personas": [p.to_payload() for p in list_personas()], "schema": SCHEMA})
                return

            if path.startswith("/personas/") and path.endswith("/doctrine"):
                persona_id = path[len("/personas/"):-len("/doctrine")]
                world_key = query.get("world_key", [""])[0]
                country = query.get("country", [""])[0].strip()
                if not country:
                    self._send_error("bad_request", "country query param is required", 400)
                    return
                state_csv, state_year, _max = _resolve_world_key(world_key)
                preview, status = _doctrine_preview_payload(
                    persona_id, country, str(state_csv) if state_csv else None, state_year,
                )
                preview["schema"] = SCHEMA
                if status != 200:
                    code = "unknown_persona" if "persona" in str(preview.get("error", "")) else "unknown_country"
                    self._send_error(code, str(preview.get("error", "error")), status)
                    return
                self._send_json(preview)
                return

            if path == "/metrics":
                world_key = query.get("world_key", [""])[0]
                agents_raw = query.get("agents", [""])[0].strip()
                self._send_json(self._metrics_payload(world_key, agents_raw))
                return

            if path.startswith("/export/"):
                self._handle_export(path[len("/export/"):], query)
                return

        except KeyError as exc:
            self._send_error("unknown_world", f"unknown world_key: {exc}", 404)
            return
        except ValueError as exc:
            self._send_error("bad_request", str(exc), 400)
            return
        except Exception as exc:  # noqa: BLE001
            self._send_error("internal", str(exc), 500)
            return

        self._send_error("not_found", f"no route for {path}", 404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if not self._authorized():
            self._send_error("unauthorized", "missing or invalid bearer token", 401)
            return

        body = self._read_json_body()

        if path == "/world/load":
            self._handle_world_load(body)
            return

        if path in ("/run/whatif", "/run/play", "/run/game"):
            mode = path.rsplit("/", 1)[-1]
            self._handle_run(mode, body)
            return

        if path == "/run/compare":
            run_ids = body.get("run_ids") or body.get("runs") or []
            if isinstance(run_ids, str):
                run_ids = [r.strip() for r in run_ids.split(",") if r.strip()]
            if len(run_ids) < 2:
                self._send_error("bad_request", "provide at least two run ids", 400)
                return
            payload = _compare_payload(list(run_ids))
            payload["schema"] = SCHEMA
            self._send_json(payload)
            return

        if path.startswith("/run/") and path.endswith("/cancel"):
            run_id = path[len("/run/"):-len("/cancel")]
            run = _get_run(run_id)
            if run is None:
                self._send_error("unknown_run", f"unknown run_id: {run_id}", 404)
                return
            run.cancelled.set()
            self._send_json({"run_id": run_id, "cancelled": True, "schema": SCHEMA})
            return

        self._send_error("not_found", f"no route for {path}", 404)

    # -- handlers ---------------------------------------------------------- #

    def _handle_world_load(self, body: dict[str, Any]) -> None:
        state_csv = body.get("state_csv")
        state_year = body.get("state_year")
        max_countries = body.get("max_countries")
        try:
            state_year_int = int(state_year) if state_year not in (None, "") else None
            max_countries_int = int(max_countries) if max_countries not in (None, "", 0, "0") else None
            world_key = _world_key_for(state_csv, state_year_int, max_countries_int)
            # Eagerly load + cache so the first light call is instant.
            _load_world_cached(state_csv, state_year_int, max_countries_int)
            actor_payload = _list_actor_options(str(state_csv) if state_csv else None)
        except Exception as exc:  # noqa: BLE001
            self._send_error("world_load_failed", str(exc), 400)
            return
        self._send_json(
            {
                "world_key": world_key,
                "state_year": state_year_int,
                "state_csv": actor_payload.get("state_csv"),
                "actors": actor_payload.get("actors", []),
                "personas": [p.to_payload() for p in list_personas()],
                "schema": SCHEMA,
            }
        )

    def _metrics_payload(self, world_key: str, agents_raw: str) -> dict[str, Any]:
        from .crisis_metrics import CrisisMetricsEngine
        from .scenario_compiler import resolve_actor_names

        world = _world_for_key(world_key)
        agent_ids = None
        if agents_raw:
            requested = [a.strip() for a in agents_raw.split(",") if a.strip()]
            agent_ids, _names, _unresolved = resolve_actor_names(world, requested)
            agent_ids = agent_ids or None
        dashboard = CrisisMetricsEngine().compute_dashboard(world, agent_ids=agent_ids)
        return {"metrics": asdict(dashboard), "schema": SCHEMA, "world_key": world_key}

    def _handle_run(self, mode: str, body: dict[str, Any]) -> None:
        if "world_key" not in body:
            self._send_error("bad_request", "world_key is required", 400)
            return
        # Validate the world_key up front (clear 404 before we start a stream).
        try:
            _resolve_world_key(body["world_key"])
        except KeyError as exc:
            self._send_error("unknown_world", f"unknown world_key: {exc}", 404)
            return

        runner = _RUN_DISPATCH[mode]
        run = _new_run(mode)

        if self._wants_sse():
            self._run_streaming(run, runner, body)
        else:
            self._run_sync(run, runner, body)

    def _run_sync(self, run: EngineRun, runner: Callable, body: dict[str, Any]) -> None:
        try:
            result = runner(run, body, None)
        except RunCancelled:
            self._send_error("cancelled", "run was cancelled", 409, detail={"run_id": run.run_id})
            return
        except (ValueError, KeyError) as exc:
            self._send_error("bad_request", str(exc), 400, detail={"run_id": run.run_id})
            return
        except Exception as exc:  # noqa: BLE001
            self._send_error("run_failed", str(exc), 500, detail={"run_id": run.run_id})
            return
        self._send_json(result)

    def _run_streaming(self, run: EngineRun, runner: Callable, body: dict[str, Any]) -> None:
        self._sse_start()

        def emit(event: str, data: dict[str, Any]) -> None:
            self._sse_emit(event, data)

        try:
            result = runner(run, body, emit)
        except RunCancelled:
            self._sse_emit("error", {"run_id": run.run_id, "code": "cancelled",
                                     "message": "run was cancelled"})
            return
        except (ValueError, KeyError) as exc:
            self._sse_emit("error", {"run_id": run.run_id, "code": "bad_request", "message": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001
            self._sse_emit("error", {"run_id": run.run_id, "code": "run_failed", "message": str(exc)})
            return
        self._sse_emit("result", result)

    def _handle_export(self, kind: str, query: dict[str, list[str]]) -> None:
        run_id = query.get("run_id", [""])[0].strip()
        if not run_id:
            self._send_error("bad_request", "run_id query param is required", 400)
            return
        if kind == "csv":
            csv_kind = query.get("kind", ["world"])[0].strip()
            path = _export_csv(run_id, csv_kind)
            if path is None:
                self._send_error("not_found", f"no {csv_kind} csv for run {run_id}", 404)
                return
            self._send_file(path, "text/csv; charset=utf-8")
            return
        if kind not in _EXPORT_FILES:
            self._send_error("not_found", f"unknown export kind: {kind}", 404)
            return
        path = _export_file(run_id, kind)
        if path is None:
            self._send_error("not_found", f"no {kind} artifact for run {run_id}", 404)
            return
        content_types = {
            "brief": "text/markdown; charset=utf-8",
            "dashboard": "text/html; charset=utf-8",
            "evaluation": "application/json; charset=utf-8",
        }
        self._send_file(path, content_types[kind])


# --------------------------------------------------------------------------- #
# Parent-pid watchdog
# --------------------------------------------------------------------------- #


def _start_parent_watchdog(server: ThreadingHTTPServer) -> None:
    """Self-exit if the parent process (the app) dies (contract §1 lifecycle)."""
    parent_pid = os.getppid()
    if parent_pid <= 1:
        return  # already orphaned / launched without a real parent

    def _watch() -> None:
        while True:
            time.sleep(2.0)
            if os.getppid() != parent_pid:
                sys.stderr.write("[engine] parent process gone; shutting down\n")
                sys.stderr.flush()
                try:
                    server.shutdown()
                finally:
                    os._exit(0)

    threading.Thread(target=_watch, name="engine-parent-watchdog", daemon=True).start()


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #


def build_engine_server(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    """Create the engine server (bound, not yet serving) with token + ready payload.

    Exposed for tests so they can grab the OS-assigned port and token without
    racing on stdout.
    """
    server = ThreadingHTTPServer((host, port), EngineHandler)
    token = secrets.token_hex(32)  # 256-bit session token
    bound_port = server.server_address[1]
    server.session_token = token  # type: ignore[attr-defined]
    server.ready_payload = _ready_payload(bound_port, token)  # type: ignore[attr-defined]
    return server


def run_engine_service(host: str = "127.0.0.1", port: int = 0) -> None:
    server = build_engine_server(host, port)
    ready = server.ready_payload  # type: ignore[attr-defined]
    # ONE line of JSON on stdout, then stdout is silent (logs go to stderr).
    sys.stdout.write(json.dumps(ready, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    _start_parent_watchdog(server)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run_engine_service()
