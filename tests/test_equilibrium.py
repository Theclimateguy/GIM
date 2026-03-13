from pathlib import Path
import unittest

from GIM_13.__main__ import build_parser
from GIM_13.explanations import format_equilibrium_result
from GIM_13.game_theory.equilibrium_runner import run_equilibrium_search
from GIM_13.game_theory.welfare import compute_trust_weights
from GIM_13.game_runner import GameRunner
from GIM_13.runtime import load_world
from GIM_13.scenario_compiler import load_game_definition


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = REPO_ROOT / "misc" / "cases" / "maritime_pressure_game.json"


class EquilibriumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.world = load_world()
        cls.runner = GameRunner(cls.world)
        cls.game = load_game_definition(CASE_PATH, cls.world)

    def test_parser_supports_equilibrium_flags_on_game(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "game",
                "--case",
                str(CASE_PATH),
                "--equilibrium",
                "--max-combinations",
                "128",
                "--episodes",
                "12",
                "--threshold",
                "0.05",
                "--trust-alpha",
                "0.7",
            ]
        )
        self.assertEqual(args.command, "game")
        self.assertTrue(args.equilibrium)
        self.assertEqual(args.episodes, 12)
        self.assertEqual(args.max_combinations, 128)
        self.assertAlmostEqual(args.threshold, 0.05)
        self.assertAlmostEqual(args.trust_alpha, 0.7)

    def test_trust_weights_are_normalized_to_player_count(self) -> None:
        weights = compute_trust_weights(self.game, self.world, alpha=0.5)
        self.assertEqual(set(weights), {player.player_id for player in self.game.players})
        self.assertAlmostEqual(sum(weights.values()), len(self.game.players), places=6)

    def test_equilibrium_search_returns_ce_and_regret_metrics(self) -> None:
        result = run_equilibrium_search(
            runner=self.runner,
            game=self.game,
            world=self.world,
            max_episodes=12,
            convergence_threshold=0.01,
            max_combinations=256,
            exploration_eps=0.0,
            trust_alpha=0.5,
        )

        self.assertGreaterEqual(result.episodes, 1)
        self.assertEqual(set(result.mean_external_regret), {player.player_id for player in self.game.players})
        self.assertTrue(all(value >= 0.0 for value in result.mean_external_regret.values()))
        self.assertTrue(result.correlated_equilibrium.is_feasible)
        self.assertEqual(result.correlated_equilibrium.solver_status, "optimal")
        self.assertEqual(set(result.recommended_profile), {player.player_id for player in self.game.players})
        self.assertIsNotNone(result.welfare)
        self.assertIsNotNone(result.price_of_anarchy)
        self.assertTrue(result.ccE_empirical)
        self.assertAlmostEqual(result.trust_alpha, 0.5)
        self.assertIn("standard correlated-equilibrium incentive constraints", result.correlated_equilibrium.objective_description)

    def test_format_equilibrium_result_includes_key_sections(self) -> None:
        result = run_equilibrium_search(
            runner=self.runner,
            game=self.game,
            world=self.world,
            max_episodes=6,
            convergence_threshold=0.01,
            exploration_eps=0.0,
            trust_alpha=0.0,
        )
        text = format_equilibrium_result(result)
        self.assertIn("Mean external regret", text)
        self.assertIn("Recommended profile", text)
        self.assertIn("Top CE support", text)
        self.assertIn("Welfare diagnostics", text)
        self.assertIn("Normative CE objective", text)

    def test_equilibrium_warns_when_stage_game_is_truncated(self) -> None:
        stage_game = self.runner.run_game(self.game, max_combinations=8)
        self.assertTrue(stage_game.truncated_action_space)
        result = run_equilibrium_search(
            runner=self.runner,
            game=self.game,
            world=self.world,
            max_episodes=4,
            max_combinations=8,
            exploration_eps=0.0,
            stage_game=stage_game,
        )
        self.assertTrue(result.warnings)
        self.assertIn("truncated stage game", result.warnings[0])


if __name__ == "__main__":
    unittest.main()
