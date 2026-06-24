from pathlib import Path
import unittest

from gim.historical_backtest import (
    DEFAULT_BASELINE_FIXTURE,
    DEFAULT_INITIAL_STATE_CSV,
    DEFAULT_OBSERVED_FIXTURE,
    GDP_BACKTEST_ACTORS,
    format_historical_backtest_result,
    load_historical_backtest_baseline,
    run_historical_backtest,
)


class HistoricalBacktestTests(unittest.TestCase):
    # [E3.1 re-anchor] Headline now uses the objective economic core: calibrated nested-CES
    # production (capital-energy substitution) + cost-minimizing energy demand, with EMISSIONS_SCALE
    # re-derived to 1.03. The objective core IMPROVES the historical fit: GDP RMSE 1.026 -> 0.630 and
    # CO2 RMSE 1.606 -> 1.106 (temperature ~unchanged). Prior Cobb-Douglas golden was 1.026/1.606/0.134.
    # [E3 full-closure base] headline = objective economic core (nested-CES + cost-min energy) PLUS
    # full price closure (resource + capital-market clearing). GDP RMSE 0.630->0.590 (further
    # improvement), CO2 1.106->1.146, temperature ~0.135. Prior Cobb-Douglas golden was 1.026/1.606/0.134.
    # [E4.1] money->price transmission now in the headline (MONEY_INFLATION_PASS=0.027, data-calibrated
    # dynamic-panel pass-through). Golden re-anchored; the move is 4th-decimal (0.590/1.146/0.135
    # unchanged at this precision). See docs/MONEY_PRICES.md.
    GOLDEN = {
        "gdp_rmse_trillions": 0.590,
        "global_co2_rmse_gtco2": 1.146,
        "temperature_rmse_c": 0.135,
    }
    TOLERANCE = 0.01

    def test_backtest_fixtures_exist(self) -> None:
        self.assertTrue(DEFAULT_OBSERVED_FIXTURE.exists(), DEFAULT_OBSERVED_FIXTURE)
        self.assertTrue(DEFAULT_INITIAL_STATE_CSV.exists(), DEFAULT_INITIAL_STATE_CSV)
        self.assertTrue(DEFAULT_BASELINE_FIXTURE.exists(), DEFAULT_BASELINE_FIXTURE)

    def test_historical_backtest_matches_baseline_envelope(self) -> None:
        baseline = load_historical_backtest_baseline()
        result = run_historical_backtest()

        print(format_historical_backtest_result(result))
        self.assertEqual(result.start_year, 2015)
        self.assertEqual(result.end_year, 2023)
        self.assertEqual(set(result.country_gdp_rmse_trillions), set(GDP_BACKTEST_ACTORS))
        self.assertEqual(
            set(result.predicted_gdp_trillions[result.start_year]),
            set(GDP_BACKTEST_ACTORS),
        )

        self.assertLessEqual(result.gdp_rmse_trillions, baseline.gdp_rmse_trillions * 1.05 + 1e-9)
        self.assertLessEqual(
            result.global_co2_rmse_gtco2,
            baseline.global_co2_rmse_gtco2 * 1.10 + 1e-9,
        )
        self.assertLessEqual(result.temperature_rmse_c, baseline.temperature_rmse_c * 1.10 + 1e-9)
        self.assertLess(result.gdp_rmse_trillions, 1.10)
        self.assertLess(result.global_co2_rmse_gtco2, 1.70)
        self.assertLess(result.temperature_rmse_c, 0.15)
        self.assertGreaterEqual(result.temperature_ensemble_size, 8)
        self.assertLess(abs(result.temperature_bias_c), 0.02)
        self.assertGreater(result.temperature_predicted_std_c, 0.08)
        self.assertLess(result.temperature_predicted_std_c, 0.12)

        for country_name, baseline_rmse in baseline.country_gdp_rmse_trillions.items():
            self.assertLessEqual(
                result.country_gdp_rmse_trillions[country_name],
                baseline_rmse * 1.10 + 1e-9,
                country_name,
            )

    def test_historical_backtest_matches_golden_values(self) -> None:
        result = run_historical_backtest()

        self.assertAlmostEqual(
            result.gdp_rmse_trillions,
            self.GOLDEN["gdp_rmse_trillions"],
            delta=self.TOLERANCE,
        )
        self.assertAlmostEqual(
            result.global_co2_rmse_gtco2,
            self.GOLDEN["global_co2_rmse_gtco2"],
            delta=self.TOLERANCE,
        )
        self.assertAlmostEqual(
            result.temperature_rmse_c,
            self.GOLDEN["temperature_rmse_c"],
            delta=self.TOLERANCE,
        )


if __name__ == "__main__":
    unittest.main()
