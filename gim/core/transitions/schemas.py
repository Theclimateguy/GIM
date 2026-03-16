from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CriticalFieldSnapshot:
    gdp: float
    capital: float
    public_debt: float
    trust_gov: float
    social_tension: float


@dataclass
class BaselineState:
    world_metrics: dict[str, float] = field(default_factory=dict)
    critical_fields_by_agent: dict[str, CriticalFieldSnapshot] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EventDetections:
    cards: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PropagationDeltas:
    world_metrics: dict[str, float] = field(default_factory=dict)
    critical_fields_by_agent: dict[str, CriticalFieldSnapshot] = field(default_factory=dict)
    cards: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReconciledWrites:
    world_metrics: dict[str, float] = field(default_factory=dict)
    critical_fields_by_agent: dict[str, CriticalFieldSnapshot] = field(default_factory=dict)
    invariants: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TransitionEnvelope:
    pre: BaselineState = field(default_factory=BaselineState)
    baseline: BaselineState = field(default_factory=BaselineState)
    detect: EventDetections = field(default_factory=EventDetections)
    propagate: PropagationDeltas = field(default_factory=PropagationDeltas)
    reconcile: ReconciledWrites = field(default_factory=ReconciledWrites)


__all__ = [
    "BaselineState",
    "CriticalFieldSnapshot",
    "EventDetections",
    "PropagationDeltas",
    "ReconciledWrites",
    "TransitionEnvelope",
]
