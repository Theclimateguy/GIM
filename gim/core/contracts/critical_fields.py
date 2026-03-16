from __future__ import annotations

from dataclasses import dataclass


CRITICAL_FIELD_PATHS = (
    "economy.gdp",
    "economy.capital",
    "economy.public_debt",
    "society.trust_gov",
    "society.social_tension",
)


@dataclass(frozen=True)
class CriticalFieldContract:
    field_path: str
    canonical_writer: str
    finalization_phase: str
    allowed_delta_producers: tuple[str, ...]
    invariant: str
    notes: str


CRITICAL_FIELD_REGISTRY = {
    "economy.gdp": CriticalFieldContract(
        field_path="economy.gdp",
        canonical_writer="gim.core.transitions.reconcile",
        finalization_phase="reconcile",
        allowed_delta_producers=(
            "actions",
            "economy",
            "geopolitics",
            "social",
            "climate",
        ),
        invariant="nonnegative",
        notes="Primary output level with high multi-writer sensitivity.",
    ),
    "economy.capital": CriticalFieldContract(
        field_path="economy.capital",
        canonical_writer="gim.core.transitions.reconcile",
        finalization_phase="reconcile",
        allowed_delta_producers=(
            "economy",
            "social",
            "climate",
            "geopolitics",
        ),
        invariant="nonnegative",
        notes="Capital stock should be finalized once per year.",
    ),
    "economy.public_debt": CriticalFieldContract(
        field_path="economy.public_debt",
        canonical_writer="gim.core.transitions.reconcile",
        finalization_phase="reconcile",
        allowed_delta_producers=(
            "economy",
            "actions",
            "institutions",
            "social",
        ),
        invariant="nonnegative",
        notes="Debt accounting identity enforced at reconcile.",
    ),
    "society.trust_gov": CriticalFieldContract(
        field_path="society.trust_gov",
        canonical_writer="gim.core.transitions.reconcile",
        finalization_phase="reconcile",
        allowed_delta_producers=(
            "social",
            "actions",
            "institutions",
            "geopolitics",
            "climate",
        ),
        invariant="unit_interval",
        notes="Trust uses baseline plus explicit channel deltas.",
    ),
    "society.social_tension": CriticalFieldContract(
        field_path="society.social_tension",
        canonical_writer="gim.core.transitions.reconcile",
        finalization_phase="reconcile",
        allowed_delta_producers=(
            "social",
            "actions",
            "institutions",
            "geopolitics",
            "climate",
        ),
        invariant="unit_interval",
        notes="Tension uses baseline plus explicit channel deltas.",
    ),
}


def get_critical_field_contract(field_path: str) -> CriticalFieldContract | None:
    return CRITICAL_FIELD_REGISTRY.get(field_path)


__all__ = [
    "CRITICAL_FIELD_PATHS",
    "CRITICAL_FIELD_REGISTRY",
    "CriticalFieldContract",
    "get_critical_field_contract",
]
