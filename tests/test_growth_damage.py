"""Tests for the switchable growth-effect climate damage channel (F4)."""

import unittest

from gim.core import calibration_params as cal
from gim.core.metrics import update_tfp_endogenous
from gim.core.params import build_params
from gim.core.policy import make_policy_map
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv

STATE_CSV = "data/agent_states_operational.csv"


class GrowthDamageTests(unittest.TestCase):
    def test_default_is_off(self):
        self.assertEqual(cal.GROWTH_DAMAGE_TFP_COEFF, 0.0)

    def test_warming_lowers_tfp_growth_when_enabled(self):
        # Same agent/world, two coefficients: with the growth-effect on and warming above
        # baseline, the realised TFP must be lower than with it off.
        def tfp_after(coeff, temp):
            w = make_world_from_csv(STATE_CSV, max_agents=2, base_year=2023)
            w.params = build_params().with_overrides({"GROWTH_DAMAGE_TFP_COEFF": coeff})
            w.global_state.temperature_global = temp
            a = next(iter(w.agents.values()))
            a.economy.tfp = 1.0
            update_tfp_endogenous(a, w)
            return a.economy.tfp

        warm = 3.0  # well above the 2023 baseline
        self.assertLess(tfp_after(0.001, warm), tfp_after(0.0, warm))

    def test_no_drag_at_or_below_baseline(self):
        # At the 2023 baseline temperature there is no growth drag even when enabled.
        from gim.core.core import TGLOBAL_2023_C

        def tfp_after(coeff):
            w = make_world_from_csv(STATE_CSV, max_agents=2, base_year=2023)
            w.params = build_params().with_overrides({"GROWTH_DAMAGE_TFP_COEFF": coeff})
            w.global_state.temperature_global = TGLOBAL_2023_C
            a = next(iter(w.agents.values()))
            a.economy.tfp = 1.0
            update_tfp_endogenous(a, w)
            return a.economy.tfp

        self.assertAlmostEqual(tfp_after(0.001), tfp_after(0.0), places=12)

    def test_enabled_channel_lowers_longrun_gdp(self):
        def world_gdp(coeff, years=30):
            w = make_world_from_csv(STATE_CSV, max_agents=8, base_year=2023)
            w.params = build_params().with_overrides({"GROWTH_DAMAGE_TFP_COEFF": coeff})
            pol = make_policy_map(w.agents.keys(), mode="simple")
            for _ in range(years):
                step_world(w, pol)
            return sum(a.economy.gdp for a in w.agents.values())

        self.assertLess(world_gdp(0.001), world_gdp(0.0))


if __name__ == "__main__":
    unittest.main()
