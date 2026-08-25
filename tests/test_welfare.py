"""Tests for the welfare module (Phase 3-A)."""

import math
import unittest

from gim.core.params import default_params
from gim.welfare import crra_utility, discounted_welfare, marginal_utility


class CRRATests(unittest.TestCase):
    def test_log_utility_at_eta_one(self):
        self.assertAlmostEqual(crra_utility(math.e, 1.0), 1.0)
        self.assertAlmostEqual(crra_utility(1.0, 1.0), 0.0)

    def test_utility_zero_at_unit_consumption(self):
        for eta in (0.5, 1.45, 2.0):
            self.assertAlmostEqual(crra_utility(1.0, eta), 0.0)

    def test_utility_is_increasing_and_concave(self):
        eta = 1.45
        u1, u2, u3 = (crra_utility(c, eta) for c in (1.0, 2.0, 3.0))
        self.assertLess(u1, u2)
        self.assertLess(u2, u3)
        self.assertGreater(u2 - u1, u3 - u2)  # diminishing marginal utility

    def test_marginal_utility_decreasing(self):
        eta = 1.45
        self.assertGreater(marginal_utility(1.0, eta), marginal_utility(2.0, eta))


class DiscountingTests(unittest.TestCase):
    def test_discounting_reduces_future_weight(self):
        params = default_params()
        cons = [100.0] * 10
        pop = [1.0] * 10
        w = discounted_welfare(cons, pop, params)
        # Undiscounted sum would be 10 * U(100); discounted must be strictly less.
        undiscounted = 10 * crra_utility(100.0, params.ELASTICITY_MARGINAL_UTILITY)
        self.assertLess(w, undiscounted)
        self.assertGreater(w, 0.0)


if __name__ == "__main__":
    unittest.main()
