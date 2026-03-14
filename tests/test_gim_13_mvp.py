from pathlib import Path
import unittest

from gim.__main__ import build_parser
from gim.case_builder import build_case_from_text
from gim.console_app import count_action_combinations, discover_cases
from gim.game_runner import GameRunner
from gim.runtime import default_state_csv, load_world
from gim.scenario_compiler import compile_question, load_game_definition


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = REPO_ROOT / "misc" / "cases" / "maritime_pressure_game.json"


class GIM13MVPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.world = load_world()
        cls.runner = GameRunner(cls.world)

    def test_compile_question_resolves_large_state_actors(self) -> None:
        scenario = compile_question(
            question=(
                "Could Iran trigger a sanctions spiral involving the United States and "
                "Saudi Arabia in 2025?"
            ),
            world=self.world,
        )
        self.assertIn("United States", scenario.actor_names)
        self.assertIn("Saudi Arabia", scenario.actor_names)
        self.assertIn("Iran", scenario.actor_names)
        self.assertEqual(scenario.unresolved_actor_names, [])
        self.assertTrue(scenario.critical_focus)
        self.assertEqual(scenario.base_year, 2023)

    def test_default_runtime_uses_large_primary_state(self) -> None:
        self.assertIn("misc/data/agent_states_operational.csv", default_state_csv())
        self.assertGreaterEqual(len(self.world.agents), 50)
        self.assertIn("USA", self.world.agents)
        self.assertIn("CHN", self.world.agents)
        self.assertIn("IRN", self.world.agents)

    def test_compile_question_detects_trade_war_template(self) -> None:
        scenario = compile_question(
            question="Could a trade war with tariffs and export controls destabilize China and the United States?",
            world=self.world,
        )
        self.assertEqual(scenario.template_id, "trade_war")

    def test_compile_question_detects_cyber_template(self) -> None:
        scenario = compile_question(
            question="Could a cyber attack on infrastructure trigger escalation between Iran and the United States?",
            world=self.world,
        )
        self.assertEqual(scenario.template_id, "cyber_disruption")

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
        self.assertIn("net_crisis_shift", evaluation.crisis_signal_summary)
        self.assertEqual(set(scenario.actor_ids), set(evaluation.crisis_dashboard.agents))

    def test_policy_game_case_runs(self) -> None:
        game = load_game_definition(CASE_PATH, self.world)
        result = self.runner.run_game(game)
        self.assertTrue(result.combinations)
        self.assertIsNotNone(result.best_combination)
        self.assertEqual(len(result.best_combination.actions), len(game.players))
        self.assertIsNotNone(result.baseline_evaluation)
        self.assertIn("net_crisis_shift", result.best_combination.evaluation.crisis_signal_summary)
        self.assertTrue(
            set(player.player_id for player in game.players).issubset(
                set(result.best_combination.evaluation.crisis_delta_by_agent)
            )
        )

    def test_actions_shift_crisis_metrics(self) -> None:
        scenario = compile_question(
            question="Could maritime pressure destabilize Saudi Arabia, Turkey and China in 2026?",
            world=self.world,
            actors=["Saudi Arabia", "Turkey", "China"],
            template_id="maritime_deterrence",
        )
        baseline = self.runner.evaluate_scenario(scenario, selected_actions={})
        escalated = self.runner.evaluate_scenario(
            scenario,
            selected_actions={
                scenario.actor_ids[0]: "maritime_interdiction",
                scenario.actor_ids[1]: "signal_deterrence",
            },
        )
        self.assertAlmostEqual(baseline.crisis_signal_summary["net_crisis_shift"], 0.0, places=6)
        self.assertGreater(escalated.crisis_signal_summary["geopolitical_stress_shift"], 0.0)

    def test_new_economic_and_cyber_actions_shift_model_outputs(self) -> None:
        scenario = compile_question(
            question="Could cyber attacks and a trade war destabilize China and the United States?",
            world=self.world,
            actors=["United States", "China"],
            template_id="trade_war",
        )
        baseline = self.runner.evaluate_scenario(scenario, selected_actions={})
        shifted = self.runner.evaluate_scenario(
            scenario,
            selected_actions={
                scenario.actor_ids[0]: "impose_tariffs",
                scenario.actor_ids[1]: "cyber_disruption_attack",
            },
        )
        self.assertGreater(shifted.crisis_signal_summary["macro_stress_shift"], 0.0)
        self.assertGreater(
            shifted.risk_probabilities["direct_strike_exchange"],
            baseline.risk_probabilities["direct_strike_exchange"],
        )

    def test_console_subcommand_is_registered(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["console"])
        self.assertEqual(args.command, "console")

    def test_question_and_game_support_sim_flags(self) -> None:
        parser = build_parser()
        question_args = parser.parse_args(["question", "--question", "test", "--horizon", "2"])
        game_args = parser.parse_args(
            [
                "game",
                "--case",
                str(CASE_PATH),
                "--horizon",
                "3",
                "--no-sim",
                "--equilibrium",
                "--episodes",
                "12",
                "--background-policy",
                "simple",
            ]
        )
        calibrate_args = parser.parse_args(["calibrate", "--horizon", "3", "--background-policy", "growth"])
        built_args = parser.parse_args(
            [
                "game",
                "--description",
                "China imposes export controls and the United States answers with tariffs.",
            ]
        )
        self.assertEqual(question_args.horizon, 2)
        self.assertFalse(question_args.no_sim)
        self.assertEqual(question_args.background_policy, "compiled-llm")
        self.assertEqual(question_args.llm_refresh, "trigger")
        self.assertEqual(game_args.horizon, 3)
        self.assertTrue(game_args.no_sim)
        self.assertTrue(game_args.equilibrium)
        self.assertEqual(game_args.episodes, 12)
        self.assertEqual(game_args.background_policy, "simple")
        self.assertEqual(calibrate_args.background_policy, "growth")
        self.assertEqual(
            built_args.description,
            "China imposes export controls and the United States answers with tariffs.",
        )

    def test_console_discovers_cases_and_counts_actions(self) -> None:
        cases = discover_cases()
        self.assertTrue(cases)
        game = load_game_definition(CASE_PATH, self.world)
        self.assertEqual(count_action_combinations(game), 256)

    def test_case_builder_fallback_produces_valid_game_definition(self) -> None:
        built = build_case_from_text(
            (
                "China introduces export controls on rare earth metals and the United States "
                "responds with tariffs. Japan is exposed as a bystander."
            ),
            self.world,
            prefer_llm=False,
        )
        self.assertTrue(built.game.players)
        self.assertEqual(built.game.scenario.template_id, "trade_war")
        self.assertIn("China", [player.display_name for player in built.game.players])
        self.assertTrue(all(player.allowed_actions for player in built.game.players))


if __name__ == "__main__":
    unittest.main()
