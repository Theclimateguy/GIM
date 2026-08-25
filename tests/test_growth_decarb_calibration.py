"""The development-structured engine terms must stay bound to their World Bank calibration.

Both TFP conditional convergence and development-dependent decarbonisation are fit in
calibration/growth_decarb_calibration.py from committed World Bank data; the engine constants in
gim.core.calibration_params must equal those fits (recompute via the script if the data changes).
"""

import json
import unittest
from pathlib import Path

from gim.core import calibration_params as cal

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = REPO_ROOT / "calibration" / "growth_decarb_calibration.json"
WB_CSV = REPO_ROOT / "data" / "worldbank_growth_decarb_2015_2023.csv"


class GrowthDecarbCalibrationTests(unittest.TestCase):
    def test_inputs_exist(self) -> None:
        self.assertTrue(ARTIFACT.exists(), ARTIFACT)
        self.assertTrue(WB_CSV.exists(), WB_CSV)

    def test_constants_match_the_fit(self) -> None:
        raw = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        conv = raw["tfp_convergence"]
        dec = raw["development_decarb"]
        # TFP convergence slope -> TFP_CONVERGENCE_SENS
        self.assertAlmostEqual(cal.TFP_CONVERGENCE_SENS, round(conv["slope"], 4), places=4)
        # Development-decarb base/slope -> DECARB_DEV_BASE / DECARB_DEV_SLOPE
        self.assertAlmostEqual(cal.DECARB_DEV_BASE, round(dec["base"], 4), places=4)
        self.assertAlmostEqual(cal.DECARB_DEV_SLOPE, round(dec["slope"], 4), places=4)

    def test_fits_have_the_expected_sign_and_shape(self) -> None:
        raw = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        # poorer countries catch up faster: positive convergence slope on the log gap.
        self.assertGreater(raw["tfp_convergence"]["slope"], 0.0)
        # richer countries decarbonise faster: positive slope on ln(gdp_pc).
        self.assertGreater(raw["development_decarb"]["slope"], 0.0)
        self.assertEqual(raw["tfp_convergence"]["n"], 20)
        self.assertEqual(raw["development_decarb"]["n"], 20)


if __name__ == "__main__":
    unittest.main()
