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
    GOLDEN = {
        "gdp_rmse_trillions": 1.053,
        "global_co2_rmse_gtco2": 1.630,
        "temperature_rmse_c": 0.136,
    }
    TOLERANCE = 0.005

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
