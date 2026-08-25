"""#13 Beta-convergence slope externally validated against the WB real-PPP cross-section + literature."""

import unittest

from gim.core import calibration_params as cp


class TFPConvergenceValidationTests(unittest.TestCase):
    def test_slope_within_validation_ci(self) -> None:
        # 95% CI [0.0068, 0.022] from calibration/calibrate_tfp_convergence.py (HC1, n=20).
        self.assertGreaterEqual(cp.TFP_CONVERGENCE_SENS, 0.0068)
        self.assertLessEqual(cp.TFP_CONVERGENCE_SENS, 0.022)

    def test_slope_within_literature_band(self) -> None:
        # Cross-section convergence band; below Islam (1995) within-panel ~0.092.
        self.assertGreaterEqual(cp.TFP_CONVERGENCE_SENS, 0.005)
        self.assertLessEqual(cp.TFP_CONVERGENCE_SENS, 0.025)
        self.assertLess(cp.TFP_CONVERGENCE_SENS, 0.092)

    def test_standard_error_documented(self) -> None:
        self.assertGreater(cp.TFP_CONVERGENCE_SE, 0.0)
        self.assertLess(cp.TFP_CONVERGENCE_SE, 0.01)


if __name__ == "__main__":
    unittest.main()
