"""Stressed-scenario re-audit of the threshold-gated risk/geo inputs (F3 / Stage 5).

Guards the honest finding that these inputs are *conditionally* load-bearing (not decorative):
debt_crisis_prone becomes load-bearing under stress, and the audit is deterministic.
"""
import unittest

from gim.stress_audit import build_stressed_world, run_stress_audit


class StressAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scores = run_stress_audit(years=8, max_agents=12)

    def test_stress_injects_active_wars(self):
        world, _ = build_stressed_world(max_agents=12, wars=3)
        n_war = sum(1 for s in world.relations.values()
                    for r in s.values() if getattr(r, "at_war", False))
        self.assertGreaterEqual(n_war, 6)  # 3 dyads, both directions

    def test_debt_crisis_prone_is_conditionally_load_bearing(self):
        # Inert in the calm base audit, but moves outputs once debt stress is on.
        self.assertGreater(self.scores["risk.debt_crisis_prone"]["influence"], 1e-3)

    def test_military_power_uses_relative_probe(self):
        # military_power is a relative (CINC-share) quantity -> single-agent probe.
        self.assertEqual(self.scores["technology.military_power"]["probe"], "single-agent (relative)")

    def test_deterministic(self):
        again = run_stress_audit(years=8, max_agents=12)
        self.assertEqual(self.scores, again)


if __name__ == "__main__":
    unittest.main()
