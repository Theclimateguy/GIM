"""Tests for the objectivity / modern-benchmark-alignment layer (F1)."""

import unittest

from gim.benchmark_alignment import (
    MODERN_ETA,
    MODERN_RHO,
    MODERN_SCC_BENCHMARKS,
    backtest_skill_report,
    gim_scc_at_discounting,
    scc_alignment_report,
)


class BenchmarkTableTests(unittest.TestCase):
    def test_modern_benchmarks_present_and_sane(self):
        by = {b.name: b.value for b in MODERN_SCC_BENCHMARKS}
        self.assertAlmostEqual(by["EPA-2023"], 190.0, delta=1.0)
        self.assertAlmostEqual(by["RFF-SP / GIVE"], 185.0, delta=1.0)
        # Lower discount -> higher SCC (1.5% > 2% > 2.5%).
        self.assertGreater(by["EPA-2023 (1.5%)"], by["EPA-2023"])
        self.assertGreater(by["EPA-2023"], by["EPA-2023 (2.5%)"])


class SCCAlignmentTests(unittest.TestCase):
    def test_lower_discount_raises_scc(self):
        from gim.core.params import build_params

        p = build_params()
        native = gim_scc_at_discounting(p.PURE_TIME_PREFERENCE, p.ELASTICITY_MARGINAL_UTILITY,
                                        horizons=(200,))
        modern = gim_scc_at_discounting(MODERN_RHO, MODERN_ETA, horizons=(200,))
        self.assertGreater(modern[200], native[200])

    def test_gim_at_modern_discounting_in_modern_consensus_band(self):
        # [E3] GIM's 200-yr SCC at the RFF-SP/EPA near-term-2% scheme is ~$140 with the objective
        # economic core (nested-CES + price/balance closure + SSP-anchored forward growth) -- within
        # the broad modern consensus range, a little below the EPA-2023/RFF-SP central (~$190).
        # The SCC is genuinely sensitive to the forward economic structure (it has ranged ~$140-380
        # across the economic-core variants); we report the headline value and document the sensitivity
        # rather than tune to a target. (See docs/climate/CLIMATE_BENCHMARKS.md.)
        rep = scc_alignment_report(horizons=(200,))
        scc200 = rep["gim_modern_2pct"][200]
        self.assertTrue(80.0 <= scc200 <= 400.0, scc200)


class SkillReportTests(unittest.TestCase):
    def test_skill_report_structure_and_temperature_beats_naive(self):
        rep = backtest_skill_report()
        self.assertEqual(set(rep), {"global_co2_gtco2", "temperature_c", "world_gdp_trillions"})
        for s in rep.values():
            self.assertIn("skill_vs_persistence", s)
        # GIM beats the naive persistence baseline on temperature and world GDP.
        self.assertGreater(rep["temperature_c"]["skill_vs_persistence"], 0.0)
        self.assertGreater(rep["world_gdp_trillions"]["skill_vs_persistence"], 0.0)


if __name__ == "__main__":
    unittest.main()
