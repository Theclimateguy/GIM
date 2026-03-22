import copy
from datetime import datetime
import os
import random
import subprocess
import sys
from pathlib import Path

from ..paths import DEFAULT_STATE_CSV, LEAFLET_CSS, LEAFLET_JS, MAP_SCRIPT, WORLD_GEOJSON
from ..results import build_run_artifacts, write_run_manifest
from .logging_utils import (
    log_actions_to_csv,
    log_institutions_to_csv,
    log_world_to_csv,
    make_sim_id,
)
from .policy import llm_enablement_status, make_policy_map, resolve_policy_mode, should_use_llm
from .simulation import step_world
from .world_factory import make_world_from_csv

MODEL_DISPLAY_NAME = "GIM16"


def _resolve_state_csv() -> str:
    cwd_candidate = Path("agent_states.csv")
    if cwd_candidate.exists():
        return str(cwd_candidate)

    if DEFAULT_STATE_CSV.exists():
        return str(DEFAULT_STATE_CSV)

    return str(cwd_candidate.resolve())


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return _is_truthy(raw)


def _resolve_state_year() -> int:
    for env_name in (
        "GIM16_STATE_YEAR",
        "GIM15_STATE_YEAR",
        "GIM_STATE_YEAR",
        "GIM13_STATE_YEAR",
        "STATE_YEAR",
        "SIM_START_YEAR",
    ):
        raw = os.getenv(env_name)
        if raw is None:
            continue
        try:
            return int(raw)
        except ValueError:
            continue
    return 2023


def _generate_credit_map(csv_path: str, state_csv: str) -> str | None:
    map_script = MAP_SCRIPT
    if not map_script.exists():
        print(f"Credit map script not found, skipping: {map_script}")
        return None

    cmd = [
        sys.executable,
        str(map_script),
        "--log",
        str(Path(csv_path).resolve()),
        "--agents-csv",
        str(Path(state_csv).resolve()),
        "--geojson",
        str(WORLD_GEOJSON.resolve()),
        "--leaflet-css",
        str(LEAFLET_CSS.resolve()),
        "--leaflet-js",
        str(LEAFLET_JS.resolve()),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("Credit map generation failed:")
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        if stderr:
            print(stderr)
        elif stdout:
            print(stdout)
        return None

    map_path: str | None = None
    for line in (result.stdout or "").splitlines():
        if line.startswith("Map HTML:"):
            map_path = line.split(":", 1)[1].strip()
            break
    return map_path


def main() -> None:
    print("=" * 70)
    print(f"MODEL {MODEL_DISPLAY_NAME}")
    print("=" * 70)

    policy_mode = resolve_policy_mode(os.getenv("POLICY_MODE", "auto"))
    use_llm = should_use_llm(policy_mode)
    _, llm_reason = llm_enablement_status(policy_mode)

    state_csv = os.getenv("STATE_CSV", _resolve_state_csv())
    state_year = _resolve_state_year()
    max_countries = _int_env("MAX_COUNTRIES", default=100, minimum=1)
    print(f"\nLoading world from {state_csv} (state_year={state_year})...")
    try:
        world = make_world_from_csv(state_csv, max_agents=max_countries, base_year=state_year)
    except ValueError as exc:
        print(f"Input CSV validation failed: {exc}")
        raise SystemExit(2) from exc
    print(f"Loaded {len(world.agents)} countries (max={max_countries})")

    seed_raw = os.getenv("SIM_SEED")
    if seed_raw is not None:
        seed = int(seed_raw)
        random.seed(seed)
        world.global_state._temperature_variability_seed = seed
        print(f"Using SIM_SEED={seed_raw}")

    policies = make_policy_map(world.agents.keys(), mode=policy_mode)
    if use_llm:
        print("\nUsing LLM agents")
        print(f"LLM enablement: {llm_reason}")
        print(
            "LLM settings: "
            f"timeout={os.getenv('LLM_TIMEOUT_SEC', '120')}s, "
            f"retries={os.getenv('LLM_MAX_RETRIES', '2')}, "
            f"backoff={os.getenv('LLM_RETRY_BACKOFF_SEC', '2.0')}s"
        )
    else:
        print("\nUsing simple baseline policies (no LLM calls)")
        print(f"LLM enablement: {llm_reason}")

    years = int(os.getenv("SIM_YEARS", "5"))
    enable_extreme_events = not _is_truthy(os.getenv("DISABLE_EXTREME_EVENTS"))
    save_csv_logs = _bool_env("SAVE_CSV_LOGS", default=False)
    generate_credit_map = _bool_env("GENERATE_CREDIT_MAP", default=True)
    run_artifacts = build_run_artifacts("world")
    print(f"Artifacts directory: {run_artifacts.run_dir}")
    print(f"\nRunning {years}-year simulation...")
    print("Progress:")

    time_start = world.time
    total_gdp_start = sum(agent.economy.gdp for agent in world.agents.values())
    total_pop_start = sum(agent.economy.population for agent in world.agents.values())
    temp_start = world.global_state.temperature_global

    history = [copy.deepcopy(world)] if save_csv_logs else []
    action_log = [] if save_csv_logs else None
    institution_log = [] if save_csv_logs else None
    for step in range(1, years + 1):
        world = step_world(
            world,
            policies,
            enable_extreme_events=enable_extreme_events,
            action_log=action_log,
            institution_log=institution_log,
        )
        if save_csv_logs:
            history.append(copy.deepcopy(world))
        progress_pct = 100.0 * step / max(years, 1)
        print(f"  Year {step:>3}/{years:<3}  {progress_pct:6.2f}%")

    print("\n\nSimulation complete")

    csv_path: str | None = None
    actions_path: str | None = None
    institutions_path: str | None = None
    map_path: str | None = None
    if save_csv_logs:
        sim_id = make_sim_id(MODEL_DISPLAY_NAME)
        csv_path = log_world_to_csv(history, sim_id, base_dir=str(run_artifacts.run_dir))
        actions_path = log_actions_to_csv(action_log or [], sim_id, base_dir=str(run_artifacts.run_dir))
        institutions_path = log_institutions_to_csv(
            institution_log or [],
            sim_id,
            base_dir=str(run_artifacts.run_dir),
        )
        print(f"\nResults saved to: {csv_path}")
        print(f"Actions log saved to: {actions_path}")
        print(f"Institutions log saved to: {institutions_path}")
        if generate_credit_map:
            map_path = _generate_credit_map(csv_path, state_csv)
            if map_path:
                print(f"Credit map saved to: {map_path}")
    else:
        print("\nCSV logs skipped (set SAVE_CSV_LOGS=1 to enable).")

    total_gdp_end = sum(agent.economy.gdp for agent in world.agents.values())
    total_pop_end = sum(agent.economy.population for agent in world.agents.values())

    gdp_growth = (total_gdp_end / total_gdp_start - 1.0) * 100.0
    pop_growth = (total_pop_end / total_pop_start - 1.0) * 100.0

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"World GDP: ${total_gdp_start:.2f}T -> ${total_gdp_end:.2f}T ({gdp_growth:+.1f}%)")
    print(f"Population: {total_pop_start/1e9:.2f}B -> {total_pop_end/1e9:.2f}B ({pop_growth:+.1f}%)")
    print(
        "Temperature: "
        f"+{temp_start:.4f}C -> "
        f"+{world.global_state.temperature_global:.4f}C"
    )
    print("=" * 70)
    manifest_path = write_run_manifest(
        {
            "command": "world",
            "run_id": run_artifacts.run_id,
            "run_timestamp": run_artifacts.run_timestamp,
            "artifacts_dir": str(run_artifacts.run_dir),
            "inputs": {
                "state_csv": str(Path(state_csv).resolve()),
                "state_year": state_year,
                "max_countries": max_countries,
                "policy_mode": policy_mode,
                "llm_enabled": use_llm,
                "llm_enablement_reason": llm_reason,
                "sim_years": years,
                "sim_seed": int(seed_raw) if seed_raw is not None else None,
                "save_csv_logs": save_csv_logs,
                "generate_credit_map": generate_credit_map,
                "extreme_events_enabled": enable_extreme_events,
            },
            "summary": {
                "time_start": time_start,
                "time_end": world.time,
                "world_gdp_start": total_gdp_start,
                "world_gdp_end": total_gdp_end,
                "world_gdp_growth_pct": gdp_growth,
                "population_start": total_pop_start,
                "population_end": total_pop_end,
                "population_growth_pct": pop_growth,
                "temperature_start": temp_start,
                "temperature_end": world.global_state.temperature_global,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            },
            "outputs": {
                "world_csv": csv_path,
                "actions_csv": actions_path,
                "institutions_csv": institutions_path,
                "credit_map_html": map_path,
            },
        },
        run_artifacts.run_dir,
    )
    print(f"Run manifest written to: {manifest_path}")


if __name__ == "__main__":
    main()
