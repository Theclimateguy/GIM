"""Lightweight, declarative scenario ontology for on-the-fly composition.

This is the data layer that lets scenarios be *composed* from a bounded set of
calibrated levers instead of being selected from a handful of hard-coded
templates. It adds **no model math**: every lever maps to a shock ``channel``
that the engine already honours in ``GameRunner._apply_shocks`` (sourced from
``geo_calibration.SHOCK_RISK_SHIFTS``), so the channel vocabulary cannot drift
away from what the simulator can actually act on — ``ENGINE_CHANNELS`` is read
straight from the calibration table.

The ontology is deliberately small and inspectable. It serves three roles:

1. the *menu* an LLM (or a deterministic selector) composes a scenario from,
2. the *contract* a validator checks generated scenarios against,
3. the *anchor* for magnitudes — intensities are multipliers on the calibrated
   prior shift, bounded to a band rather than invented free-hand.

Freeman inspires the shape (actors / levers / channels / outcomes as data), but
this module deliberately keeps its own minimal ontology inside GIM with no
runtime dependency on Freeman.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import geo_calibration as geo
from .types import RISK_CLASSES, RISK_LABELS

# The channel vocabulary the engine can actually act on. Single source of truth:
# the keys of the calibrated shock table. If a channel is not here, a shock on it
# is inert (silently ignored by ``_apply_shocks``) — the validator flags that.
ENGINE_CHANNELS: Tuple[str, ...] = tuple(geo.SHOCK_RISK_SHIFTS.keys())

# Magnitude is an intensity multiplier on the calibrated prior shift. 1.0 == the
# nominal expert-prior shift; the band keeps an LLM from inventing extreme or
# negligible intensities. 0.60 matches the intensity used by the legacy
# templates, so composed scenarios stay comparable to the hand-tuned ones.
MAGNITUDE_MIN: float = 0.15
MAGNITUDE_MAX: float = 1.25
DEFAULT_MAGNITUDE: float = 0.60


@dataclass(frozen=True)
class Lever:
    """A human-meaningful pressure that resolves to exactly one engine channel."""

    id: str
    channel: str
    label: str
    label_ru: str
    triggers: Tuple[str, ...]  # normalized ru+en keyword stems
    default_magnitude: float = DEFAULT_MAGNITUDE
    indicators: Tuple[str, ...] = ()
    rationale: str = ""


# One lever per channel in v0. The structure allows several levers per channel
# later (e.g. "energy embargo" vs "grain shock" both on ``resource``) without
# touching the engine — they would just differ in label/triggers/indicators.
LEVERS: Dict[str, Lever] = {
    "sanctions": Lever(
        id="sanctions",
        channel="sanctions",
        label="Sanctions / financial pressure",
        label_ru="Санкции / финансовое давление",
        triggers=("санкц", "эмбарго", "sanction", "embargo", "финансов блокад", "swift"),
        indicators=("sanctions_pressure", "resource_gap", "debt_stress", "tail_pressure"),
        rationale="External financing and import access tighten over the horizon.",
    ),
    "alliance": Lever(
        id="alliance",
        channel="alliance",
        label="Alliance / bloc mobilization",
        label_ru="Альянс / мобилизация блока",
        # NB: "блок"/"bloc" are deliberately excluded — they are prefixes of
        # "блокада"/"blockade" (a maritime lever) and would cross-fire.
        triggers=("альянс", "коалиц", "alliance", "нато", "nato", "coalition"),
        indicators=("conflict_stress", "tension_mean", "tail_pressure"),
        rationale="Bloc alignment widens the conflict envelope and couples actors.",
    ),
    "proxy": Lever(
        id="proxy",
        channel="proxy",
        label="Proxy escalation",
        label_ru="Прокси-эскалация",
        triggers=("прокси", "ополчен", "посредник", "proxy", "militia", "insurgen"),
        indicators=("conflict_stress", "limited_proxy_escalation", "tail_pressure"),
        rationale="Arming or backing a proxy raises limited-escalation pressure.",
    ),
    "maritime": Lever(
        id="maritime",
        channel="maritime",
        label="Maritime chokepoint pressure",
        label_ru="Давление в морском узле",
        triggers=("морск", "пролив", "блокад", "strait", "maritime", "chokepoint", "ормуз", "hormuz", "малакк", "malacca"),
        indicators=("maritime_chokepoint_crisis", "trade_fragmentation", "resource_gap"),
        rationale="A chokepoint squeeze disrupts trade and energy flows.",
    ),
    "resource": Lever(
        id="resource",
        channel="resource",
        label="Resource / energy / food shock",
        label_ru="Ресурсный / энергетический / продовольственный шок",
        triggers=("ресурс", "энерг", "нефт", "газ", "продовольств", "зерн", "resource", "energy", "oil", "gas", "grain", "food"),
        indicators=("resource_gap", "social_stress", "sovereign_financial_crisis"),
        rationale="A supply shortfall stresses households and public finances.",
    ),
    "domestic": Lever(
        id="domestic",
        channel="domestic",
        label="Domestic destabilization",
        label_ru="Внутренняя дестабилизация",
        triggers=("внутрен", "протест", "беспорядк", "репресс", "domestic", "unrest", "protest", "crackdown", "repression"),
        indicators=("social_stress", "social_unrest_without_military", "internal_destabilization"),
        rationale="Domestic grievance raises unrest and suppression pressure.",
    ),
    "technology": Lever(
        id="technology",
        channel="technology",
        label="Technology / export controls",
        label_ru="Технологии / экспортный контроль",
        triggers=("технолог", "экспортн контрол", "чип", "полупровод", "tech", "export control", "semiconductor", "chip"),
        indicators=("trade_fragmentation", "sovereign_financial_crisis", "tail_pressure"),
        rationale="Tech denial fragments supply chains and strains finance.",
    ),
    "cyber": Lever(
        id="cyber",
        channel="cyber",
        label="Cyber operations",
        label_ru="Кибероперации",
        triggers=("кибер", "cyber", "хакер", "hack", "infrastructure attack", "атак на инфраструктур"),
        indicators=("conflict_stress", "direct_strike_exchange", "tail_pressure"),
        rationale="Cyber disruption can spill into direct-exchange pressure.",
    ),
}


def _norm(text: str) -> str:
    """Lowercase and collapse to alnum tokens, keeping Cyrillic (unlike the
    Latin-only normalizer in ``scenario_compiler``)."""

    return re.sub(r"[^0-9a-zа-яё]+", " ", text.lower()).strip()


def clamp_magnitude(value: float) -> float:
    return max(MAGNITUDE_MIN, min(MAGNITUDE_MAX, float(value)))


def channel_risk_shifts(channel: str) -> Dict[str, float]:
    """The calibrated risk-class shifts a channel applies (nominal magnitude)."""

    return {
        risk_name: weight.value
        for risk_name, weight in geo.SHOCK_RISK_SHIFTS.get(channel, {}).items()
    }


def dominant_risk(channel: str) -> Optional[str]:
    shifts = channel_risk_shifts(channel)
    if not shifts:
        return None
    return max(shifts, key=shifts.get)


def levers_for_channel(channel: str) -> List[Lever]:
    return [lever for lever in LEVERS.values() if lever.channel == channel]


def _trigger_fires(normalized_prompt: str, trigger: str) -> bool:
    # Word-boundary (prefix) match, so a stem like "санкц" still catches
    # "санкции" but "oil" does not fire inside "boil" and "gas" not in
    # "Madagascar". The trailing boundary is intentionally open to allow
    # inflections ("sanction" -> "sanctions").
    pattern = r"\b" + re.escape(_norm(trigger))
    return re.search(pattern, normalized_prompt) is not None


def match_levers(prompt: str) -> List[str]:
    """Return ids of levers whose triggers fire on the prompt (deterministic)."""

    normalized = _norm(prompt)
    hits: List[str] = []
    for lever_id, lever in LEVERS.items():
        if any(_trigger_fires(normalized, trigger) for trigger in lever.triggers):
            hits.append(lever_id)
    return hits


def ontology_spec(world: Any | None = None) -> Dict[str, Any]:
    """Machine-readable menu handed to an LLM (or selector): the bounded set of
    levers, the engine channels, risk classes, magnitude band and — if a world
    is supplied — the resolvable actor names."""

    spec: Dict[str, Any] = {
        "engine_channels": list(ENGINE_CHANNELS),
        "magnitude_range": [MAGNITUDE_MIN, MAGNITUDE_MAX],
        "default_magnitude": DEFAULT_MAGNITUDE,
        "risk_classes": [
            {"id": risk_id, "label": RISK_LABELS.get(risk_id, risk_id)}
            for risk_id in RISK_CLASSES
        ],
        "levers": [
            {
                "id": lever.id,
                "channel": lever.channel,
                "label": lever.label,
                "label_ru": lever.label_ru,
                "default_magnitude": lever.default_magnitude,
                "dominant_risk": dominant_risk(lever.channel),
                "risk_shifts": channel_risk_shifts(lever.channel),
                "indicators": list(lever.indicators),
                "rationale": lever.rationale,
            }
            for lever in LEVERS.values()
        ],
    }
    if world is not None:
        spec["actors"] = sorted(agent.name for agent in world.agents.values())
    return spec


def validate_scenario(scenario: Any, world: Any | None = None) -> List[str]:
    """Check a (possibly LLM-authored) scenario against the ontology contract.

    Returns a list of human-readable problems; empty means the scenario is safe
    to hand to the engine. This is the guardrail that keeps generated scenarios
    *real* (channels the engine honours) and *bounded* (magnitudes in band)."""

    problems: List[str] = []

    for index, shock in enumerate(scenario.shocks):
        if shock.channel not in ENGINE_CHANNELS:
            problems.append(
                f"shock[{index}]: channel '{shock.channel}' is not an engine channel "
                f"(allowed: {', '.join(ENGINE_CHANNELS)}); it would be silently ignored."
            )
        if not (MAGNITUDE_MIN <= shock.magnitude <= MAGNITUDE_MAX):
            problems.append(
                f"shock[{index}]: magnitude {shock.magnitude:.3f} outside calibrated band "
                f"[{MAGNITUDE_MIN}, {MAGNITUDE_MAX}]."
            )

    for risk_name in scenario.risk_biases:
        if risk_name not in RISK_CLASSES:
            problems.append(
                f"risk_bias '{risk_name}' is not a known risk class."
            )

    if not scenario.actor_ids:
        problems.append("scenario resolves to no actors.")

    if world is not None and scenario.unresolved_actor_names:
        problems.append(
            "unresolved actors: " + ", ".join(scenario.unresolved_actor_names)
        )

    return problems
