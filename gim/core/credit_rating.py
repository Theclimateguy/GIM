from __future__ import annotations

from typing import Any, Dict

from . import calibration_params as cal
from .core import AgentState, WorldState, clamp01
from .economy import compute_effective_interest_rate
from .memory import summarize_agent_memory
from .metrics import compute_debt_stress, compute_protest_risk, compute_reserve_years

PRIME_MAX = cal.CR_RATING_PRIME_MAX
INVESTMENT_MAX = cal.CR_RATING_INVESTMENT_MAX
SUB_INVESTMENT_MAX = cal.CR_RATING_SUB_INVESTMENT_MAX
DISTRESSED_MAX = cal.CR_RATING_DISTRESSED_MAX
RATING_MIN = cal.CR_RATING_MIN
RATING_MAX = cal.CR_RATING_MAX


def _normalize(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return clamp01((value - lo) / (hi - lo))


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    if abs(den) <= 1e-9:
        return default
    return num / den


def rating_zone(rating: int) -> str:
    if rating <= PRIME_MAX:
        return "prime"
    if rating <= INVESTMENT_MAX:
        return "investment"
    if rating <= SUB_INVESTMENT_MAX:
        return "sub_investment"
    if rating <= DISTRESSED_MAX:
        return "distressed"
    return "default"


def _inbound_sanction_pressure(world: WorldState, agent_id: str) -> tuple[float, int, int]:
    mild = 0
    strong = 0
    for actor in world.agents.values():
        sanction_type = actor.active_sanctions.get(agent_id)
        if sanction_type == "mild":
            mild += 1
        elif sanction_type == "strong":
            strong += 1
    pressure = clamp01(
        (mild + cal.CR_SANCTION_PRESSURE_STRONG_WEIGHT * strong) / cal.CR_SANCTION_PRESSURE_DIVISOR
    )
    return pressure, mild, strong


def _war_metrics(agent: AgentState, world: WorldState) -> tuple[float, float, int, int]:
    rels = world.relations.get(agent.id, {})
    war_links = 0
    high_conflict_links = 0
    war_risk = 0.0

    for target_id, rel in rels.items():
        if rel.at_war:
            war_links += 1
        if rel.conflict_level >= cal.CR_WAR_HIGH_CONFLICT_THRESHOLD:
            high_conflict_links += 1

        target = world.agents.get(target_id)
        target_mil = target.technology.military_power if target is not None else 1.0
        own_mil = max(agent.technology.military_power, 1e-6)
        military_pressure = clamp01((target_mil / own_mil - 1.0) / cal.CR_WAR_MIL_PRESSURE_SCALE)

        link_risk = (
            cal.CR_WAR_LINK_CONFLICT_W * clamp01(rel.conflict_level)
            + cal.CR_WAR_LINK_TRUST_W * (1.0 - clamp01(rel.trust))
            + cal.CR_WAR_LINK_MILITARY_W * military_pressure
        )
        war_risk = max(war_risk, link_risk)

    at_war = 1.0 if war_links > 0 else 0.0
    next_year_war_risk = clamp01(
        cal.CR_WAR_NEXT_WAR_W * war_risk
        + cal.CR_WAR_NEXT_CONFLICT_PRONE_W * clamp01(agent.risk.conflict_proneness)
        + cal.CR_WAR_NEXT_HAWKISH_W * clamp01(agent.political.hawkishness)
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
        hostility = (
            cal.CR_SANCTION_HOSTILITY_CONFLICT_W * clamp01(rel.conflict_level)
            + cal.CR_SANCTION_HOSTILITY_TRUST_W * (1.0 - clamp01(rel.trust))
        )
        propensity = clamp01(actor.political.sanction_propensity)
        candidate = max(
            candidate,
            clamp01(
                cal.CR_SANCTION_NEXT_HOSTILITY_W * hostility
                + cal.CR_SANCTION_NEXT_PROPENSITY_W * propensity
            ),
        )
    return candidate


def _social_structural_risk(agent: AgentState) -> tuple[float, float]:
    gini = _normalize(agent.society.inequality_gini, cal.CR_SOCIAL_GINI_LO, cal.CR_SOCIAL_GINI_HI)
    unemployment = _normalize(
        agent.economy.unemployment,
        cal.CR_SOCIAL_UNEMPLOYMENT_LO,
        cal.CR_SOCIAL_UNEMPLOYMENT_HI,
    )
    inflation = _normalize(
        agent.economy.inflation,
        cal.CR_SOCIAL_INFLATION_LO,
        cal.CR_SOCIAL_INFLATION_HI,
    )
    water = clamp01(agent.risk.water_stress)

    reserves = compute_reserve_years(agent)
    food_years = reserves.get("food", 5.0)
    food_stress = clamp01(
        (cal.CR_SOCIAL_FOOD_YEARS_CAP - min(food_years, cal.CR_SOCIAL_FOOD_YEARS_CAP))
        / cal.CR_SOCIAL_FOOD_YEARS_CAP
    )

    structural = clamp01(
        cal.CR_SOCIAL_STRUCTURAL_GINI_W * gini
        + cal.CR_SOCIAL_STRUCTURAL_UNEMPLOYMENT_W * unemployment
        + cal.CR_SOCIAL_STRUCTURAL_INFLATION_W * inflation
        + cal.CR_SOCIAL_STRUCTURAL_WATER_W * water
        + cal.CR_SOCIAL_FOOD_STRESS_W * food_stress
    )

    social_spending_share = clamp01(_safe_div(agent.economy.social_spending, max(agent.economy.gdp, 1e-6)))
    management = clamp01(
        cal.CR_SOCIAL_MANAGEMENT_TRUST_W * clamp01(agent.society.trust_gov)
        + cal.CR_SOCIAL_MANAGEMENT_POLICY_W * clamp01(agent.political.policy_space)
        + cal.CR_SOCIAL_MANAGEMENT_STABILITY_W * clamp01(agent.risk.regime_stability)
        + cal.CR_SOCIAL_MANAGEMENT_SPENDING_W
        * _normalize(social_spending_share, cal.CR_SOCIAL_SPENDING_LO, cal.CR_SOCIAL_SPENDING_HI)
    )
    return structural, management


def _credit_risk_components(agent: AgentState, world: WorldState, memory_summary: Dict[str, Any]) -> Dict[str, float]:
    gdp = max(agent.economy.gdp, 1e-6)
    debt_gdp = _safe_div(agent.economy.public_debt, gdp)
    interest_rate = compute_effective_interest_rate(agent, world)
    debt_stress = clamp01(compute_debt_stress(agent) / 3.0)
    debt_crisis_now = 1.0 if agent.risk.debt_crisis_active_years > 0 else 0.0
    fx_crisis_now = 1.0 if agent.risk.fx_crisis_active_years > 0 else 0.0

    gdp_trend = float(memory_summary.get("gdp_trend", 0.0))
    gdp_trend_ratio = _safe_div(gdp_trend, gdp)
    growth_deterioration = _normalize(
        -gdp_trend_ratio,
        cal.CR_GROWTH_DETERIORATION_LO,
        cal.CR_GROWTH_DETERIORATION_HI,
    )

    financial_now = clamp01(
        cal.CR_FINANCIAL_NOW_DEBT_W
        * _normalize(debt_gdp, cal.CR_FINANCIAL_DEBT_GDP_LO, cal.CR_FINANCIAL_DEBT_GDP_HI)
        + cal.CR_FINANCIAL_NOW_RATE_W
        * _normalize(interest_rate, cal.CR_FINANCIAL_RATE_LO, cal.CR_FINANCIAL_RATE_HI)
        + cal.CR_FINANCIAL_NOW_STRESS_W * debt_stress
        + cal.CR_FINANCIAL_NOW_CRISIS_W * max(debt_crisis_now, fx_crisis_now)
    )
    financial_next = clamp01(
        cal.CR_FINANCIAL_NEXT_STRESS_W * debt_stress
        + cal.CR_FINANCIAL_NEXT_GROWTH_W * growth_deterioration
    )
    financial_risk = clamp01(
        cal.CR_FINANCIAL_BLEND_NOW_W * financial_now
        + cal.CR_FINANCIAL_BLEND_NEXT_W * financial_next
    )

    at_war, next_year_war_risk, war_links, high_conflict_links = _war_metrics(agent, world)
    war_risk = clamp01(cal.CR_WAR_BLEND_AT_WAR_W * at_war + cal.CR_WAR_BLEND_NEXT_W * next_year_war_risk)

    protest_risk = clamp01(compute_protest_risk(agent))
    trust = clamp01(agent.society.trust_gov)
    tension = clamp01(agent.society.social_tension)
    regime_fragility = 1.0 - clamp01(agent.risk.regime_stability)
    collapsed_now = 1.0 if agent.risk.regime_crisis_active_years > 0 else 0.0

    tension_trend = float(memory_summary.get("tension_trend", 0.0))
    trust_trend = float(memory_summary.get("trust_trend", 0.0))
    next_year_revolution_risk = clamp01(
        cal.CR_REV_PROTEST_W * protest_risk
        + cal.CR_REV_TENSION_W * tension
        + cal.CR_REV_TRUST_W * (1.0 - trust)
        + cal.CR_REV_FRAGILITY_W * regime_fragility
        + cal.CR_REV_TREND_W
        * _normalize(tension_trend - trust_trend, cal.CR_REV_TREND_LO, cal.CR_REV_TREND_HI)
    )

    structural_risk, management_strength = _social_structural_risk(agent)
    social_risk = clamp01(
        cal.CR_SOCIAL_RISK_REV_W * next_year_revolution_risk
        + cal.CR_SOCIAL_RISK_STRUCT_W * structural_risk
        + cal.CR_SOCIAL_RISK_COLLAPSE_W * collapsed_now
        - cal.CR_SOCIAL_RISK_MANAGEMENT_W * management_strength
    )

    sanction_now, mild_count, strong_count = _inbound_sanction_pressure(world, agent.id)
    sanction_next = _sanction_risk_next_year(agent, world)
    sanctions_risk = clamp01(
        cal.CR_SANCTIONS_BLEND_NOW_W * sanction_now
        + cal.CR_SANCTIONS_BLEND_NEXT_W * sanction_next
    )

    fx_buffer = _safe_div(agent.economy.fx_reserves, gdp)
    reserves = compute_reserve_years(agent)
    reserve_risk = clamp01(
        cal.CR_RESERVE_RISK_ENERGY_W
        * _normalize(
            cal.CR_RESERVE_ENERGY_YEARS
            - min(reserves.get("energy", cal.CR_RESERVE_ENERGY_YEARS), cal.CR_RESERVE_ENERGY_YEARS),
            0.0,
            cal.CR_RESERVE_ENERGY_YEARS,
        )
        + cal.CR_RESERVE_RISK_FOOD_W
        * _normalize(
            cal.CR_RESERVE_FOOD_YEARS
            - min(reserves.get("food", cal.CR_RESERVE_FOOD_YEARS), cal.CR_RESERVE_FOOD_YEARS),
            0.0,
            cal.CR_RESERVE_FOOD_YEARS,
        )
        + cal.CR_RESERVE_RISK_METALS_W
        * _normalize(
            cal.CR_RESERVE_METALS_YEARS
            - min(reserves.get("metals", cal.CR_RESERVE_METALS_YEARS), cal.CR_RESERVE_METALS_YEARS),
            0.0,
            cal.CR_RESERVE_METALS_YEARS,
        )
    )
    macro_risk = clamp01(
        cal.CR_MACRO_GROWTH_W
        * _normalize(-gdp_trend_ratio, cal.CR_GROWTH_DETERIORATION_LO, cal.CR_GROWTH_DETERIORATION_HI)
        + cal.CR_MACRO_UNEMPLOYMENT_W
        * _normalize(agent.economy.unemployment, cal.CR_MACRO_UNEMPLOYMENT_LO, cal.CR_MACRO_UNEMPLOYMENT_HI)
        + cal.CR_MACRO_INFLATION_W
        * _normalize(agent.economy.inflation, cal.CR_MACRO_INFLATION_LO, cal.CR_MACRO_INFLATION_HI)
        + cal.CR_MACRO_FX_BUFFER_W
        * _normalize(
            cal.CR_MACRO_FX_BUFFER_CAP - min(fx_buffer, cal.CR_MACRO_FX_BUFFER_CAP),
            0.0,
            cal.CR_MACRO_FX_BUFFER_CAP,
        )
        + cal.CR_MACRO_RESERVE_W * reserve_risk
    )

    total_risk_score = clamp01(
        cal.CR_TOTAL_FINANCIAL_W * financial_risk
        + cal.CR_TOTAL_WAR_W * war_risk
        + cal.CR_TOTAL_SOCIAL_W * social_risk
        + cal.CR_TOTAL_SANCTIONS_W * sanctions_risk
        + cal.CR_TOTAL_MACRO_W * macro_risk
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
        "fx_crisis_now": fx_crisis_now,
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
