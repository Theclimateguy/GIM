import math
from typing import Dict

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
    raw = max(0.0, debt_gdp - 1.0)
    stress = raw * agent.risk.debt_crisis_prone
    return float(min(stress, 3.0))


def compute_protest_risk(agent: AgentState) -> float:
    tension = agent.society.social_tension
    trust = agent.society.trust_gov
    gini = agent.society.inequality_gini

    base = 0.6 * tension + 0.3 * (1.0 - trust) + 0.1 * (gini / 100.0)
    fragility = 1.0 - agent.risk.regime_stability
    risk = base * (0.5 + 0.5 * fragility)

    return float(max(0.0, min(risk, 1.0)))


def update_tfp_endogenous(agent: AgentState, world: WorldState) -> None:
    economy = agent.economy

    # Initialize TFP from observed current state once.
    if not hasattr(economy, "tfp") or economy.tfp is None:
        alpha, beta, gamma = 0.30, 0.60, 0.10
        capital = max(economy.capital, 1e-6)
        labor = max(economy.population / 1e9, 1e-3)
        energy = agent.resources.get("energy")
        energy_input = max(energy.consumption / 1000.0, 1e-3) if energy else 1.0
        base = capital**alpha * labor**beta * energy_input**gamma
        economy.tfp = economy.gdp / base if base > 0 else 1.0

    gdp = max(economy.gdp, 1e-6)
    rd_share = economy.rd_spending / gdp if gdp > 0 else 0.0

    phi = 2.0
    psi = 0.3
    tfp_drift = 0.01
    diffusion_eta = 0.02

    avg_trade = 0.0
    count = 0
    for rel in world.relations.get(agent.id, {}).values():
        avg_trade += effective_trade_intensity(rel)
        count += 1
    if count > 0:
        avg_trade /= count

    spillover = 1.0 + psi * avg_trade
    tfp_growth = phi * rd_share * spillover

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
    diffusion = diffusion_eta * avg_gap

    tfp_growth = tfp_drift + tfp_growth + diffusion
    tfp_growth = max(-0.05, min(tfp_growth, 0.05))

    economy.tfp *= 1.0 + tfp_growth
