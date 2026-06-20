"""Tests for the long-window climate-only backtest (T1.3)."""

import json
import unittest

from gim.climate_backtest import (
    SPINUP_START_YEAR,
    best_ecs,
    load_emissions_history,
    load_observations,
    run_climate_backtest,
    sweep_ecs,
)

LEGACY_FIXTURE = "tests/fixtures/historical_backtest_observed.json"


class ObservationsDataTests(unittest.TestCase):
    def test_scored_window_is_1990_2023(self):
        obs = load_observations()
        self.assertEqual(obs.start_year, 1990)
        self.assertEqual(obs.end_year, 2023)
        self.assertEqual(len(obs.years()), 34)

    def test_temperatures_match_legacy_fixture_exactly(self):
        # The 1850-1900 rebasing offset is fixed so 2015-2023 reproduce the legacy
        # economic-backtest observations bit-for-bit; this guards that contract.
        obs = load_observations()
        with open(LEGACY_FIXTURE, "r", encoding="utf-8") as fh:
            legacy = json.load(fh)["temperature_c_preindustrial"]
        for y in range(2015, 2024):
            self.assertAlmostEqual(obs.temperature_c[y], legacy[str(y)], places=9)

    def test_emissions_history_covers_preindustrial_to_present(self):
        hist = load_emissions_history()
        self.assertEqual(min(hist), SPINUP_START_YEAR)
        self.assertGreaterEqual(max(hist), 2023)
        # cumulative fossil+cement CO2 1750-2023 ~ 1800 GtCO2 (~490 GtC) per GCB.
        cum = sum(v for y, v in hist.items() if y <= 2023)
        self.assertTrue(1700 < cum < 1950, cum)


class BacktestRunTests(unittest.TestCase):
    def test_emission_mode_tracks_co2_with_known_landuse_gap(self):
        # Fossil+cement-only forcing under-predicts atmospheric CO2 (no land-use
        # source); the gap is a stable ~10 ppm, not a blow-up.
        res = run_climate_backtest(mode="emission")
        self.assertEqual(set(res.predicted_temperature), set(range(1990, 2024)))
        self.assertLess(res.scores["ppm_rmse"], 12.0)
        self.assertLess(res.scores["temperature_rmse"], 0.4)

    def test_concentration_mode_is_deterministic(self):
        a = run_climate_backtest(mode="concentration")
        b = run_climate_backtest(mode="concentration")
        self.assertEqual(a.predicted_temperature, b.predicted_temperature)

    def test_long_window_identifies_central_ecs_at_physical_heat_capacity(self):
        # The headline T1.3 result: at the physical Geoffroy surface heat capacity
        # (~8) with Geoffroy-baseline ocean exchange (0.7), the 34-year
        # concentration-driven window has a clear interior minimum at ECS=3.0 (the
        # IPCC AR6 central estimate) - i.e. the window *identifies* ECS. (Params are
        # pinned here so the test is independent of the production defaults, which the
        # T1.3b joint recalibration moved to cap=8/oex=1.0.)
        obs = load_observations()
        from gim.climate_backtest import load_emissions_history as _h

        hist = _h()
        rmse = {}
        for e in (2.0, 2.5, 3.0, 3.5, 4.0):
            r = run_climate_backtest(
                obs, ecs=e, mode="concentration",
                params_override={"HEAT_CAP_SURFACE": 8.0, "OCEAN_EXCHANGE": 0.7},
                emissions_history=hist,
            )
            rmse[e] = r.scores["temperature_rmse"]
        # Forced-response fit (variability off): a clear INTERIOR minimum in the AR6
        # central band (2.5-3.0), strictly better than the 2.0 and 4.0 endpoints - i.e.
        # the 34-year window identifies ECS, and not at a boundary.
        best = min(rmse, key=rmse.get)
        self.assertIn(best, (2.5, 3.0))
        self.assertLess(rmse[best], rmse[2.0])
        self.assertLess(rmse[best], rmse[4.0])

    def test_sweep_returns_one_rmse_per_ecs(self):
        pairs = sweep_ecs([2.0, 3.0, 4.0])
        self.assertEqual([p[0] for p in pairs], [2.0, 3.0, 4.0])
        self.assertTrue(all(r > 0 for _, r in pairs))


if __name__ == "__main__":
    unittest.main()
