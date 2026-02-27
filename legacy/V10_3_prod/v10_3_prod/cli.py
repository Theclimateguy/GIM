import copy
import os
import random
from pathlib import Path

from .logging_utils import log_world_to_csv, make_sim_id
from .policy import llm_enablement_status, make_policy_map, resolve_policy_mode, should_use_llm
from .simulation import step_world_verbose
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


def _is_falsy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"0", "false", "no", "n", "off"}


def main() -> None:
    print("=" * 70)
    print("MODEL V10.3")
    print("=" * 70)

    policy_mode = resolve_policy_mode(os.getenv("POLICY_MODE", "auto"))
    use_llm = should_use_llm(policy_mode)
    _, llm_reason = llm_enablement_status(policy_mode)

    state_csv = _resolve_state_csv()
    print(f"\nLoading world from {state_csv}...")
    world = make_world_from_csv(state_csv)
    print(f"Loaded {len(world.agents)} countries")

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
    verbose_env = os.getenv("VERBOSE_COUNTRY_DETAILS")
    detailed_output = not _is_falsy(verbose_env)
    print(f"\nRunning {years}-year simulation...")
    print("\nProgress: ", end="", flush=True)

    history = []
    for step in range(years + 1):
        if step == 0:
            history.append(copy.deepcopy(world))
            print("0", end="", flush=True)
        else:
            world = step_world_verbose(
                world,
                policies,
                enable_extreme_events=enable_extreme_events,
                detailed_output=detailed_output,
            )
            history.append(copy.deepcopy(world))
            print(f".{step}", end="", flush=True)

    print("\n\nSimulation complete")

    sim_id = make_sim_id("V10_3_prod")
    csv_path = log_world_to_csv(history, sim_id)
    print(f"\nResults saved to: {csv_path}")

    world_start = history[0]
    world_end = history[-1]

    total_gdp_start = sum(agent.economy.gdp for agent in world_start.agents.values())
    total_gdp_end = sum(agent.economy.gdp for agent in world_end.agents.values())
    total_pop_start = sum(agent.economy.population for agent in world_start.agents.values())
    total_pop_end = sum(agent.economy.population for agent in world_end.agents.values())

    gdp_growth = (total_gdp_end / total_gdp_start - 1.0) * 100.0
    pop_growth = (total_pop_end / total_pop_start - 1.0) * 100.0

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"World GDP: ${total_gdp_start:.2f}T -> ${total_gdp_end:.2f}T ({gdp_growth:+.1f}%)")
    print(f"Population: {total_pop_start/1e9:.2f}B -> {total_pop_end/1e9:.2f}B ({pop_growth:+.1f}%)")
    print(
        "Temperature: "
        f"+{world_start.global_state.temperature_global:.4f}C -> "
        f"+{world_end.global_state.temperature_global:.4f}C"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
