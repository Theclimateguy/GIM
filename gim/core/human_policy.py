from __future__ import annotations

import copy
from typing import Any, Callable, Dict, Mapping

from .core import (
    Action,
    DomesticPolicy,
    FinancePolicy,
    ForeignPolicy,
    Observation,
    SanctionsAction,
    SecurityActions,
    TradeDeal,
    TradeRestriction,
)
from .policy import _normalize_action_for_stability


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _as_trade_deals(raw: Any) -> list[TradeDeal]:
    deals: list[TradeDeal] = []
    if not isinstance(raw, list):
        return deals
    for item in raw:
        if not isinstance(item, dict):
            continue
        deals.append(
            TradeDeal(
                partner=str(item.get("partner", "")).strip(),
                resource=str(item.get("resource", "energy")).strip() or "energy",
                direction=str(item.get("direction", "import")).strip() or "import",
                volume_change=_to_float(item.get("volume_change", 0.0)),
                price_preference=str(item.get("price_preference", "fair")).strip() or "fair",
            )
        )
    return deals


def _as_sanctions(raw: Any) -> list[SanctionsAction]:
    sanctions: list[SanctionsAction] = []
    if not isinstance(raw, list):
        return sanctions
    for item in raw:
        if not isinstance(item, dict):
            continue
        target = str(item.get("target", "")).strip()
        if not target:
            continue
        sanctions.append(
            SanctionsAction(
                target=target,
                type=str(item.get("type", "none")).strip() or "none",
                reason=str(item.get("reason", "")).strip(),
            )
        )
    return sanctions


def _as_restrictions(raw: Any) -> list[TradeRestriction]:
    restrictions: list[TradeRestriction] = []
    if not isinstance(raw, list):
        return restrictions
    for item in raw:
        if not isinstance(item, dict):
            continue
        target = str(item.get("target", "")).strip()
        if not target:
            continue
        restrictions.append(
            TradeRestriction(
                target=target,
                level=str(item.get("level", "none")).strip() or "none",
                reason=str(item.get("reason", "")).strip(),
            )
        )
    return restrictions


def action_from_intent(
    intent: Mapping[str, Any] | Action,
    *,
    agent_id: str,
    time: int,
) -> Action:
    if isinstance(intent, Action):
        action = copy.deepcopy(intent)
        action.agent_id = str(action.agent_id or agent_id)
        action.time = _to_int(action.time, time)
        return _normalize_action_for_stability(action)

    root = _as_dict(intent)
    if "action" in root and isinstance(root.get("action"), dict):
        root = _as_dict(root["action"])

    domestic_raw = _as_dict(root.get("domestic_policy", root.get("domestic", {})))
    foreign_raw = _as_dict(root.get("foreign_policy", root.get("foreign", {})))
    finance_raw = _as_dict(root.get("finance", {}))
    security_raw = _as_dict(foreign_raw.get("security_actions", foreign_raw.get("security", {})))

    action = Action(
        agent_id=str(root.get("agent_id", agent_id)).strip() or agent_id,
        time=_to_int(root.get("time", time), time),
        domestic_policy=DomesticPolicy(
            tax_fuel_change=_to_float(domestic_raw.get("tax_fuel_change", 0.0)),
            social_spending_change=_to_float(domestic_raw.get("social_spending_change", 0.0)),
            military_spending_change=_to_float(domestic_raw.get("military_spending_change", 0.0)),
            rd_investment_change=_to_float(domestic_raw.get("rd_investment_change", 0.0)),
            climate_policy=str(domestic_raw.get("climate_policy", "none")).strip() or "none",
        ),
        foreign_policy=ForeignPolicy(
            proposed_trade_deals=_as_trade_deals(foreign_raw.get("proposed_trade_deals", [])),
            sanctions_actions=_as_sanctions(foreign_raw.get("sanctions_actions", [])),
            trade_restrictions=_as_restrictions(foreign_raw.get("trade_restrictions", [])),
            security_actions=SecurityActions(
                type=str(security_raw.get("type", "none")).strip() or "none",
                target=str(security_raw.get("target", "")).strip() or None,
            ),
        ),
        finance=FinancePolicy(
            borrow_from_global_markets=_to_float(finance_raw.get("borrow_from_global_markets", 0.0)),
            use_fx_reserves_change=_to_float(finance_raw.get("use_fx_reserves_change", 0.0)),
        ),
        explanation=str(root.get("explanation", "human intent")).strip() or "human intent",
    )
    return _normalize_action_for_stability(action)


def make_human_policy(intent: Mapping[str, Any] | Action) -> Callable[[Observation], Action]:
    def _policy(obs: Observation) -> Action:
        return action_from_intent(intent, agent_id=obs.agent_id, time=obs.time)

    return _policy


def make_human_policy_map(
    intents_by_agent: Mapping[str, Mapping[str, Any] | Action],
) -> Dict[str, Callable[[Observation], Action]]:
    return {agent_id: make_human_policy(intent) for agent_id, intent in intents_by_agent.items()}
