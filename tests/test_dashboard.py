from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from gim.__main__ import build_parser
from gim.case_builder import build_case_from_text
from gim.dashboard import DashboardConfig, DashboardRenderer, write_dashboard_artifacts
from gim.game_theory.equilibrium_runner import run_equilibrium_search
from gim.game_runner import GameRunner
from gim.runtime import load_world
from gim.scenario_compiler import compile_question, load_game_definition
from gim.sim_bridge import SimBridge


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = REPO_ROOT / "misc" / "cases" / "maritime_pressure_game.json"


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
                equilibrium_result=None,
                trajectory=[self.world],
                scenario_def=scenario,
                config=DashboardConfig(
                    output_path=str(output_path),
                    show_trajectory=False,
                    prefer_llm_interpretation=False,
                ),
                save_json=True,
            )

            html = output_path.read_text(encoding="utf-8")
            self.assertIn("Outcome Distribution", html)
            self.assertIn("World State Snapshot", html)
            self.assertNotIn("Trajectory Dynamics", html)
            self.assertIn("Decision Brief", html)
            self.assertIn("Decision-Maker Interpretation", html)
            self.assertIn("Key drivers", html)
            self.assertIn('aria-label="Criticality gauge"', html)
            self.assertIn(">0.0<", html)
            self.assertIn(">1.0<", html)
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
                equilibrium_result=None,
                trajectory=trajectory,
                scenario_def=scenario,
                config=DashboardConfig(
                    output_path=str(output_path),
                    show_trajectory=True,
                    execution_label="sim",
                    policy_mode_label="simple",
                    horizon_years=1,
                    prefer_llm_interpretation=False,
                ),
                save_json=False,
            )

            html = output_path.read_text(encoding="utf-8")
            self.assertIn("Trajectory Dynamics", html)
            self.assertIn("Decision Brief", html)
            self.assertIn("Decision-Maker Interpretation", html)
            self.assertIn("Trajectory shift", html)
            self.assertIn("Model terms", html)

    def test_dashboard_year_metadata_uses_snapshot_and_display_year(self) -> None:
        world = load_world(state_year=2026)
        scenario = compile_question(
            question="Oil shock in 2028",
            world=world,
            base_year=2028,
            horizon_months=18,
            actors=["United States", "China", "Germany"],
        )
        evaluation, trajectory = self.bridge.evaluate_scenario(
            world,
            scenario,
            n_years=1,
            default_mode="simple",
        )

        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "dashboard_years.html"
            write_dashboard_artifacts(
                renderer=DashboardRenderer(),
                evaluation=evaluation,
                game_result=None,
                equilibrium_result=None,
                trajectory=trajectory,
                scenario_def=scenario,
                config=DashboardConfig(
                    output_path=str(output_path),
                    show_trajectory=True,
                    execution_label="sim",
                    policy_mode_label="simple",
                    horizon_years=1,
                    prefer_llm_interpretation=False,
                ),
                save_json=False,
            )

            html = output_path.read_text(encoding="utf-8")
            self.assertIn("Data snapshot", html)
            self.assertIn(">2026<", html)
            self.assertIn("Display year: 2028", html)
            self.assertIn("1 years (2028-&gt;2029)", html)
            self.assertNotIn("1 years (2026-&gt;2027)", html)

    def test_game_dashboard_includes_strategy_ranking(self) -> None:
        game = load_game_definition(CASE_PATH, self.world)
        result = self.runner.run_game(game)
        equilibrium_result = run_equilibrium_search(
            runner=self.runner,
            game=game,
            world=self.world,
            max_episodes=6,
            exploration_eps=0.0,
            stage_game=result,
        )

        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "dashboard.html"
            write_dashboard_artifacts(
                renderer=DashboardRenderer(),
                evaluation=result.best_combination.evaluation,
                game_result=result,
                equilibrium_result=equilibrium_result,
                trajectory=[self.world],
                scenario_def=game.scenario,
                config=DashboardConfig(
                    output_path=str(output_path),
                    show_trajectory=False,
                    show_game_results=True,
                    prefer_llm_interpretation=False,
                ),
                save_json=False,
            )

            html = output_path.read_text(encoding="utf-8")
            self.assertIn("Strategy ranking", html)
            self.assertIn("Decision Brief", html)
            self.assertIn("Decision-Maker Interpretation", html)
            self.assertIn("Orchestrator highlights", html)
            self.assertIn("Policy Game Results and Orchestrator Highlights", html)
            self.assertIn("Equilibrium diagnostics", html)
            self.assertIn("Mean external regret", html)

    def test_dashboard_renders_for_builder_generated_game(self) -> None:
        built = build_case_from_text(
            (
                "China introduces export controls on critical minerals and the United States responds "
                "with tariffs while Japan stays exposed as a bystander."
            ),
            self.world,
            prefer_llm=False,
        )
        result = self.runner.run_game(built.game)

        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "builder_dashboard.html"
            write_dashboard_artifacts(
                renderer=DashboardRenderer(),
                evaluation=result.best_combination.evaluation,
                game_result=result,
                equilibrium_result=None,
                trajectory=[self.world],
                scenario_def=built.game.scenario,
                config=DashboardConfig(
                    output_path=str(output_path),
                    show_trajectory=False,
                    show_game_results=True,
                    prefer_llm_interpretation=False,
                ),
                save_json=False,
            )

            html = output_path.read_text(encoding="utf-8")
            self.assertIn("Decision Brief", html)
            self.assertIn("Strategy ranking", html)
            self.assertIn("China", html)

    def test_dashboard_renders_interpretive_summary_as_multiple_html_paragraphs(self) -> None:
        world = load_world(state_csv=str(REPO_ROOT / "data" / "agent_states_operational.csv"))
        scenario = compile_question(
            question="Will war start in Iran?",
            world=world,
            actors=["Iran"],
            horizon_months=36,
        )
        evaluation = GameRunner(world).evaluate_scenario(scenario)

        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "dashboard.html"
            write_dashboard_artifacts(
                renderer=DashboardRenderer(),
                evaluation=evaluation,
                game_result=None,
                equilibrium_result=None,
                trajectory=[world],
                scenario_def=scenario,
                config=DashboardConfig(
                    output_path=str(output_path),
                    show_trajectory=False,
                    prefer_llm_interpretation=False,
                ),
                save_json=False,
            )

            html = output_path.read_text(encoding="utf-8")
            self.assertIn("<p>The model does not make direct war in Iran the base case", html)
            self.assertIn("<p>The quantitative picture is being driven mainly", html)
            self.assertIn("<p>For a decision-maker, the practical implication is", html)


if __name__ == "__main__":
    unittest.main()
