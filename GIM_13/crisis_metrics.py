from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .runtime import AgentState, WorldState

from gim_11_1.core import clamp01, effective_trade_intensity
from gim_11_1.economy import compute_effective_interest_rate
from gim_11_1.metrics import compute_debt_stress, compute_protest_risk, compute_reserve_years


AGENT_METRIC_DESCRIPTIONS = {
    "inflation": "Estimated CPI-style inflation pressure with import and sanctions pass-through.",
    "oil_vulnerability": "Exposure to oil and energy shocks through import dependence, route pressure and cover.",
    "fx_stress": "External liquidity pressure measured through reserves cover and import compression risk.",
    "sovereign_stress": "Debt rollover and sovereign financing pressure.",
    "food_affordability_stress": "Stress from food gaps, basket prices and weak income buffers.",
    "protest_pressure": "Composite protest risk from prices, labor stress, inequality and trust erosion.",
    "regime_fragility": "Near-term regime weakness combining legitimacy, stability and coercive limits.",
    "sanctions_strangulation": "How tightly sanctions and barriers compress trade, FX and rerouting capacity.",
    "conflict_escalation_pressure": "Escalation pressure from conflict, mistrust, hawkishness and force posture.",
    "strategic_dependency": "Dependence on critical resource imports and thin reserve buffers.",
    "chokepoint_exposure": "Proxy exposure to route disruption through energy imports and trade openness.",
}

GLOBAL_METRIC_DESCRIPTIONS = {
    "global_oil_market_stress": "Proxy oil benchmark built from energy prices, supply-demand gaps and coercive pressure.",
    "global_energy_volume_gap": "Positive global energy volume shortfall relative to current demand.",
    "global_sanctions_footprint": "Density of active sanctions links across the system.",
    "global_trade_fragmentation": "Average barrier pressure across bilateral relationships.",
}

ARCHETYPE_RELEVANCE = {
    "advanced_service_democracy": {
        "inflation": 0.80,
        "oil_vulnerability": 0.35,
        "fx_stress": 0.30,
        "sovereign_stress": 0.85,
        "food_affordability_stress": 0.20,
        "protest_pressure": 0.60,
        "regime_fragility": 0.45,
        "sanctions_strangulation": 0.60,
        "conflict_escalation_pressure": 0.60,
        "strategic_dependency": 0.75,
        "chokepoint_exposure": 0.50,
    },
    "developing_importer": {
        "inflation": 0.90,
        "oil_vulnerability": 0.90,
        "fx_stress": 0.95,
        "sovereign_stress": 0.80,
        "food_affordability_stress": 0.95,
        "protest_pressure": 0.90,
        "regime_fragility": 0.80,
        "sanctions_strangulation": 0.65,
        "conflict_escalation_pressure": 0.55,
        "strategic_dependency": 0.85,
        "chokepoint_exposure": 0.80,
    },
    "hydrocarbon_exporter": {
        "inflation": 0.70,
        "oil_vulnerability": 0.95,
        "fx_stress": 0.55,
        "sovereign_stress": 0.60,
        "food_affordability_stress": 0.55,
        "protest_pressure": 0.75,
        "regime_fragility": 0.85,
        "sanctions_strangulation": 0.90,
        "conflict_escalation_pressure": 0.85,
        "strategic_dependency": 0.70,
        "chokepoint_exposure": 0.95,
    },
    "industrial_power": {
        "inflation": 0.75,
        "oil_vulnerability": 0.55,
        "fx_stress": 0.40,
        "sovereign_stress": 0.70,
        "food_affordability_stress": 0.30,
        "protest_pressure": 0.55,
        "regime_fragility": 0.55,
        "sanctions_strangulation": 0.90,
        "conflict_escalation_pressure": 0.85,
        "strategic_dependency": 0.90,
        "chokepoint_exposure": 0.75,
    },
    "fragile_conflict_state": {
        "inflation": 0.80,
        "oil_vulnerability": 0.70,
        "fx_stress": 0.85,
        "sovereign_stress": 0.90,
        "food_affordability_stress": 1.00,
        "protest_pressure": 1.00,
        "regime_fragility": 1.00,
        "sanctions_strangulation": 0.80,
        "conflict_escalation_pressure": 0.95,
        "strategic_dependency": 0.90,
        "chokepoint_exposure": 0.65,
    },
    "mixed_emerging": {
        "inflation": 0.80,
        "oil_vulnerability": 0.70,
        "fx_stress": 0.70,
        "sovereign_stress": 0.75,
        "food_affordability_stress": 0.60,
        "protest_pressure": 0.75,
        "regime_fragility": 0.70,
        "sanctions_strangulation": 0.65,
        "conflict_escalation_pressure": 0.65,
        "strategic_dependency": 0.75,
        "chokepoint_exposure": 0.65,
    },
}

REGIONAL_ROUTE_RISK = {
    "Middle East": 0.85,
    "East Asia": 0.70,
    "Europe": 0.45,
    "North America": 0.25,
    "Global South": 0.50,
}


def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    if abs(denominator) <= 1e-9:
        return default
    return numerator / denominator


def _resource_gap_ratio(agent: AgentState, resource_name: str) -> float:
    resource = agent.resources.get(resource_name)
    if resource is None:
        return 0.0
    return max(0.0, resource.consumption - resource.production) / max(resource.consumption, 1e-6)


def _cover_days(agent: AgentState, resource_name: str) -> float:
    resource = agent.resources.get(resource_name)
    if resource is None:
        return 365.0
    return 365.0 * _safe_div(resource.own_reserve, max(resource.consumption, 1e-6), default=365.0)


def _trigger_from_level(level: float, threshold: float) -> float:
    if level <= threshold:
        return 0.0
    return clamp01(_safe_div(level - threshold, max(1.0 - threshold, 1e-6)))


def _severity(level: float, momentum: float, buffer: float, trigger: float) -> float:
    worsening = max(momentum, 0.0)
    return clamp01(0.45 * level + 0.20 * worsening + 0.20 * (1.0 - buffer) + 0.15 * trigger)


def _normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return clamp01((value - low) / (high - low))


@dataclass
class CrisisMetric:
    name: str
    description: str
    value: float
    unit: str
    level: float
    momentum: float
    buffer: float
    trigger: float
    severity: float
    relevance: float
    threshold_flag: bool
    contributors: Dict[str, float] = field(default_factory=dict)


@dataclass
class GlobalCrisisContext:
    metrics: Dict[str, CrisisMetric]


@dataclass
class AgentCrisisReport:
    agent_id: str
    agent_name: str
    archetype: str
    metrics: Dict[str, CrisisMetric]
    top_metric_names: List[str]
    notes: List[str] = field(default_factory=list)


@dataclass
class CrisisDashboard:
    global_context: GlobalCrisisContext
    agents: Dict[str, AgentCrisisReport]


class CrisisMetricsEngine:
    def detect_archetype(self, agent: AgentState, world: WorldState) -> str:
        gdp_pc = agent.economy.gdp_per_capita or (
            agent.economy.gdp * 1e12 / max(agent.economy.population, 1.0)
        )
        energy_gap = _resource_gap_ratio(agent, "energy")
        energy_export = max(
            0.0,
            _safe_div(
                agent.resources["energy"].production - agent.resources["energy"].consumption,
                max(agent.resources["energy"].production, 1e-6),
                default=0.0,
            ),
        )
        regime = agent.culture.regime_type.lower()

        if energy_export >= 0.15 and agent.region == "Middle East":
            return "hydrocarbon_exporter"

        if agent.risk.conflict_proneness >= 0.75 or agent.risk.regime_stability <= 0.40:
            return "fragile_conflict_state"

        if agent.economy.gdp >= 10.0 or (
            agent.economy.gdp >= 4.0 and agent.economy.population >= 150_000_000
        ):
            return "industrial_power"

        if regime == "democracy" and gdp_pc >= 35_000:
            return "advanced_service_democracy"

        if energy_gap >= 0.10 or _safe_div(agent.economy.fx_reserves, agent.economy.gdp, 0.0) < 0.15:
            return "developing_importer"

        return "mixed_emerging"

    def _relation_stats(self, world: WorldState, agent_id: str) -> Dict[str, float]:
        relations = list(world.relations.get(agent_id, {}).values())
        if not relations:
            return {
                "avg_trade_intensity": 0.0,
                "avg_trade_barrier": 0.0,
                "avg_trust": 0.5,
                "avg_conflict": 0.0,
                "war_links": 0.0,
            }

        trade_intensity = sum(effective_trade_intensity(rel) for rel in relations) / len(relations)
        trade_barrier = sum(rel.trade_barrier for rel in relations) / len(relations)
        trust = sum(rel.trust for rel in relations) / len(relations)
        conflict = sum(rel.conflict_level for rel in relations) / len(relations)
        war_links = sum(1.0 for rel in relations if rel.at_war) / len(relations)
        return {
            "avg_trade_intensity": trade_intensity,
            "avg_trade_barrier": trade_barrier,
            "avg_trust": trust,
            "avg_conflict": conflict,
            "war_links": war_links,
        }

    def _global_context_body(self, world: WorldState) -> GlobalCrisisContext:
        energy_supply = 0.0
        energy_demand = 0.0
        total_relations = 0
        barrier_sum = 0.0
        conflict_sum = 0.0
        sanctions_links = 0

        for agent in world.agents.values():
            energy = agent.resources.get("energy")
            if energy is not None:
                energy_supply += max(0.0, energy.production)
                energy_demand += max(0.0, energy.consumption)
            sanctions_links += len(agent.active_sanctions)

        for relations in world.relations.values():
            for rel in relations.values():
                total_relations += 1
                barrier_sum += rel.trade_barrier
                conflict_sum += rel.conflict_level

        positive_gap = max(0.0, energy_demand - energy_supply)
        energy_gap_ratio = max(0.0, _safe_div(positive_gap, max(energy_supply, 1e-6), default=0.0))
        sanctions_footprint = _safe_div(
            sanctions_links,
            max(len(world.agents) * max(len(world.agents) - 1, 1), 1),
            default=0.0,
        )
        avg_barrier = _safe_div(barrier_sum, total_relations, 0.0)
        avg_conflict = _safe_div(conflict_sum, total_relations, 0.0)

        oil_benchmark = world.global_state.prices.get("energy", 1.0) * (
            1.0 + 0.65 * energy_gap_ratio + 0.20 * sanctions_footprint + 0.15 * avg_conflict
        )
        oil_level = _normalize(oil_benchmark, 1.0, 2.5)
        oil_buffer = clamp01(1.0 - energy_gap_ratio / 0.25)
        oil_trigger = _trigger_from_level(oil_level, 0.55)

        metrics = {
            "global_oil_market_stress": CrisisMetric(
                name="global_oil_market_stress",
                description=GLOBAL_METRIC_DESCRIPTIONS["global_oil_market_stress"],
                value=oil_benchmark,
                unit="index",
                level=oil_level,
                momentum=0.0,
                buffer=oil_buffer,
                trigger=oil_trigger,
                severity=_severity(oil_level, 0.0, oil_buffer, oil_trigger),
                relevance=1.0,
                threshold_flag=oil_level >= 0.55,
                contributors={
                    "base_energy_price": world.global_state.prices.get("energy", 1.0),
                    "energy_gap_ratio": energy_gap_ratio,
                    "sanctions_footprint": sanctions_footprint,
                    "avg_conflict": avg_conflict,
                },
            ),
            "global_energy_volume_gap": CrisisMetric(
                name="global_energy_volume_gap",
                description=GLOBAL_METRIC_DESCRIPTIONS["global_energy_volume_gap"],
                value=positive_gap,
                unit="energy_volume",
                level=_normalize(energy_gap_ratio, 0.0, 0.20),
                momentum=0.0,
                buffer=clamp01(1.0 - energy_gap_ratio / 0.20),
                trigger=_trigger_from_level(_normalize(energy_gap_ratio, 0.0, 0.20), 0.50),
                severity=_severity(
                    _normalize(energy_gap_ratio, 0.0, 0.20),
                    0.0,
                    clamp01(1.0 - energy_gap_ratio / 0.20),
                    _trigger_from_level(_normalize(energy_gap_ratio, 0.0, 0.20), 0.50),
                ),
                relevance=1.0,
                threshold_flag=energy_gap_ratio >= 0.10,
                contributors={
                    "energy_supply": energy_supply,
                    "energy_demand": energy_demand,
                    "energy_gap_ratio": energy_gap_ratio,
                },
            ),
            "global_sanctions_footprint": CrisisMetric(
                name="global_sanctions_footprint",
                description=GLOBAL_METRIC_DESCRIPTIONS["global_sanctions_footprint"],
                value=sanctions_footprint,
                unit="share",
                level=_normalize(sanctions_footprint, 0.0, 0.15),
                momentum=0.0,
                buffer=clamp01(1.0 - sanctions_footprint / 0.15),
                trigger=_trigger_from_level(_normalize(sanctions_footprint, 0.0, 0.15), 0.40),
                severity=_severity(
                    _normalize(sanctions_footprint, 0.0, 0.15),
                    0.0,
                    clamp01(1.0 - sanctions_footprint / 0.15),
                    _trigger_from_level(_normalize(sanctions_footprint, 0.0, 0.15), 0.40),
                ),
                relevance=1.0,
                threshold_flag=sanctions_footprint >= 0.06,
                contributors={"sanctions_links": float(sanctions_links)},
            ),
            "global_trade_fragmentation": CrisisMetric(
                name="global_trade_fragmentation",
                description=GLOBAL_METRIC_DESCRIPTIONS["global_trade_fragmentation"],
                value=avg_barrier,
                unit="share",
                level=_normalize(avg_barrier, 0.0, 0.70),
                momentum=0.0,
                buffer=clamp01(1.0 - avg_barrier / 0.70),
                trigger=_trigger_from_level(_normalize(avg_barrier, 0.0, 0.70), 0.45),
                severity=_severity(
                    _normalize(avg_barrier, 0.0, 0.70),
                    0.0,
                    clamp01(1.0 - avg_barrier / 0.70),
                    _trigger_from_level(_normalize(avg_barrier, 0.0, 0.70), 0.45),
                ),
                relevance=1.0,
                threshold_flag=avg_barrier >= 0.25,
                contributors={"avg_trade_barrier": avg_barrier, "avg_conflict": avg_conflict},
            ),
        }
        return GlobalCrisisContext(metrics=metrics)

    def compute_global_context(
        self,
        world: WorldState,
        history: List[WorldState] | None = None,
    ) -> GlobalCrisisContext:
        context = self._global_context_body(world)
        if history:
            previous = self._global_context_body(history[-1])
            for name, metric in context.metrics.items():
                previous_metric = previous.metrics.get(name)
                if previous_metric is None:
                    continue
                metric.momentum = metric.level - previous_metric.level
                metric.severity = _severity(metric.level, metric.momentum, metric.buffer, metric.trigger)
        return context

    def _make_metric(
        self,
        name: str,
        value: float,
        unit: str,
        level: float,
        buffer: float,
        trigger: float,
        relevance: float,
        contributors: Dict[str, float],
        momentum: float = 0.0,
        threshold: float = 0.60,
    ) -> CrisisMetric:
        return CrisisMetric(
            name=name,
            description=AGENT_METRIC_DESCRIPTIONS[name],
            value=value,
            unit=unit,
            level=clamp01(level),
            momentum=momentum,
            buffer=clamp01(buffer),
            trigger=clamp01(trigger),
            severity=_severity(level, momentum, buffer, trigger),
            relevance=relevance,
            threshold_flag=level >= threshold,
            contributors=contributors,
        )

    def _agent_report_body(
        self,
        agent_id: str,
        world: WorldState,
        global_context: GlobalCrisisContext,
    ) -> AgentCrisisReport:
        agent = world.agents[agent_id]
        archetype = self.detect_archetype(agent, world)
        relevance_map = ARCHETYPE_RELEVANCE[archetype]
        relation_stats = self._relation_stats(world, agent_id)
        reserve_years = compute_reserve_years(agent)

        baseline_gdp_pc = getattr(world.global_state, "baseline_gdp_pc", 0.0) or 20_000.0
        gdp_pc = agent.economy.gdp_per_capita or (
            agent.economy.gdp * 1e12 / max(agent.economy.population, 1.0)
        )

        energy_gap = _resource_gap_ratio(agent, "energy")
        food_gap = _resource_gap_ratio(agent, "food")
        metals_gap = _resource_gap_ratio(agent, "metals")
        import_dependency = 0.50 * energy_gap + 0.30 * food_gap + 0.20 * metals_gap
        avg_trade_intensity = relation_stats["avg_trade_intensity"]
        avg_trade_barrier = relation_stats["avg_trade_barrier"]
        avg_trust = relation_stats["avg_trust"]
        avg_conflict = relation_stats["avg_conflict"]

        active_sanctions = float(len(agent.active_sanctions))
        oil_stress = global_context.metrics["global_oil_market_stress"]
        trade_fragmentation = global_context.metrics["global_trade_fragmentation"]

        price_energy = world.global_state.prices.get("energy", 1.0)
        price_food = world.global_state.prices.get("food", 1.0)
        price_metals = world.global_state.prices.get("metals", 1.0)
        sanctions_scale = clamp01(active_sanctions / 4.0)

        inflation_estimate = max(
            0.0,
            agent.economy.inflation
            + 0.07 * max(price_energy - 1.0, 0.0) * (0.4 + 0.6 * energy_gap)
            + 0.05 * max(price_food - 1.0, 0.0) * (0.3 + 0.7 * food_gap)
            + 0.03 * max(price_metals - 1.0, 0.0) * (0.2 + 0.8 * metals_gap)
            + 0.04 * sanctions_scale
            + 0.03 * avg_trade_barrier,
        )
        inflation_level = _normalize(inflation_estimate, 0.02, 0.15)
        inflation_buffer = clamp01(1.0 - import_dependency)
        inflation_trigger = _trigger_from_level(inflation_level, 0.55)

        import_bill_proxy = agent.economy.gdp * (0.08 + 0.24 * import_dependency + 0.10 * avg_trade_intensity)
        monthly_import_bill = max(import_bill_proxy / 12.0, 1e-6)
        fx_cover_months = agent.economy.fx_reserves / monthly_import_bill
        fx_level = clamp01(max(0.0, 6.0 - min(fx_cover_months, 6.0)) / 6.0)
        fx_buffer = clamp01(fx_cover_months / 6.0)
        fx_trigger = clamp01(max(0.0, 3.0 - min(fx_cover_months, 3.0)) / 3.0)

        debt_gdp = _safe_div(agent.economy.public_debt, max(agent.economy.gdp, 1e-6), 0.0)
        interest_rate = compute_effective_interest_rate(agent, world)
        interest_to_revenue = _safe_div(
            agent.economy.interest_payments or (interest_rate * agent.economy.public_debt),
            max(agent.economy.taxes or (0.22 * agent.economy.gdp), 1e-6),
            0.0,
        )
        sovereign_level = clamp01(
            0.35 * _normalize(debt_gdp, 0.6, 1.4)
            + 0.25 * _normalize(interest_rate, 0.03, 0.15)
            + 0.20 * _normalize(interest_to_revenue, 0.10, 0.40)
            + 0.20 * fx_level
        )
        sovereign_buffer = clamp01(0.5 * fx_buffer + 0.5 * (1.0 - _normalize(debt_gdp, 0.6, 1.4)))
        sovereign_trigger = clamp01(
            0.6 * clamp01(max(debt_gdp - 1.2, 0.0) / 0.4)
            + 0.4 * clamp01(max(interest_rate - 0.12, 0.0) / 0.08)
        )

        food_cover_days = _cover_days(agent, "food")
        income_buffer = clamp01(gdp_pc / max(1.5 * baseline_gdp_pc, 1.0))
        basket_price = 0.60 * price_food + 0.25 * price_energy + 0.15 * price_metals
        food_level = clamp01(
            0.45 * food_gap
            + 0.25 * _normalize(basket_price, 1.0, 2.2)
            + 0.15 * inflation_level
            + 0.15 * (1.0 - income_buffer)
        )
        food_buffer = clamp01(0.5 * income_buffer + 0.5 * min(food_cover_days / 180.0, 1.0))
        food_trigger = clamp01(0.6 * food_gap + 0.4 * (1.0 - food_buffer))

        protest_base = compute_protest_risk(agent)
        unemployment_norm = _normalize(agent.economy.unemployment, 0.04, 0.20)
        protest_level = clamp01(
            0.35 * protest_base
            + 0.20 * inflation_level
            + 0.15 * unemployment_norm
            + 0.15 * food_level
            + 0.15 * (1.0 - agent.society.trust_gov)
        )
        protest_buffer = clamp01(0.5 * agent.society.trust_gov + 0.5 * agent.risk.regime_stability)
        protest_trigger = clamp01(0.5 * protest_level + 0.5 * agent.political.protest_pressure)

        regime_level = clamp01(
            0.30 * (1.0 - agent.risk.regime_stability)
            + 0.20 * (1.0 - agent.society.trust_gov)
            + 0.20 * agent.society.social_tension
            + 0.15 * protest_level
            + 0.15 * sanctions_scale
        )
        regime_buffer = clamp01(
            0.35 * agent.technology.security_index
            + 0.30 * agent.political.policy_space
            + 0.35 * agent.society.trust_gov
        )
        regime_trigger = clamp01(0.6 * protest_level + 0.4 * (1.0 - agent.risk.regime_stability))

        sanctions_level = clamp01(
            0.35 * sanctions_scale
            + 0.20 * avg_trade_barrier
            + 0.20 * trade_fragmentation.level
            + 0.15 * fx_level
            + 0.10 * clamp01(max(0.5 - avg_trade_intensity, 0.0) / 0.5)
        )
        sanctions_buffer = clamp01(
            0.50 * agent.political.policy_space + 0.50 * (1.0 - avg_trade_barrier)
        )
        sanctions_trigger = clamp01(0.7 * sanctions_scale + 0.3 * avg_trade_barrier)

        reserve_stress = clamp01(
            0.50 * _normalize(max(5.0 - reserve_years.get("energy", 5.0), 0.0), 0.0, 5.0)
            + 0.30 * _normalize(max(3.0 - reserve_years.get("food", 3.0), 0.0), 0.0, 3.0)
            + 0.20 * _normalize(max(5.0 - reserve_years.get("metals", 5.0), 0.0), 0.0, 5.0)
        )
        strategic_level = clamp01(0.60 * import_dependency + 0.40 * reserve_stress)
        strategic_buffer = clamp01(1.0 - reserve_stress)
        strategic_trigger = clamp01(0.7 * import_dependency + 0.3 * reserve_stress)

        route_risk = REGIONAL_ROUTE_RISK.get(agent.region, 0.40)
        chokepoint_level = clamp01(
            0.40 * (energy_gap * avg_trade_intensity)
            + 0.20 * avg_trade_intensity
            + 0.25 * oil_stress.level
            + 0.15 * route_risk
        )
        chokepoint_buffer = clamp01(1.0 - energy_gap * avg_trade_intensity)
        chokepoint_trigger = clamp01(0.6 * oil_stress.level + 0.4 * chokepoint_level)

        energy_cover_days = _cover_days(agent, "energy")
        energy_export_ratio = max(
            0.0,
            _safe_div(
                agent.resources["energy"].production - agent.resources["energy"].consumption,
                max(agent.resources["energy"].production, 1e-6),
                default=0.0,
            ),
        )
        oil_level = clamp01(
            0.45 * energy_gap
            + 0.20 * (1.0 - min(energy_cover_days / 180.0, 1.0))
            + 0.20 * chokepoint_level
            + 0.15 * (energy_export_ratio * oil_stress.level)
        )
        oil_buffer = clamp01(0.60 * min(energy_cover_days / 180.0, 1.0) + 0.40 * (1.0 - energy_gap))
        oil_trigger = clamp01(0.5 * oil_stress.level + 0.5 * energy_gap)

        conflict_level = clamp01(
            0.30 * avg_conflict
            + 0.20 * (1.0 - avg_trust)
            + 0.15 * agent.political.hawkishness
            + 0.15 * clamp01(agent.technology.military_power / 2.0)
            + 0.10 * sanctions_level
            + 0.10 * relation_stats["war_links"]
        )
        conflict_buffer = clamp01(
            0.50 * agent.political.coalition_openness + 0.50 * agent.technology.security_index
        )
        conflict_trigger = clamp01(
            0.50 * avg_conflict + 0.30 * agent.political.hawkishness + 0.20 * relation_stats["war_links"]
        )

        metrics = {
            "inflation": self._make_metric(
                name="inflation",
                value=inflation_estimate,
                unit="share",
                level=inflation_level,
                buffer=inflation_buffer,
                trigger=inflation_trigger,
                relevance=relevance_map["inflation"],
                contributors={
                    "base_inflation": agent.economy.inflation,
                    "energy_price": price_energy,
                    "food_price": price_food,
                    "sanctions_scale": sanctions_scale,
                },
            ),
            "oil_vulnerability": self._make_metric(
                name="oil_vulnerability",
                value=oil_level,
                unit="index",
                level=oil_level,
                buffer=oil_buffer,
                trigger=oil_trigger,
                relevance=relevance_map["oil_vulnerability"],
                contributors={
                    "energy_gap": energy_gap,
                    "energy_cover_days": energy_cover_days,
                    "route_pressure": chokepoint_level,
                    "energy_export_ratio": energy_export_ratio,
                },
            ),
            "fx_stress": self._make_metric(
                name="fx_stress",
                value=fx_cover_months,
                unit="months",
                level=fx_level,
                buffer=fx_buffer,
                trigger=fx_trigger,
                relevance=relevance_map["fx_stress"],
                contributors={
                    "fx_reserves": agent.economy.fx_reserves,
                    "monthly_import_bill_proxy": monthly_import_bill,
                    "import_dependency": import_dependency,
                },
            ),
            "sovereign_stress": self._make_metric(
                name="sovereign_stress",
                value=debt_gdp,
                unit="debt_to_gdp",
                level=sovereign_level,
                buffer=sovereign_buffer,
                trigger=sovereign_trigger,
                relevance=relevance_map["sovereign_stress"],
                contributors={
                    "debt_gdp": debt_gdp,
                    "interest_rate": interest_rate,
                    "interest_to_revenue": interest_to_revenue,
                    "debt_stress_core": compute_debt_stress(agent),
                },
            ),
            "food_affordability_stress": self._make_metric(
                name="food_affordability_stress",
                value=basket_price,
                unit="basket_index",
                level=food_level,
                buffer=food_buffer,
                trigger=food_trigger,
                relevance=relevance_map["food_affordability_stress"],
                contributors={
                    "food_gap": food_gap,
                    "food_cover_days": food_cover_days,
                    "income_buffer": income_buffer,
                    "basket_price": basket_price,
                },
            ),
            "protest_pressure": self._make_metric(
                name="protest_pressure",
                value=protest_level,
                unit="index",
                level=protest_level,
                buffer=protest_buffer,
                trigger=protest_trigger,
                relevance=relevance_map["protest_pressure"],
                contributors={
                    "base_protest_risk": protest_base,
                    "inflation_level": inflation_level,
                    "unemployment_norm": unemployment_norm,
                    "food_stress": food_level,
                },
            ),
            "regime_fragility": self._make_metric(
                name="regime_fragility",
                value=regime_level,
                unit="index",
                level=regime_level,
                buffer=regime_buffer,
                trigger=regime_trigger,
                relevance=relevance_map["regime_fragility"],
                contributors={
                    "regime_stability": agent.risk.regime_stability,
                    "trust_gov": agent.society.trust_gov,
                    "social_tension": agent.society.social_tension,
                    "policy_space": agent.political.policy_space,
                },
            ),
            "sanctions_strangulation": self._make_metric(
                name="sanctions_strangulation",
                value=sanctions_level,
                unit="index",
                level=sanctions_level,
                buffer=sanctions_buffer,
                trigger=sanctions_trigger,
                relevance=relevance_map["sanctions_strangulation"],
                contributors={
                    "active_sanctions": active_sanctions,
                    "avg_trade_barrier": avg_trade_barrier,
                    "avg_trade_intensity": avg_trade_intensity,
                    "fx_stress_level": fx_level,
                },
            ),
            "conflict_escalation_pressure": self._make_metric(
                name="conflict_escalation_pressure",
                value=conflict_level,
                unit="index",
                level=conflict_level,
                buffer=conflict_buffer,
                trigger=conflict_trigger,
                relevance=relevance_map["conflict_escalation_pressure"],
                contributors={
                    "avg_conflict": avg_conflict,
                    "avg_trust": avg_trust,
                    "hawkishness": agent.political.hawkishness,
                    "war_links": relation_stats["war_links"],
                },
            ),
            "strategic_dependency": self._make_metric(
                name="strategic_dependency",
                value=strategic_level,
                unit="index",
                level=strategic_level,
                buffer=strategic_buffer,
                trigger=strategic_trigger,
                relevance=relevance_map["strategic_dependency"],
                contributors={
                    "energy_gap": energy_gap,
                    "food_gap": food_gap,
                    "metals_gap": metals_gap,
                    "reserve_stress": reserve_stress,
                },
            ),
            "chokepoint_exposure": self._make_metric(
                name="chokepoint_exposure",
                value=chokepoint_level,
                unit="index",
                level=chokepoint_level,
                buffer=chokepoint_buffer,
                trigger=chokepoint_trigger,
                relevance=relevance_map["chokepoint_exposure"],
                contributors={
                    "energy_gap": energy_gap,
                    "trade_intensity": avg_trade_intensity,
                    "route_risk": route_risk,
                    "global_oil_stress": oil_stress.level,
                },
            ),
        }

        top_metric_names = [
            name
            for name, _metric in sorted(
                metrics.items(),
                key=lambda item: item[1].severity * item[1].relevance,
                reverse=True,
            )[:5]
        ]

        notes = [
            f"Archetype router selected `{archetype}` for relevance weighting.",
            "Metrics are diagnostic only and do not mutate the underlying world state.",
        ]

        return AgentCrisisReport(
            agent_id=agent_id,
            agent_name=agent.name,
            archetype=archetype,
            metrics=metrics,
            top_metric_names=top_metric_names,
            notes=notes,
        )

    def compute_agent_report(
        self,
        agent_id: str,
        world: WorldState,
        global_context: GlobalCrisisContext | None = None,
        history: List[WorldState] | None = None,
    ) -> AgentCrisisReport:
        context = global_context or self.compute_global_context(world, history=None)
        report = self._agent_report_body(agent_id, world, context)
        if history and history[-1].agents.get(agent_id) is not None:
            previous_context = self.compute_global_context(history[-1], history=None)
            previous_report = self._agent_report_body(agent_id, history[-1], previous_context)
            for name, metric in report.metrics.items():
                previous_metric = previous_report.metrics.get(name)
                if previous_metric is None:
                    continue
                metric.momentum = metric.level - previous_metric.level
                metric.severity = _severity(metric.level, metric.momentum, metric.buffer, metric.trigger)
            report.top_metric_names = [
                name
                for name, _metric in sorted(
                    report.metrics.items(),
                    key=lambda item: item[1].severity * item[1].relevance,
                    reverse=True,
                )[:5]
            ]
        return report

    def compute_dashboard(
        self,
        world: WorldState,
        agent_ids: List[str] | None = None,
        history: List[WorldState] | None = None,
    ) -> CrisisDashboard:
        context = self.compute_global_context(world, history=history)
        selected_agent_ids = agent_ids
        if selected_agent_ids is None:
            selected_agent_ids = [
                agent.id
                for agent in sorted(
                    world.agents.values(),
                    key=lambda current: current.economy.gdp,
                    reverse=True,
                )[:5]
            ]

        reports = {
            agent_id: self.compute_agent_report(
                agent_id,
                world,
                global_context=context,
                history=history,
            )
            for agent_id in selected_agent_ids
            if agent_id in world.agents
        }
        return CrisisDashboard(global_context=context, agents=reports)
