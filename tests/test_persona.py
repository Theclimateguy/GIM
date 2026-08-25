"""Tests for the persona bias layer (THE-47). Pure unittest (no pytest in CI)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from gim.compiled_policy import CompiledLLMPolicyManager
from gim.persona import (
    ARCHETYPES,
    DOCTRINE_DIMENSIONS,
    Persona,
    apply_nudges,
    get_persona,
    list_personas,
)


def _obs(agent_id: str = "USA"):
    """Minimal Observation-shaped stub sufficient for doctrine compilation."""
    return SimpleNamespace(
        agent_id=agent_id,
        time=0,
        self_state={
            "political": {
                "hawkishness": 0.5,
                "protectionism": 0.5,
                "coalition_openness": 0.5,
                "sanction_propensity": 0.5,
                "policy_space": 0.5,
            },
            "society": {"trust_gov": 0.5, "social_tension": 0.5, "inequality_gini": 0.4},
            "culture": {},
            "climate": {"climate_risk": 0.5},
            "competitive": {
                "protest_risk": 0.4,
                "debt_stress": 0.4,
                "security_margin": 1.0,
                "reserve_years": {"energy": 2.0},
            },
            "economy": {"gdp_per_capita": 50000.0},
            "active_sanctions": {},
        },
        external_actors={"neighbors": []},
        resource_balance={},
        memory={"policy_history": []},
    )


class PersonaTests(unittest.TestCase):
    def test_archetype_catalog_is_valid(self):
        personas = list_personas()
        self.assertTrue({"hawk_protectionist", "dove", "technocrat"} <= set(ARCHETYPES))
        self.assertEqual(len(personas), len(ARCHETYPES))
        for persona in personas:
            for dim in persona.nudges:
                self.assertIn(dim, DOCTRINE_DIMENSIONS)
            payload = persona.to_payload()
            self.assertTrue(payload["name"]["ru"] and payload["name"]["en"])
            self.assertTrue(payload["declaration"]["ru"] and payload["declaration"]["en"])

    def test_unknown_nudge_dimension_raises(self):
        with self.assertRaises(ValueError):
            Persona(
                id="bad",
                name_ru="x",
                name_en="x",
                tagline_ru="x",
                tagline_en="x",
                declaration_ru="x",
                declaration_en="x",
                nudges={"not_a_dimension": 0.5},
            )

    def test_apply_nudges_clamps_to_unit_interval(self):
        base = {dim: 0.95 for dim in DOCTRINE_DIMENSIONS}
        shifted = apply_nudges(base, get_persona("hawk_protectionist"))
        for value in shifted.values():
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)
        self.assertEqual(shifted["sanctions_tolerance"], 1.0)

    def test_hawk_persona_shifts_doctrine_direction(self):
        obs = _obs()
        base = CompiledLLMPolicyManager(prefer_llm=False).get_or_compile_doctrine("USA", obs)
        shifted = CompiledLLMPolicyManager(
            prefer_llm=False, personas={"USA": get_persona("hawk_protectionist")}
        ).get_or_compile_doctrine("USA", obs)
        self.assertGreater(shifted.escalation_bias, base.escalation_bias)
        self.assertGreater(shifted.sanctions_tolerance, base.sanctions_tolerance)
        self.assertLess(shifted.trade_openness, base.trade_openness)
        self.assertLess(shifted.mediation_openness, base.mediation_openness)
        self.assertEqual(shifted.source, "heuristic+persona")

    def test_dove_persona_shifts_opposite_to_hawk(self):
        obs = _obs()
        base = CompiledLLMPolicyManager(prefer_llm=False).get_or_compile_doctrine("USA", obs)
        shifted = CompiledLLMPolicyManager(
            prefer_llm=False, personas={"USA": get_persona("dove")}
        ).get_or_compile_doctrine("USA", obs)
        self.assertGreater(shifted.mediation_openness, base.mediation_openness)
        self.assertLess(shifted.escalation_bias, base.escalation_bias)
        self.assertGreater(shifted.trade_openness, base.trade_openness)

    def test_persona_doctrine_is_cached_separately(self):
        obs = _obs()
        manager = CompiledLLMPolicyManager(prefer_llm=False, personas={"USA": get_persona("dove")})
        first = manager.get_or_compile_doctrine("USA", obs)
        second = manager.get_or_compile_doctrine("USA", obs)
        self.assertIs(first, second)

    def test_doctrine_preview_reports_base_shift_and_deltas(self):
        obs = _obs()
        preview = CompiledLLMPolicyManager(prefer_llm=False).doctrine_preview(
            "USA", obs, get_persona("hawk_protectionist")
        )
        self.assertEqual(preview["persona_id"], "hawk_protectionist")
        self.assertEqual(set(preview["deltas"]), set(DOCTRINE_DIMENSIONS))
        self.assertTrue(set(preview["base"]) >= set(DOCTRINE_DIMENSIONS))
        self.assertGreater(preview["deltas"]["escalation_bias"], 0)
        self.assertLess(preview["deltas"]["trade_openness"], 0)
        self.assertEqual(preview["base"]["source"], "heuristic")
        self.assertEqual(preview["shifted"]["source"], "heuristic+persona")

    def test_doctrine_preview_without_persona_has_zero_deltas(self):
        obs = _obs()
        preview = CompiledLLMPolicyManager(prefer_llm=False).doctrine_preview("USA", obs, None)
        self.assertIsNone(preview["persona_id"])
        self.assertTrue(all(value == 0 for value in preview["deltas"].values()))
        self.assertEqual(preview["base"], preview["shifted"])

    def test_set_persona_attaches_and_clears(self):
        obs = _obs()
        manager = CompiledLLMPolicyManager(prefer_llm=False)
        plain = manager.get_or_compile_doctrine("USA", obs)
        self.assertEqual(plain.source, "heuristic")

        manager.set_persona("USA", get_persona("hawk_protectionist"))
        biased = manager.get_or_compile_doctrine("USA", obs)
        self.assertEqual(biased.source, "heuristic+persona")
        self.assertGreater(biased.escalation_bias, plain.escalation_bias)

        manager.set_persona("USA", None)
        cleared = manager.get_or_compile_doctrine("USA", obs)
        self.assertEqual(cleared.source, "heuristic")


if __name__ == "__main__":
    unittest.main()
