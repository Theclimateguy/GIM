"""#15 Logistic demographic transition (Lutz 2001 / Preston 1975), switchable.

Guards: default OFF (golden-safe), monotone transition shape, high-income birth plateau (no clamp
artifact), WPP-consistent crude rates, world natural increase ~ UN WPP, and a working switched-on run.
"""

import unittest

from gim.core import calibration_params as cp
from gim.core.policy import make_policy_map
from gim.core.simulation import step_world
from gim.core.social import logistic_birth_rate, preston_death_rate
from gim.core.world_factory import make_world_from_csv
from gim.historical_backtest import DEFAULT_INITIAL_STATE_CSV, DEFAULT_POLICY_MODE


class DemographicTransitionTests(unittest.TestCase):
    def test_default_off_is_golden_safe(self) -> None:
        self.assertFalse(cp.DEMOGRAPHIC_LOGISTIC)

    def test_birth_rate_monotone_and_plateaus(self) -> None:
        rates = [logistic_birth_rate(y, cp) for y in (1000, 5000, 15000, 40000, 80000)]
        for a, b in zip(rates, rates[1:]):
            self.assertGreater(a, b)  # strictly falling with income
        # low-income high (~40/1000), high-income plateau near CBR_LOGISTIC_MIN.
        self.assertGreater(rates[0], 0.038)
        self.assertLess(rates[-1], 0.011)
        self.assertGreaterEqual(rates[-1], cp.CBR_LOGISTIC_MIN)

    def test_death_rate_falls_with_income(self) -> None:
        rates = [preston_death_rate(y, cp) for y in (1500, 10000, 60000)]
        self.assertGreater(rates[0], rates[1])
        self.assertGreater(rates[1], rates[2])
        self.assertGreaterEqual(rates[-1], cp.CDR_LOGISTIC_MIN)

    def test_world_natural_increase_matches_wpp(self) -> None:
        # At world-mean income ~$12k, natural increase should be ~0.95%/yr (UN WPP 2015-2023).
        ni = (logistic_birth_rate(12000, cp) - preston_death_rate(12000, cp)) * 100.0
        self.assertGreater(ni, 0.7)
        self.assertLess(ni, 1.2)

    def test_switched_on_run_is_stable(self) -> None:
        world = make_world_from_csv(str(DEFAULT_INITIAL_STATE_CSV))
        world.params = world.params.with_overrides({"DEMOGRAPHIC_LOGISTIC": True})
        policies = make_policy_map(world.agents.keys(), mode=DEFAULT_POLICY_MODE)
        pop0 = sum(a.economy.population for a in world.agents.values())
        for _ in range(10):
            world = step_world(world, policies, enable_extreme_events=False)
        pop1 = sum(a.economy.population for a in world.agents.values())
        # Population grows but stays bounded and positive (no clamp blow-up).
        self.assertGreater(pop1, pop0)
        self.assertLess(pop1 / pop0, 1.3)


if __name__ == "__main__":
    unittest.main()
