"""F2.4 (D4): SSP growth anchoring + GDP-skill report."""
import unittest

from gim.core.params import default_params
from gim.scenario_alignment import (
    SSP_TFP_DRIFT,
    gdp_growth_alignment_report,
    ssp_growth_preset,
)


class GrowthSspTests(unittest.TestCase):
    def test_ssp_preset_returns_tfp_override(self):
        self.assertEqual(ssp_growth_preset("SSP2"), {"TFP_DRIFT": SSP_TFP_DRIFT["SSP2"]})
        self.assertEqual(ssp_growth_preset("SSP3-7.0"), {"TFP_DRIFT": SSP_TFP_DRIFT["SSP3"]})

    def test_unknown_ssp_raises(self):
        with self.assertRaises(KeyError):
            ssp_growth_preset("SSP9")

    def test_default_drift_below_ssp2(self):
        # docs/ECONOMICS_BENCHMARK flags GIM baseline growth as low vs SSP2.
        rep = gdp_growth_alignment_report()
        self.assertTrue(rep["below_ssp2"])
        self.assertAlmostEqual(rep["gim_tfp_drift"], float(default_params().TFP_DRIFT))

    def test_preset_is_applicable_as_override(self):
        # the preset must be a valid numeric override (flows through ParameterSet).
        p = default_params().with_overrides(ssp_growth_preset("SSP2"))
        self.assertAlmostEqual(p.TFP_DRIFT, SSP_TFP_DRIFT["SSP2"])


if __name__ == "__main__":
    unittest.main()
