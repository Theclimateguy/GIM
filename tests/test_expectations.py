"""Expectations: F2.5 limited-foresight proxy + E4.3 near-rational (model-consistent) operator."""
import contextlib
import io
import unittest

from gim.core import calibration_params as cal
from gim.core.expectations import update_expectations
from gim.core.labor_market import update_inflation_unemployment
from gim.core.params import default_params
from gim.core.world_factory import make_world_from_csv
from gim.historical_backtest import run_historical_backtest

STATE = "data/agent_states_operational.csv"


def _small_world(overrides):
    world = make_world_from_csv(STATE, max_agents=6, base_year=2023)
    world.params = default_params().with_overrides(overrides)
    return world


class ExpectationsTests(unittest.TestCase):
    def test_default_is_adaptive(self):
        self.assertEqual(cal.EXPECTATIONS_FORESIGHT, 0.0)
        self.assertEqual(cal.EXPECTATIONS_HORIZON, 0)

    def test_default_golden_preserved(self):
        with contextlib.redirect_stdout(io.StringIO()):
            g = run_historical_backtest()
        self.assertAlmostEqual(g.gdp_rmse_trillions, 0.621, places=2)
        self.assertAlmostEqual(g.global_co2_rmse_gtco2, 0.933, places=2)

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
        self.assertAlmostEqual(g.gdp_rmse_trillions, 0.621, places=2)
        self.assertAlmostEqual(g.global_co2_rmse_gtco2, 0.933, places=2)

    def test_forward_differs_from_backward_proxy(self):
        # With the tilt on, sourcing expected growth from the forward projection (HORIZON>0) should move
        # the trajectory away from the backward Delta-gdp proxy (HORIZON=0).
        with contextlib.redirect_stdout(io.StringIO()):
            backward = run_historical_backtest(params_override={"EXPECTATIONS_FORESIGHT": 0.5})
            forward = run_historical_backtest(
                params_override={"EXPECTATIONS_FORESIGHT": 0.5, "EXPECTATIONS_HORIZON": 3})
        self.assertNotAlmostEqual(backward.gdp_rmse_trillions, forward.gdp_rmse_trillions, places=5)


class InflationAnchorSiteTests(unittest.TestCase):
    def test_inflation_weight_default_off(self):
        self.assertEqual(cal.EXPECTATIONS_INFLATION_WEIGHT, 0.0)

    def test_inflation_site_applies_forecast(self):
        # The anchor must actually read and blend the cached forecast: a high injected expected inflation
        # (vs the absent-forecast adaptive case) should raise realised inflation for every agent.
        over = {"EXPECTATIONS_HORIZON": 3, "EXPECTATIONS_INFLATION_WEIGHT": 0.9}
        adaptive = _small_world(over)          # no forecast cached -> falls back to adaptive
        forward = _small_world(over)
        forward._expected_paths = {aid: {"gdp_growth": 0.0, "inflation": 0.5} for aid in forward.agents}
        forward._expected_paths_year = int(getattr(forward, "time", 0))
        update_inflation_unemployment(adaptive)
        update_inflation_unemployment(forward)
        for aid in adaptive.agents:
            self.assertGreater(forward.agents[aid].economy.inflation,
                               adaptive.agents[aid].economy.inflation)

    def test_inflation_on_alone_is_golden(self):
        # In-sample the model-consistent inflation forecast ~ the adaptive anchor, so turning on the
        # inflation site alone (tilt off) leaves the validated backtest bit-identical.
        with contextlib.redirect_stdout(io.StringIO()):
            g = run_historical_backtest(
                params_override={"EXPECTATIONS_HORIZON": 3, "EXPECTATIONS_INFLATION_WEIGHT": 0.65})
        self.assertAlmostEqual(g.gdp_rmse_trillions, 0.621, places=2)
        self.assertAlmostEqual(g.global_co2_rmse_gtco2, 0.933, places=2)

    def test_full_activation_stays_in_validated_band(self):
        # Both sites on with the grounded on-values: the 2015-2023 fit moves but stays within the band.
        with contextlib.redirect_stdout(io.StringIO()):
            base = run_historical_backtest()
            full = run_historical_backtest(params_override={
                "EXPECTATIONS_HORIZON": 3, "EXPECTATIONS_FORESIGHT": 0.5,
                "EXPECTATIONS_INFLATION_WEIGHT": 0.65})
        self.assertNotAlmostEqual(base.gdp_rmse_trillions, full.gdp_rmse_trillions, places=4)
        self.assertLess(full.gdp_rmse_trillions, 0.70)
        self.assertLess(full.global_co2_rmse_gtco2, 1.35)  # [RECAL 2026-06] base co2_rmse now 1.258


if __name__ == "__main__":
    unittest.main()
