import json
import os
from pathlib import Path
from unittest.mock import Mock, patch
import unittest

from gim.case_builder import REQUESTS_AVAILABLE, build_case_from_text, serialize_game_definition
from gim.runtime import load_world


REPO_ROOT = Path(__file__).resolve().parents[1]


class CaseBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.world = load_world()

    def test_deterministic_builder_creates_valid_trade_case(self) -> None:
        built = build_case_from_text(
            (
                "China introduces export controls on rare earth metals, the United States responds "
                "with tariffs, and Japan is exposed as a bystander."
            ),
            self.world,
            prefer_llm=False,
        )
        self.assertEqual(built.source, "deterministic")
        self.assertEqual(built.game.scenario.template_id, "trade_war")
        self.assertGreaterEqual(len(built.game.players), 2)
        self.assertTrue(all(player.allowed_actions for player in built.game.players))

    def test_deterministic_builder_creates_valid_tech_blockade_case(self) -> None:
        built = build_case_from_text(
            (
                "The United States tightens semiconductor export controls against Huawei and China "
                "responds with industrial countermeasures."
            ),
            self.world,
            prefer_llm=False,
        )
        self.assertEqual(built.source, "deterministic")
        self.assertEqual(built.game.scenario.template_id, "tech_blockade")
        self.assertTrue(any("export_controls" in player.allowed_actions for player in built.game.players))

    @unittest.skipUnless(REQUESTS_AVAILABLE, "requires requests to exercise the LLM case-builder path")
    def test_llm_builder_cleans_invalid_template_actions_and_objectives(self) -> None:
        mocked_response = Mock()
        mocked_response.raise_for_status.return_value = None
        mocked_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "id": "bad-case",
                                "title": "Bad Case",
                                "scenario": {
                                    "question": "China and the United States fight a tariff war.",
                                    "actors": ["China", "United States", "Japan"],
                                    "horizon_months": 80,
                                    "template": "unknown_template",
                                },
                                "players": [
                                    {
                                        "actor": "China",
                                        "objectives": {"fake_objective": 9, "resource_access": 3.5},
                                        "allowed_actions": ["fake_action", "export_controls"],
                                    },
                                    {
                                        "actor": "United States",
                                        "objectives": {"reduce_war_risk": 1.2},
                                        "allowed_actions": ["impose_tariffs", "nonexistent"],
                                    },
                                ],
                            }
                        )
                    }
                }
            ]
        }
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}, clear=False), patch(
            "gim.case_builder.requests.post",
            return_value=mocked_response,
        ):
            built = build_case_from_text(
                "China and the United States enter a tariff war.",
                self.world,
                prefer_llm=True,
            )

        self.assertEqual(built.source, "llm")
        self.assertEqual(built.game.scenario.template_id, "trade_war")
        self.assertLessEqual(built.game.scenario.horizon_months, 60)
        self.assertIn("export_controls", built.game.players[0].allowed_actions)
        self.assertNotIn("fake_action", built.game.players[0].allowed_actions)
        self.assertIn("resource_access", built.game.players[0].objectives)
        self.assertNotIn("fake_objective", built.game.players[0].objectives)

    def test_serialized_game_payload_matches_loader_shape(self) -> None:
        built = build_case_from_text(
            "Iran faces cyber pressure while the United States and Saudi Arabia react.",
            self.world,
            prefer_llm=False,
        )
        payload = serialize_game_definition(built.game)
        self.assertIn("scenario", payload)
        self.assertIn("players", payload)
        self.assertIn("template", payload["scenario"])
        self.assertTrue(payload["players"])


if __name__ == "__main__":
    unittest.main()
