from copy import deepcopy
from pathlib import Path
import unittest

from GIM_13.game_runner import ACTION_RISK_SHIFTS
from GIM_13.runtime import load_world
from GIM_13.scenario_compiler import compile_question, load_game_definition
from GIM_13.sim_bridge import SimBridge


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = REPO_ROOT / "misc" / "cases" / "maritime_pressure_game.json"


class SimBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.world = load_world()
        cls.bridge = SimBridge()

    def test_action_mapping_covers_all_static_actions(self) -> None:
        self.assertEqual(set(ACTION_RISK_SHIFTS), set(self.bridge.ACTION_TO_POLICY))
        self.assertEqual(self.bridge.unmapped_actions(), [])

    def test_build_policy_map_raises_for_unmapped_action_label(self) -> None:
        game = load_game_definition(CASE_PATH, self.world)
        broken_game = deepcopy(game)
        broken_game.players[0].allowed_actions = ["unknown_action"]
        with self.assertRaises(ValueError):
            self.bridge.build_policy_map(
                self.world,
                broken_game,
                default_mode="simple",
                selected_actions={broken_game.players[0].player_id: "unknown_action"},
            )

    def test_simulated_question_scores_terminal_state(self) -> None:
        scenario = compile_question(
            question="Will Red Sea tensions escalate for Saudi Arabia, Turkey and China?",
            world=self.world,
            actors=["Saudi Arabia", "Turkey", "China"],
            template_id="maritime_deterrence",
        )
        evaluation, trajectory = self.bridge.evaluate_scenario(
            self.world,
            scenario,
            n_years=1,
            default_mode="simple",
        )
        self.assertEqual(len(trajectory), 2)
        self.assertIn("net_crisis_shift", evaluation.crisis_signal_summary)
        self.assertTrue(
            any("terminal state" in note.lower() for note in evaluation.consistency_notes)
        )

    def test_simulated_game_populates_trajectory(self) -> None:
        game = load_game_definition(CASE_PATH, self.world)
        result = self.bridge.run_game(
            self.world,
            game,
            n_years=1,
            default_mode="simple",
        )
        self.assertTrue(result.combinations)
        self.assertIsNotNone(result.trajectory)
        self.assertIsNotNone(result.baseline_trajectory)
        self.assertEqual(len(result.trajectory), 2)
        self.assertEqual(len(result.baseline_trajectory), 2)


if __name__ == "__main__":
    unittest.main()
