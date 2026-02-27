from dataclasses import asdict

from .core import Observation, WorldState
from .metrics import (
    compute_debt_stress,
    compute_protest_risk,
    compute_relative_metrics,
    compute_reserve_years,
)


def build_observation(world: WorldState, agent_id: str) -> Observation:
    agent = world.agents[agent_id]

    # Keep comparative metrics fresh for every decision.
    compute_relative_metrics(world)

    self_state = {
        "economy": asdict(agent.economy),
        "resources": {name: asdict(resource) for name, resource in agent.resources.items()},
        "society": asdict(agent.society),
        "climate": asdict(agent.climate),
        "culture": asdict(agent.culture),
        "technology": asdict(agent.technology),
        "risk": asdict(agent.risk),
        "alliance_block": agent.alliance_block,
    }

    resource_balance = {
        name: {"net_imports": max(0.0, resource.consumption - resource.production)}
        for name, resource in agent.resources.items()
    }

    competitive = {
        "gdp_share": getattr(agent.economy, "gdp_share", 0.0),
        "gdp_rank": getattr(agent.economy, "gdp_rank", None),
        "influence_score": getattr(agent, "influence_score", 0.0),
        "security_margin": getattr(agent, "security_margin", 1.0),
        "reserve_years": compute_reserve_years(agent),
        "debt_stress": compute_debt_stress(agent),
        "protest_risk": compute_protest_risk(agent),
    }
    self_state["competitive"] = competitive

    neighbors = []
    for other_id, relation in world.relations.get(agent_id, {}).items():
        other = world.agents.get(other_id)
        if other is None:
            continue
        neighbors.append(
            {
                "agent_id": other_id,
                "trade_intensity": relation.trade_intensity,
                "trust": relation.trust,
                "conflict_level": relation.conflict_level,
                "gdp": other.economy.gdp,
                "military_power": other.technology.military_power,
                "alliance_block": other.alliance_block,
            }
        )

    external_actors = {
        "neighbors": neighbors,
        "global": asdict(world.global_state),
    }

    summary = (
        f"Year {world.time} | GDP: {agent.economy.gdp:.1f}T | "
        f"Pop: {agent.economy.population / 1e6:.0f}M"
    )

    return Observation(
        agent_id=agent_id,
        time=world.time,
        self_state=self_state,
        resource_balance=resource_balance,
        external_actors=external_actors,
        summary=summary,
    )
