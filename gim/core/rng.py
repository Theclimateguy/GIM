"""World-scoped deterministic RNG for GIM17 (Stage D).

Stochastic core channels must draw from a single seeded random stream attached to
the `WorldState`, not from the process-global `random` module. This makes a bare
`step_world` reproducible (same seed -> identical trajectory) and lets independent
worlds (e.g. Monte-Carlo ensemble members) run without interfering through shared
global RNG state.

Note: `random.Random(s)` reproduces the same sequence as `random.seed(s)` followed by
module-level `random` calls, so seeding a world to the value previously passed to
`random.seed` preserves draw-for-draw behaviour as long as the draw order is unchanged.
"""

from __future__ import annotations

import random

_SEED_ATTR = "_sim_seed"
_RNG_ATTR = "_sim_rng"
DEFAULT_SEED = 0


def seed_world(world, seed: int) -> random.Random:
    """Seed the world's master RNG (and keep the temperature-variability seed in sync)."""
    value = int(seed)
    gs = world.global_state
    setattr(gs, _SEED_ATTR, value)
    setattr(gs, _RNG_ATTR, random.Random(value))
    setattr(gs, "_temperature_variability_seed", value)
    return getattr(gs, _RNG_ATTR)


def get_rng(world) -> random.Random:
    """Return the world's master RNG, lazily creating it from the stored seed (default 0)."""
    gs = world.global_state
    rng = getattr(gs, _RNG_ATTR, None)
    if rng is None:
        rng = random.Random(int(getattr(gs, _SEED_ATTR, DEFAULT_SEED)))
        setattr(gs, _RNG_ATTR, rng)
    return rng


def get_seed(world) -> int:
    return int(getattr(world.global_state, _SEED_ATTR, DEFAULT_SEED))


__all__ = ["seed_world", "get_rng", "get_seed", "DEFAULT_SEED"]
