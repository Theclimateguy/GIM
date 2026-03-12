from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from GIM_13.__main__ import build_parser
from GIM_13.dashboard import DashboardConfig, DashboardRenderer, write_dashboard_artifacts
from GIM_13.game_runner import GameRunner
from GIM_13.runtime import load_world
from GIM_13.scenario_compiler import compile_question, load_game_definition
from GIM_13.sim_bridge import SimBridge


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = REPO_ROOT / "GIM_13" / "cases" / "maritime_pressure_game.json"


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.world = load_world()
        cls.runner = GameRunner(cls.world)
        cls.bridge = SimBridge()

    def test_parser_supports_dashboard_flags_and_positional_question(self) -> None:
        parser = build_parser()
        question_args = parser.parse_args(
            [
                "question",
                "Will Red Sea tensions escalate?",
                "--dashboard",
                "--dashboard-output",
                "brief.html",
            ]
        )
        game_args = parser.parse_args(
            [
                "game",
                "--case",
                str(CASE_PATH),
                "--dashboard",
                "--json",
            ]
        )
        self.assertEqual(question_args.question_text, "Will Red Sea tensions escalate?")
        self.assertTrue(question_args.dashboard)
        self.assertEqual(question_args.dashboard_output, "brief.html")
        self.assertTrue(game_args.dashboard)
        self.assertTrue(game_args.json_output)

    def test_static_question_dashboard_writes_html_and_json(self) -> None:
        scenario = compile_question(
            question="Will Red Sea tensions escalate?",
            world=self.world,
            actors=["Saudi Arabia", "Turkey", "China"],
            template_id="maritime_deterrence",
        )
        evaluation = self.runner.evaluate_scenario(scenario)

        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "dashboard.html"
            written = write_dashboard_artifacts(
                renderer=DashboardRenderer(),
                evaluation=evaluation,
                game_result=None,
                trajectory=[self.world],
                scenario_def=scenario,
                config=DashboardConfig(
                    output_path=str(output_path),
                    show_trajectory=False,
                ),
                save_json=True,
            )

            html = output_path.read_text(encoding="utf-8")
            self.assertIn("Outcome Distribution", html)
            self.assertIn("World State Snapshot", html)
            self.assertNotIn("Trajectory Dynamics", html)
            self.assertIn("Decision Brief", html)
            self.assertIn("Key drivers", html)
            self.assertTrue(Path(written["json"]).exists())

    def test_sim_question_dashboard_includes_trajectory_block(self) -> None:
        scenario = compile_question(
            question="Will Red Sea tensions escalate?",
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

        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "dashboard.html"
            write_dashboard_artifacts(
                renderer=DashboardRenderer(),
                evaluation=evaluation,
                game_result=None,
                trajectory=trajectory,
                scenario_def=scenario,
                config=DashboardConfig(
                    output_path=str(output_path),
                    show_trajectory=True,
                    execution_label="sim",
                    policy_mode_label="simple",
                    horizon_years=1,
                ),
                save_json=False,
            )

            html = output_path.read_text(encoding="utf-8")
            self.assertIn("Trajectory Dynamics", html)
            self.assertIn("Decision Brief", html)
            self.assertIn("Trajectory shift", html)
            self.assertIn("Model terms", html)

    def test_game_dashboard_includes_strategy_ranking(self) -> None:
        game = load_game_definition(CASE_PATH, self.world)
        result = self.runner.run_game(game)

        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "dashboard.html"
            write_dashboard_artifacts(
                renderer=DashboardRenderer(),
                evaluation=result.best_combination.evaluation,
                game_result=result,
                trajectory=[self.world],
                scenario_def=game.scenario,
                config=DashboardConfig(
                    output_path=str(output_path),
                    show_trajectory=False,
                    show_game_results=True,
                ),
                save_json=False,
            )

            html = output_path.read_text(encoding="utf-8")
            self.assertIn("Strategy ranking", html)
            self.assertIn("Decision Brief", html)
            self.assertIn("Orchestrator highlights", html)
            self.assertIn("Policy Game Results and Orchestrator Highlights", html)


if __name__ == "__main__":
    unittest.main()
