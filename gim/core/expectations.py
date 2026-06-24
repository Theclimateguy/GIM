"""[E4.3] Near-rational (model-consistent) expectations operator.

Agents form forward expectations by simulating the model itself forward, rather than extrapolating the
past. `update_expectations(world)` runs an H-step EVENT-FROZEN projection on a throwaway deep-copy of
the world and caches each agent's expected GDP growth (and inflation) on `world._expected_paths`. The
investment site (gim/core/economy.py::update_capital_endogenous) then reads its forecast from that
shared cache.

Design (see docs + the architecture diagram):
  * Near-rational / LEVEL-1, not full rational expectations. A recursion guard (`_in_expectation` on the
    shadow's global_state) makes the projection's OWN inner steps fall back to the cheap adaptive rule,
    so the nesting truncates at one level -- no infinite regress, no fixed-point solver. This is the
    deliberate departure from textbook RE that preserves GIM's non-equilibrium identity.
  * World-level and shared: the projection runs ONCE per refresh (every EXPECTATIONS_REFRESH_EVERY
    years), and every agent reads its own forecast off the same path -> cost is O(T*H), not O(T*N*H).
  * Deterministic & non-perturbing: the shadow is event-frozen (no extreme events) and its RNG is
    re-seeded from a derived seed, so the projection never touches the main world's stochastic stream.
  * Golden-safe: EXPECTATIONS_HORIZON=0 (default) -> `update_expectations` is a no-op that writes no
    extra state -> byte-identical to the validated baseline.

`update_expectations` must be called from the TOP of `step_world`, BEFORE the CriticalWriteGuard
context is entered: that guard uses a process-global handle, so the inner projection steps must run
their own guard while no outer guard is active (otherwise the inner __exit__ would clear it early).
"""
from __future__ import annotations

import copy

from .params import resolve_params
from .policy import make_policy_map
from .rng import get_seed, seed_world

_GUARD_ATTR = "_in_expectation"        # on world.global_state: True inside a projection
_CACHE_ATTR = "_expected_paths"        # on world: {agent_id: {"gdp_growth", "inflation"}}
_YEAR_ATTR = "_expected_paths_year"    # on world: the time the cache was last refreshed
_PROJECTION_SEED_OFFSET = 7919         # keep the shadow RNG independent of the main stream


def in_expectation_mode(world) -> bool:
    return bool(getattr(world.global_state, _GUARD_ATTR, False))


def expected_growth(world, agent_id: str) -> float | None:
    """The cached expected annual GDP growth for an agent, or None when expectations are off/absent."""
    cache = getattr(world, _CACHE_ATTR, None)
    if not cache:
        return None
    record = cache.get(agent_id)
    return record["gdp_growth"] if record else None


def update_expectations(world) -> None:
    """Refresh `world._expected_paths` when near-rational expectations are active.

    No-op (writes nothing) when EXPECTATIONS_HORIZON<=0 or when called inside a projection (recursion
    guard) -> golden-safe and recursion-bounded. Honours the EXPECTATIONS_REFRESH_EVERY cadence.
    """
    cal = resolve_params(world)
    horizon = int(getattr(cal, "EXPECTATIONS_HORIZON", 0))
    if horizon <= 0 or in_expectation_mode(world):
        return

    year = int(getattr(world, "time", 0))
    every = max(1, int(getattr(cal, "EXPECTATIONS_REFRESH_EVERY", 1)))
    last = getattr(world, _YEAR_ATTR, None)
    cached = getattr(world, _CACHE_ATTR, None)
    if cached is not None and last is not None and (year - last) < every:
        return  # reuse the still-fresh shared forecast

    setattr(world, _CACHE_ATTR, _project(world, horizon))
    setattr(world, _YEAR_ATTR, year)


def _project(world, horizon: int) -> dict[str, dict[str, float]]:
    # Throwaway shadow: deep-copy, set the recursion guard, freeze events, and re-seed the RNG from a
    # derived seed so the forecast is deterministic and independent of the main stochastic stream.
    from .simulation import step_world  # local import: avoid a circular import at module load

    shadow = copy.deepcopy(world)
    setattr(shadow.global_state, _GUARD_ATTR, True)
    seed_world(shadow, get_seed(world) + _PROJECTION_SEED_OFFSET + int(getattr(world, "time", 0)))
    policies = make_policy_map(shadow.agents.keys(), mode="simple")  # deterministic, never an LLM call

    gdp0 = {aid: max(float(a.economy.gdp), 1e-9) for aid, a in shadow.agents.items()}
    infl_sum: dict[str, float] = {aid: 0.0 for aid in shadow.agents}
    for _ in range(horizon):
        shadow = step_world(shadow, policies, enable_extreme_events=False)
        for aid, agent in shadow.agents.items():
            infl_sum[aid] += float(getattr(agent.economy, "inflation", 0.0))

    paths: dict[str, dict[str, float]] = {}
    for aid, agent in shadow.agents.items():
        if aid not in gdp0:
            continue
        gdp_h = max(float(agent.economy.gdp), 1e-9)
        paths[aid] = {
            "gdp_growth": (gdp_h / gdp0[aid]) ** (1.0 / horizon) - 1.0,  # annualized expected growth
            "inflation": infl_sum[aid] / horizon,                        # mean expected inflation
        }
    return paths


__all__ = ["update_expectations", "expected_growth", "in_expectation_mode"]
