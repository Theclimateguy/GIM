from typing import Any, Dict

from .core import Action, AgentMemory, WorldState


def update_agent_memory(
    memory: AgentMemory,
    world: WorldState,
    actions: Dict[str, Action],
    max_horizon: int = 10,
) -> None:
    for agent_id, agent in world.agents.items():
        econ = agent.economy
        society = agent.society
        climate = agent.climate

        last_action = actions.get(agent_id)
        if last_action is not None:
            domestic = last_action.domestic_policy
            last_action_summary = {
                "tax_fuel_change": domestic.tax_fuel_change,
                "social_spending_change": domestic.social_spending_change,
                "military_spending_change": domestic.military_spending_change,
                "rd_investment_change": domestic.rd_investment_change,
                "climate_policy": domestic.climate_policy,
            }
        else:
            last_action_summary = None

        snapshot = {
            "time": world.time,
            "gdp": econ.gdp,
            "gdp_per_capita": econ.gdp_per_capita,
            "trust_gov": society.trust_gov,
            "social_tension": society.social_tension,
            "security_margin": getattr(agent, "security_margin", 1.0),
            "climate_risk": climate.climate_risk,
            "co2_emissions": climate.co2_annual_emissions,
            "last_action": last_action_summary,
        }

        memory.setdefault(agent_id, []).append(snapshot)
        if len(memory[agent_id]) > max_horizon:
            memory[agent_id] = memory[agent_id][-max_horizon:]


def summarize_agent_memory(memory: AgentMemory, agent_id: str) -> Dict[str, Any]:
    history = memory.get(agent_id, [])
    if not history:
        return {"horizon": 0}

    first = history[0]
    last = history[-1]

    def diff(key: str) -> float:
        return float(last.get(key, 0.0) - first.get(key, 0.0))

    summary: Dict[str, Any] = {
        "horizon": last["time"] - first["time"],
        "gdp_trend": diff("gdp"),
        "gdp_per_capita_trend": diff("gdp_per_capita"),
        "trust_trend": diff("trust_gov"),
        "tension_trend": diff("social_tension"),
        "security_trend": diff("security_margin"),
        "climate_risk_trend": diff("climate_risk"),
        "last_actions": [
            {"time": item["time"], "last_action": item["last_action"]}
            for item in history[-3:]
            if item.get("last_action") is not None
        ],
    }
    return summary
