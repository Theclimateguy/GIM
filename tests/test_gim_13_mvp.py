from pathlib import Path
import unittest

from GIM_13.game_runner import GameRunner
from GIM_13.runtime import load_world
from GIM_13.scenario_compiler import compile_question, load_game_definition


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = REPO_ROOT / "GIM_13" / "cases" / "maritime_pressure_game.json"


class GIM13MVPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.world = load_world()
        cls.runner = GameRunner(cls.world)

    def test_compile_question_keeps_unresolved_tail_risk_actor(self) -> None:
        scenario = compile_question(
            question=(
                "Could Iran trigger a sanctions spiral involving the United States and "
                "Saudi Arabia in 2025?"
            ),
            world=self.world,
        )
        self.assertIn("United States", scenario.actor_names)
        self.assertIn("Saudi Arabia", scenario.actor_names)
        self.assertIn("Iran", scenario.unresolved_actor_names)
        self.assertTrue(scenario.critical_focus)

    def test_scenario_probabilities_sum_to_one(self) -> None:
        scenario = compile_question(
            question=(
                "Could maritime pressure destabilize Saudi Arabia, Turkey and China in 2026?"
            ),
            world=self.world,
            actors=["Saudi Arabia", "Turkey", "China"],
            template_id="maritime_deterrence",
        )
        evaluation = self.runner.evaluate_scenario(scenario)
        self.assertAlmostEqual(sum(evaluation.risk_probabilities.values()), 1.0, places=6)
        self.assertGreaterEqual(evaluation.calibration_score, 0.0)
        self.assertLessEqual(evaluation.physical_consistency_score, 1.0)
        self.assertTrue(evaluation.dominant_outcomes)

    def test_policy_game_case_runs(self) -> None:
        game = load_game_definition(CASE_PATH, self.world)
        result = self.runner.run_game(game)
        self.assertTrue(result.combinations)
        self.assertIsNotNone(result.best_combination)
        self.assertEqual(len(result.best_combination.actions), len(game.players))


if __name__ == "__main__":
    unittest.main()
