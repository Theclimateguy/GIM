from __future__ import annotations

import unittest

from gim.core import Action, Observation
from gim.core.human_policy import action_from_intent, make_human_policy, make_human_policy_map


class HumanPolicyAdapterTests(unittest.TestCase):
    def test_action_from_intent_supports_alias_fields(self) -> None:
        intent = {
            "domestic": {
                "tax_fuel_change": 0.2,
                "social_spending_change": 0.01,
                "military_spending_change": 0.005,
                "rd_investment_change": 0.003,
                "climate_policy": "moderate",
            },
            "foreign": {
                "security": {"type": "arms_buildup", "target": "B"},
                "sanctions_actions": [{"target": "B", "type": "mild"}],
                "trade_restrictions": [{"target": "B", "level": "soft"}],
                "proposed_trade_deals": [
                    {
                        "partner": "B",
                        "resource": "energy",
                        "direction": "import",
                        "volume_change": 12.0,
                        "price_preference": "fair",
                    }
                ],
            },
            "finance": {"borrow_from_global_markets": 0.02, "use_fx_reserves_change": 0.03},
            "explanation": "table decision",
        }
        action = action_from_intent(intent, agent_id="A", time=3)
        self.assertEqual(action.agent_id, "A")
        self.assertEqual(action.time, 3)
        self.assertAlmostEqual(action.domestic_policy.tax_fuel_change, 0.2, places=9)
        self.assertEqual(action.foreign_policy.security_actions.type, "arms_buildup")
        self.assertEqual(action.foreign_policy.security_actions.target, "B")
        self.assertEqual(len(action.foreign_policy.sanctions_actions), 1)
        self.assertEqual(len(action.foreign_policy.trade_restrictions), 1)
        self.assertEqual(len(action.foreign_policy.proposed_trade_deals), 1)

    def test_action_from_intent_applies_guardrails(self) -> None:
        intent = {
            "domestic_policy": {
                "tax_fuel_change": 999.0,
                "social_spending_change": -1.0,
                "military_spending_change": 1.0,
                "rd_investment_change": 1.0,
                "climate_policy": "invalid",
            },
            "foreign_policy": {
                "sanctions_actions": [
                    {"target": "B", "type": "strong"},
                    {"target": "C", "type": "mild"},
                    {"target": "D", "type": "mild"},
                ],
                "trade_restrictions": [
                    {"target": "B", "level": "hard"},
                    {"target": "C", "level": "soft"},
                    {"target": "D", "level": "soft"},
                ],
                "proposed_trade_deals": [
                    {
                        "partner": "B",
                        "resource": "energy",
                        "direction": "import",
                        "volume_change": 999.0,
                        "price_preference": "fair",
                    }
                ],
            },
        }
        action = action_from_intent(intent, agent_id="A", time=5)
        self.assertAlmostEqual(action.domestic_policy.tax_fuel_change, 1.5, places=9)
        self.assertAlmostEqual(action.domestic_policy.social_spending_change, -0.03, places=9)
        self.assertAlmostEqual(action.domestic_policy.military_spending_change, 0.03, places=9)
        self.assertAlmostEqual(action.domestic_policy.rd_investment_change, 0.008, places=9)
        self.assertEqual(action.domestic_policy.climate_policy, "none")
        self.assertLessEqual(len(action.foreign_policy.sanctions_actions), 2)
        self.assertLessEqual(len(action.foreign_policy.trade_restrictions), 2)
        self.assertEqual(action.foreign_policy.proposed_trade_deals[0].volume_change, 50.0)

    def test_make_human_policy_and_policy_map(self) -> None:
        obs = Observation(
            agent_id="A",
            time=7,
            self_state={},
            resource_balance={},
            external_actors={},
        )
        policy = make_human_policy({"domestic_policy": {"rd_investment_change": 0.002}})
        action = policy(obs)
        self.assertIsInstance(action, Action)
        self.assertEqual(action.agent_id, "A")
        self.assertEqual(action.time, 7)
        self.assertAlmostEqual(action.domestic_policy.rd_investment_change, 0.002, places=9)

        policy_map = make_human_policy_map({"A": {"domestic_policy": {"tax_fuel_change": 0.1}}})
        self.assertIn("A", policy_map)
        action2 = policy_map["A"](obs)
        self.assertEqual(action2.agent_id, "A")
        self.assertEqual(action2.time, 7)
        self.assertAlmostEqual(action2.domestic_policy.tax_fuel_change, 0.1, places=9)


if __name__ == "__main__":
    unittest.main()
