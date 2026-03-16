import unittest

from gim.core.contracts import CRITICAL_FIELD_PATHS, CRITICAL_FIELD_REGISTRY
from gim.core.policy import make_policy_map
from gim.core.simulation import step_world
from gim.paths import DEFAULT_STATE_CSV
from gim.runtime import load_world


class TransitionContractTests(unittest.TestCase):
    def test_critical_field_registry_has_expected_paths(self) -> None:
        self.assertEqual(set(CRITICAL_FIELD_PATHS), set(CRITICAL_FIELD_REGISTRY))
        for field in CRITICAL_FIELD_PATHS:
            contract = CRITICAL_FIELD_REGISTRY[field]
            self.assertEqual(contract.field_path, field)
            self.assertEqual(contract.finalization_phase, "reconcile")
            self.assertIn("gim.core.transitions.reconcile", contract.canonical_writer)

    def test_phase_trace_contains_transition_envelope(self) -> None:
        world = load_world(state_csv=str(DEFAULT_STATE_CSV), max_agents=8, state_year=2023)
        policies = make_policy_map(world.agents.keys(), mode="simple")
        phase_trace: dict = {}
        step_world(
            world,
            policies,
            enable_extreme_events=False,
            phase_trace=phase_trace,
        )
        self.assertIn("transition_envelope", phase_trace)
        self.assertIn("critical_field_accounting", phase_trace)
        self.assertIn("critical_write_guard", phase_trace)
        envelope = phase_trace["transition_envelope"]
        self.assertTrue(hasattr(envelope, "baseline"))
        self.assertTrue(hasattr(envelope, "detect"))
        self.assertTrue(hasattr(envelope, "propagate"))
        self.assertTrue(hasattr(envelope, "reconcile"))
        self.assertGreater(len(envelope.reconcile.critical_fields_by_agent), 0)
        sample_agent_id = next(iter(phase_trace["critical_field_accounting"]))
        sample = phase_trace["critical_field_accounting"][sample_agent_id]
        self.assertIn("baseline", sample)
        self.assertIn("channels", sample)
        self.assertIn("reconcile_adjustment", sample)
        self.assertIn("final", sample)
        channels = sample["channels"]
        self.assertIn("sanctions_conflict", channels)
        self.assertIn("policy_trade", channels)
        self.assertIn("climate_macro", channels)
        self.assertIn("social_feedback", channels)
        self.assertIn("net_propagation", channels)
        for field in ("gdp", "capital", "public_debt", "trust_gov", "social_tension"):
            channel_sum = (
                channels["sanctions_conflict"][field]
                + channels["policy_trade"][field]
                + channels["climate_macro"][field]
                + channels["social_feedback"][field]
            )
            self.assertAlmostEqual(channel_sum, channels["net_propagation"][field], places=10)
        guard_summary = phase_trace["critical_write_guard"]
        self.assertIn("mode", guard_summary)
        self.assertIn("record_count", guard_summary)
        self.assertIn("by_module", guard_summary)
        self.assertGreater(guard_summary["record_count"], 0)
        self.assertNotIn("gim/core/institutions.py", guard_summary["by_module"])
        self.assertNotIn("gim/core/social.py", guard_summary["by_module"])
        self.assertNotIn("gim/core/actions.py", guard_summary["by_module"])
        self.assertNotIn("gim/core/economy.py", guard_summary["by_module"])
        self.assertNotIn("gim/core/climate.py", guard_summary["by_module"])
        self.assertNotIn("gim/core/geopolitics.py", guard_summary["by_module"])
        self.assertIn("gim/core/transitions/propagate.py", guard_summary["by_module"])


if __name__ == "__main__":
    unittest.main()
