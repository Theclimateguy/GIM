"""Tests for the Taylor-rule monetary-policy reaction (P4-C)."""

import unittest

from gim.core import calibration_params as cal
from gim.core.economy import compute_effective_interest_rate
from gim.core.world_factory import make_world_from_csv

STATE_CSV = "data/agent_states_operational_2026_calibrated.csv"


def _agent_world():
    w = make_world_from_csv(STATE_CSV, max_agents=4, base_year=2026)
    a = next(iter(w.agents.values()))
    # Neutralise the debt spread so we isolate the Taylor term: low debt/GDP.
    a.economy.public_debt = 0.1 * a.economy.gdp
    return a, w


class TaylorRuleTests(unittest.TestCase):
    def test_neutral_at_target_inflation_and_nairu(self):
        a, w = _agent_world()
        a.economy.inflation = cal.INFLATION_TARGET
        a.economy.unemployment = cal.NAIRU
        self.assertAlmostEqual(compute_effective_interest_rate(a, w), cal.BASE_INTEREST_RATE, places=6)

    def test_high_inflation_raises_rate(self):
        a, w = _agent_world()
        a.economy.unemployment = cal.NAIRU
        a.economy.inflation = cal.INFLATION_TARGET
        low = compute_effective_interest_rate(a, w)
        a.economy.inflation = cal.INFLATION_TARGET + 0.03
        high = compute_effective_interest_rate(a, w)
        self.assertGreater(high, low)
        self.assertAlmostEqual(high - low, cal.TAYLOR_PHI_PI * 0.03, places=6)

    def test_labor_slack_lowers_rate(self):
        a, w = _agent_world()
        a.economy.inflation = cal.INFLATION_TARGET
        a.economy.unemployment = cal.NAIRU
        base = compute_effective_interest_rate(a, w)
        a.economy.unemployment = cal.NAIRU + 0.04  # recession
        self.assertLess(compute_effective_interest_rate(a, w), base)

    def test_deviation_is_capped(self):
        a, w = _agent_world()
        a.economy.unemployment = cal.NAIRU
        a.economy.inflation = cal.INFLATION_TARGET + 1.0  # absurd
        rate = compute_effective_interest_rate(a, w)
        self.assertLessEqual(rate, cal.BASE_INTEREST_RATE + cal.TAYLOR_DEVIATION_CAP + 1e-9)

    def test_channel_disable_restores_constant_base(self):
        a, w = _agent_world()
        a.economy.inflation = cal.INFLATION_TARGET + 0.05
        a.economy.unemployment = cal.NAIRU
        w.global_state._ablation_disabled_channels = {"monetary_policy_feedback"}
        # With the channel disabled the Taylor term vanishes -> just the neutral base rate.
        self.assertAlmostEqual(compute_effective_interest_rate(a, w), cal.BASE_INTEREST_RATE, places=6)


if __name__ == "__main__":
    unittest.main()
