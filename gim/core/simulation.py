import copy
import inspect
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import calibration_params as cal
from .actions import apply_action, apply_trade_deals
from .climate import apply_climate_extreme_events, update_climate_risks, update_global_climate
from .credit_rating import update_credit_ratings
from .core import Action, AgentMemory, Observation, PolicyRecord, TGLOBAL_2023_C, WorldState
from .economy import compute_effective_interest_rate, update_economy_output, update_public_finances
from .geopolitics import apply_sanctions_effects, apply_security_actions, update_active_conflicts
from .institutions import update_institutions
from .memory import summarize_agent_memory, update_agent_memory
from .metrics import compute_crisis_flags, compute_relative_metrics
from .observation import build_observation
from .political_dynamics import (
    apply_political_constraints,
    apply_trade_barrier_effects,
    resolve_foreign_policy,
    update_relations_endogenous,
    update_political_states,
)
from .policy import llm_policy, simple_rule_based_policy
from .resources import (
    allocate_energy_reserves_and_caps,
    update_global_resource_prices,
    update_resource_stocks,
)
from .social import (
    check_debt_crisis,
    check_regime_stability,
    update_migration_flows,
    update_population,
    update_social_state,
)
from .transitions import (
    ALLOWED_LEGACY_WRITER_MODULES,
    CriticalWriteGuard,
    TransitionEnvelope,
    apply_actions_pending_deltas,
    apply_climate_pending_deltas,
    apply_economy_pending_deltas,
    apply_geopolitics_pending_deltas,
    apply_institution_pending_deltas,
    apply_social_pending_deltas,
    build_baseline_state,
    build_event_detections,
    build_propagation_snapshot,
    build_reconciled_writes,
    capture_effective_critical_fields,
    capture_critical_fields,
    reconcile_critical_fields,
    reset_transition_pending,
    resolve_guard_mode,
)

LOGGER = logging.getLogger(__name__)


def _policy_accepts_memory_summary(policy: Callable[..., Action]) -> bool:
    try:
        signature = inspect.signature(policy)
    except (TypeError, ValueError):
        return False

    positional = [
        param
        for param in signature.parameters.values()
        if param.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    has_varargs = any(
        param.kind == inspect.Parameter.VAR_POSITIONAL
        for param in signature.parameters.values()
    )
    return has_varargs or len(positional) >= 2


COUNTRY_FLAGS = {
    "United States": "🇺🇸",
    "China": "🇨🇳",
    "Japan": "🇯🇵",
    "Germany": "🇩🇪",
    "India": "🇮🇳",
    "United Kingdom": "🇬🇧",
    "France": "🇫🇷",
    "Italy": "🇮🇹",
    "Brazil": "🇧🇷",
    "Canada": "🇨🇦",
    "Russia": "🇷🇺",
    "South Korea": "🇰🇷",
    "Mexico": "🇲🇽",
    "Australia": "🇦🇺",
    "Spain": "🇪🇸",
    "Indonesia": "🇮🇩",
    "Saudi Arabia": "🇸🇦",
    "Turkey": "🇹🇷",
    "Netherlands": "🇳🇱",
    "Switzerland": "🇨🇭",
    "Rest of World": "RW",
}


def _normalize_target(value: object) -> str | None:
    if isinstance(value, str):
        candidate = value.strip()
        return candidate or None
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item.strip()
    return None


def _country_marker(name: str) -> str:
    return COUNTRY_FLAGS.get(name, "??")


def _agent_label(world: WorldState, agent_id: str | None) -> str:
    if not agent_id:
        return "unknown"
    agent = world.agents.get(agent_id)
    if agent is None:
        return agent_id
    return f"{_country_marker(agent.name)} {agent.name}"


def _format_trade_details(world: WorldState, action: Action) -> str:
    if not action.foreign_policy.proposed_trade_deals:
        return "none"

    pieces: List[str] = []
    for deal in action.foreign_policy.proposed_trade_deals[:3]:
        partner = _agent_label(world, deal.partner)
        pieces.append(
            f"{deal.direction} {deal.resource} {deal.volume_change:.1f} with {partner} ({deal.price_preference})"
        )
    if len(action.foreign_policy.proposed_trade_deals) > 3:
        pieces.append(f"+{len(action.foreign_policy.proposed_trade_deals)-3} more")
    return "; ".join(pieces)


def _format_sanctions_details(world: WorldState, action: Action) -> str:
    sanctions = action.foreign_policy.sanctions_actions
    if not sanctions:
        return "none"
    pieces: List[str] = []
    for sanc in sanctions[:3]:
        pieces.append(f"{sanc.type} -> {_agent_label(world, _normalize_target(sanc.target))}")
    if len(sanctions) > 3:
        pieces.append(f"+{len(sanctions)-3} more")
    return "; ".join(pieces)


def _format_trade_restrictions_details(world: WorldState, action: Action) -> str:
    restrictions = action.foreign_policy.trade_restrictions
    if not restrictions:
        return "none"
    pieces: List[str] = []
    for item in restrictions[:3]:
        pieces.append(f"{item.level} -> {_agent_label(world, _normalize_target(item.target))}")
    if len(restrictions) > 3:
        pieces.append(f"+{len(restrictions)-3} more")
    return "; ".join(pieces)


def _format_security_details(world: WorldState, action: Action) -> str:
    sec = action.foreign_policy.security_actions
    if sec.type == "none":
        return "none"
    return f"{sec.type} -> {_agent_label(world, _normalize_target(sec.target))}"


def _serialize_trade_deals(action: Action) -> str:
    payload = [
        {
            "partner": deal.partner,
            "resource": deal.resource,
            "direction": deal.direction,
            "volume_change": deal.volume_change,
            "price_preference": deal.price_preference,
        }
        for deal in action.foreign_policy.proposed_trade_deals
    ]
    return json.dumps(payload, ensure_ascii=False)


def _serialize_trade_realized(action: Action) -> str:
    realized = getattr(action, "_trade_realized", [])
    return json.dumps(realized, ensure_ascii=False)


def _serialize_sanctions(action: Action) -> str:
    payload = [
        {"target": s.target, "type": s.type, "reason": s.reason}
        for s in action.foreign_policy.sanctions_actions
    ]
    return json.dumps(payload, ensure_ascii=False)


def _serialize_trade_restrictions(action: Action) -> str:
    payload = [
        {"target": r.target, "level": r.level, "reason": r.reason}
        for r in action.foreign_policy.trade_restrictions
    ]
    return json.dumps(payload, ensure_ascii=False)


def _append_action_logs(
    world: WorldState,
    actions: Dict[str, Action],
    action_log: List[Dict[str, Any]],
    security_intents: Dict[str, Tuple[str, Optional[str]]],
) -> None:
    for agent_id, action in actions.items():
        agent = world.agents.get(agent_id)
        if agent is None:
            continue

        rels = list(world.relations.get(agent_id, {}).values())
        if rels:
            avg_trade_barrier = sum(r.trade_barrier for r in rels) / len(rels)
            avg_trade_intensity = sum(r.trade_intensity for r in rels) / len(rels)
            avg_trust = sum(r.trust for r in rels) / len(rels)
            avg_conflict = sum(r.conflict_level for r in rels) / len(rels)
        else:
            avg_trade_barrier = 0.0
            avg_trade_intensity = 0.0
            avg_trust = 0.0
            avg_conflict = 0.0

        intent_type, intent_target = security_intents.get(agent_id, ("none", None))
        applied_sec = action.foreign_policy.security_actions

        record = {
            "time": world.time,
            "agent_id": agent_id,
            "agent_name": agent.name,
            "alliance_block": agent.alliance_block,
            "gdp": agent.economy.gdp,
            "trust_gov": agent.society.trust_gov,
            "social_tension": agent.society.social_tension,
            "inequality_gini": agent.society.inequality_gini,
            "political_legitimacy": agent.political.legitimacy,
            "political_protest_pressure": agent.political.protest_pressure,
            "political_hawkishness": agent.political.hawkishness,
            "political_protectionism": agent.political.protectionism,
            "political_coalition_openness": agent.political.coalition_openness,
            "political_sanction_propensity": agent.political.sanction_propensity,
            "political_policy_space": agent.political.policy_space,
            "dom_tax_fuel_change": action.domestic_policy.tax_fuel_change,
            "dom_social_spending_change": action.domestic_policy.social_spending_change,
            "dom_military_spending_change": action.domestic_policy.military_spending_change,
            "dom_rd_investment_change": action.domestic_policy.rd_investment_change,
            "dom_climate_policy": action.domestic_policy.climate_policy,
            "trade_deals": _serialize_trade_deals(action),
            "trade_realized": _serialize_trade_realized(action),
            "sanctions_intent": _serialize_sanctions(action),
            "trade_restrictions_intent": _serialize_trade_restrictions(action),
            "security_intent_type": intent_type,
            "security_intent_target": intent_target,
            "security_applied_type": applied_sec.type,
            "security_applied_target": applied_sec.target,
            "active_sanctions": json.dumps(agent.active_sanctions, ensure_ascii=False),
            "avg_trade_barrier": avg_trade_barrier,
            "avg_trade_intensity": avg_trade_intensity,
            "avg_relation_trust": avg_trust,
            "avg_relation_conflict": avg_conflict,
            "credit_rating_pre_step": agent.credit_rating,
            "credit_zone_pre_step": agent.credit_zone,
            "credit_risk_score_pre_step": agent.credit_risk_score,
            "explanation": action.explanation,
        }
        action_log.append(record)


def format_policy_summary(action: Action) -> str:
    domestic = action.domestic_policy
    foreign = action.foreign_policy
    parts = []

    if abs(domestic.tax_fuel_change) > 0.1:
        parts.append(f"Tax: {domestic.tax_fuel_change:+.1f}")
    if abs(domestic.social_spending_change) > 0.1:
        parts.append(f"Social: {domestic.social_spending_change:+.1f}")
    if abs(domestic.rd_investment_change) > 0.1:
        parts.append(f"R&D: {domestic.rd_investment_change:+.1f}")
    if domestic.climate_policy != "none":
        parts.append(f"Climate: {domestic.climate_policy}")
    if foreign.proposed_trade_deals:
        parts.append(f"Trade: {len(foreign.proposed_trade_deals)} deals")
    if foreign.sanctions_actions:
        parts.append(f"Sanctions: {len(foreign.sanctions_actions)}")
    if foreign.trade_restrictions:
        parts.append(f"TradeRestr: {len(foreign.trade_restrictions)}")

    return ", ".join(parts) if parts else "No changes"


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)


def _chunked(values: List[str], chunk_size: int) -> List[List[str]]:
    return [values[i : i + chunk_size] for i in range(0, len(values), chunk_size)]


def _capture_trend_baselines(world: WorldState) -> Dict[str, Dict[str, float]]:
    baselines: Dict[str, Dict[str, float]] = {}
    for agent_id, agent in world.agents.items():
        gdp = float(agent.economy.gdp)
        baselines[agent_id] = {
            "gdp": gdp,
            "debt": float(agent.economy.public_debt),
            "debt_gdp": float(agent.economy.public_debt / max(gdp, 1e-6)),
            "trust": float(agent.society.trust_gov),
            "tension": float(agent.society.social_tension),
            "emissions": float(agent.climate.co2_annual_emissions),
        }
        agent.economy._gdp_step_start = gdp
    return baselines


def _persist_trend_baselines(
    world: WorldState,
    baselines: Dict[str, Dict[str, float]],
) -> None:
    for agent_id, baseline in baselines.items():
        agent = world.agents.get(agent_id)
        if agent is None:
            continue
        agent.economy._gdp_prev = baseline["gdp"]
        agent.economy._debt_gdp_prev = baseline["debt_gdp"]
        agent.society._trust_prev = baseline["trust"]
        agent.society._tension_prev = baseline["tension"]
        agent.climate._emissions_prev = baseline["emissions"]
        if hasattr(agent.economy, "_gdp_step_start"):
            delattr(agent.economy, "_gdp_step_start")


def _policy_record_label(action: Action) -> tuple[str, Dict[str, Any]]:
    domestic = action.domestic_policy
    foreign = action.foreign_policy
    labels: List[str] = []
    params: Dict[str, Any] = {}

    if domestic.social_spending_change <= -0.005:
        labels.append("fiscal_austerity")
        params["social_spending_change"] = round(domestic.social_spending_change, 3)
    elif domestic.social_spending_change >= 0.005:
        labels.append("social_support")
        params["social_spending_change"] = round(domestic.social_spending_change, 3)

    if domestic.military_spending_change >= 0.005:
        labels.append("military_buildup")
        params["military_spending_change"] = round(domestic.military_spending_change, 3)
    elif domestic.rd_investment_change >= 0.002:
        labels.append("innovation_push")
        params["rd_investment_change"] = round(domestic.rd_investment_change, 3)

    if domestic.tax_fuel_change >= 0.5:
        labels.append("raise_fuel_tax")
        params["tax_fuel_change"] = round(domestic.tax_fuel_change, 2)
    elif domestic.tax_fuel_change <= -0.5:
        labels.append("cut_fuel_tax")
        params["tax_fuel_change"] = round(domestic.tax_fuel_change, 2)

    if domestic.climate_policy != "none":
        labels.append(f"climate_{domestic.climate_policy}")
        params["climate_policy"] = domestic.climate_policy

    if foreign.sanctions_actions:
        labels.append("sanctions")
        params["sanctions_count"] = len(foreign.sanctions_actions)
    if foreign.trade_restrictions:
        labels.append("trade_restrictions")
        params["trade_restrictions_count"] = len(foreign.trade_restrictions)
    if foreign.proposed_trade_deals:
        labels.append("trade_rebalancing")
        params["trade_deals_count"] = len(foreign.proposed_trade_deals)
    if foreign.security_actions.type != "none":
        labels.append(str(foreign.security_actions.type))
        params["security_action"] = foreign.security_actions.type

    if not labels:
        return "status_quo", {}
    return "+".join(labels[:2]), params


def _append_policy_records(
    world: WorldState,
    actions: Dict[str, Action],
    baselines: Dict[str, Dict[str, float]],
) -> None:
    for agent_id, agent in world.agents.items():
        action = actions.get(agent_id)
        if action is None:
            continue
        baseline = baselines.get(agent_id)
        if baseline is None:
            continue

        gdp_now = float(agent.economy.gdp)
        debt_gdp_now = float(agent.economy.public_debt / max(gdp_now, 1e-6))
        action_label, action_params = _policy_record_label(action)
        record = PolicyRecord(
            step=int(world.time) + 1,
            action=action_label,
            action_params=action_params,
            gdp_delta=float((gdp_now - baseline["gdp"]) / max(baseline["gdp"], 1e-6)),
            debt_gdp_delta=float(debt_gdp_now - baseline["debt_gdp"]),
            trust_delta=float(agent.society.trust_gov - baseline["trust"]),
            tension_delta=float(agent.society.social_tension - baseline["tension"]),
            crisis_flags_after=[
                str(flag["type"])
                for flag in compute_crisis_flags(agent, world)
                if int(flag.get("active_years", 1)) > 0
            ],
        )
        agent.policy_log.append(record)
        if len(agent.policy_log) > cal.POLICY_LOG_DEPTH:
            agent.policy_log = agent.policy_log[-cal.POLICY_LOG_DEPTH :]


def _uses_async_policy(policy: Callable[[Observation], Action] | None) -> bool:
    if policy is None:
        return False
    return policy is llm_policy or bool(getattr(policy, "__gim_async_policy__", False))


def _safe_apply_policy(
    world: WorldState,
    policies: Dict[str, Callable[[Observation], Action]],
    agent_id: str,
    memory_summary: Optional[Dict[str, Any]],
) -> Action:
    policy = policies.get(agent_id)
    if policy is None:
        return simple_rule_based_policy(build_observation(world, agent_id))

    obs = build_observation(world, agent_id)
    try:
        if memory_summary is not None and _policy_accepts_memory_summary(policy):
            return policy(obs, memory_summary)
        return policy(obs)
    except Exception as exc:
        LOGGER.warning(
            "Policy function failed for %s, falling back to simple policy: %s",
            agent_id,
            exc,
        )
        return simple_rule_based_policy(obs)


def _aggregate_world_metrics(world: WorldState) -> Dict[str, float]:
    agents = list(world.agents.values())
    total_gdp = float(sum(agent.economy.gdp for agent in agents))
    total_debt = float(sum(agent.economy.public_debt for agent in agents))
    total_emissions = float(sum(agent.climate.co2_annual_emissions for agent in agents))
    avg_trust = float(
        sum(agent.society.trust_gov for agent in agents) / max(len(agents), 1)
    )
    avg_tension = float(
        sum(agent.society.social_tension for agent in agents) / max(len(agents), 1)
    )
    return {
        "total_gdp": total_gdp,
        "total_debt": total_debt,
        "total_emissions": total_emissions,
        "avg_trust": avg_trust,
        "avg_tension": avg_tension,
        "global_temperature": float(world.global_state.temperature_global),
        "global_co2": float(world.global_state.co2),
    }


def _channel_enabled(
    channel_overrides: Optional[Dict[str, bool]],
    channel_name: str,
) -> bool:
    if channel_overrides is None:
        return True
    return bool(channel_overrides.get(channel_name, True))


def _collect_detection_cards(world: WorldState) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []

    debt_watch = cal.DEBT_CRISIS_DEBT_THRESHOLD * 0.9
    rate_watch = cal.DEBT_CRISIS_RATE_THRESHOLD * 0.85
    for agent in world.agents.values():
        gdp = max(agent.economy.gdp, 1e-6)
        debt_gdp = agent.economy.public_debt / gdp
        rate = compute_effective_interest_rate(agent, world)
        if debt_gdp >= debt_watch and rate >= rate_watch:
            score = min(1.0, (debt_gdp / max(cal.DEBT_CRISIS_DEBT_THRESHOLD, 1e-6)) * (rate / max(cal.DEBT_CRISIS_RATE_THRESHOLD, 1e-6)) / 2.0)
            cards.append(
                {
                    "type": "debt_crisis_watch",
                    "agent_id": agent.id,
                    "score": float(score),
                    "debt_gdp": float(debt_gdp),
                    "rate": float(rate),
                }
            )

        if (
            agent.society.trust_gov <= cal.REGIME_COLLAPSE_TRUST_THRESHOLD + 0.05
            and agent.society.social_tension >= cal.REGIME_COLLAPSE_TENSION_THRESHOLD - 0.05
        ):
            score = min(
                1.0,
                0.5 * (1.0 - agent.society.trust_gov) + 0.5 * agent.society.social_tension,
            )
            cards.append(
                {
                    "type": "regime_crisis_watch",
                    "agent_id": agent.id,
                    "score": float(score),
                    "trust_gov": float(agent.society.trust_gov),
                    "social_tension": float(agent.society.social_tension),
                }
            )

        temp = float(world.global_state.temperature_global)
        extra_warming = max(0.0, temp - TGLOBAL_2023_C)
        temp_factor = 1.0 + cal.EVENT_TEMP_WARMING_SENS * extra_warming
        event_prob = (cal.EVENT_BASE_PROB + cal.EVENT_MAX_EXTRA_PROB * agent.climate.climate_risk) * temp_factor
        if event_prob >= 0.08:
            cards.append(
                {
                    "type": "climate_extreme_watch",
                    "agent_id": agent.id,
                    "score": float(min(1.0, event_prob)),
                    "event_prob": float(event_prob),
                    "climate_risk": float(agent.climate.climate_risk),
                }
            )

    for actor_id, rels in world.relations.items():
        for target_id, rel in rels.items():
            if actor_id >= target_id:
                continue
            if rel.at_war or rel.conflict_level >= 0.6:
                cards.append(
                    {
                        "type": "war_escalation_watch",
                        "pair": f"{actor_id}:{target_id}",
                        "score": float(max(rel.conflict_level, 0.7 if rel.at_war else 0.0)),
                        "conflict_level": float(rel.conflict_level),
                        "at_war": bool(rel.at_war),
                    }
                )

    for actor_id, actor in world.agents.items():
        if not actor.active_sanctions:
            continue
        cards.append(
            {
                "type": "sanctions_active",
                "actor_id": actor_id,
                "score": float(min(1.0, len(actor.active_sanctions) / 4.0)),
                "targets": sorted(actor.active_sanctions.keys()),
            }
        )

    cards.sort(key=lambda card: float(card.get("score", 0.0)), reverse=True)
    return cards[:50]


def _collect_propagation_cards(world: WorldState) -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    for agent in world.agents.values():
        if agent.risk.debt_crisis_active_years > 0:
            cards.append(
                {
                    "type": "debt_crisis_active",
                    "agent_id": agent.id,
                    "score": float(min(1.0, agent.risk.debt_crisis_active_years / 4.0)),
                    "active_years": int(agent.risk.debt_crisis_active_years),
                }
            )
        if agent.risk.regime_crisis_active_years > 0:
            cards.append(
                {
                    "type": "regime_crisis_active",
                    "agent_id": agent.id,
                    "score": float(min(1.0, agent.risk.regime_crisis_active_years / 4.0)),
                    "active_years": int(agent.risk.regime_crisis_active_years),
                }
            )
        if agent.economy.climate_shock_years > 0:
            cards.append(
                {
                    "type": "climate_shock_active",
                    "agent_id": agent.id,
                    "score": float(min(1.0, agent.economy.climate_shock_years / 4.0)),
                    "active_years": int(agent.economy.climate_shock_years),
                }
            )

    for actor_id, rels in world.relations.items():
        for target_id, rel in rels.items():
            if actor_id >= target_id:
                continue
            if rel.at_war:
                cards.append(
                    {
                        "type": "war_active",
                        "pair": f"{actor_id}:{target_id}",
                        "score": float(min(1.0, rel.war_years / 4.0)),
                        "war_years": int(rel.war_years),
                    }
                )

    cards.sort(key=lambda card: float(card.get("score", 0.0)), reverse=True)
    return cards[:50]


def _invariant_report(
    world: WorldState,
    baselines: Dict[str, Dict[str, float]],
) -> Dict[str, Any]:
    breaches: List[Dict[str, Any]] = []
    debt_residuals: List[Dict[str, Any]] = []

    for agent_id, agent in world.agents.items():
        if agent.economy.gdp < 0.0:
            breaches.append({"agent_id": agent_id, "field": "economy.gdp", "value": float(agent.economy.gdp)})
        if agent.economy.capital < 0.0:
            breaches.append({"agent_id": agent_id, "field": "economy.capital", "value": float(agent.economy.capital)})
        if agent.economy.population < 0.0:
            breaches.append({"agent_id": agent_id, "field": "economy.population", "value": float(agent.economy.population)})
        if agent.economy.public_debt < 0.0:
            breaches.append({"agent_id": agent_id, "field": "economy.public_debt", "value": float(agent.economy.public_debt)})
        if not (0.0 <= agent.society.trust_gov <= 1.0):
            breaches.append({"agent_id": agent_id, "field": "society.trust_gov", "value": float(agent.society.trust_gov)})
        if not (0.0 <= agent.society.social_tension <= 1.0):
            breaches.append({"agent_id": agent_id, "field": "society.social_tension", "value": float(agent.society.social_tension)})
        if not (0.0 <= agent.climate.climate_risk <= 1.0):
            breaches.append({"agent_id": agent_id, "field": "climate.climate_risk", "value": float(agent.climate.climate_risk)})
        if not (0.0 <= agent.risk.regime_stability <= 1.0):
            breaches.append({"agent_id": agent_id, "field": "risk.regime_stability", "value": float(agent.risk.regime_stability)})

        baseline = baselines.get(agent_id)
        if baseline is None:
            continue
        debt_start = float(baseline.get("debt", agent.economy.public_debt))
        debt_end = float(agent.economy.public_debt)
        expected_delta = float(agent.economy.gov_spending - agent.economy.taxes + agent.economy.interest_payments)
        residual = debt_end - debt_start - expected_delta
        debt_residuals.append(
            {
                "agent_id": agent_id,
                "residual": float(residual),
                "residual_gdp_share": float(residual / max(agent.economy.gdp, 1e-6)),
            }
        )

    for resource_name, reserve in world.global_state.global_reserves.items():
        if reserve < 0.0:
            breaches.append({"field": f"global_reserves.{resource_name}", "value": float(reserve)})

    top_residuals = sorted(
        debt_residuals,
        key=lambda item: abs(float(item["residual_gdp_share"])),
        reverse=True,
    )[:10]

    return {
        "breach_count": int(len(breaches)),
        "breaches": breaches[:50],
        "debt_accounting_residual_top10": top_residuals,
    }


def _run_phase_baseline(
    world: WorldState,
    policies: Dict[str, Callable[[Observation], Action]],
    memory: AgentMemory,
    apply_political_filters: bool,
    apply_institutions: bool,
    institution_log: Optional[List[Dict[str, Any]]],
    policy_progress: Optional[Callable[[str], None]],
) -> tuple[Dict[str, Action], Dict[str, Tuple[str, Optional[str]]]]:
    actions: Dict[str, Action] = {}
    security_intents: Dict[str, Tuple[str, Optional[str]]] = {}

    # Phase 1: baseline structural update before event state transitions.
    compute_relative_metrics(world)
    update_political_states(world)
    if apply_institutions:
        reports = update_institutions(world)
        if institution_log is not None:
            institution_log.extend(reports)

    llm_agent_ids: List[str] = []
    for agent_id in world.agents:
        policy = policies.get(agent_id)
        if policy is None:
            continue
        if _uses_async_policy(policy):
            llm_agent_ids.append(agent_id)
            continue

        action = _safe_apply_policy(
            world,
            policies,
            agent_id,
            summarize_agent_memory(memory, agent_id),
        )
        if apply_political_filters:
            action = apply_political_constraints(action, world.agents[agent_id])
        sec = action.foreign_policy.security_actions
        security_intents[agent_id] = (sec.type, sec.target)
        actions[agent_id] = action
        if policy_progress is not None:
            policy_progress(agent_id)

    if llm_agent_ids:
        max_workers = _int_env("LLM_MAX_CONCURRENCY", default=8, minimum=1)
        batch_size = _int_env("LLM_BATCH_SIZE", default=12, minimum=1)
        batch_size = min(batch_size, len(llm_agent_ids))

        for batch_ids in _chunked(llm_agent_ids, batch_size):
            with ThreadPoolExecutor(max_workers=min(max_workers, len(batch_ids))) as executor:
                futures = {
                    executor.submit(
                        _safe_apply_policy,
                        world,
                        policies,
                        agent_id,
                        summarize_agent_memory(memory, agent_id),
                    ): agent_id
                    for agent_id in batch_ids
                }
                for future in as_completed(futures):
                    agent_id = futures[future]
                    try:
                        action = future.result()
                    except Exception:
                        obs = build_observation(world, agent_id)
                        action = simple_rule_based_policy(obs)
                    if apply_political_filters:
                        action = apply_political_constraints(action, world.agents[agent_id])
                    sec = action.foreign_policy.security_actions
                    security_intents[agent_id] = (sec.type, sec.target)
                    actions[agent_id] = action
                    if policy_progress is not None:
                        policy_progress(agent_id)

    return actions, security_intents


def _run_phase_detection(world: WorldState, actions: Dict[str, Action]) -> None:
    # Phase 2: resolve event activation intent before effects propagation.
    resolve_foreign_policy(world, actions)


def _run_phase_propagation(
    world: WorldState,
    actions: Dict[str, Action],
    action_log: Optional[List[Dict[str, Any]]],
    security_intents: Dict[str, Tuple[str, Optional[str]]],
    enable_extreme_events: bool,
    channel_overrides: Optional[Dict[str, bool]],
    channel_snapshots: Optional[Dict[str, Dict[str, Any]]] = None,
) -> None:
    # Phase 3: propagate event and policy effects through coupled channels.
    reset_transition_pending(world)

    if _channel_enabled(channel_overrides, "sanctions_channel"):
        apply_sanctions_effects(world)
        apply_geopolitics_pending_deltas(world)
    apply_security_actions(world, actions)
    apply_geopolitics_pending_deltas(world)
    update_active_conflicts(world)
    apply_geopolitics_pending_deltas(world)
    if _channel_enabled(channel_overrides, "trade_barrier_channel"):
        apply_trade_barrier_effects(world)
    if channel_snapshots is not None:
        channel_snapshots["after_security_trade_barrier"] = capture_effective_critical_fields(world)

    for action in actions.values():
        apply_action(world, action, defer_critical_writes=True)
    apply_actions_pending_deltas(world)

    apply_trade_deals(world, actions, defer_critical_writes=True)
    apply_actions_pending_deltas(world)
    update_relations_endogenous(world)
    if channel_snapshots is not None:
        channel_snapshots["after_policy_trade_relations"] = capture_effective_critical_fields(world)

    if action_log is not None:
        _append_action_logs(world, actions, action_log, security_intents)

    energy_alloc = allocate_energy_reserves_and_caps(world)
    update_resource_stocks(world, energy_alloc=energy_alloc)
    update_global_resource_prices(world)

    update_global_climate(world)
    update_climate_risks(world)
    if enable_extreme_events:
        apply_climate_extreme_events(world)
    apply_climate_pending_deltas(world)

    for agent in world.agents.values():
        update_economy_output(agent, world, defer_critical_writes=True)
        apply_economy_pending_deltas(world, agent_ids=[agent.id])

    for agent in world.agents.values():
        update_public_finances(agent, world, defer_critical_writes=True)
        apply_economy_pending_deltas(world, agent_ids=[agent.id])
        check_debt_crisis(agent, world, defer_critical_writes=True)
    if channel_snapshots is not None:
        channel_snapshots["after_climate_macro"] = capture_effective_critical_fields(world)

    if _channel_enabled(channel_overrides, "migration_feedback"):
        update_migration_flows(world)
    for agent in world.agents.values():
        update_population(agent, world)
        if _channel_enabled(channel_overrides, "social_instability_feedback") and agent.id in actions:
            update_social_state(agent, actions[agent.id], world)
        if _channel_enabled(channel_overrides, "social_instability_feedback"):
            check_regime_stability(agent, world)

    # Apply queued institution deltas for critical fields in propagation phase.
    apply_institution_pending_deltas(world)
    apply_social_pending_deltas(world)


def _run_phase_reconciliation(
    world: WorldState,
    memory: AgentMemory,
    actions: Dict[str, Action],
    trend_baselines: Dict[str, Dict[str, float]],
    baseline_critical_fields: Dict[str, Any],
    propagated_critical_fields: Dict[str, Any],
    channel_snapshots: Dict[str, Dict[str, Any]],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    # Phase 4: reconcile, refresh diagnostics, and finalize the year.
    critical_accounting = reconcile_critical_fields(
        world,
        baseline=baseline_critical_fields,
        propagated=propagated_critical_fields,
        channel_snapshots=channel_snapshots,
    )
    reset_transition_pending(world)
    compute_relative_metrics(world)
    update_agent_memory(memory, world, actions)
    update_credit_ratings(world, memory)
    _append_policy_records(world, actions, trend_baselines)
    _persist_trend_baselines(world, trend_baselines)
    invariants = _invariant_report(world, trend_baselines)
    world.time += 1
    return invariants, critical_accounting


def step_world(
    world: WorldState,
    policies: Dict[str, Callable[[Observation], Action]],
    memory: Optional[AgentMemory] = None,
    enable_extreme_events: bool = True,
    apply_political_filters: bool = True,
    action_log: Optional[List[Dict[str, Any]]] = None,
    institution_log: Optional[List[Dict[str, Any]]] = None,
    apply_institutions: bool = True,
    policy_progress: Optional[Callable[[str], None]] = None,
    phase_trace: Optional[Dict[str, Any]] = None,
    channel_overrides: Optional[Dict[str, bool]] = None,
) -> WorldState:
    if memory is None:
        memory = {}
    previous_disabled_channels = getattr(world.global_state, "_ablation_disabled_channels", None)
    if channel_overrides:
        disabled_channels = {name for name, enabled in channel_overrides.items() if not enabled}
    else:
        disabled_channels = set()
    setattr(world.global_state, "_ablation_disabled_channels", disabled_channels)

    guard_mode = resolve_guard_mode(phase_trace_requested=phase_trace is not None)
    write_guard = CriticalWriteGuard(
        mode=guard_mode,
        allowed_writer_modules=set(ALLOWED_LEGACY_WRITER_MODULES),
    )

    try:
        with write_guard:
            trend_baselines = _capture_trend_baselines(world)
            transition_envelope = TransitionEnvelope()
            if phase_trace is not None:
                pre_metrics = _aggregate_world_metrics(world)
                phase_trace["pre"] = pre_metrics
                transition_envelope.pre = build_baseline_state(world, pre_metrics)

            write_guard.set_phase("baseline")
            actions, security_intents = _run_phase_baseline(
                world,
                policies,
                memory,
                apply_political_filters,
                apply_institutions,
                institution_log,
                policy_progress,
            )
            if phase_trace is not None:
                baseline_metrics = _aggregate_world_metrics(world)
                phase_trace["baseline"] = baseline_metrics
                transition_envelope.baseline = build_baseline_state(world, baseline_metrics)
            baseline_critical_fields = capture_critical_fields(world)

            write_guard.set_phase("detect")
            _run_phase_detection(world, actions)
            if phase_trace is not None:
                detect_metrics = _aggregate_world_metrics(world)
                detect_cards = _collect_detection_cards(world)
                phase_trace["detect"] = detect_metrics
                phase_trace["detect_cards"] = detect_cards
                transition_envelope.detect = build_event_detections(detect_cards)

            write_guard.set_phase("propagate")
            channel_snapshots: Dict[str, Dict[str, Any]] = {}
            _run_phase_propagation(
                world,
                actions,
                action_log,
                security_intents,
                enable_extreme_events,
                channel_overrides,
                channel_snapshots=channel_snapshots,
            )
            if phase_trace is not None:
                propagate_metrics = _aggregate_world_metrics(world)
                propagate_cards = _collect_propagation_cards(world)
                phase_trace["propagate"] = propagate_metrics
                phase_trace["propagate_cards"] = propagate_cards
                transition_envelope.propagate = build_propagation_snapshot(
                    world,
                    propagate_metrics,
                    propagate_cards,
                    metadata={"channel_snapshot_keys": sorted(channel_snapshots.keys())},
                )
            propagated_critical_fields = capture_effective_critical_fields(world)

            write_guard.set_phase("reconcile")
            invariants, critical_accounting = _run_phase_reconciliation(
                world,
                memory,
                actions,
                trend_baselines,
                baseline_critical_fields,
                propagated_critical_fields,
                channel_snapshots,
            )
            if phase_trace is not None:
                reconcile_metrics = _aggregate_world_metrics(world)
                phase_trace["reconcile"] = reconcile_metrics
                phase_trace["invariants"] = invariants
                phase_trace["critical_field_accounting"] = critical_accounting
                transition_envelope.reconcile = build_reconciled_writes(
                    world,
                    reconcile_metrics,
                    invariants,
                )
                phase_trace["transition_envelope"] = transition_envelope
                phase_trace["critical_write_guard"] = write_guard.summary()
    finally:
        if previous_disabled_channels is None:
            delattr(world.global_state, "_ablation_disabled_channels")
        else:
            setattr(world.global_state, "_ablation_disabled_channels", previous_disabled_channels)

    return world


def step_world_verbose(
    world: WorldState,
    policies: Dict[str, Callable[[Observation], Action]],
    enable_extreme_events: bool = True,
    detailed_output: bool = True,
    action_log: Optional[List[Dict[str, Any]]] = None,
    institution_log: Optional[List[Dict[str, Any]]] = None,
) -> WorldState:
    compute_relative_metrics(world)
    pre_snapshot = {
        agent_id: {
            "gdp": agent.economy.gdp,
            "trust": agent.society.trust_gov,
            "tension": agent.society.social_tension,
        }
        for agent_id, agent in world.agents.items()
    }

    print("\n " + "-" * 68)
    print(f" Year {world.time} -> {world.time + 1} | Generating actions...")
    actions: Dict[str, Action] = {}

    update_political_states(world)
    reports = update_institutions(world)
    if institution_log is not None:
        institution_log.extend(reports)

    print(" " + "-" * 68)
    print(" Country Decisions")
    print(" " + "-" * 68)

    sorted_ids = sorted(world.agents, key=lambda aid: world.agents[aid].economy.gdp, reverse=True)
    for index, agent_id in enumerate(sorted_ids, start=1):
        obs = build_observation(world, agent_id)
        policy = policies[agent_id]
        try:
            action = policy(obs)
        except Exception as exc:
            print(f"  Policy error for {agent_id}: {exc}, using simple baseline")
            action = simple_rule_based_policy(obs)
        action = apply_political_constraints(action, world.agents[agent_id])
        actions[agent_id] = action

        agent = world.agents[agent_id]
        domestic = action.domestic_policy
        marker = _country_marker(agent.name)

        print(
            f" {index:2d}. {marker} {agent.name:<18} "
            f"GDP:${agent.economy.gdp:>6.2f}T "
            f"Trust:{agent.society.trust_gov:.2f} "
            f"Tension:{agent.society.social_tension:.2f}"
        )
        print(
            f"     Domestic | FuelTax:{domestic.tax_fuel_change:+.2f} "
            f"Social:{domestic.social_spending_change:+.3f} "
            f"Military:{domestic.military_spending_change:+.3f} "
            f"R&D:{domestic.rd_investment_change:+.3f} "
            f"Climate:{domestic.climate_policy}"
        )

        if detailed_output:
            print(f"     Trade     | {_format_trade_details(world, action)}")
            print(f"     Sanctions | {_format_sanctions_details(world, action)}")
            print(f"     TradeRes  | {_format_trade_restrictions_details(world, action)}")
            print(f"     Security  | {_format_security_details(world, action)}")
            if action.explanation:
                snippet = action.explanation.strip().replace("\n", " ")
                if len(snippet) > 180:
                    snippet = snippet[:177] + "..."
                print(f"     Rationale | {snippet}")

    if detailed_output and world.institution_reports:
        print(" " + "-" * 68)
        print(" Institution Reports")
        print(" " + "-" * 68)
        for report in world.institution_reports:
            measures = report.get("measures", [])
            print(
                f" {report.get('org_id')} ({report.get('org_type')}) "
                f"Legit:{report.get('legitimacy'):.2f} "
                f"Budget:{report.get('budget'):.3f} "
                f"Measures:{measures}"
            )

    print(" " + "-" * 68)
    print(" Applying physics...", end="", flush=True)

    replay_policies = {agent_id: (lambda obs, a=actions[agent_id]: a) for agent_id in world.agents}
    world = step_world(
        world,
        replay_policies,
        enable_extreme_events=enable_extreme_events,
        apply_political_filters=False,
        action_log=action_log,
        apply_institutions=False,
    )

    print(" Done!")
    print(" " + "-" * 68)
    print(" Country Outcomes")
    print(" " + "-" * 68)
    for index, agent_id in enumerate(sorted_ids, start=1):
        agent = world.agents[agent_id]
        marker = _country_marker(agent.name)
        prev = pre_snapshot[agent_id]
        gdp_prev = max(prev["gdp"], 1e-9)
        gdp_now = agent.economy.gdp
        gdp_delta = (gdp_now / gdp_prev - 1.0) * 100.0
        trust_delta = agent.society.trust_gov - prev["trust"]
        tension_delta = agent.society.social_tension - prev["tension"]
        print(
            f" {index:2d}. {marker} {agent.name:<18} "
            f"GDP:{gdp_now:6.2f}T ({gdp_delta:+6.2f}%) "
            f"Trust:{agent.society.trust_gov:.2f} ({trust_delta:+.2f}) "
            f"Tension:{agent.society.social_tension:.2f} ({tension_delta:+.2f})"
        )

    avg_trust = sum(a.society.trust_gov for a in world.agents.values()) / len(world.agents)
    avg_tension = sum(a.society.social_tension for a in world.agents.values()) / len(world.agents)
    total_gdp = sum(a.economy.gdp for a in world.agents.values())
    total_pop = sum(a.economy.population for a in world.agents.values())

    print(f"\n Year {world.time} Summary:")
    print(
        f"    GDP: ${total_gdp:.1f}T | Pop: {total_pop/1e9:.2f}B | "
        f"Trust: {avg_trust:.3f} | Tension: {avg_tension:.3f}"
    )
    print(
        f"    CO2: {world.global_state.co2:.0f} Gt | "
        f"Temp: +{world.global_state.temperature_global:.4f}C"
    )

    return world


def run_simulation(
    world: WorldState,
    policies: Dict[str, Callable[[Observation], Action]],
    years: int,
    enable_extreme_events: bool = True,
    detailed_output: bool = True,
    action_log: Optional[List[Dict[str, Any]]] = None,
    institution_log: Optional[List[Dict[str, Any]]] = None,
) -> List[WorldState]:
    history: List[WorldState] = []
    for _ in range(years):
        history.append(copy.deepcopy(world))
        world = step_world_verbose(
            world,
            policies,
            enable_extreme_events=enable_extreme_events,
            detailed_output=detailed_output,
            action_log=action_log,
            institution_log=institution_log,
        )
    history.append(copy.deepcopy(world))
    return history
