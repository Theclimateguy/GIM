from __future__ import annotations

import json
from pathlib import Path
import unittest

from gim.core import calibration_params as cal


REPO_ROOT = Path(__file__).resolve().parents[1]
CALIBRATION_ARTIFACT = REPO_ROOT / "misc" / "calibration" / "decarb_rate_calibration.json"


class DecarbCalibrationArtifactTests(unittest.TestCase):
    def test_calibration_artifact_exists_with_expected_shape(self) -> None:
        self.assertTrue(CALIBRATION_ARTIFACT.exists(), CALIBRATION_ARTIFACT)
        raw = json.loads(CALIBRATION_ARTIFACT.read_text(encoding="utf-8"))

        for group in ("global", "oecd", "non_oecd"):
            fit = raw[group]
            self.assertIn("estimate", fit)
            self.assertIn("ci_95", fit)
            self.assertIn("r2", fit)
            self.assertIsInstance(fit["estimate"], float)
            self.assertEqual(len(fit["ci_95"]), 2)
            self.assertIsInstance(fit["ci_95"][0], float)
            self.assertIsInstance(fit["ci_95"][1], float)
            self.assertIsInstance(fit["r2"], float)
            self.assertGreaterEqual(fit["start_year"], 2000)
            self.assertEqual(fit["end_year"], 2023)

        self.assertGreaterEqual(raw["global"]["estimate"], 0.015)
        self.assertLessEqual(raw["global"]["estimate"], 0.030)
        self.assertAlmostEqual(raw["global"]["estimate"], cal.DECARB_RATE_OBSERVED_REFERENCE)
        self.assertAlmostEqual(
            raw["active_rate_backtest"]["active_artifact_rate"],
            cal.DECARB_RATE_STRUCTURAL,
        )
        self.assertAlmostEqual(
            raw["active_rate_backtest"]["recommended_active_rate"],
            cal.DECARB_RATE_STRUCTURAL,
        )


if __name__ == "__main__":
    unittest.main()
