from pathlib import Path
import unittest

from GIM_13.crisis_metrics import CrisisMetricsEngine
from GIM_13.game_runner import GameRunner
from GIM_13.runtime import load_world
from GIM_13.scenario_compiler import compile_question, resolve_actor_names


REPO_ROOT = Path(__file__).resolve().parents[1]


class CrisisMetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.world = load_world()
        cls.engine = CrisisMetricsEngine()
        cls.runner = GameRunner(cls.world)
        cls.actor_ids, _names, unresolved = resolve_actor_names(
            cls.world,
            ["United States", "Saudi Arabia", "Turkey"],
        )
        if unresolved:
            raise AssertionError(f"Failed to resolve baseline actors: {unresolved}")

    def test_dashboard_contains_global_and_agent_metrics(self) -> None:
        dashboard = self.engine.compute_dashboard(self.world, agent_ids=self.actor_ids)
        us_id, saudi_id, _turkiye_id = self.actor_ids
        self.assertIn("global_oil_market_stress", dashboard.global_context.metrics)
        self.assertIn(us_id, dashboard.agents)
        self.assertIn("inflation", dashboard.agents[us_id].metrics)
        self.assertIn("fx_stress", dashboard.agents[us_id].metrics)
        self.assertIn("conflict_escalation_pressure", dashboard.agents[saudi_id].metrics)

    def test_relevance_router_reduces_food_stress_for_large_advanced_power(self) -> None:
        dashboard = self.engine.compute_dashboard(self.world, agent_ids=self.actor_ids)
        us_id, _saudi_id, turkiye_id = self.actor_ids
        us_food = dashboard.agents[us_id].metrics["food_affordability_stress"].relevance
        turkiye_food = dashboard.agents[turkiye_id].metrics["food_affordability_stress"].relevance
        self.assertLess(us_food, turkiye_food)

    def test_saudi_is_classified_as_hydrocarbon_exporter(self) -> None:
        _us_id, saudi_id, _turkiye_id = self.actor_ids
        report = self.engine.compute_agent_report(saudi_id, self.world)
        self.assertEqual(report.archetype, "hydrocarbon_exporter")

    def test_game_runner_carries_crisis_dashboard(self) -> None:
        scenario = compile_question(
            question="Could sanctions pressure destabilize Saudi Arabia and Turkey in 2026?",
            world=self.world,
            actors=["Saudi Arabia", "Turkey", "United States"],
            template_id="sanctions_spiral",
        )
        evaluation = self.runner.evaluate_scenario(scenario)
        self.assertIn(self.actor_ids[0], evaluation.crisis_dashboard.agents)
        self.assertIn("__global__", evaluation.crisis_delta_by_agent)


if __name__ == "__main__":
    unittest.main()
