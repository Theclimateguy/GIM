from __future__ import annotations

from typing import Dict


_TRANSITION_CRITICAL_PENDING_ATTR = "_transition_critical_pending"
_CRITICAL_FIELDS = ("gdp", "capital", "public_debt", "trust_gov", "social_tension")


def get_transition_pending(world) -> Dict[str, Dict[str, float]]:
    pending = getattr(world.global_state, _TRANSITION_CRITICAL_PENDING_ATTR, None)
    if pending is None:
        pending = {}
        setattr(world.global_state, _TRANSITION_CRITICAL_PENDING_ATTR, pending)
    return pending


def clear_transition_pending(world) -> None:
    setattr(world.global_state, _TRANSITION_CRITICAL_PENDING_ATTR, {})


def add_transition_delta(
    world,
    agent_id: str,
    *,
    gdp: float = 0.0,
    capital: float = 0.0,
    public_debt: float = 0.0,
    trust_gov: float = 0.0,
    social_tension: float = 0.0,
) -> None:
    pending = get_transition_pending(world)
    values = pending.setdefault(
        agent_id,
        {field: 0.0 for field in _CRITICAL_FIELDS},
    )
    values["gdp"] += float(gdp)
    values["capital"] += float(capital)
    values["public_debt"] += float(public_debt)
    values["trust_gov"] += float(trust_gov)
    values["social_tension"] += float(social_tension)


# --- Debt-flow ledger (Phase 2.5 / T1.1) ---------------------------------------------
# Records every public_debt write by its economic source so the fiscal identity closes:
# Delta(debt) == sum of recorded flows. Makes the crisis "haircut" an explicit, labelled
# flow (restructuring) rather than an unexplained shock. Recording only — debt unchanged.

_DEBT_FLOW_LEDGER_ATTR = "_debt_flow_ledger"
DEBT_FLOW_SOURCES = ("fiscal", "restructuring", "policy", "institution")


def get_debt_flows(world) -> Dict[str, Dict[str, float]]:
    ledger = getattr(world.global_state, _DEBT_FLOW_LEDGER_ATTR, None)
    if ledger is None:
        ledger = {}
        setattr(world.global_state, _DEBT_FLOW_LEDGER_ATTR, ledger)
    return ledger


def reset_debt_flows(world) -> None:
    setattr(world.global_state, _DEBT_FLOW_LEDGER_ATTR, {})


def record_debt_flow(world, agent_id: str, source: str, amount: float) -> None:
    if not amount:
        return
    ledger = get_debt_flows(world)
    record = ledger.setdefault(agent_id, {s: 0.0 for s in DEBT_FLOW_SOURCES})
    record[source] = record.get(source, 0.0) + float(amount)

