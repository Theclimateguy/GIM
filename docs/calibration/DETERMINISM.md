# GIM18 Determinism

Scientific runs must be reproducible: the same inputs and seed must produce the same
trajectory, regardless of process-global state or run order (so Monte-Carlo ensemble
members don't interfere).

## World-scoped RNG

All stochastic **core** channels draw from a single seeded RNG attached to the world
(`gim/core/rng.py`), not from the process-global `random` module:

- `seed_world(world, seed)` — set the master seed (also syncs the temperature-variability seed).
- `get_rng(world)` — the world's `random.Random`, created lazily from the stored seed
  (default `0`).

Channels migrated to the world RNG: climate extreme events (`climate.py`) and the
geopolitical security-action roll (`geopolitics.py`). Temperature variability was already
seeded per `(seed, year)`.

## How to get a reproducible run

- CLI: set `SIM_SEED` (e.g. `SIM_SEED=42 python3 -m gim.core`). Without it, the default
  master seed is `0` — still fully reproducible.
- Library: call `seed_world(world, seed)` after `make_world_from_csv(...)`.

## Deterministic policy by default

The world CLI now defaults to **rule-based** policy (`POLICY_MODE=simple`). LLM agents are
non-deterministic and must be opted into explicitly with `POLICY_MODE=llm` (plus
`DEEPSEEK_API_KEY`). This keeps scientific and CI runs reproducible by default.

## Known residual

`hybrid_simulator.py`, `state_projection.py`, and `game_theory/` still seed the global
`random` module directly. They seed explicitly so they are reproducible in isolation, but
they are not yet isolated from global state. Migrate them to the world RNG if they enter
scientific/ensemble pipelines.

Covered by `tests/test_determinism.py` (same seed → identical trajectory; independence from
global RNG state; default-seed reproducibility).
