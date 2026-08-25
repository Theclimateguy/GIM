"""Influence audit of the unique cultural layer (F3).

Post-finalization state: GIM retains 4 Hofstede dimensions. `idv` is load-bearing in the
always-on social block; `pdi/uai/lto` are wired via the switchable CULTURE_SOCIAL_LINKS
channel and are load-bearing only when it is enabled. The 4 inert dimensions
(mas/ind/traditional_secular/survival_self_expression) were removed from the model.
"""

import unittest

from gim.core.core import CulturalState
from gim.influence_audit import (
    culture_perturbations,
    decorative_inputs,
    run_influence_audit,
)

REMOVED_DIMS = ("mas", "ind", "traditional_secular", "survival_self_expression")
RETAINED_DIMS = ("pdi", "idv", "uai", "lto")
WIRED_DIMS = ("culture.pdi", "culture.uai", "culture.lto")


class InfluenceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.off = run_influence_audit(years=10, max_agents=10, culture_links=False)
        cls.on = run_influence_audit(years=10, max_agents=10, culture_links=True)

    def test_inert_dims_removed_from_model(self):
        # The 4 decorative dims no longer exist on the state object.
        fields = set(vars(CulturalState()).keys())
        for d in REMOVED_DIMS:
            self.assertNotIn(d, fields, f"{d} should have been removed from CulturalState")
        for d in RETAINED_DIMS:
            self.assertIn(d, fields)

    def test_audit_covers_retained_dims(self):
        self.assertEqual(len(self.off), len(culture_perturbations()))
        self.assertEqual(set(self.off), {f"culture.{d}" for d in RETAINED_DIMS})

    def test_individualism_is_load_bearing(self):
        # idv feeds inequality sensitivity in the always-on social block (channel-independent).
        self.assertGreater(self.off["culture.idv"], 0.0)
        self.assertGreater(self.on["culture.idv"], 0.0)

    def test_wired_dims_inert_off_loadbearing_on(self):
        # pdi/uai/lto are decorative with the channel OFF, load-bearing with it ON.
        dead_off = set(decorative_inputs(self.off))
        for d in WIRED_DIMS:
            self.assertIn(d, dead_off, f"{d} should be inert when CULTURE_SOCIAL_LINKS is off")
            self.assertGreater(self.on[d], 0.0, f"{d} should be load-bearing when the channel is on")

    def test_deterministic(self):
        again = run_influence_audit(years=10, max_agents=10, culture_links=True)
        self.assertEqual(self.on, again)


if __name__ == "__main__":
    unittest.main()
