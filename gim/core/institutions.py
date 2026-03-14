from __future__ import annotations

from typing import Any, Dict, List

from .core import InstitutionState, WorldState, clamp01


ORG_TYPES = {
    "UN": "SecurityOrg",
    "UNSC": "SecurityOrg",
    "IMF": "FinanceOrg",
    "WorldBank": "FinanceOrg",
    "FSB": "FinanceOrg",
    "WTO": "TradeOrg",
    "EU": "TradeOrg",
    "USMCA": "TradeOrg",
    "ASEAN": "TradeOrg",
    "UNFCCC": "ClimateOrg",
    "GCF": "ClimateOrg",
    "IPCC": "KnowledgeOrg",
    "NATO": "SecurityOrg",
    "WHO": "SocialOrg",
    "ILO": "SocialOrg",
    "UNEP_UNESCO": "SocialOrg",
}


def _members_by_region(world: WorldState) -> Dict[str, List[str]]:
    region_map: Dict[str, List[str]] = {}
    for agent in world.agents.values():
        region_map.setdefault(agent.region, []).append(agent.id)
    return region_map


def build_default_institutions(world: WorldState) -> Dict[str, InstitutionState]:
    all_members = list(world.agents.keys())
    regions = _members_by_region(world)

    # Approximate regional blocks using region labels.
    eu_members = regions.get("Europe", [])
    usmca_members = regions.get("North America", [])
    asean_members = regions.get("East Asia", [])

    # NATO proxy: Western block.
    nato_members = [
        agent.id for agent in world.agents.values() if agent.alliance_block == "Western"
    ]

    # Security Council proxy: top-5 GDP.
    top_gdp = sorted(world.agents.values(), key=lambda a: a.economy.gdp, reverse=True)
    unsc_members = [agent.id for agent in top_gdp[:5]]

    institutions = {
        "UN": InstitutionState(
            id="UN",
            name="United Nations",
            org_type=ORG_TYPES["UN"],
            mandate=["norms", "mediation"],
            members=all_members,
            legitimacy=0.72,
        ),
        "UNSC": InstitutionState(
            id="UNSC",
            name="UN Security Council",
            org_type=ORG_TYPES["UNSC"],
            mandate=["sanctions", "mediation"],
            members=unsc_members,
            legitimacy=0.68,
        ),
        "IMF": InstitutionState(
            id="IMF",
            name="International Monetary Fund",
            org_type=ORG_TYPES["IMF"],
            mandate=["liquidity", "stability"],
            members=all_members,
            legitimacy=0.65,
            base_budget_share=0.0012,
        ),
        "WorldBank": InstitutionState(
            id="WorldBank",
            name="World Bank",
            org_type=ORG_TYPES["WorldBank"],
            mandate=["development", "infrastructure"],
            members=all_members,
            legitimacy=0.62,
            base_budget_share=0.0008,
        ),
        "FSB": InstitutionState(
            id="FSB",
            name="FSB/Basel",
            org_type=ORG_TYPES["FSB"],
            mandate=["financial_rules"],
            members=all_members,
            legitimacy=0.6,
            base_budget_share=0.0003,
        ),
        "WTO": InstitutionState(
            id="WTO",
            name="World Trade Organization",
            org_type=ORG_TYPES["WTO"],
            mandate=["trade_rules"],
            members=all_members,
            legitimacy=0.66,
        ),
        "EU": InstitutionState(
            id="EU",
            name="EU",
            org_type=ORG_TYPES["EU"],
            mandate=["regional_trade"],
            members=eu_members,
            legitimacy=0.7,
        ),
        "USMCA": InstitutionState(
            id="USMCA",
            name="USMCA",
            org_type=ORG_TYPES["USMCA"],
            mandate=["regional_trade"],
            members=usmca_members,
            legitimacy=0.7,
        ),
        "ASEAN": InstitutionState(
            id="ASEAN",
            name="ASEAN",
            org_type=ORG_TYPES["ASEAN"],
            mandate=["regional_trade"],
            members=asean_members,
            legitimacy=0.62,
        ),
        "UNFCCC": InstitutionState(
            id="UNFCCC",
            name="UNFCCC",
            org_type=ORG_TYPES["UNFCCC"],
            mandate=["climate_rules"],
            members=all_members,
            legitimacy=0.62,
        ),
        "GCF": InstitutionState(
            id="GCF",
            name="Green Climate Fund",
            org_type=ORG_TYPES["GCF"],
            mandate=["climate_finance"],
            members=all_members,
            legitimacy=0.6,
            base_budget_share=0.0006,
        ),
        "IPCC": InstitutionState(
            id="IPCC",
            name="IPCC",
            org_type=ORG_TYPES["IPCC"],
            mandate=["knowledge"],
            members=all_members,
            legitimacy=0.78,
        ),
        "NATO": InstitutionState(
            id="NATO",
            name="NATO",
            org_type=ORG_TYPES["NATO"],
            mandate=["collective_defense"],
            members=nato_members,
            legitimacy=0.65,
        ),
        "WHO": InstitutionState(
            id="WHO",
            name="WHO",
            org_type=ORG_TYPES["WHO"],
            mandate=["health"],
            members=all_members,
            legitimacy=0.7,
        ),
        "ILO": InstitutionState(
            id="ILO",
            name="ILO",
            org_type=ORG_TYPES["ILO"],
            mandate=["labor"],
            members=all_members,
            legitimacy=0.58,
        ),
        "UNEP_UNESCO": InstitutionState(
            id="UNEP_UNESCO",
            name="UNEP/UNESCO",
            org_type=ORG_TYPES["UNEP_UNESCO"],
            mandate=["social", "education"],
            members=all_members,
            legitimacy=0.6,
        ),
    }

    return institutions


def _compute_global_metrics(world: WorldState) -> Dict[str, float]:
    agents = list(world.agents.values())
    total_gdp = sum(a.economy.gdp for a in agents)
    avg_trust = sum(a.society.trust_gov for a in agents) / max(len(agents), 1)
    avg_tension = sum(a.society.social_tension for a in agents) / max(len(agents), 1)

    total_rel = 0.0
    trust_sum = 0.0
    conflict_sum = 0.0
    trade_sum = 0.0
    count = 0
    for rels in world.relations.values():
        for rel in rels.values():
            trust_sum += rel.trust
            conflict_sum += rel.conflict_level
            trade_sum += rel.trade_intensity
            count += 1
    if count > 0:
        avg_rel_trust = trust_sum / count
        avg_rel_conflict = conflict_sum / count
        avg_trade_intensity = trade_sum / count
    else:
        avg_rel_trust = 0.0
        avg_rel_conflict = 0.0
        avg_trade_intensity = 0.0

    return {
        "total_gdp": total_gdp,
        "avg_trust": avg_trust,
        "avg_tension": avg_tension,
        "avg_rel_trust": avg_rel_trust,
        "avg_rel_conflict": avg_rel_conflict,
        "avg_trade_intensity": avg_trade_intensity,
        "global_co2": world.global_state.co2,
        "global_temp": world.global_state.temperature_global,
    }


def _update_legitimacy(org: InstitutionState, target: float) -> None:
    org.legitimacy = clamp01(0.95 * org.legitimacy + 0.05 * target)


def update_institutions(world: WorldState) -> List[Dict[str, Any]]:
    if not world.institutions:
        world.institutions = build_default_institutions(world)

    metrics = _compute_global_metrics(world)
    reports: List[Dict[str, Any]] = []

    for org in world.institutions.values():
        target_legitimacy = org.legitimacy
        if org.org_type in {"SecurityOrg", "TradeOrg"}:
            target_legitimacy = clamp01(0.5 + 0.5 * metrics["avg_rel_trust"])
        elif org.org_type in {"FinanceOrg"}:
            target_legitimacy = clamp01(0.4 + 0.6 * metrics["avg_trust"])
        elif org.org_type in {"ClimateOrg", "KnowledgeOrg"}:
            target_legitimacy = clamp01(0.45 + 0.55 * (1.0 - metrics["avg_tension"]))
        elif org.org_type in {"SocialOrg"}:
            target_legitimacy = clamp01(0.4 + 0.6 * metrics["avg_trust"])

        _update_legitimacy(org, target_legitimacy)

        org.budget = org.base_budget_share * metrics["total_gdp"] * org.legitimacy

        measures = _apply_org_measures(world, org, metrics)

        report = {
            "time": world.time,
            "org_id": org.id,
            "org_type": org.org_type,
            "legitimacy": org.legitimacy,
            "budget": org.budget,
            "members": len(org.members),
            "measures": measures,
            "global_gdp": metrics["total_gdp"],
            "global_trust": metrics["avg_trust"],
            "global_tension": metrics["avg_tension"],
            "global_rel_trust": metrics["avg_rel_trust"],
            "global_rel_conflict": metrics["avg_rel_conflict"],
            "global_trade_intensity": metrics["avg_trade_intensity"],
            "global_co2": metrics["global_co2"],
            "global_temp": metrics["global_temp"],
        }
        reports.append(report)

    world.institution_reports = reports
    return reports


def _apply_org_measures(
    world: WorldState,
    org: InstitutionState,
    metrics: Dict[str, float],
) -> List[Dict[str, Any]]:
    measures: List[Dict[str, Any]] = []
    if not org.members:
        return measures

    if org.org_type == "TradeOrg":
        delta = 0.01 * org.legitimacy
        for member_id in org.members:
            rels = world.relations.get(member_id, {})
            for partner_id, relation in rels.items():
                if partner_id not in org.members:
                    continue
                if relation.trade_barrier <= 0.0:
                    continue
                relation.trade_barrier = max(0.0, relation.trade_barrier - delta)
        measures.append({"action": "reduce_trade_barriers", "delta": delta})

    elif org.org_type == "FinanceOrg":
        if org.budget <= 0.0:
            return measures
        for member_id in org.members:
            agent = world.agents.get(member_id)
            if agent is None:
                continue
            gdp = max(agent.economy.gdp, 1e-6)
            debt_gdp = agent.economy.public_debt / gdp
            need = max(0.0, debt_gdp - 1.0) + max(0.0, 0.02 - agent.economy.fx_reserves / gdp)
            if need <= 0.0:
                continue
            grant = min(org.budget, 0.005 * gdp)
            if grant <= 0.0:
                continue
            agent.economy.fx_reserves += grant
            agent.economy.public_debt += grant
            org.budget -= grant
            measures.append({"action": "liquidity_support", "agent": member_id, "amount": grant})
            if org.budget <= 0.0:
                break

    elif org.org_type == "SecurityOrg":
        delta = 0.01 * org.legitimacy
        for member_id in org.members:
            rels = world.relations.get(member_id, {})
            for partner_id, relation in rels.items():
                if partner_id not in org.members:
                    continue
                if relation.conflict_level < 0.25:
                    continue
                relation.conflict_level = max(0.0, relation.conflict_level - delta)
        measures.append({"action": "mediation", "delta": delta})

    elif org.org_type == "ClimateOrg":
        delta = 0.002 * org.legitimacy
        for member_id in org.members:
            agent = world.agents.get(member_id)
            if agent is None:
                continue
            if agent.climate.climate_risk < 0.5:
                continue
            agent.climate.climate_risk = max(0.0, agent.climate.climate_risk - delta)
        measures.append({"action": "climate_adaptation", "delta": delta})

    elif org.org_type == "SocialOrg":
        delta = 0.003 * org.legitimacy
        for member_id in org.members:
            agent = world.agents.get(member_id)
            if agent is None:
                continue
            agent.society.social_tension = max(
                0.0, agent.society.social_tension - 0.5 * delta
            )
            agent.society.trust_gov = clamp01(agent.society.trust_gov + 0.3 * delta)
        measures.append({"action": "social_support", "delta": delta})

    elif org.org_type == "KnowledgeOrg":
        measures.append({"action": "risk_signal", "focus": "climate"})

    return measures
