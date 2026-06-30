"""E4.2: R&D capital-stock (Jones) growth channel + SSP1-5 anchoring (switchable; default off / SSP2)."""
import contextlib
import io
import unittest

from gim.core import calibration_params as cal
from gim.core.metrics import update_tfp_endogenous
from gim.core.params import default_params
from gim.core.world_factory import make_world_from_csv
from gim.historical_backtest import run_historical_backtest

STATE = "data/agent_states_operational.csv"


def _tfp_after_update(rd_frac, *, stock_form):
    world = make_world_from_csv(STATE, max_agents=6, base_year=2023)
    world.params = default_params().with_overrides({"RD_STOCK_GROWTH": stock_form})
    agent = next(iter(world.agents.values()))
    agent.economy.rd_spending = rd_frac * agent.economy.gdp
    update_tfp_endogenous(agent, world)
    return agent


class GrowthFoundationsTests(unittest.TestCase):
    def test_defaults_are_golden_safe(self):
        self.assertFalse(cal.RD_STOCK_GROWTH)
        self.assertEqual(cal.SSP_SCENARIO, "SSP2")
        # default scenario reproduces the prior single forward drift -> golden + forward unchanged.
        self.assertEqual(cal.SSP_TFP_DRIFT_PRESETS["SSP2"], cal.SSP_FORWARD_TFP_DRIFT)

    def test_default_golden_preserved(self):
        with contextlib.redirect_stdout(io.StringIO()):
            g = run_historical_backtest()
        self.assertAlmostEqual(g.gdp_rmse_trillions, 0.621, places=2)
        self.assertAlmostEqual(g.global_co2_rmse_gtco2, 0.933, places=2)

    def test_ssp_preset_ordering(self):
        p = cal.SSP_TFP_DRIFT_PRESETS
        self.assertGreater(p["SSP5"], p["SSP1"])
        self.assertGreater(p["SSP1"], p["SSP2"])
        self.assertGreater(p["SSP2"], p["SSP4"])
        self.assertGreater(p["SSP4"], p["SSP3"])

    def test_calibrated_values_contract(self):
        # Calibration contract (calibration/growth_foundations_calibration.json + docs/GROWTH_FOUNDATIONS.md).
        # Guards the WB-panel R&D-stock fit and the SSP-pathway-grounded presets against accidental drift.
        self.assertAlmostEqual(cal.TFP_RD_STOCK_SENS, 0.0141, places=4)  # level-matched to the flow form
        self.assertEqual(cal.TFP_RD_STOCK_ELASTICITY, 0.50)
        self.assertEqual(cal.RD_STOCK_DEPRECIATION, 0.15)
        self.assertEqual(cal.SSP_TFP_DRIFT_PRESETS,
                         {"SSP1": 0.020, "SSP2": 0.018, "SSP3": 0.009, "SSP4": 0.015, "SSP5": 0.024})

    def test_rd_stock_accumulates(self):
        agent = _tfp_after_update(0.02, stock_form=True)
        self.assertIsNotNone(getattr(agent.economy, "_rd_stock", None))
        self.assertGreater(agent.economy._rd_stock, 0.0)

    def test_rd_stock_form_differs_from_flow(self):
        flow = _tfp_after_update(0.02, stock_form=False).economy.tfp
        stock = _tfp_after_update(0.02, stock_form=True).economy.tfp
        self.assertNotAlmostEqual(flow, stock, places=6)

    def test_rd_stock_raises_growth_vs_no_rd(self):
        with_rd = _tfp_after_update(0.03, stock_form=True).economy.tfp
        no_rd = _tfp_after_update(0.0, stock_form=True).economy.tfp
        self.assertGreater(with_rd, no_rd)


if __name__ == "__main__":
    unittest.main()
