"""IPCC SSP/RCP alignment + FAIR/MAGICC-style benchmark tests (T2.1 + benchmark)."""

import unittest

from gim.scenario_alignment import (
    AR6_ECS,
    AR6_SSP_WARMING_2100,
    AR6_TCR,
    ar6_consistency_report,
    classify_warming,
    closest_ssp,
    equilibrium_climate_sensitivity,
    transient_climate_response,
)


class EmulatorBenchmarkTests(unittest.TestCase):
    def test_ecs_matches_ar6_best_estimate(self):
        self.assertAlmostEqual(equilibrium_climate_sensitivity(), AR6_ECS[0], places=6)

    def test_tcr_within_ar6_likely_range(self):
        tcr = transient_climate_response()
        self.assertTrue(AR6_TCR[1] <= tcr <= AR6_TCR[2], tcr)
        # and close to the AR6 best estimate (1.8 C)
        self.assertAlmostEqual(tcr, AR6_TCR[0], delta=0.15)

    def test_consistency_report_flags_both_within_ar6(self):
        rep = ar6_consistency_report()
        self.assertTrue(rep["ecs_within_ar6_likely"])
        self.assertTrue(rep["tcr_within_ar6_likely"])


class SSPEnvelopeTests(unittest.TestCase):
    def test_envelopes_are_ordered(self):
        bests = [AR6_SSP_WARMING_2100[s][0] for s in
                 ("SSP1-1.9", "SSP1-2.6", "SSP2-4.5", "SSP3-7.0", "SSP5-8.5")]
        self.assertEqual(bests, sorted(bests))

    def test_classify_warming_buckets(self):
        self.assertIn("SSP1-2.6", classify_warming(2.0))
        self.assertIn("SSP2-4.5", classify_warming(2.7))
        self.assertIn("SSP3-7.0", classify_warming(3.6))

    def test_closest_ssp(self):
        self.assertEqual(closest_ssp(2.7), "SSP2-4.5")
        self.assertEqual(closest_ssp(3.6), "SSP3-7.0")
        # GIM's strongly-decarbonising baseline (~2.0 C at 2100) is closest to SSP1-2.6.
        self.assertEqual(closest_ssp(2.0), "SSP1-2.6")


if __name__ == "__main__":
    unittest.main()
