from __future__ import annotations

from typing import Any, Dict

from .core import AgentState, WorldState, clamp01
from .economy import compute_effective_interest_rate
from .memory import summarize_agent_memory
from .metrics import compute_debt_stress, compute_protest_risk, compute_reserve_years

GREEN_MAX = 12
YELLOW_MAX = 20
RATING_MIN = 1
RATING_MAX = 26


def _normalize(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return clamp01((value - lo) / (hi - lo))


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    if abs(den) <= 1e-9:
        return default
    return num / den


def rating_zone(rating: int) -> str:
    if rating <= GREEN_MAX:
        return "green"
    if rating <= YELLOW_MAX:
        return "yellow"
    return "red"


def _inbound_sanction_pressure(world: WorldState, agent_id: str) -> tuple[float, int, int]:
    mild = 0
    strong = 0
    for actor in world.agents.values():
        sanction_type = actor.active_sanctions.get(agent_id)
        if sanction_type == "mild":
            mild += 1
        elif sanction_type == "strong":
            strong += 1
    pressure = clamp01((mild + 2.0 * strong) / 8.0)
    return pressure, mild, strong


def _war_metrics(agent: AgentState, world: WorldState) -> tuple[float, float, int, int]:
    rels = world.relations.get(agent.id, {})
    war_links = 0
    high_conflict_links = 0
    war_risk = 0.0

    for target_id, rel in rels.items():
        if rel.at_war:
            war_links += 1
        if rel.conflict_level >= 0.55:
            high_conflict_links += 1

        target = world.agents.get(target_id)
        target_mil = target.technology.military_power if target is not None else 1.0
        own_mil = max(agent.technology.military_power, 1e-6)
        military_pressure = clamp01((target_mil / own_mil - 1.0) / 1.5)

        link_risk = (
            0.55 * clamp01(rel.conflict_level)
            + 0.25 * (1.0 - clamp01(rel.trust))
            + 0.20 * military_pressure
        )
        war_risk = max(war_risk, link_risk)

    at_war = 1.0 if war_links > 0 else 0.0
    next_year_war_risk = clamp01(
        0.65 * war_risk
        + 0.20 * clamp01(agent.risk.conflict_proneness)
        + 0.15 * clamp01(agent.political.hawkishness)
    )
    return at_war, next_year_war_risk, war_links, high_conflict_links


def _sanction_risk_next_year(agent: AgentState, world: WorldState) -> float:
    rels = world.relations.get(agent.id, {})
    if not rels:
        return 0.0

    candidate = 0.0
    for actor_id, rel in rels.items():
        actor = world.agents.get(actor_id)
        if actor is None:
            continue
        hostility = 0.55 * clamp01(rel.conflict_level) + 0.45 * (1.0 - clamp01(rel.trust))
        propensity = clamp01(actor.political.sanction_propensity)
        candidate = max(candidate, clamp01(0.6 * hostility + 0.4 * propensity))
    return candidate


def _social_structural_risk(agent: AgentState) -> tuple[float, float]:
    gini = _normalize(agent.society.inequality_gini, 30.0, 65.0)
    unemployment = _normalize(agent.economy.unemployment, 0.05, 0.25)
    inflation = _normalize(agent.economy.inflation, 0.02, 0.15)
    water = clamp01(agent.risk.water_stress)

    reserves = compute_reserve_years(agent)
    food_years = reserves.get("food", 5.0)
    food_stress = clamp01((2.0 - min(food_years, 2.0)) / 2.0)

    structural = clamp01(
        0.30 * gini
        + 0.20 * unemployment
        + 0.15 * inflation
        + 0.20 * water
        + 0.15 * food_stress
    )

    social_spending_share = clamp01(_safe_div(agent.economy.social_spending, max(agent.economy.gdp, 1e-6)))
    management = clamp01(
        0.35 * clamp01(agent.society.trust_gov)
        + 0.25 * clamp01(agent.political.policy_space)
        + 0.20 * clamp01(agent.risk.regime_stability)
        + 0.20 * _normalize(social_spending_share, 0.04, 0.20)
    )
    return structural, management


def _credit_risk_components(agent: AgentState, world: WorldState, memory_summary: Dict[str, Any]) -> Dict[str, float]:
    gdp = max(agent.economy.gdp, 1e-6)
    debt_gdp = _safe_div(agent.economy.public_debt, gdp)
    interest_rate = compute_effective_interest_rate(agent, world)
    debt_stress = clamp01(compute_debt_stress(agent) / 3.0)
    debt_crisis_now = 1.0 if bool(getattr(agent, "_debt_crisis_this_step", False)) else 0.0

    gdp_trend = float(memory_summary.get("gdp_trend", 0.0))
    gdp_trend_ratio = _safe_div(gdp_trend, gdp)
    growth_deterioration = _normalize(-gdp_trend_ratio, 0.01, 0.20)

    financial_now = clamp01(
        0.35 * _normalize(debt_gdp, 0.6, 1.8)
        + 0.25 * _normalize(interest_rate, 0.04, 0.20)
        + 0.25 * debt_stress
        + 0.15 * debt_crisis_now
    )
    financial_next = clamp01(0.65 * debt_stress + 0.35 * growth_deterioration)
    financial_risk = clamp01(0.60 * financial_now + 0.40 * financial_next)

    at_war, next_year_war_risk, war_links, high_conflict_links = _war_metrics(agent, world)
    war_risk = clamp01(0.60 * at_war + 0.40 * next_year_war_risk)

    protest_risk = clamp01(compute_protest_risk(agent))
    trust = clamp01(agent.society.trust_gov)
    tension = clamp01(agent.society.social_tension)
    regime_fragility = 1.0 - clamp01(agent.risk.regime_stability)
    collapsed_now = 1.0 if bool(getattr(agent, "_collapsed_this_step", False)) else 0.0

    tension_trend = float(memory_summary.get("tension_trend", 0.0))
    trust_trend = float(memory_summary.get("trust_trend", 0.0))
    next_year_revolution_risk = clamp01(
        0.30 * protest_risk
        + 0.25 * tension
        + 0.20 * (1.0 - trust)
        + 0.15 * regime_fragility
        + 0.10 * _normalize(tension_trend - trust_trend, 0.00, 0.20)
    )

    structural_risk, management_strength = _social_structural_risk(agent)
    social_risk = clamp01(
        0.55 * next_year_revolution_risk
        + 0.30 * structural_risk
        + 0.15 * collapsed_now
        - 0.20 * management_strength
    )

    sanction_now, mild_count, strong_count = _inbound_sanction_pressure(world, agent.id)
    sanction_next = _sanction_risk_next_year(agent, world)
    sanctions_risk = clamp01(0.55 * sanction_now + 0.45 * sanction_next)

    fx_buffer = _safe_div(agent.economy.fx_reserves, gdp)
    reserves = compute_reserve_years(agent)
    reserve_risk = clamp01(
        0.5 * _normalize(3.0 - min(reserves.get("energy", 3.0), 3.0), 0.0, 3.0)
        + 0.3 * _normalize(2.0 - min(reserves.get("food", 2.0), 2.0), 0.0, 2.0)
        + 0.2 * _normalize(3.0 - min(reserves.get("metals", 3.0), 3.0), 0.0, 3.0)
    )
    macro_risk = clamp01(
        0.35 * _normalize(-gdp_trend_ratio, 0.01, 0.20)
        + 0.20 * _normalize(agent.economy.unemployment, 0.05, 0.22)
        + 0.15 * _normalize(agent.economy.inflation, 0.02, 0.12)
        + 0.15 * _normalize(0.20 - min(fx_buffer, 0.20), 0.0, 0.20)
        + 0.15 * reserve_risk
    )

    total_risk_score = clamp01(
        0.25 * financial_risk
        + 0.20 * war_risk
        + 0.22 * social_risk
        + 0.13 * sanctions_risk
        + 0.20 * macro_risk
    )

    return {
        "financial_risk": financial_risk,
        "war_risk": war_risk,
        "social_risk": social_risk,
        "sanctions_risk": sanctions_risk,
        "macro_risk": macro_risk,
        "total_risk_score": total_risk_score,
        "debt_gdp": debt_gdp,
        "interest_rate": interest_rate,
        "debt_crisis_now": debt_crisis_now,
        "at_war_now": at_war,
        "war_links": float(war_links),
        "high_conflict_links": float(high_conflict_links),
        "protest_risk": protest_risk,
        "next_year_revolution_risk": next_year_revolution_risk,
        "structural_social_risk": structural_risk,
        "management_strength": management_strength,
        "sanction_now": sanction_now,
        "sanction_next": sanction_next,
        "inbound_sanctions_mild": float(mild_count),
        "inbound_sanctions_strong": float(strong_count),
        "macro_reserve_risk": reserve_risk,
        "gdp_trend_ratio": gdp_trend_ratio,
    }


def _risk_to_rating(risk_score: float) -> int:
    mapped = int(round(RATING_MIN + clamp01(risk_score) * (RATING_MAX - RATING_MIN)))
    return max(RATING_MIN, min(RATING_MAX, mapped))


def update_credit_ratings(world: WorldState, memory: Dict[str, Any]) -> None:
    for agent_id, agent in world.agents.items():
        summary = summarize_agent_memory(memory, agent_id)
        components = _credit_risk_components(agent, world, summary)
        rating = _risk_to_rating(components["total_risk_score"])
        zone = rating_zone(rating)

        agent.credit_rating = rating
        agent.credit_zone = zone
        agent.credit_risk_score = float(components["total_risk_score"])
        agent.credit_rating_details = components
