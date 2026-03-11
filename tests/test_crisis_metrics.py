from pathlib import Path
import unittest

from GIM_13.crisis_metrics import CrisisMetricsEngine
from GIM_13.runtime import load_world


REPO_ROOT = Path(__file__).resolve().parents[1]


class CrisisMetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.world = load_world()
        cls.engine = CrisisMetricsEngine()

    def test_dashboard_contains_global_and_agent_metrics(self) -> None:
        dashboard = self.engine.compute_dashboard(self.world, agent_ids=["C01", "C18", "C19"])
        self.assertIn("global_oil_market_stress", dashboard.global_context.metrics)
        self.assertIn("C01", dashboard.agents)
        self.assertIn("inflation", dashboard.agents["C01"].metrics)
        self.assertIn("fx_stress", dashboard.agents["C01"].metrics)
        self.assertIn("conflict_escalation_pressure", dashboard.agents["C18"].metrics)

    def test_relevance_router_reduces_food_stress_for_large_advanced_power(self) -> None:
        dashboard = self.engine.compute_dashboard(self.world, agent_ids=["C01", "C19"])
        us_food = dashboard.agents["C01"].metrics["food_affordability_stress"].relevance
        turkey_food = dashboard.agents["C19"].metrics["food_affordability_stress"].relevance
        self.assertLess(us_food, turkey_food)

    def test_saudi_is_classified_as_hydrocarbon_exporter(self) -> None:
        report = self.engine.compute_agent_report("C18", self.world)
        self.assertEqual(report.archetype, "hydrocarbon_exporter")


if __name__ == "__main__":
    unittest.main()
