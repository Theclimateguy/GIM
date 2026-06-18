import math
from typing import Dict

from . import calibration_params as cal
from .core import AgentState, WorldState, effective_trade_intensity


def compute_reserve_years(agent: AgentState) -> Dict[str, float]:
    eps = 1e-6
    reserve_years: Dict[str, float] = {}
    for name, resource in agent.resources.items():
        reserve_years[name] = resource.own_reserve / max(resource.production, eps)
    return reserve_years


def compute_relative_metrics(world: WorldState) -> None:
    agents = list(world.agents.values())
    total_gdp = sum(a.economy.gdp for a in agents)
    if total_gdp <= 0.0:
        total_gdp = 1e-6

    sorted_agents = sorted(agents, key=lambda a: a.economy.gdp, reverse=True)
    ranks: Dict[str, int] = {a.id: i + 1 for i, a in enumerate(sorted_agents)}

    trade_degree: Dict[str, float] = {a.id: 0.0 for a in agents}
    for agent_id, rels in world.relations.items():
        trade_degree[agent_id] = sum(effective_trade_intensity(rel) for rel in rels.values())

    for agent in agents:
        agent.economy.gdp_share = agent.economy.gdp / total_gdp
        agent.economy.gdp_rank = ranks.get(agent.id, None)

        pop = max(agent.economy.population, 1.0)
        gdp_term = math.log1p(agent.economy.gdp)
        pop_term = math.log1p(pop / 1e6)
        degree_term = math.log1p(trade_degree.get(agent.id, 0.0))
        agent.influence_score = float(gdp_term + pop_term + 0.5 * degree_term)

        own_mil = agent.technology.military_power
        neighbor_mil = []
        for neighbor_id in world.relations.get(agent.id, {}):
            other = world.agents.get(neighbor_id)
            if other is not None:
                neighbor_mil.append(other.technology.military_power)

        if neighbor_mil:
            avg_neighbor = sum(neighbor_mil) / len(neighbor_mil)
            agent.security_margin = float(own_mil / max(avg_neighbor, 1e-3))
        else:
            agent.security_margin = 1.0


def compute_debt_stress(agent: AgentState) -> float:
    gdp = max(agent.economy.gdp, 1e-6)
    debt_gdp = agent.economy.public_debt / gdp
    raw = max(0.0, debt_gdp - cal.DEBT_STRESS_THRESHOLD)
    stress = raw * agent.risk.debt_crisis_prone
    return float(min(stress, cal.DEBT_STRESS_CAP))


def compute_protest_risk(agent: AgentState) -> float:
    tension = agent.society.social_tension
    trust = agent.society.trust_gov
    gini = agent.society.inequality_gini

    base = (
        cal.PROTEST_RISK_TENSION_W * tension
        + cal.PROTEST_RISK_DISTRUST_W * (1.0 - trust)
        + cal.PROTEST_RISK_GINI_W * (gini / 100.0)
    )
    fragility = 1.0 - agent.risk.regime_stability
    risk = base * (cal.PROTEST_RISK_FRAGILITY_BASE + cal.PROTEST_RISK_FRAGILITY_SENS * fragility)

    return float(max(0.0, min(risk, 1.0)))


def compute_crisis_flags(agent: AgentState, world: WorldState) -> list[dict[str, object]]:
    flags: list[dict[str, object]] = []
    gdp = max(agent.economy.gdp, 1e-6)

    debt_years = agent.risk.debt_crisis_active_years
    if debt_years > 0:
        flags.append(
            {
                "type": "debt_crisis",
                "active_years": debt_years,
                "severity": "high" if debt_years >= 3 else "moderate",
            }
        )
    elif agent.economy.public_debt / gdp > cal.DEBT_CRISIS_DEBT_THRESHOLD * 0.85:
        flags.append(
            {
                "type": "debt_stress_elevated",
                "active_years": 0,
                "severity": "watch",
            }
        )

    fx_years = agent.risk.fx_crisis_active_years
    if fx_years > 0:
        flags.append(
            {
                "type": "fx_crisis",
                "active_years": fx_years,
                "severity": "high" if fx_years >= 2 else "moderate",
            }
        )
    elif (
        agent.risk.external_debt_ratio >= cal.FX_CRISIS_EXTERNAL_DEBT_THRESHOLD * 0.9
        and agent.risk.current_account_ratio <= cal.FX_CRISIS_CURRENT_ACCOUNT_DEFICIT_THRESHOLD * 0.75
        and agent.risk.fx_reserve_cover_months <= cal.FX_CRISIS_RESERVE_MONTHS_THRESHOLD * 1.25
    ):
        flags.append(
            {
                "type": "fx_stress_elevated",
                "active_years": 0,
                "severity": "watch",
            }
        )

    regime_years = agent.risk.regime_crisis_active_years
    if regime_years > 0:
        flags.append(
            {
                "type": "regime_crisis",
                "active_years": regime_years,
                "severity": "critical",
            }
        )
    elif agent.society.trust_gov < 0.30 and agent.society.social_tension > 0.65:
        flags.append(
            {
                "type": "political_instability",
                "active_years": 0,
                "severity": "watch",
            }
        )

    if agent.economy.climate_shock_years > 0:
        flags.append(
            {
                "type": "climate_shock",
                "active_years": agent.economy.climate_shock_years,
                "severity": "moderate",
            }
        )

    for other_id, relation in world.relations.get(agent.id, {}).items():
        if relation.at_war:
            flags.append(
                {
                    "type": "active_war",
                    "with": other_id,
                    "war_years": relation.war_years,
                    "severity": "critical",
                }
            )
            break

    sanctioning_count = sum(1 for other in world.agents.values() if agent.id in other.active_sanctions)
    if sanctioning_count >= 2:
        flags.append(
            {
                "type": "sanctions_pressure",
                "sanctioning_count": sanctioning_count,
                "severity": "high" if sanctioning_count >= 4 else "moderate",
            }
        )

    return flags


def update_tfp_endogenous(agent: AgentState, world: WorldState) -> None:
    economy = agent.economy

    # Initialize TFP from observed current state once.
    if not hasattr(economy, "tfp") or economy.tfp is None:
        alpha, beta, gamma = cal.ALPHA_CAPITAL, cal.BETA_LABOR, cal.GAMMA_ENERGY
        capital = max(economy.capital, 1e-6)
        labor = max(economy.population / 1e9, 1e-3)
        energy = agent.resources.get("energy")
        energy_input = max(energy.consumption / 1000.0, 1e-3) if energy else 1.0
        base = capital**alpha * labor**beta * energy_input**gamma
        economy.tfp = economy.gdp / base if base > 0 else 1.0

    gdp = max(economy.gdp, 1e-6)
    rd_share = economy.rd_spending / gdp if gdp > 0 else 0.0

    avg_trade = 0.0
    count = 0
    for rel in world.relations.get(agent.id, {}).values():
        avg_trade += effective_trade_intensity(rel)
        count += 1
    if count > 0:
        avg_trade /= count

    spillover = 1.0 + cal.TFP_TRADE_SPILLOVER_SENS * avg_trade
    tfp_growth = cal.TFP_RD_SHARE_SENS * rd_share * spillover

    tech_gap_weighted = 0.0
    tech_weight = 0.0
    for partner_id, rel in world.relations.get(agent.id, {}).items():
        partner = world.agents.get(partner_id)
        if partner is None:
            continue
        gap = max(0.0, partner.technology.tech_level - agent.technology.tech_level)
        weight = max(0.0, effective_trade_intensity(rel))
        tech_gap_weighted += weight * gap
        tech_weight += weight
    avg_gap = tech_gap_weighted / tech_weight if tech_weight > 0 else 0.0
    diffusion = cal.TFP_DIFFUSION_SENS * avg_gap

    tfp_growth = cal.TFP_DRIFT + tfp_growth + diffusion
    tfp_growth = max(cal.TFP_GROWTH_MIN, min(tfp_growth, cal.TFP_GROWTH_MAX))

    economy.tfp *= 1.0 + tfp_growth
