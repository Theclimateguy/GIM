"""Persona layer for the GIM17 decision-maker UI.

A persona is a *bias* on top of the country's own compiled doctrine, not an
override. It carries an opening declaration (fed into the doctrine-compilation
prompt) and additive nudges applied to the 9-dimensional doctrine vector. See
``docs/ui_redesign/design_spec.md`` (Persona model) and the
``CompiledLLMPolicyManager`` in ``gim/compiled_policy.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


DOCTRINE_DIMENSIONS = (
    "domestic_priority",
    "escalation_bias",
    "sanctions_tolerance",
    "trade_openness",
    "mediation_openness",
    "reserve_protection",
    "military_readiness",
    "finance_defensiveness",
    "climate_pragmatism",
)


def _clamp01(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, numeric))


@dataclass(frozen=True)
class Persona:
    """A neutral behavioral archetype that biases doctrine compilation."""

    id: str
    name_ru: str
    name_en: str
    tagline_ru: str
    tagline_en: str
    declaration_ru: str
    declaration_en: str
    nudges: Mapping[str, float] = field(default_factory=dict)
    intent_keywords: str = ""

    def __post_init__(self) -> None:
        for dim in self.nudges:
            if dim not in DOCTRINE_DIMENSIONS:
                raise ValueError(f"Unknown doctrine dimension in persona nudges: {dim!r}")

    def to_payload(self) -> dict[str, Any]:
        """Serialize for the API / UI (bilingual labels + nudge directions)."""
        return {
            "id": self.id,
            "name": {"ru": self.name_ru, "en": self.name_en},
            "tagline": {"ru": self.tagline_ru, "en": self.tagline_en},
            "declaration": {"ru": self.declaration_ru, "en": self.declaration_en},
            "nudges": {dim: round(float(value), 3) for dim, value in self.nudges.items()},
            "intent_keywords": self.intent_keywords,
        }


ARCHETYPES: dict[str, Persona] = {
    "hawk_protectionist": Persona(
        id="hawk_protectionist",
        name_ru="Ястреб-протекционист",
        name_en="Protectionist hawk",
        tagline_ru="тарифы, давление, сделки",
        tagline_en="tariffs, pressure, deals",
        declaration_ru=(
            "Действует транзакционно и с позиции силы: предпочитает тарифы, "
            "экспортный контроль и двусторонние сделки альянсам; скептичен к "
            "многостороннему посредничеству; терпим к санкциям и силовому давлению."
        ),
        declaration_en=(
            "Acts transactionally and from strength: prefers tariffs, export "
            "controls and bilateral deals over alliances; skeptical of "
            "multilateral mediation; tolerant of sanctions and coercive pressure."
        ),
        nudges={
            "escalation_bias": 0.20,
            "sanctions_tolerance": 0.25,
            "trade_openness": -0.25,
            "mediation_openness": -0.25,
            "domestic_priority": 0.10,
            "military_readiness": 0.10,
        },
        intent_keywords="impose tariffs, export controls, sanctions, deterrence",
    ),
    "dove": Persona(
        id="dove",
        name_ru="Голубь",
        name_en="Dove",
        tagline_ru="деэскалация, посредничество",
        tagline_en="de-escalation, mediation",
        declaration_ru=(
            "Ищет деэскалацию и переговорные развязки: ставит на посредничество, "
            "сдержанность и открытую торговлю; избегает санкционных спиралей и "
            "военного наращивания."
        ),
        declaration_en=(
            "Seeks de-escalation and negotiated settlements: favors mediation, "
            "restraint and open trade; avoids sanctions spirals and military build-ups."
        ),
        nudges={
            "mediation_openness": 0.30,
            "escalation_bias": -0.25,
            "trade_openness": 0.20,
            "sanctions_tolerance": -0.20,
            "military_readiness": -0.15,
        },
        intent_keywords="de-escalate, mediate, restraint, propose trade deal",
    ),
    "technocrat": Persona(
        id="technocrat",
        name_ru="Технократ",
        name_en="Technocrat",
        tagline_ru="расчёт, без идеологии",
        tagline_en="calculation, no ideology",
        declaration_ru=(
            "Прагматично оптимизирует без идеологии: бережёт фискально-финансовую "
            "устойчивость и климатический прагматизм; умеренно деэскалационен, "
            "опирается на данные."
        ),
        declaration_en=(
            "Optimizes pragmatically with little ideology: protects fiscal and "
            "financial stability and pursues climate pragmatism; modestly "
            "de-escalatory and data-driven."
        ),
        nudges={
            "finance_defensiveness": 0.15,
            "climate_pragmatism": 0.15,
            "escalation_bias": -0.10,
            "sanctions_tolerance": -0.05,
        },
        intent_keywords="stabilize debt, fiscal restraint, climate investment",
    ),
}


def list_personas() -> list[Persona]:
    return list(ARCHETYPES.values())


def get_persona(persona_id: str | None) -> Persona | None:
    if not persona_id:
        return None
    return ARCHETYPES.get(str(persona_id))


def apply_nudges(payload: Mapping[str, Any], persona: Persona) -> dict[str, Any]:
    """Return a copy of a doctrine payload with persona nudges applied (clamped)."""
    out = dict(payload)
    for dim, delta in persona.nudges.items():
        if dim in out:
            out[dim] = _clamp01(_clamp01(out[dim]) + float(delta))
    return out


def augment_intent(goal: str, persona: Persona | None) -> str:
    """Blend a decision-maker goal with the persona's keyword leanings.

    The hybrid intent parser matches English topic keywords; appending the
    persona's keywords biases the compiled (forced) action toward its style.
    """
    goal = (goal or "").strip()
    if persona is None or not persona.intent_keywords:
        return goal
    if not goal:
        return persona.intent_keywords
    return f"{goal}. {persona.intent_keywords}"


def persona_prompt_block(persona: Persona) -> str:
    """Instruction block appended to the doctrine-compilation prompt."""
    directions = ", ".join(
        f"{dim} {'+' if value >= 0 else ''}{value:.2f}" for dim, value in persona.nudges.items()
    )
    return (
        "PERSONA BIAS — apply this as a strategic-style shift layered on top of the "
        "country's own state, do not ignore the country's fundamentals:\n"
        f"- archetype: {persona.name_en}\n"
        f"- declaration: {persona.declaration_en}\n"
        f"- preferred directional shifts (additive, in doctrine units): {directions}\n"
    )
