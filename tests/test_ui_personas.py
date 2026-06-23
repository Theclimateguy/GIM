"""Tests for the persona-aware UI server endpoints. Pure unittest (no pytest in CI)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gim.ui_server import (
    RESULTS_DIR,
    _apply_personas_to_payload,
    _compare_payload,
    _doctrine_preview_payload,
    _intents_feed_payload,
    _personas_payload,
    _summarize_actions,
)


class UIPersonaTests(unittest.TestCase):
    def test_personas_payload_lists_archetypes(self):
        payload = _personas_payload()
        ids = {p["id"] for p in payload["personas"]}
        self.assertTrue({"hawk_protectionist", "dove", "technocrat"} <= ids)
        for persona in payload["personas"]:
            self.assertTrue(persona["name"]["ru"] and persona["name"]["en"])
            self.assertIn("nudges", persona)

    def test_apply_personas_augments_list_intents(self):
        payload = {
            "command": "hybrid",
            "tables": ["United States"],
            "intents": ["United States=Pressure China on trade"],
            "persona": {"United States": "hawk_protectionist"},
        }
        _apply_personas_to_payload(payload)
        intent = payload["intents"][0]
        self.assertTrue(intent.startswith("United States=Pressure China on trade"))
        self.assertIn("tariffs", intent)

    def test_apply_personas_handles_dict_intents_and_unknown_persona(self):
        payload = {"intents": {"Iran": "Hold the line"}, "persona": {"Iran": "not_real"}}
        _apply_personas_to_payload(payload)
        self.assertEqual(payload["intents"], ["Iran=Hold the line"])

    def test_doctrine_preview_for_real_country(self):
        preview, status = _doctrine_preview_payload(
            "hawk_protectionist", "United States", None, 2026
        )
        self.assertEqual(status, 200)
        self.assertEqual(preview["country"], "United States")
        for side in ("base", "shifted", "deltas"):
            self.assertIn("escalation_bias", preview[side])
        self.assertGreater(preview["deltas"]["escalation_bias"], 0)
        self.assertLess(preview["deltas"]["trade_openness"], 0)

    def test_doctrine_preview_unknown_country_is_400(self):
        _preview, status = _doctrine_preview_payload("dove", "Atlantis", None, 2026)
        self.assertEqual(status, 400)

    def test_summarize_actions_extracts_chips(self):
        chips = _summarize_actions(
            [
                {
                    "foreign_policy": {
                        "sanctions_actions": [{"type": "strong", "target": "CHN"}],
                        "security_actions": {"type": "none"},
                    },
                    "domestic_policy": {"military_spending_change": 0.01},
                }
            ]
        )
        self.assertIn("sanctions→CHN", chips)
        self.assertIn("military_spend↑", chips)
        self.assertEqual(_summarize_actions([]), [])

    def test_intents_feed_from_hybrid_result(self):
        data = {
            "hybrid_result": {
                "intents": [
                    {
                        "agent_id": "USA",
                        "agent_name": "United States",
                        "raw_text": "Pressure China",
                        "matched_topics": ["trade_restrict", "sanctions"],
                        "intensity": "medium",
                    }
                ],
                "effective_actions_by_agent": {
                    "USA": [{"domestic_policy": {"military_spending_change": 0.01}}]
                },
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hybrid_result.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            feed = _intents_feed_payload(path)["feed"]
        self.assertEqual(len(feed), 1)
        self.assertEqual(feed[0]["agent_name"], "United States")
        self.assertEqual(feed[0]["tags"], ["trade_restrict", "sanctions"])
        self.assertIn("military_spend↑", feed[0]["actions"])

    def test_compare_payload_diffs_two_runs(self):
        dirs = [
            p.parent.name
            for p in sorted(
                RESULTS_DIR.glob("*/evaluation.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True,
            )
        ][:2]
        if len(dirs) < 2:
            self.skipTest("need two runs with evaluation.json")
        result = _compare_payload(dirs)
        self.assertEqual(len(result["runs"]), 2)
        self.assertIn("criticality", result["runs"][0])
        self.assertIn("criticality_delta", result["diff"])
        self.assertGreaterEqual(len(result["diff"]["outcome_deltas"]), 1)

    def test_compare_payload_requires_resolvable_runs(self):
        result = _compare_payload(["does-not-exist-1", "does-not-exist-2"])
        self.assertEqual(result["runs"], [])
        self.assertEqual(result["diff"], {})


if __name__ == "__main__":
    unittest.main()
