"""Tests for the per-run ParameterSet context (Phase 1, option B2)."""

from dataclasses import asdict
import copy
import json
import unittest

from gim.core.params import ParameterSet, build_params, default_params, resolve_params
from gim.core.policy import make_policy_map
from gim.core.rng import seed_world
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv

STATE_CSV = "data/agent_states_operational.csv"


def _world(max_agents: int = 8):
    return make_world_from_csv(STATE_CSV, max_agents=max_agents, base_year=2023)


class ParameterSetUnitTests(unittest.TestCase):
    def test_attribute_access_and_immutability(self):
        p = default_params()
        self.assertIsInstance(p.ALPHA_CAPITAL, float)
        with self.assertRaises(AttributeError):
            p.ALPHA_CAPITAL = 0.5  # immutable
        with self.assertRaises(AttributeError):
            _ = p.NOT_A_REAL_PARAM

    def test_with_overrides_returns_new_set_and_validates(self):
        p = default_params()
        q = p.with_overrides({"ALPHA_CAPITAL": 0.32})
        self.assertEqual(q.ALPHA_CAPITAL, 0.32)
        self.assertNotEqual(p.ALPHA_CAPITAL, 0.32)  # original unchanged
        with self.assertRaises(KeyError):
            p.with_overrides({"TOTALLY_UNKNOWN": 1.0})  # guards sampling typos

    def test_covers_full_calibration_surface(self):
        # Every parameter the model reads must be present in the set.
        self.assertGreaterEqual(len(default_params()), 284)

    def test_deepcopy_shares_immutable_set(self):
        p = default_params()
        self.assertIs(copy.deepcopy(p), p)


class WorldIntegrationTests(unittest.TestCase):
    def test_world_has_params_and_resolves(self):
        w = _world()
        self.assertIsInstance(resolve_params(w), ParameterSet)
        self.assertGreaterEqual(len(resolve_params(w)), 284)

    def test_params_excluded_from_world_serialization(self):
        # Regression: params must NOT appear in asdict(world) (keeps snapshots JSON-safe).
        w = _world(max_agents=4)
        d = asdict(w)
        self.assertNotIn("params", d)
        json.dumps(d)  # must not raise

    def test_resolve_params_falls_back_to_default(self):
        class _Bare:
            pass

        self.assertIs(resolve_params(_Bare()), default_params())


class OverridePropagationTests(unittest.TestCase):
    """The decisive rigor check: overriding world.params changes simulation output."""

    def _run(self, params_override=None, years=3, seed=7):
        w = _world(max_agents=10)
        seed_world(w, seed)
        if params_override is not None:
            w.params = resolve_params(w).with_overrides(params_override)
        policies = make_policy_map(w.agents.keys(), mode="simple")
        for _ in range(years):
            step_world(w, policies)
        return w

    def test_emissions_scale_override_changes_co2(self):
        base = self._run()
        scaled = self._run({"EMISSIONS_SCALE": resolve_params(_world()).EMISSIONS_SCALE * 1.5})
        self.assertNotAlmostEqual(base.global_state.co2, scaled.global_state.co2, places=3)

    def test_production_elasticity_override_changes_gdp(self):
        base = self._run()
        tilted = self._run({"ALPHA_CAPITAL": 0.4})
        base_gdp = sum(a.economy.gdp for a in base.agents.values())
        tilted_gdp = sum(a.economy.gdp for a in tilted.agents.values())
        self.assertNotAlmostEqual(base_gdp, tilted_gdp, places=3)

    def test_default_override_is_behaviourally_identity(self):
        # Overriding with the same values must not change anything.
        base = self._run()
        same = self._run({"ALPHA_CAPITAL": resolve_params(_world()).ALPHA_CAPITAL})
        self.assertAlmostEqual(
            sum(a.economy.gdp for a in base.agents.values()),
            sum(a.economy.gdp for a in same.agents.values()),
            places=9,
        )


if __name__ == "__main__":
    unittest.main()
