"""On-the-fly scenario composition over the lightweight ontology.

This replaces the fixed-template path (``detect_template`` → one of ~6 presets)
with a *combinatorial* one: any subset of the calibrated levers, at chosen
intensities, over resolved actors. The result is a plain ``ScenarioDefinition``
the engine already runs via ``GameRunner.evaluate_scenario`` — composition adds
reach, not new math. With 8 channels the reachable space is ``2**8`` channel
subsets × intensities × actor sets, versus a handful of frozen templates.

Two front-ends share one builder and one validator:

- ``deterministic`` (default, no network): keyword → lever selection. Always
  available and fully testable, so the path works out-of-the-box.
- an LLM ``selector`` seam: a callable handed the ``ontology_spec`` that returns
  a :class:`LeverSelection`. Its output is validated against the ontology before
  it can touch the engine, so numbers stay bounded and channels stay real — the
  LLM proposes, the ontology disposes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from . import scenario_ontology as onto
from .scenario_compiler import infer_actor_names, resolve_actor_names
from .types import ScenarioDefinition, ScenarioShock

# Fallback when the world state carries no calendar metadata.
_DATA_SNAPSHOT_YEAR = 2023


class CompositionError(ValueError):
    """Raised when a (typically LLM-proposed) selection violates the ontology."""


@dataclass
class LeverSelection:
    """What a selector (deterministic or LLM) chooses: which levers, how hard,
    over which actors. This is the small, validated surface between free-form
    intent and the engine contract."""

    lever_magnitudes: Dict[str, float] = field(default_factory=dict)
    actors: List[str] = field(default_factory=list)
    horizon_months: int = 24
    rationale: str = ""


# A selector turns (prompt, ontology_spec) into a LeverSelection. The LLM seam
# has exactly this shape; the deterministic default is adapted to it below.
Selector = Callable[[str, Dict[str, Any]], LeverSelection]


def deterministic_select(prompt: str, world: Any) -> LeverSelection:
    """Keyword-driven lever selection — the no-network default."""

    lever_ids = onto.match_levers(prompt)
    magnitudes = {
        lever_id: onto.LEVERS[lever_id].default_magnitude for lever_id in lever_ids
    }
    actors = infer_actor_names(prompt, world)
    return LeverSelection(
        lever_magnitudes=magnitudes,
        actors=actors,
        rationale="deterministic keyword match over the lever ontology",
    )


def _resolve_year(world: Any) -> int:
    return int(getattr(world.global_state, "_calendar_year_base", _DATA_SNAPSHOT_YEAR))


def compose_scenario(
    prompt: str,
    world: Any,
    *,
    horizon_months: int = 24,
    selector: Optional[Selector] = None,
    display_year: Optional[int] = None,
) -> ScenarioDefinition:
    """Compose a validated ``ScenarioDefinition`` from free-form intent.

    ``selector`` defaults to the deterministic keyword matcher. Pass an LLM-backed
    selector (same signature) to author scenarios on the fly; either way the
    output is validated against the ontology before it is returned.
    """

    if selector is None:
        selection = deterministic_select(prompt, world)
    else:
        selection = selector(prompt, onto.ontology_spec(world))

    actor_inputs = selection.actors or infer_actor_names(prompt, world)
    actor_ids, actor_names, unresolved = resolve_actor_names(world, actor_inputs)

    shocks: List[ScenarioShock] = []
    indicators: List[str] = []
    for lever_id, raw_magnitude in selection.lever_magnitudes.items():
        lever = onto.LEVERS.get(lever_id)
        if lever is None:
            raise CompositionError(f"unknown lever id: {lever_id}")
        magnitude = onto.clamp_magnitude(raw_magnitude)
        shocks.append(
            ScenarioShock(
                channel=lever.channel,
                magnitude=magnitude,
                cadence="monthly",
                rationale=lever.rationale,
            )
        )
        indicators.extend(lever.indicators)

    base_year = _resolve_year(world)
    resolved_display_year = display_year if display_year is not None else base_year
    selected_labels = [onto.LEVERS[lid].label for lid in selection.lever_magnitudes]
    narrative = (
        "Composed scenario over " + (", ".join(selected_labels) or "no active levers")
        + f" for {', '.join(actor_names) or 'default actors'}."
    )

    scenario = ScenarioDefinition(
        id=f"composed-{base_year}-{abs(hash((prompt, tuple(sorted(selection.lever_magnitudes))))) % 100000:05d}",
        title="Composed scenario",
        template_id="composed",
        source_prompt=prompt,
        base_year=base_year,
        display_year=resolved_display_year,
        horizon_months=int(selection.horizon_months or horizon_months),
        actor_ids=actor_ids,
        actor_names=actor_names,
        unresolved_actor_names=unresolved,
        actor_resolution_method="composed",
        actor_resolution_confidence=0.9 if actor_ids else 0.2,
        monitored_indicators=_dedupe(indicators),
        assumptions=[
            "Scenario composed on the fly from the calibrated lever ontology.",
            "Each shock channel is one the engine honours in GameRunner._apply_shocks.",
        ],
        narrative=narrative,
        shocks=shocks,
        risk_biases={},
        critical_focus=True,
        tags=["composed", "on-the-fly"]
        + [onto.LEVERS[lid].channel for lid in selection.lever_magnitudes],
    )

    problems = onto.validate_scenario(scenario, world)
    if problems:
        raise CompositionError("; ".join(problems))
    return scenario


def baseline_scenario(world: Any, actors: Optional[List[str]] = None) -> ScenarioDefinition:
    """A no-shock, no-bias scenario over the same actors — the comparison point
    that proves a composed scenario actually moves the engine."""

    actor_inputs = actors or [
        agent.name
        for agent in sorted(world.agents.values(), key=lambda a: a.economy.gdp, reverse=True)[:3]
    ]
    actor_ids, actor_names, unresolved = resolve_actor_names(world, actor_inputs)
    base_year = _resolve_year(world)
    return ScenarioDefinition(
        id=f"baseline-{base_year}",
        title="Baseline (no levers)",
        template_id="baseline",
        source_prompt="",
        base_year=base_year,
        display_year=base_year,
        horizon_months=24,
        actor_ids=actor_ids,
        actor_names=actor_names,
        unresolved_actor_names=unresolved,
        actor_resolution_method="baseline",
        narrative="Baseline world prior with no composed levers.",
        shocks=[],
        risk_biases={},
        tags=["baseline"],
    )


def _dedupe(values: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out
