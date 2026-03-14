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
        self.assertLess(result.gdp_rmse_trillions, 1.35)
        self.assertLess(result.global_co2_rmse_gtco2, 2.20)

        for country_name, baseline_rmse in baseline.country_gdp_rmse_trillions.items():
            self.assertLessEqual(
                result.country_gdp_rmse_trillions[country_name],
                baseline_rmse * 1.10 + 1e-9,
                country_name,
            )


if __name__ == "__main__":
    unittest.main()
