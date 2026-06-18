from __future__ import annotations

import json
from pathlib import Path
import unittest

from gim.calibration_validator import run_sanity_suite, validate_action_shifts
from gim.game_runner import GameRunner
from gim.geo_calibration import OUTCOME_INTERCEPTS, iter_geo_weight_entries
from gim.runtime import load_world
from gim.scenario_compiler import compile_question


REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "baseline_evaluation.json"


class GeoCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.world = load_world()
        cls.runner = GameRunner(cls.world)

    def test_all_geo_weights_within_ci(self) -> None:
        for category, key, subkey, weight in iter_geo_weight_entries():
            with self.subTest(category=category, key=key, subkey=subkey):
                self.assertLessEqual(weight.ci95[0], weight.value)
                self.assertLessEqual(weight.value, weight.ci95[1])

    def test_status_quo_largest_intercept(self) -> None:
        other_values = [
            weight.value
            for key, weight in OUTCOME_INTERCEPTS.items()
            if key != "status_quo"
        ]
        self.assertGreater(OUTCOME_INTERCEPTS["status_quo"].value, max(other_values))

    def test_sanity_suite_runs(self) -> None:
        suite = run_sanity_suite()
        self.assertIsInstance(suite, dict)
        self.assertTrue(suite["pass"])

    def test_game_runner_uses_calibration_weights(self) -> None:
        baseline = json.loads(BASELINE_FIXTURE.read_text())
        scenario = compile_question(
            question="Could sanctions pressure destabilize Saudi Arabia and Turkey in 2026?",
            world=self.world,
            actors=["Saudi Arabia", "Turkey", "United States"],
            template_id="sanctions_spiral",
        )
        evaluation = self.runner.evaluate_scenario(scenario)
        snapshot = {
            "scenario_id": evaluation.scenario.id,
            "dominant_outcomes": evaluation.dominant_outcomes,
            "raw_risk_scores": evaluation.raw_risk_scores,
            "risk_probabilities": evaluation.risk_probabilities,
            "driver_scores": evaluation.driver_scores,
            "criticality_score": evaluation.criticality_score,
            "calibration_score": evaluation.calibration_score,
            "physical_consistency_score": evaluation.physical_consistency_score,
            "crisis_signal_summary": evaluation.crisis_signal_summary,
        }
        self._assert_nested_close(snapshot, baseline)

    def test_action_shift_validator_reports_extremes(self) -> None:
        warnings = validate_action_shifts()
        self.assertTrue(any("targeted_strike" in warning for warning in warnings))
        self.assertTrue(any("maritime_interdiction" in warning for warning in warnings))

    def _assert_nested_close(self, actual, expected, places: int = 12) -> None:
        if isinstance(expected, dict):
            self.assertEqual(set(actual.keys()), set(expected.keys()))
            for key in expected:
                self._assert_nested_close(actual[key], expected[key], places=places)
            return
        if isinstance(expected, list):
            self.assertEqual(len(actual), len(expected))
            for actual_item, expected_item in zip(actual, expected):
                self._assert_nested_close(actual_item, expected_item, places=places)
            return
        if isinstance(expected, float):
            self.assertAlmostEqual(actual, expected, places=places)
            return
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
