import copy
import os
import random
import subprocess
import sys
from pathlib import Path

from .logging_utils import (
    log_actions_to_csv,
    log_institutions_to_csv,
    log_world_to_csv,
    make_sim_id,
)
from .policy import llm_enablement_status, make_policy_map, resolve_policy_mode, should_use_llm
from .simulation import step_world
from .world_factory import make_world_from_csv


def _resolve_state_csv() -> str:
    cwd_candidate = Path("agent_states.csv")
    if cwd_candidate.exists():
        return str(cwd_candidate)

    package_candidate = Path(__file__).resolve().parent.parent / "agent_states.csv"
    if package_candidate.exists():
        return str(package_candidate)

    return str(cwd_candidate)


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


def _generate_credit_map(csv_path: str, state_csv: str) -> str | None:
    root_dir = Path(__file__).resolve().parent.parent
    map_script = root_dir / "credit_map_leaflet.py"
    if not map_script.exists():
        print(f"Credit map script not found, skipping: {map_script}")
        return None

    geojson_path = root_dir / "data" / "world_countries.geojson"
    leaflet_css = root_dir / "vendor" / "leaflet" / "leaflet.css"
    leaflet_js = root_dir / "vendor" / "leaflet" / "leaflet.js"

    cmd = [
        sys.executable,
        str(map_script),
        "--log",
        str(Path(csv_path).resolve()),
        "--agents-csv",
        str(Path(state_csv).resolve()),
        "--geojson",
        str(geojson_path.resolve()),
        "--leaflet-css",
        str(leaflet_css.resolve()),
        "--leaflet-js",
        str(leaflet_js.resolve()),
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
    print("MODEL GIM_11_1")
    print("=" * 70)

    policy_mode = resolve_policy_mode(os.getenv("POLICY_MODE", "auto"))
    use_llm = should_use_llm(policy_mode)
    _, llm_reason = llm_enablement_status(policy_mode)

    state_csv = os.getenv("STATE_CSV", _resolve_state_csv())
    max_countries = _int_env("MAX_COUNTRIES", default=100, minimum=1)
    print(f"\nLoading world from {state_csv}...")
    try:
        world = make_world_from_csv(state_csv, max_agents=max_countries)
    except ValueError as exc:
        print(f"Input CSV validation failed: {exc}")
        raise SystemExit(2) from exc
    print(f"Loaded {len(world.agents)} countries (max={max_countries})")

    seed_raw = os.getenv("SIM_SEED")
    if seed_raw is not None:
        random.seed(int(seed_raw))
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
    print(f"\nRunning {years}-year simulation...")
    print("Progress:")

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

    if save_csv_logs:
        sim_id = make_sim_id("GIM_11_1")
        csv_path = log_world_to_csv(history, sim_id)
        actions_path = log_actions_to_csv(action_log or [], sim_id)
        institutions_path = log_institutions_to_csv(institution_log or [], sim_id)
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


if __name__ == "__main__":
    main()
