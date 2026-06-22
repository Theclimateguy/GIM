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

    def test_gim_at_modern_discounting_sits_above_epa_rff_central(self):
        # [E2.4 re-anchor] Post-Phase-4 + headline land-use, GIM's 200-yr SCC at the RFF-SP/EPA
        # near-term-2% scheme is ~$300-350 -- ABOVE the EPA-2023/RFF-SP central (~$190), and this is
        # honest: GIM's damage function is higher (5.4%/3C, cross-validated T1.4, ~2.5x DICE) and
        # land-use adds long-horizon CO2. The earlier "$191 ~= EPA" (F1) was a pre-Phase-4 coincidence;
        # we report the true value rather than detune validated damages to force $190.
        rep = scc_alignment_report(horizons=(200,))
        scc200 = rep["gim_modern_2pct"][200]
        self.assertTrue(250.0 <= scc200 <= 450.0, scc200)
        self.assertGreater(scc200, 190.0)  # above the EPA/RFF central, by design


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
