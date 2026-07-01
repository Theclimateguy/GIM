"""S2 — migration gravity elasticities: engine reproduction + prior anchoring.

GIM's shipped migration engine must behave like a gravity model — unit population-mass elasticity,
positive order-1 income elasticity, positive trade-linkage (proximity) elasticity — and the MIGRATION_*
priors must be sourced. Trade linkage substitutes for the gravity distance term (no distance field).
"""

import unittest

from gim.core.params import default_params
from gim.core.priors import key_priors
from gim.migration_validation import build_migration_world, gravity_elasticities, measure_bilateral_flows

MIGRATION_PRIORS = (
    "MIGRATION_BASE_RATE",
    "MIGRATION_MAX_SHARE",
    "MIGRATION_INCOME_PUSH_W",
    "MIGRATION_CONFLICT_PUSH_W",
)


class S2MigrationGravityTests(unittest.TestCase):
    def test_migration_priors_are_sourced_and_real(self):
        kp = key_priors()
        base = default_params()
        for name in MIGRATION_PRIORS:
            self.assertIn(name, kp, f"{name} missing from priors CSV")
            self.assertTrue(kp[name].source.strip(), f"{name} needs a source citation")
            self.assertIn(name, base, f"{name} is not a real model parameter")
            self.assertAlmostEqual(kp[name].p1, float(base.get(name)), places=6)

    def test_engine_reproduces_gravity_elasticities(self):
        e = gravity_elasticities()
        # canonical gravity mass term: doubling origin population doubles flows
        self.assertAlmostEqual(e["mass_elasticity"], 1.0, delta=0.02)
        # engine is linear in income gap and in trade linkage -> unit elasticity
        self.assertAlmostEqual(e["gap_elasticity"], 1.0, delta=0.02)
        self.assertAlmostEqual(e["linkage_elasticity"], 1.0, delta=0.02)
        # income LEVEL elasticity positive, order ~1 (gravity band ~0.5-1.5)
        self.assertTrue(0.5 <= e["income_level_elasticity"] <= 2.0, e["income_level_elasticity"])

    def test_richer_destination_attracts_more_migrants(self):
        # monotonicity: with equal linkage, the richer destination receives the larger flow
        world, dest_ids = build_migration_world(
            dest_incomes=[1.5 * 20_000.0, 4.0 * 20_000.0],
            dest_linkages=[0.5, 0.5],
            baseline=20_000.0,
        )
        flows = measure_bilateral_flows(world, dest_ids)
        self.assertGreater(flows[dest_ids[1]], flows[dest_ids[0]])

    def test_stronger_linkage_attracts_more_migrants(self):
        # monotonicity: with equal income, the better-linked destination receives the larger flow
        world, dest_ids = build_migration_world(
            dest_incomes=[3.0 * 20_000.0, 3.0 * 20_000.0],
            dest_linkages=[0.2, 0.8],
            baseline=20_000.0,
        )
        flows = measure_bilateral_flows(world, dest_ids)
        self.assertGreater(flows[dest_ids[1]], flows[dest_ids[0]])


if __name__ == "__main__":
    unittest.main()
