"""#19 Returns-to-scale verification: document and bound the DRS vs CRS gap.

The production exponents sum to alpha+beta+gamma = 0.942 (mild decreasing returns to scale).
A naive Cobb-Douglas reading predicts DRS compounds to ~43% lower output over 100 years. This
test demonstrates that prediction is WRONG for GIM: the per-country `_scale_factor` re-anchoring
pins the output LEVEL at the base year, so the exponent SUM has no compounding level effect. The
DRS-vs-CRS gap at 2100 is small and sign-ambiguous (it depends on which factor absorbs the
renormalization to sum=1.0), not a structural bias.
"""

import unittest

from gim.core.policy import make_policy_map
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv
from gim.historical_backtest import DEFAULT_INITIAL_STATE_CSV, DEFAULT_POLICY_MODE


def _global_gdp_path(overrides, start=2015, end=2100):
    world = make_world_from_csv(str(DEFAULT_INITIAL_STATE_CSV))
    if overrides:
        world.params = world.params.with_overrides(overrides)
    policies = make_policy_map(world.agents.keys(), mode=DEFAULT_POLICY_MODE)
    path = {start: sum(a.economy.gdp for a in world.agents.values())}
    for offset in range(1, end - start + 1):
        world = step_world(world, policies, enable_extreme_events=False)
        path[start + offset] = sum(a.economy.gdp for a in world.agents.values())
    return path


class ReturnsToScaleTests(unittest.TestCase):
    def test_base_year_level_independent_of_exponent_sum(self) -> None:
        """The 2015 level is pinned by `_scale_factor` regardless of the exponent sum."""
        drs = _global_gdp_path(None, end=2015)
        crs_gamma = _global_gdp_path({"GAMMA_ENERGY": 0.10}, end=2015)  # sum -> 1.0 via energy
        crs_beta = _global_gdp_path({"BETA_LABOR": 0.658}, end=2015)  # sum -> 1.0 via labour
        self.assertAlmostEqual(drs[2015], crs_gamma[2015], places=6)
        self.assertAlmostEqual(drs[2015], crs_beta[2015], places=6)

    def test_drs_vs_crs_gap_is_small_and_bounded(self) -> None:
        """DRS is not a hidden ~43% bias: the 2100 gap to CRS stays within +/-12%."""
        drs = _global_gdp_path(None)
        crs_gamma = _global_gdp_path({"GAMMA_ENERGY": 0.10})
        crs_beta = _global_gdp_path({"BETA_LABOR": 0.658})
        gap_gamma = crs_gamma[2100] / drs[2100] - 1.0
        gap_beta = crs_beta[2100] / drs[2100] - 1.0
        # Both small (observed ~ -7% and -9%): the renormalization moves 2100 output by < 12% either
        # way -- and which way depends on which factor absorbs it AND on the damage/growth regime, so it
        # is not a systematic DRS bias. (The exact sign is not robust and is deliberately not asserted.)
        self.assertLess(abs(gap_gamma), 0.12)
        self.assertLess(abs(gap_beta), 0.12)
        # Sanity: the naive "43% lower" textbook prediction is nowhere near realised.
        self.assertGreater(crs_gamma[2100] / drs[2100], 0.85)
        self.assertGreater(crs_beta[2100] / drs[2100], 0.85)

    def test_gamma_energy_within_literature_range(self) -> None:
        """Energy share is inside the Koetse et al. (2008) energy-augmented production range."""
        from gim.core import calibration_params as cp

        self.assertGreaterEqual(cp.GAMMA_ENERGY, 0.03)
        self.assertLessEqual(cp.GAMMA_ENERGY, 0.06)


if __name__ == "__main__":
    unittest.main()
