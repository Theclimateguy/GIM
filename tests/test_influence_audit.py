"""Influence audit of the unique cultural layer (F3)."""

import unittest

from gim.influence_audit import (
    culture_perturbations,
    decorative_inputs,
    run_influence_audit,
)


class InfluenceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scores = run_influence_audit(years=10, max_agents=10)

    def test_audit_covers_all_hofstede_dims(self):
        self.assertEqual(len(self.scores), len(culture_perturbations()))

    def test_individualism_is_load_bearing(self):
        # idv feeds inequality sensitivity in the social block -> measurable influence.
        self.assertGreater(self.scores["culture.idv"], 0.0)

    def test_most_hofstede_dims_are_decorative(self):
        # Honest finding: the audit flags the inert dimensions. This guards the finding and
        # will flip (and require attention) if a dimension is later wired into the dynamics.
        dead = set(decorative_inputs(self.scores))
        for d in ("culture.lto", "culture.ind", "culture.traditional_secular"):
            self.assertIn(d, dead, f"{d} expected inert; if wired in, update F3 docs/audit")
        self.assertGreaterEqual(len(dead), 5)

    def test_deterministic(self):
        again = run_influence_audit(years=10, max_agents=10)
        self.assertEqual(self.scores, again)


if __name__ == "__main__":
    unittest.main()
