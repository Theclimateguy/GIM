"""S5 — geography-aware conflict risk: pure-function unit tests (no shapely/UCDP needed).

The spatial-exposure and AUC-scan logic is tested on a synthetic graph where geography is known to
carry (or not carry) signal, so the test is deterministic and dependency-light.
"""

import unittest

from gim.conflict_geography import auc, blended_auc_scan, spatial_exposure


class ConflictGeographyTests(unittest.TestCase):
    def test_spatial_exposure_is_neighbour_mean(self):
        names = ["A", "B", "C", "D"]
        val = {"A": 1.0, "B": 0.0, "C": 1.0, "D": 0.0}
        adj = {frozenset(("A", "B")), frozenset(("B", "C"))}
        exp = spatial_exposure(names, val, adj)
        self.assertAlmostEqual(exp["A"], 0.0)            # A's only neighbour is B(0)
        self.assertAlmostEqual(exp["B"], 1.0)            # B's neighbours A(1),C(1) -> mean 1
        self.assertAlmostEqual(exp["C"], 0.0)            # C's only neighbour is B(0)

    def test_isolated_node_gets_global_mean(self):
        names = ["A", "B", "C"]
        val = {"A": 0.0, "B": 1.0, "C": 0.5}
        exp = spatial_exposure(names, val, set())        # no edges -> all isolated
        self.assertAlmostEqual(exp["A"], 0.5)            # global mean (0+1+0.5)/3
        self.assertAlmostEqual(exp["C"], 0.5)

    def test_auc_perfect_and_chance(self):
        self.assertAlmostEqual(auc([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0]), 1.0)
        self.assertAlmostEqual(auc([0.5, 0.5, 0.5, 0.5], [1, 0, 1, 0]), 0.5)

    def test_blend_helps_when_neighbours_carry_signal(self):
        # outcome is driven by neighbour exposure, not the base score -> blending must lift AUC
        names = [f"N{i}" for i in range(8)]
        base = [0.5] * 8                                  # base score is uninformative
        labels = [1, 1, 1, 1, 0, 0, 0, 0]
        # build adjacency so each node's neighbours' base-proxy separates the classes
        risk = {n: (1.0 if i < 4 else 0.0) for i, n in enumerate(names)}
        adj = set()
        for i in range(0, 8, 2):
            adj.add(frozenset((names[i], names[i + 1])))
        exposure = spatial_exposure(names, risk, adj)
        best_auc, best_w, base_auc = blended_auc_scan(base, [exposure[n] for n in names], labels)
        self.assertGreaterEqual(best_auc, base_auc)
        self.assertGreater(best_auc, 0.5)

    def test_blend_never_below_baseline(self):
        # pure noise extra -> the scan can always fall back to w=0 (base)
        base = [0.1, 0.9, 0.4, 0.6, 0.3]
        noise = [0.5, 0.5, 0.5, 0.5, 0.5]
        labels = [0, 1, 0, 1, 0]
        best_auc, _, base_auc = blended_auc_scan(base, noise, labels)
        self.assertGreaterEqual(best_auc, base_auc)


if __name__ == "__main__":
    unittest.main()
