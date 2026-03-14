from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from gim.__main__ import build_parser
from gim.briefing import AnalyticsBriefRenderer, BriefConfig, write_brief_artifact
from gim.game_theory.equilibrium_runner import run_equilibrium_search
from gim.game_runner import GameRunner
from gim.interpretive_summary import build_interpretive_summary
from gim.runtime import load_world
from gim.scenario_compiler import compile_question, load_game_definition
from gim.sim_bridge import SimBridge


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = REPO_ROOT / "misc" / "cases" / "maritime_pressure_game.json"


class BriefingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.world = load_world()
        cls.runner = GameRunner(cls.world)
        cls.bridge = SimBridge()

    def test_parser_supports_brief_flags_and_subcommand(self) -> None:
        parser = build_parser()
        question_args = parser.parse_args(
            ["question", "Will Red Sea tensions escalate?", "--brief", "--brief-output", "brief.md"]
        )
        game_args = parser.parse_args(["game", "--case", str(CASE_PATH), "--brief"])
        brief_args = parser.parse_args(["brief", "--from-json", "evaluation.json", "--output", "memo.md"])
        self.assertTrue(question_args.brief)
        self.assertEqual(question_args.brief_output, "brief.md")
        self.assertTrue(game_args.brief)
        self.assertEqual(brief_args.command, "brief")
        self.assertEqual(brief_args.output, "memo.md")

    def test_question_brief_writes_markdown(self) -> None:
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
            output_path = Path(tmp_dir) / "decision_brief.md"
            written = write_brief_artifact(
                renderer=AnalyticsBriefRenderer(),
                evaluation=evaluation,
                game_result=None,
                equilibrium_result=None,
                trajectory=trajectory,
                scenario_def=scenario,
                config=BriefConfig(
                    output_path=str(output_path),
                    include_trajectory=True,
                    include_game_results=False,
                    execution_label="sim",
                    policy_mode_label="simple",
                    prefer_llm_interpretation=False,
                ),
            )
            text = Path(written).read_text(encoding="utf-8")
            self.assertIn("## Decision-Maker Interpretation", text)
            self.assertIn("## Executive Summary", text)
            self.assertIn("## Global Trajectory", text)
            self.assertIn("## Analyst Highlights", text)
            self.assertIn("## Model Terms", text)
            self.assertIn("Policy space", text)
            self.assertIn("Interpretation source: Deterministic fallback.", text)

    def test_game_brief_from_json_writes_markdown(self) -> None:
        game = load_game_definition(CASE_PATH, self.world)
        result = self.runner.run_game(game)
        scenario = game.scenario
        payload = {
            "scenario": asdict(scenario),
            "evaluation": asdict(result.best_combination.evaluation),
            "game_result": asdict(result),
            "trajectory": [asdict(self.world)],
            "dashboard_config": {"execution_label": "static", "policy_mode_label": "snapshot"},
        }
        with TemporaryDirectory() as tmp_dir:
            input_path = Path(tmp_dir) / "evaluation.json"
            output_path = Path(tmp_dir) / "decision_brief.md"
            input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            written = AnalyticsBriefRenderer().write_from_json(
                input_path=str(input_path),
                config=BriefConfig(output_path=str(output_path), prefer_llm_interpretation=False),
            )
            text = Path(written).read_text(encoding="utf-8")
            self.assertIn("## Decision-Maker Interpretation", text)
            self.assertIn("## Strategy Ranking", text)
            self.assertIn("Maritime pressure policy game", text)

    def test_interpretive_summary_answers_war_question_directly(self) -> None:
        world = load_world(state_csv=str(REPO_ROOT / "misc" / "data" / "agent_states_operational.csv"))
        scenario = compile_question(
            question="Will war start in Iran?",
            world=world,
            actors=["Iran"],
            horizon_months=36,
        )
        evaluation = GameRunner(world).evaluate_scenario(scenario)
        summary = build_interpretive_summary(
            {
                "scenario": asdict(scenario),
                "evaluation": asdict(evaluation),
                "trajectory": [asdict(world)],
            },
            prefer_llm=False,
        )
        self.assertEqual(len(summary.paragraphs), 3)
        self.assertIn("war", summary.paragraphs[0].lower())
        self.assertIn("Iran", summary.paragraphs[0])

    def test_interpretive_summary_is_split_into_markdown_paragraphs(self) -> None:
        world = load_world(state_csv=str(REPO_ROOT / "misc" / "data" / "agent_states_operational.csv"))
        scenario = compile_question(
            question="Will war start in Iran?",
            world=world,
            actors=["Iran"],
            horizon_months=36,
        )
        evaluation = GameRunner(world).evaluate_scenario(scenario)
        text = AnalyticsBriefRenderer().render(
            evaluation=evaluation,
            game_result=None,
            equilibrium_result=None,
            trajectory=[world],
            scenario_def=scenario,
            config=BriefConfig(prefer_llm_interpretation=False),
        )
        self.assertIn("Interpretation source: Deterministic fallback.\n\nThe model", text)
        self.assertIn("environment rather than a clean immediate-war forecast", text)
        self.assertIn("forecast, especially because calibration remains", text)
        self.assertIn("consistency remains 1.00.\n\nFor a decision-maker", text)

    def test_game_brief_includes_equilibrium_section(self) -> None:
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
        text = AnalyticsBriefRenderer().render(
            evaluation=result.best_combination.evaluation,
            game_result=result,
            equilibrium_result=equilibrium_result,
            trajectory=[self.world],
            scenario_def=game.scenario,
            config=BriefConfig(
                include_game_results=True,
                prefer_llm_interpretation=False,
            ),
        )
        self.assertIn("## Equilibrium Analysis", text)
        self.assertIn("Mean external regret", text)
        self.assertIn("Recommended profile", text)


if __name__ == "__main__":
    unittest.main()
