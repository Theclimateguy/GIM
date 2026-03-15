from dataclasses import asdict

from . import calibration_params as cal
from .climate import effective_damage_multiplier
from .core import Observation, WorldState
from .metrics import (
    compute_crisis_flags,
    compute_debt_stress,
    compute_protest_risk,
    compute_reserve_years,
)


def _strip_private_fields(
    payload: object,
    *,
    exclude: set[str] | None = None,
) -> object:
    if isinstance(payload, dict):
        blocked = exclude or set()
        return {
            key: _strip_private_fields(value, exclude=exclude)
            for key, value in payload.items()
            if not str(key).startswith("_") and key not in blocked
        }
    if isinstance(payload, list):
        return [_strip_private_fields(item, exclude=exclude) for item in payload]
    return payload


def _public_asdict(value: object, *, exclude: set[str] | None = None) -> dict[str, object]:
    return _strip_private_fields(asdict(value), exclude=exclude)


def _resolve_previous(current: float, previous: object) -> float:
    if previous is None:
        return float(current)
    return float(previous)


def _inbound_sanctions(world: WorldState, agent_id: str) -> dict[str, dict[str, object]]:
    inbound: dict[str, dict[str, object]] = {}
    for other_id, other in world.agents.items():
        sanction_type = other.active_sanctions.get(agent_id)
        if sanction_type is None:
            continue
        inbound[other_id] = {
            "type": sanction_type,
            "years": int(other.sanction_years.get(agent_id, 0)),
        }
    return inbound


def build_observation(world: WorldState, agent_id: str) -> Observation:
    agent = world.agents[agent_id]
    inbound_sanctions = _inbound_sanctions(world, agent_id)
    climate_damage_factor = getattr(agent.economy, "climate_damage_factor", None)
    if climate_damage_factor is None:
        climate_damage_factor = min(1.0, effective_damage_multiplier(agent, world))
    gdp_now = float(agent.economy.gdp)
    gdp_prev = _resolve_previous(gdp_now, getattr(agent.economy, "_gdp_prev", None))
    debt_gdp_now = float(agent.economy.public_debt / max(agent.economy.gdp, 1e-6))
    debt_gdp_prev = _resolve_previous(
        debt_gdp_now,
        getattr(agent.economy, "_debt_gdp_prev", None),
    )
    trust_now = float(agent.society.trust_gov)
    trust_prev = _resolve_previous(trust_now, getattr(agent.society, "_trust_prev", None))
    tension_now = float(agent.society.social_tension)
    tension_prev = _resolve_previous(
        tension_now,
        getattr(agent.society, "_tension_prev", None),
    )
    emissions_now = float(agent.climate.co2_annual_emissions)
    emissions_prev = _resolve_previous(
        emissions_now,
        getattr(agent.climate, "_emissions_prev", None),
    )

    self_state = {
        "economy": _public_asdict(agent.economy),
        "resources": {name: _public_asdict(resource) for name, resource in agent.resources.items()},
        "society": _public_asdict(agent.society),
        "climate": _public_asdict(agent.climate),
        "culture": _public_asdict(agent.culture),
        "technology": _public_asdict(agent.technology),
        "risk": _public_asdict(agent.risk),
        "political": _public_asdict(agent.political),
        "alliance_block": agent.alliance_block,
        "active_sanctions": dict(agent.active_sanctions),
        "credit": {
            "rating": agent.credit_rating,
            "zone": agent.credit_zone,
            "risk_score": agent.credit_risk_score,
            "details": dict(agent.credit_rating_details),
        },
        "trends": {
            "gdp_growth_last_step": float((gdp_now - gdp_prev) / max(gdp_prev, 1e-6)),
            "debt_gdp_change": float(debt_gdp_now - debt_gdp_prev),
            "trust_change": float(trust_now - trust_prev),
            "social_tension_change": float(tension_now - tension_prev),
            "temp_trend_3yr": float(getattr(world.global_state, "temp_trend_3yr", 0.0)),
            "emissions_change": float(emissions_now - emissions_prev),
        },
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
        "climate_damage_factor": climate_damage_factor,
        "inbound_sanctions": inbound_sanctions,
        "crisis_flags": compute_crisis_flags(agent, world),
    }
    self_state["competitive"] = competitive

    neighbors = []
    rel_items = sorted(
        world.relations.get(agent_id, {}).items(),
        key=lambda item: item[1].trade_intensity + item[1].conflict_level,
        reverse=True,
    )[: cal.OBS_MAX_NEIGHBORS]
    for other_id, relation in rel_items:
        other = world.agents.get(other_id)
        if other is None:
            continue
        neighbors.append(
            {
                "agent_id": other_id,
                "trade_intensity": relation.trade_intensity,
                "trade_barrier": relation.trade_barrier,
                "trust": relation.trust,
                "conflict_level": relation.conflict_level,
                "gdp": other.economy.gdp,
                "military_power": other.technology.military_power,
                "alliance_block": other.alliance_block,
                "inbound_sanction_type": inbound_sanctions.get(other_id, {}).get("type"),
            }
        )

    external_actors = {
        "neighbors": neighbors,
        "global": _public_asdict(world.global_state, exclude={"temp_history"}),
    }
    institutions_summary = []
    for inst in world.institutions.values():
        institutions_summary.append(
            {
                "id": inst.id,
                "type": inst.org_type,
                "legitimacy": inst.legitimacy,
                "mandate": inst.mandate,
                "members": len(inst.members),
                "active_rules": inst.active_rules,
            }
        )
    if institutions_summary:
        external_actors["institutions"] = institutions_summary
    if world.institution_reports:
        external_actors["institution_reports"] = world.institution_reports

    active_crises = [
        str(flag["type"])
        for flag in competitive["crisis_flags"]
        if int(flag.get("active_years", 1)) > 0
    ]
    crisis_str = f" | CRISIS: {', '.join(active_crises)}" if active_crises else ""
    summary = (
        f"Year {world.time} | GDP: {agent.economy.gdp:.1f}T | "
        f"Pop: {agent.economy.population / 1e6:.0f}M"
        f"{crisis_str}"
    )

    return Observation(
        agent_id=agent_id,
        time=world.time,
        self_state=self_state,
        resource_balance=resource_balance,
        external_actors=external_actors,
        summary=summary,
    )
