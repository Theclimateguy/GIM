import unittest
from pathlib import Path
import tempfile

from gim.ui_server import (
    ROOT,
    _build_cli_from_payload,
    _analytics_payload_from_manifest_path,
    _artifacts_payload_from_manifest_path,
    _latest_analytics_payload,
    _latest_artifacts_payload,
    _list_actor_options,
    _list_docs,
    _list_state_csvs,
    _safe_join,
    _scenario_color,
)


class UIServerTests(unittest.TestCase):
    def test_safe_join_blocks_escape(self):
        with self.assertRaises(ValueError):
            _safe_join(ROOT, "../etc/passwd")

    def test_docs_list_contains_core_entries(self):
        docs = _list_docs()
        paths = {d["path"] for d in docs}
        self.assertIn("README.md", paths)
        self.assertIn("docs/MODEL_METHODOLOGY.md", paths)

    def test_state_csv_listing(self):
        csvs = _list_state_csvs()
        self.assertTrue(any(p.endswith("agent_states_operational_2026_calibrated.csv") for p in csvs))

    def test_actor_options_from_default_state_csv(self):
        payload = _list_actor_options()
        names = {entry["name"] for entry in payload["actors"]}
        self.assertIn("United States", names)
        self.assertTrue(payload["state_csv"].endswith("agent_states_operational_2026_calibrated.csv"))

    def test_scenario_color_mapping(self):
        self.assertEqual(_scenario_color("direct_strike_exchange"), "#d85c5c")
        self.assertEqual(_scenario_color("negotiated_deescalation"), "#3fbf74")
        self.assertEqual(_scenario_color("internal_destabilization"), "#d85c5c")

    def test_build_cli_for_question(self):
        payload = {
            "command": "question",
            "question": "How will sanctions evolve?",
            "actors": '"United States" Iran',
            "template": "sanctions_spiral",
            "state_year": 2026,
            "horizon": 3,
            "background_policy": "compiled-llm",
            "llm_refresh": "trigger",
            "llm_refresh_years": 2,
            "state_csv": "data/agent_states_operational_2026_calibrated.csv",
            "dashboard": True,
            "brief": True,
            "narrative": False,
            "json": True,
            "sim": True,
            "dashboard_output": "dashboard.html",
            "brief_output": "decision_brief.md",
        }
        argv = _build_cli_from_payload(payload)
        self.assertEqual(argv[:4], ["python3", "-m", "gim", "question"])
        self.assertIn("--question", argv)
        self.assertIn("--actors", argv)
        self.assertIn("United States", argv)
        self.assertIn("Iran", argv)
        joined = " ".join(argv)
        self.assertIn("--background-policy compiled-llm", joined)
        self.assertIn("--dashboard", joined)
        self.assertIn("--brief", joined)
        self.assertIn("--json", joined)

    def test_build_cli_omits_blank_template(self):
        payload = {
            "command": "question",
            "question": "How will sanctions evolve?",
            "actors": "United States Iran",
            "template": "",
            "dashboard": False,
            "brief": False,
            "sim": False,
        }
        argv = _build_cli_from_payload(payload)
        self.assertNotIn("--template", argv)

    def test_build_cli_for_game_uses_description_from_question(self):
        payload = {
            "command": "game",
            "question": "Assess escalation path under maritime pressure.",
            "state_year": 2026,
            "horizon": 5,
            "sim": True,
            "dashboard": True,
            "brief": True,
        }
        argv = _build_cli_from_payload(payload)
        self.assertEqual(argv[:4], ["python3", "-m", "gim", "game"])
        self.assertIn("--description", argv)
        self.assertIn("Assess escalation path under maritime pressure.", argv)

    def test_build_cli_for_hybrid_round(self):
        payload = {
            "command": "hybrid",
            "tables": ['United States'],
            "intents": {"United States": "Increase AI spending moderately."},
            "mode": "WHAT_IF",
            "round_years": 4,
            "ensemble_size": 3,
            "seed": 2026,
            "state_year": 2026,
            "background_policy": "simple",
            "llm_refresh": "trigger",
            "llm_refresh_years": 2,
            "dashboard": True,
            "brief": True,
            "json": True,
        }
        argv = _build_cli_from_payload(payload)
        joined = " ".join(argv)
        self.assertEqual(argv[:4], ["python3", "-m", "gim", "hybrid"])
        self.assertIn("--tables", argv)
        self.assertIn("--intent", argv)
        self.assertIn("--mode WHAT_IF", joined)
        self.assertIn("--round-years 4", joined)
        self.assertIn("--ensemble-size 3", joined)
        self.assertIn("--brief-output hybrid_report.md", joined)

    def test_manifest_payloads_are_run_specific(self):
        with tempfile.TemporaryDirectory(prefix="test-ui-run-", dir=ROOT / "results") as tmp:
            run_dir = Path(tmp)
            evaluation_path = run_dir / "evaluation.json"
            dashboard_path = run_dir / "dashboard.html"
            brief_path = run_dir / "decision_brief.md"
            manifest_path = run_dir / "run_manifest.json"

            evaluation_path.write_text(
                """
                {
                  "scenario": {"base_year": 2028},
                  "evaluation": {
                    "risk_probabilities": {"internal_destabilization": 0.42, "status_quo": 0.18},
                    "driver_scores": {"debt_rollover": 0.91, "sanctions_pressure": 0.72},
                    "criticality_score": 0.61,
                    "dominant_outcomes": ["internal_destabilization", "status_quo"],
                    "crisis_dashboard": {
                      "global_context": {
                        "metrics": {
                          "global_oil_market_stress": {"value": 1.03},
                          "global_sanctions_footprint": {"value": 0.48},
                          "global_trade_fragmentation": {"value": 0.27},
                          "global_energy_volume_gap": {"value": 0.07}
                        }
                      }
                    }
                  },
                  "trajectory": [
                    {
                      "agents": {
                        "usa": {
                          "name": "United States",
                          "economy": {"gdp": 25.0, "inflation": 0.02},
                          "society": {"social_tension": 0.18},
                          "climate": {"co2_annual_emissions": 5.0}
                        },
                        "irn": {
                          "name": "Iran",
                          "economy": {"gdp": 1.2, "inflation": 0.08},
                          "society": {"social_tension": 0.54},
                          "climate": {"co2_annual_emissions": 0.8}
                        }
                      },
                      "global_state": {"prices": {"energy": 1.0, "food": 1.0, "metals": 1.0}}
                    },
                    {
                      "agents": {
                        "usa": {
                          "name": "United States",
                          "economy": {"gdp": 26.2, "inflation": 0.03},
                          "society": {"social_tension": 0.20},
                          "climate": {"co2_annual_emissions": 5.1}
                        },
                        "irn": {
                          "name": "Iran",
                          "economy": {"gdp": 1.0, "inflation": 0.11},
                          "society": {"social_tension": 0.66},
                          "climate": {"co2_annual_emissions": 0.85}
                        }
                      },
                      "global_state": {"prices": {"energy": 1.4, "food": 1.1, "metals": 1.0}}
                    }
                  ]
                }
                """.strip(),
                encoding="utf-8",
            )
            dashboard_path.write_text("<html></html>", encoding="utf-8")
            brief_path.write_text(
                """
                ## Decision-Maker Interpretation
                The model indicates elevated macro stress with meaningful downside branch mass.

                ## Executive Summary
                Use this as the operational summary block for the dashboard.

                ## Outcome Distribution
                1. Internal destabilization: 42.0%
                2. Status quo: 18.0%

                ## Main Drivers
                Debt rollover: 0.91
                Sanctions pressure: 0.72
                """.strip(),
                encoding="utf-8",
            )
            manifest_path.write_text(
                (
                    "{\n"
                    '  "command": "question",\n'
                    '  "run_id": "question-test-ui",\n'
                    f'  "artifacts_dir": "{run_dir}",\n'
                    '  "outputs": {\n'
                    f'    "evaluation_json": "{evaluation_path}",\n'
                    f'    "dashboard_html": "{dashboard_path.relative_to(ROOT)}",\n'
                    f'    "brief_markdown": "{brief_path}"\n'
                    "  }\n"
                    "}"
                ),
                encoding="utf-8",
            )

            artifacts = _artifacts_payload_from_manifest_path(manifest_path)
            analytics = _analytics_payload_from_manifest_path(manifest_path)

            self.assertEqual(artifacts["run_id"], "question-test-ui")
            self.assertIn("dashboard.html", artifacts["artifacts"])
            self.assertTrue(artifacts["artifacts"]["dashboard.html"].endswith("dashboard.html"))

            self.assertEqual(analytics["run_id"], "question-test-ui")
            self.assertAlmostEqual(analytics["criticality"], 0.61)
            self.assertEqual(analytics["years"], [2028, 2029])
            self.assertTrue(analytics["scenario_distribution"])
            self.assertTrue(analytics["gdp_series"])
            self.assertIn("DECISION-MAKER INTERPRETATION", analytics["summary"])
            self.assertEqual(analytics["brief_outcomes"][0], "1. Internal Destabilization: 42.0%")
            self.assertEqual(analytics["brief_drivers"][0], "Debt Rollover: 0.91")
            self.assertTrue(all(0.0 <= float(metric["value"]) <= 1.0 for metric in analytics["quant"]))

    def test_manifest_payload_uses_actual_custom_artifact_name(self):
        with tempfile.TemporaryDirectory(prefix="test-ui-hybrid-", dir=ROOT / "results") as tmp:
            run_dir = Path(tmp)
            manifest_path = run_dir / "run_manifest.json"
            brief_path = run_dir / "hybrid_report.md"
            brief_path.write_text("## Executive Summary\ncustom\n", encoding="utf-8")
            manifest_path.write_text(
                (
                    "{\n"
                    '  "command": "hybrid",\n'
                    '  "run_id": "hybrid-test-ui",\n'
                    f'  "artifacts_dir": "{run_dir}",\n'
                    '  "outputs": {\n'
                    f'    "brief_markdown": "{brief_path}"\n'
                    "  }\n"
                    "}"
                ),
                encoding="utf-8",
            )

            artifacts = _artifacts_payload_from_manifest_path(manifest_path)
            self.assertIn("hybrid_report.md", artifacts["artifacts"])
            self.assertNotIn("decision_brief.md", artifacts["artifacts"])

    def test_latest_artifacts_payload_shape(self):
        payload = _latest_artifacts_payload()
        self.assertIn("latest_run", payload)
        self.assertIn("artifacts", payload)
        self.assertIsInstance(payload["artifacts"], dict)

    def test_latest_analytics_payload_shape(self):
        payload = _latest_analytics_payload()
        self.assertIn("summary", payload)
        self.assertIn("scenario_distribution", payload)
        self.assertIn("criticality", payload)
        self.assertIn("quant", payload)
        self.assertIsInstance(payload["quant"], list)


if __name__ == "__main__":
    unittest.main()
