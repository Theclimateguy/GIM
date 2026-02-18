import copy
import json
from typing import Any, Callable, Dict, List, Optional, Tuple

from .actions import apply_action, apply_trade_deals
from .climate import apply_climate_extreme_events, update_climate_risks, update_global_climate
from .core import Action, AgentMemory, Observation, WorldState
from .economy import update_economy_output, update_public_finances
from .geopolitics import apply_sanctions_effects, apply_security_actions, update_active_conflicts
from .institutions import update_institutions
from .memory import summarize_agent_memory, update_agent_memory
from .metrics import compute_relative_metrics
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


def step_world(
    world: WorldState,
    policies: Dict[str, Callable[[Observation], Action]],
    memory: Optional[AgentMemory] = None,
    enable_extreme_events: bool = True,
    apply_political_filters: bool = True,
    action_log: Optional[List[Dict[str, Any]]] = None,
    institution_log: Optional[List[Dict[str, Any]]] = None,
    apply_institutions: bool = True,
) -> WorldState:
    actions: Dict[str, Action] = {}
    security_intents: Dict[str, Tuple[str, Optional[str]]] = {}
    if memory is None:
        memory = {}

    update_political_states(world)
    if apply_institutions:
        reports = update_institutions(world)
        if institution_log is not None:
            institution_log.extend(reports)

    for agent_id in world.agents:
        policy = policies.get(agent_id)
        if policy is None:
            continue

        obs = build_observation(world, agent_id)
        memory_summary = summarize_agent_memory(memory, agent_id) if policy is llm_policy else None

        try:
            if memory_summary is None:
                action = policy(obs)
            else:
                action = policy(obs, memory_summary)
        except Exception:
            action = simple_rule_based_policy(obs)

        if apply_political_filters:
            action = apply_political_constraints(action, world.agents[agent_id])
        sec = action.foreign_policy.security_actions
        security_intents[agent_id] = (sec.type, sec.target)
        actions[agent_id] = action

    resolve_foreign_policy(world, actions)
    apply_sanctions_effects(world)
    apply_security_actions(world, actions)
    update_active_conflicts(world)
    apply_trade_barrier_effects(world)

    for action in actions.values():
        apply_action(world, action)

    apply_trade_deals(world, actions)
    update_relations_endogenous(world)

    if action_log is not None:
        _append_action_logs(world, actions, action_log, security_intents)

    energy_alloc = allocate_energy_reserves_and_caps(world)
    update_resource_stocks(world, energy_alloc=energy_alloc)
    update_global_resource_prices(world)

    update_global_climate(world)
    update_climate_risks(world)
    if enable_extreme_events:
        apply_climate_extreme_events(world)

    for agent in world.agents.values():
        update_economy_output(agent, world)

    for agent in world.agents.values():
        update_public_finances(agent, world)
        check_debt_crisis(agent, world)

    update_migration_flows(world)
    for agent in world.agents.values():
        update_population(agent, world)
        if agent.id in actions:
            update_social_state(agent, actions[agent.id], world)
        check_regime_stability(agent)

    compute_relative_metrics(world)
    update_agent_memory(memory, world, actions)

    world.time += 1
    return world


def step_world_verbose(
    world: WorldState,
    policies: Dict[str, Callable[[Observation], Action]],
    enable_extreme_events: bool = True,
    detailed_output: bool = True,
    action_log: Optional[List[Dict[str, Any]]] = None,
    institution_log: Optional[List[Dict[str, Any]]] = None,
) -> WorldState:
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
