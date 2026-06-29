"""Determinism tests for the world-scoped RNG (Stage D).

Guarantees:
  1. same seed -> identical trajectory
  2. trajectory is independent of process-global ``random`` state
  3. the default (unseeded) world is reproducible (seed 0)
"""

import random
import unittest

from gim.core.policy import make_policy_map
from gim.core.rng import get_rng, get_seed, seed_world
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv

STATE_CSV = "data/agent_states_operational.csv"


def _build(max_agents: int = 12):
    return make_world_from_csv(STATE_CSV, max_agents=max_agents, base_year=2023)


def _run(world, years: int = 6):
    policies = make_policy_map(world.agents.keys(), mode="simple")
    for _ in range(years):
        # extreme events ON so the climate stochastic channel is exercised
        step_world(world, policies, enable_extreme_events=True)
    return world


def _fingerprint(world):
    rows = []
    for aid in sorted(world.agents):
        e = world.agents[aid].economy
        rows.append((aid, round(e.gdp, 9), round(e.public_debt, 9), round(e.capital, 9)))
    g = world.global_state
    return (tuple(rows), round(g.temperature_global, 9), round(g.co2, 9))


class DeterminismTests(unittest.TestCase):
    def test_same_seed_identical_trajectory(self):
        w1 = _build(); seed_world(w1, 42)
        w2 = _build(); seed_world(w2, 42)
        self.assertEqual(_fingerprint(_run(w1)), _fingerprint(_run(w2)))

    def test_independent_of_global_random_state(self):
        w1 = _build(); seed_world(w1, 123)
        fp1 = _fingerprint(_run(w1))
        # Perturb the process-global RNG between runs; the world RNG must be unaffected.
        random.seed(999)
        _ = [random.random() for _ in range(1000)]
        w2 = _build(); seed_world(w2, 123)
        fp2 = _fingerprint(_run(w2))
        self.assertEqual(fp1, fp2)

    def test_default_unseeded_world_is_reproducible(self):
        # No explicit seed -> default master seed 0, still reproducible.
        w1 = _build()
        w2 = _build()
        self.assertEqual(get_seed(w1), 0)
        self.assertEqual(_fingerprint(_run(w1)), _fingerprint(_run(w2)))


class RngUnitTests(unittest.TestCase):
    def test_seed_world_sets_seed_and_syncs_temperature_seed(self):
        w = _build()
        seed_world(w, 7)
        self.assertEqual(get_seed(w), 7)
        self.assertEqual(w.global_state._temperature_variability_seed, 7)

    def test_same_seed_same_sequence(self):
        w1 = _build(); seed_world(w1, 5)
        w2 = _build(); seed_world(w2, 5)
        seq1 = [get_rng(w1).random() for _ in range(8)]
        seq2 = [get_rng(w2).random() for _ in range(8)]
        self.assertEqual(seq1, seq2)

    def test_different_seed_different_sequence(self):
        w1 = _build(); seed_world(w1, 1)
        w2 = _build(); seed_world(w2, 2)
        seq1 = [get_rng(w1).random() for _ in range(8)]
        seq2 = [get_rng(w2).random() for _ in range(8)]
        self.assertNotEqual(seq1, seq2)


if __name__ == "__main__":
    unittest.main()
