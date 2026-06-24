"""Expectations: F2.5 limited-foresight proxy + E4.3 near-rational (model-consistent) operator."""
import contextlib
import io
import unittest

from gim.core import calibration_params as cal
from gim.core.expectations import update_expectations
from gim.core.params import default_params
from gim.core.world_factory import make_world_from_csv
from gim.historical_backtest import run_historical_backtest

STATE = "data/agent_states_operational_2026_calibrated.csv"


def _small_world(overrides):
    world = make_world_from_csv(STATE, max_agents=6, base_year=2026)
    world.params = default_params().with_overrides(overrides)
    return world


class ExpectationsTests(unittest.TestCase):
    def test_default_is_adaptive(self):
        self.assertEqual(cal.EXPECTATIONS_FORESIGHT, 0.0)
        self.assertEqual(cal.EXPECTATIONS_HORIZON, 0)

    def test_default_golden_preserved(self):
        with contextlib.redirect_stdout(io.StringIO()):
            g = run_historical_backtest()
        self.assertAlmostEqual(g.gdp_rmse_trillions, 0.590, places=2)
        self.assertAlmostEqual(g.global_co2_rmse_gtco2, 1.146, places=2)

    def test_foresight_changes_trajectory(self):
        with contextlib.redirect_stdout(io.StringIO()):
            base = run_historical_backtest()
            fore = run_historical_backtest(params_override={"EXPECTATIONS_FORESIGHT": 0.5})
        self.assertNotAlmostEqual(base.gdp_rmse_trillions, fore.gdp_rmse_trillions, places=4)


class NearRationalTests(unittest.TestCase):
    def test_operator_caches_per_agent_forecast(self):
        world = _small_world({"EXPECTATIONS_HORIZON": 3})
        update_expectations(world)
        cache = getattr(world, "_expected_paths", None)
        self.assertIsNotNone(cache)
        self.assertEqual(set(cache), set(world.agents))
        for rec in cache.values():
            self.assertIn("gdp_growth", rec)
            self.assertIn("inflation", rec)
            self.assertTrue(-0.5 < rec["gdp_growth"] < 0.5)  # bounded, sane

    def test_recursion_guard_suppresses_operator(self):
        # Inside a projection the guard must make update_expectations a no-op (no nested projection).
        world = _small_world({"EXPECTATIONS_HORIZON": 3})
        world.global_state._in_expectation = True
        update_expectations(world)
        self.assertIsNone(getattr(world, "_expected_paths", None))

    def test_horizon_off_writes_no_state(self):
        world = _small_world({"EXPECTATIONS_HORIZON": 0})
        update_expectations(world)
        self.assertIsNone(getattr(world, "_expected_paths", None))

    def test_operator_alone_is_golden(self):
        # HORIZON>0 with the tilt off (FORESIGHT=0): the operator runs but its forecast is unused, and
        # the event-frozen projection never touches the main RNG/critical fields -> golden bit-identical.
        with contextlib.redirect_stdout(io.StringIO()):
            g = run_historical_backtest(params_override={"EXPECTATIONS_HORIZON": 3})
        self.assertAlmostEqual(g.gdp_rmse_trillions, 0.590, places=2)
        self.assertAlmostEqual(g.global_co2_rmse_gtco2, 1.146, places=2)

    def test_forward_differs_from_backward_proxy(self):
        # With the tilt on, sourcing expected growth from the forward projection (HORIZON>0) should move
        # the trajectory away from the backward Delta-gdp proxy (HORIZON=0).
        with contextlib.redirect_stdout(io.StringIO()):
            backward = run_historical_backtest(params_override={"EXPECTATIONS_FORESIGHT": 0.5})
            forward = run_historical_backtest(
                params_override={"EXPECTATIONS_FORESIGHT": 0.5, "EXPECTATIONS_HORIZON": 3})
        self.assertNotAlmostEqual(backward.gdp_rmse_trillions, forward.gdp_rmse_trillions, places=5)


if __name__ == "__main__":
    unittest.main()
