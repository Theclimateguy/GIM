"""Tests for the persona bias layer (THE-47)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

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


def test_archetype_catalog_is_valid():
    personas = list_personas()
    assert {"hawk_protectionist", "dove", "technocrat"} <= set(ARCHETYPES)
    assert len(personas) == len(ARCHETYPES)
    for persona in personas:
        for dim in persona.nudges:
            assert dim in DOCTRINE_DIMENSIONS
        payload = persona.to_payload()
        assert payload["name"]["ru"] and payload["name"]["en"]
        assert payload["declaration"]["ru"] and payload["declaration"]["en"]


def test_unknown_nudge_dimension_raises():
    with pytest.raises(ValueError):
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


def test_apply_nudges_clamps_to_unit_interval():
    base = {dim: 0.95 for dim in DOCTRINE_DIMENSIONS}
    hawk = get_persona("hawk_protectionist")
    shifted = apply_nudges(base, hawk)
    for dim, value in shifted.items():
        assert 0.0 <= value <= 1.0
    assert shifted["sanctions_tolerance"] == 1.0


def test_hawk_persona_shifts_doctrine_direction():
    obs = _obs()
    base = CompiledLLMPolicyManager(prefer_llm=False).get_or_compile_doctrine("USA", obs)
    hawk = get_persona("hawk_protectionist")
    shifted = CompiledLLMPolicyManager(
        prefer_llm=False, personas={"USA": hawk}
    ).get_or_compile_doctrine("USA", obs)

    assert shifted.escalation_bias > base.escalation_bias
    assert shifted.sanctions_tolerance > base.sanctions_tolerance
    assert shifted.trade_openness < base.trade_openness
    assert shifted.mediation_openness < base.mediation_openness
    assert shifted.source == "heuristic+persona"


def test_dove_persona_shifts_opposite_to_hawk():
    obs = _obs()
    base = CompiledLLMPolicyManager(prefer_llm=False).get_or_compile_doctrine("USA", obs)
    dove = get_persona("dove")
    shifted = CompiledLLMPolicyManager(
        prefer_llm=False, personas={"USA": dove}
    ).get_or_compile_doctrine("USA", obs)

    assert shifted.mediation_openness > base.mediation_openness
    assert shifted.escalation_bias < base.escalation_bias
    assert shifted.trade_openness > base.trade_openness


def test_persona_doctrine_is_cached_separately():
    obs = _obs()
    manager = CompiledLLMPolicyManager(prefer_llm=False, personas={"USA": get_persona("dove")})
    first = manager.get_or_compile_doctrine("USA", obs)
    second = manager.get_or_compile_doctrine("USA", obs)
    assert first is second  # served from cache keyed by (agent, signature, persona)


def test_set_persona_attaches_and_clears():
    obs = _obs()
    manager = CompiledLLMPolicyManager(prefer_llm=False)
    plain = manager.get_or_compile_doctrine("USA", obs)
    assert plain.source == "heuristic"

    manager.set_persona("USA", get_persona("hawk_protectionist"))
    biased = manager.get_or_compile_doctrine("USA", obs)
    assert biased.source == "heuristic+persona"
    assert biased.escalation_bias > plain.escalation_bias

    manager.set_persona("USA", None)
    cleared = manager.get_or_compile_doctrine("USA", obs)
    assert cleared.source == "heuristic"


def test_doctrine_preview_reports_base_shift_and_deltas():
    obs = _obs()
    manager = CompiledLLMPolicyManager(prefer_llm=False)
    preview = manager.doctrine_preview("USA", obs, get_persona("hawk_protectionist"))

    assert preview["persona_id"] == "hawk_protectionist"
    assert set(preview["deltas"]) == set(DOCTRINE_DIMENSIONS)
    assert set(preview["base"]) >= set(DOCTRINE_DIMENSIONS)
    assert preview["deltas"]["escalation_bias"] > 0
    assert preview["deltas"]["trade_openness"] < 0
    assert preview["base"]["source"] == "heuristic"
    assert preview["shifted"]["source"] == "heuristic+persona"


def test_doctrine_preview_without_persona_has_zero_deltas():
    obs = _obs()
    manager = CompiledLLMPolicyManager(prefer_llm=False)
    preview = manager.doctrine_preview("USA", obs, None)

    assert preview["persona_id"] is None
    assert all(value == 0 for value in preview["deltas"].values())
    assert preview["base"] == preview["shifted"]
