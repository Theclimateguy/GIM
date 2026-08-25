"""#12 Internal temperature variability calibrated to observed forced residuals.

Guards the data-derived sigma/rho: they must stay inside the AR(1) bootstrap CI, the ensemble
spread must match the observed spread, and the deterministic forced fit must be preserved.
"""

import unittest

import numpy as np

from gim.core import calibration_params as cp
from gim.historical_backtest import run_historical_backtest


class TemperatureVariabilityCalibrationTests(unittest.TestCase):
    def test_sigma_within_ar1_bootstrap_ci(self) -> None:
        # 95% CI from calibration/calibrate_variability_ar1.py (observed 1990-2023 forced residuals).
        self.assertGreaterEqual(cp.TEMP_NATURAL_VARIABILITY_SIGMA, 0.074)
        self.assertLessEqual(cp.TEMP_NATURAL_VARIABILITY_SIGMA, 0.120)

    def test_rho_is_weak_not_enso_strong(self) -> None:
        # The forced residuals are near-white; rho must be modest, not the old assumed 0.65.
        self.assertLessEqual(cp.TEMP_NATURAL_VARIABILITY_AR1_RHO, 0.45)
        self.assertGreaterEqual(cp.TEMP_NATURAL_VARIABILITY_AR1_RHO, 0.0)

    def test_ensemble_spread_matches_observed(self) -> None:
        r = run_historical_backtest()
        # pred_std should match obs_std to within 15% (cured under-dispersion).
        ratio = r.temperature_predicted_std_c / r.temperature_observed_std_c
        self.assertGreater(ratio, 0.85)
        self.assertLess(ratio, 1.15)

    def test_forced_mean_fit_preserved(self) -> None:
        r = run_historical_backtest()
        years = range(r.start_year, r.end_year + 1)
        mean_rmse = np.sqrt(
            np.mean(
                [(r.predicted_temperature_c[y] - r.actual_temperature_c[y]) ** 2 for y in years]
            )
        )
        # The ensemble-MEAN forced fit is independent of the noise amplitude (~0.099).
        self.assertLess(mean_rmse, 0.11)


if __name__ == "__main__":
    unittest.main()
