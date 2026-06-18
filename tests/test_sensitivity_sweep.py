from __future__ import annotations

import unittest

from gim.geo_calibration import collect_geo_weight_paths
from gim.sensitivity_sweep import (
    discriminating_weight_paths,
    outcome_weight_paths,
    run_geo_sensitivity_sweep,
)


class SensitivitySweepTests(unittest.TestCase):
    def test_outcome_weight_paths_are_scoped_to_outcome_layers(self) -> None:
        paths = outcome_weight_paths()
        self.assertTrue(paths)
        self.assertTrue(
            all(path.split(":", 1)[0] in {"outcome_intercept", "outcome_driver", "outcome_link", "tail_risk"} for path in paths)
        )

    def test_sweep_restores_geo_weights_and_returns_report(self) -> None:
        weight_paths = [
            "outcome_intercept:status_quo",
            "outcome_driver:internal_destabilization:debt_stress",
        ]
        original = {path: collect_geo_weight_paths()[path] for path in weight_paths}

        report = run_geo_sensitivity_sweep(
            weight_paths=weight_paths,
            case_ids={"argentina_debt_2023", "norway_stability_2023"},
        )

        self.assertEqual(report.baseline_case_count, 2)
        self.assertEqual(len(report.entries), 2)
        for entry in report.entries:
            with self.subTest(path=entry.path):
                self.assertIn(entry.sensitivity_flag, {"high", "low"})
                self.assertEqual(len(entry.perturbations), 2)
                self.assertGreaterEqual(entry.max_abs_average_score_delta, 0.0)

        restored = collect_geo_weight_paths()
        for path, weight in original.items():
            self.assertEqual(restored[path], weight)

    def test_operational_v2_defaults_to_discriminating_paths_and_flags_high_sensitivity(self) -> None:
        discriminating_paths = discriminating_weight_paths(suite_id="operational_v2")
        report = run_geo_sensitivity_sweep(suite_id="operational_v2")

        self.assertEqual(sorted(entry.path for entry in report.entries), discriminating_paths)
        high_entries = [entry for entry in report.entries if entry.sensitivity_flag == "high"]
        self.assertGreaterEqual(len(high_entries), 6)


if __name__ == "__main__":
    unittest.main()
