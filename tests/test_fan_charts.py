"""Tests for probabilistic fan-chart rendering (Phase 1-E)."""

import unittest

from gim.ensemble import METRICS, EnsembleConfig, run_ensemble
from gim.fan_charts import render_fan_charts


class FanChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg = EnsembleConfig(
            state_csv="data/agent_states_operational.csv",
            n_members=10, years=3, max_agents=8, master_seed=2026, prior_set="key", n_jobs=1,
        )
        cls.result = run_ensemble(cfg)
        cls.html = render_fan_charts(cls.result)

    def test_is_self_contained_html(self):
        self.assertIn("<!doctype html>", self.html.lower())
        self.assertIn("</html>", self.html)
        self.assertNotIn("http://", self.html.replace("http://www.w3.org/2000/svg", ""))  # no external assets

    def test_contains_an_svg_panel_per_metric(self):
        self.assertEqual(self.html.count("<svg"), len(METRICS))

    def test_contains_bands_and_median(self):
        # outer + inner band polygons and a median polyline per metric
        self.assertGreaterEqual(self.html.count("<polygon"), 2 * len(METRICS))
        self.assertGreaterEqual(self.html.count("<polyline"), len(METRICS))

    def test_includes_legend_and_metric_labels(self):
        self.assertIn("5–95%", self.html)
        self.assertIn("median", self.html)
        self.assertIn("Global temperature", self.html)


if __name__ == "__main__":
    unittest.main()
