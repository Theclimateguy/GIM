from __future__ import annotations

import copy
import math
import random
import re
from dataclasses import asdict, dataclass, field
from statistics import median
from typing import Any, Mapping

from .core import Action, Observation, action_from_intent, build_observation, make_human_policy
from .core.logging_utils import log_actions_to_csv, log_institutions_to_csv, log_world_to_csv
from .core.simulation import step_world
from .crisis_metrics import CrisisDashboard, CrisisMetricsEngine
from .runtime import WorldState
from .scenario_compiler import resolve_actor_names
from .sim_bridge import SimBridge
from .types import CalibrationGuardrails, ScenarioDefinition, ScenarioEvaluation


HUMAN_MODE_ACTION = "ACTION"
HUMAN_MODE_WHAT_IF = "WHAT_IF"

DEFAULT_MONITORED_INDICATORS = [
    "gdp",
    "debt_to_gdp",
    "trust_gov",
    "social_tension",
    "conflict_escalation_pressure",
    "global_trade_fragmentation",
    "climate_damage_proxy",
]

BENCHMARK_INTENTS = {
    "balanced_innovation": "Increase AI and R&D spending moderately while keeping fiscal policy prudent and trade open.",
    "fiscal_resilience": "Stabilize debt, rebuild policy space, avoid escalation and keep reserves protected.",
    "social_stability": "Increase social spending moderately, reduce domestic stress and avoid confrontation.",
    "deterrence_with_restraint": "Increase military readiness moderately, avoid open conflict and keep sanctions options limited.",
}

TOPIC_KEYWORDS = {
    "ai_rd": (
        "ai",
        "artificial intelligence",
        "machine learning",
        "r&d",
        "research",
        "innovation",
        "technology",
        "tech",
        "ии",
        "наук",
        "исслед",
        "инновац",
        "технолог",
    ),
    "social": (
        "social",
        "welfare",
        "health",
        "healthcare",
        "education",
        "household",
        "inequality",
        "бедност",
        "социал",
        "здрав",
        "образован",
        "неравен",
        "домохозяй",
    ),
    "military": (
        "military",
        "defense",
        "deterrence",
        "army",
        "security",
        "mobilization",
        "readiness",
        "обор",
        "воен",
        "арм",
        "сдержив",
        "мобилиза",
    ),
    "tax": (
        "tax",
        "taxes",
        "fuel tax",
        "carbon tax",
        "налог",
        "акциз",
        "топлив",
    ),
    "climate": (
        "climate",
        "decarbon",
        "emission",
        "renewable",
        "green",
        "adaptation",
        "климат",
        "декарб",
        "выброс",
        "зелен",
        "адаптац",
    ),
    "trade_open": (
        "trade deal",
        "trade opening",
        "open trade",
        "liberaliz",
        "import more",
        "export more",
        "сделк",
        "открыт торгов",
        "либерализ",
        "увеличить импорт",
        "увеличить экспорт",
    ),
    "trade_restrict": (
        "tariff",
        "export control",
        "trade restriction",
        "restrict trade",
        "protection",
        "embargo",
        "пошлин",
        "тариф",
        "ограничить торгов",
        "протекциони",
        "эмбарго",
    ),
    "sanctions": (
        "sanction",
        "санкц",
        "secondary sanctions",
    ),
    "deescalate": (
        "de-escal",
        "deescal",
        "mediate",
        "negotiat",
        "restraint",
        "dialogue",
        "переговор",
        "медиац",
        "деэскал",
        "сдержан",
        "диалог",
    ),
    "finance": (
        "debt",
        "borrow",
        "reserves",
        "fx",
        "currency",
        "budget",
        "deficit",
        "austerity",
        "delever",
        "долг",
        "заимств",
        "резерв",
        "валют",
        "бюджет",
        "дефицит",
        "экономи",
        "консолидац",
    ),
}

INCREASE_WORDS = (
    "increase",
    "boost",
    "raise",
    "expand",
    "grow",
    "more",
    "up",
    "нараст",
    "увелич",
    "расшир",
    "усил",
    "больше",
)

DECREASE_WORDS = (
    "decrease",
    "reduce",
    "cut",
    "lower",
    "less",
    "down",
    "remove",
    "lift",
    "сниз",
    "сократ",
    "уменьш",
    "ослаб",
    "убрат",
    "отмен",
    "снять",
)

HIGH_INTENSITY_WORDS = (
    "aggressively",
    "strongly",
    "massively",
    "substantially",
    "major",
    "hard",
    "резко",
    "сильно",
    "существенно",
    "масштабно",
    "жестко",
)

LOW_INTENSITY_WORDS = (
    "slightly",
    "lightly",
    "incrementally",
    "gently",
    "мягко",
    "слегка",
    "умеренно",
    "постепенно",
)


@dataclass(frozen=True)
class HybridIntent:
    agent_id: str
    agent_name: str
    raw_text: str
    mode: str
    confidence: float
    intensity: str
    matched_topics: list[str]
    notes: list[str]
    raw_payload: dict[str, Any]
    normalized_action: Action


@dataclass(frozen=True)
class MetricBand:
    median: float
    p10: float
    p90: float


@dataclass(frozen=True)
class AgentRoundMetrics:
    gdp: float
    debt_to_gdp: float
    trust_gov: float
    social_tension: float
    conflict_escalation: float
    trade_fragmentation: float
    climate_damage_proxy: float


@dataclass(frozen=True)
class AgentRoundComparison:
    agent_id: str
    agent_name: str
    baseline: AgentRoundMetrics
    policy: AgentRoundMetrics
    delta: dict[str, float]
    ensemble_delta_bands: dict[str, MetricBand]
    regret_vs_baseline: float
    regret_vs_robust_benchmark: float | None
    dominant_outcomes: list[str]


@dataclass(frozen=True)
class ChannelContribution:
    label: str
    delta_vs_full_policy: dict[str, float]


@dataclass(frozen=True)
class RoundRunArtifacts:
    seed: int
    trajectory: list[WorldState]
    evaluation: ScenarioEvaluation
    action_log: list[dict[str, Any]]
    institution_log: list[dict[str, Any]]
    phase_traces: list[dict[str, Any]]


@dataclass(frozen=True)
class HybridRoundResult:
    mode: str
    round_years: int
    ensemble_size: int
    background_policy: str
    llm_refresh: str
    llm_refresh_years: int
    scenario: ScenarioDefinition
    intents: list[HybridIntent]
    baseline_run: RoundRunArtifacts
    policy_run: RoundRunArtifacts
    robust_benchmark_run: RoundRunArtifacts | None
    actor_comparisons: list[AgentRoundComparison]
    crisis_delta_summary: dict[str, float]
    channel_contributions: dict[str, list[ChannelContribution]]
    effective_actions_by_agent: dict[str, list[dict[str, Any]]]
    policy_world_csv: str | None = None
    baseline_world_csv: str | None = None
    policy_actions_csv: str | None = None
    baseline_actions_csv: str | None = None
    policy_institutions_csv: str | None = None
    baseline_institutions_csv: str | None = None


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ\-+/ ]+", " ", text.lower())).strip()


def _contains_any(text: str, candidates: tuple[str, ...]) -> bool:
    return any(candidate in text for candidate in candidates)


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = max(0.0, min(1.0, q)) * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _metric_band(values: list[float]) -> MetricBand:
    return MetricBand(
        median=_percentile(values, 0.5),
        p10=_percentile(values, 0.1),
        p90=_percentile(values, 0.9),
    )


def _best_neighbor(obs: Observation, *, by: str, reverse: bool = True, exclude_id: str | None = None) -> str | None:
    neighbors = list(obs.external_actors.get("neighbors", []))
    ranked = [
        neighbor
        for neighbor in neighbors
        if isinstance(neighbor, dict) and str(neighbor.get("agent_id", "")).strip()
    ]
    if exclude_id is not None:
        ranked = [neighbor for neighbor in ranked if str(neighbor.get("agent_id")) != exclude_id]
    if not ranked:
        return None
    ranked.sort(key=lambda item: float(item.get(by, 0.0)), reverse=reverse)
    return str(ranked[0].get("agent_id"))


def _primary_rival(obs: Observation) -> str | None:
    neighbors = list(obs.external_actors.get("neighbors", []))
    if not neighbors:
        return None
    ranked = sorted(
        neighbors,
        key=lambda item: (
            float(item.get("conflict_level", 0.0)),
            1.0 - float(item.get("trust", 0.5)),
            float(item.get("gdp", 0.0)),
        ),
        reverse=True,
    )
    top = ranked[0]
    return str(top.get("agent_id")) if top.get("agent_id") else None


def _best_partner(obs: Observation, *, exclude_id: str | None = None) -> str | None:
    neighbors = list(obs.external_actors.get("neighbors", []))
    ranked = [
        neighbor
        for neighbor in neighbors
        if isinstance(neighbor, dict) and str(neighbor.get("agent_id", "")).strip()
    ]
    if exclude_id is not None:
        ranked = [neighbor for neighbor in ranked if str(neighbor.get("agent_id")) != exclude_id]
    if not ranked:
        return None
    ranked.sort(
        key=lambda item: (
            float(item.get("trust", 0.5)),
            1.0 - float(item.get("trade_barrier", 0.0)),
            float(item.get("trade_intensity", 0.0)),
        ),
        reverse=True,
    )
    return str(ranked[0].get("agent_id"))


def _resolve_text_targets(world: WorldState, agent_id: str, text: str) -> tuple[str | None, str | None]:
    actor_ids, _names, _unresolved = resolve_actor_names(world, [text])
    for candidate in actor_ids:
        if candidate != agent_id:
            return candidate, candidate
    obs = build_observation(world, agent_id)
    rival = _primary_rival(obs)
    partner = _best_partner(obs, exclude_id=rival)
    return rival, partner


def _direction(text: str) -> int:
    if _contains_any(text, DECREASE_WORDS) and not _contains_any(text, INCREASE_WORDS):
        return -1
    return 1


def _intensity(text: str) -> tuple[str, float]:
    if _contains_any(text, HIGH_INTENSITY_WORDS):
        return "high", 1.0
    if _contains_any(text, LOW_INTENSITY_WORDS):
        return "low", 0.5
    return "medium", 0.75


def _matched_topics(text: str) -> list[str]:
    topics: list[str] = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if _contains_any(text, keywords):
            topics.append(topic)
    return topics


def _neutral_payload(agent_id: str, text: str) -> dict[str, Any]:
    return {
        "agent_id": agent_id,
        "domestic_policy": {},
        "foreign_policy": {},
        "finance": {},
        "explanation": f"Neutral/no-op intent fallback for: {text}",
    }


def _apply_fiscal_guardrails(payload: dict[str, Any], obs: Observation) -> list[str]:
    notes: list[str] = []
    economy = obs.self_state.get("economy", {})
    political = obs.self_state.get("political", {})
    debt_to_gdp = float(economy.get("public_debt", 0.0)) / max(float(economy.get("gdp", 1.0)), 1e-6)
    policy_space = float(political.get("policy_space", 0.5))

    domestic = payload.setdefault("domestic_policy", {})
    rd = float(domestic.get("rd_investment_change", 0.0) or 0.0)
    social = float(domestic.get("social_spending_change", 0.0) or 0.0)
    military = float(domestic.get("military_spending_change", 0.0) or 0.0)
    net_spending_push = rd + max(0.0, social) + max(0.0, military)

    if net_spending_push > 0.0 and (debt_to_gdp >= 0.75 or policy_space <= 0.35):
        domestic["tax_fuel_change"] = float(domestic.get("tax_fuel_change", 0.0) or 0.0) + min(
            0.25,
            8.0 * net_spending_push,
        )
        notes.append("Added a fiscal offset through fuel taxes because debt stress/policy space is tight.")

    return notes


def _compile_text_intent(
    *,
    world: WorldState,
    agent_id: str,
    mode: str,
    text: str,
) -> HybridIntent:
    obs = build_observation(world, agent_id)
    normalized = _normalize_text(text)
    topics = _matched_topics(normalized)
    direction = _direction(normalized)
    intensity_label, intensity_scale = _intensity(normalized)
    rival_id, partner_id = _resolve_text_targets(world, agent_id, text)
    domestic: dict[str, Any] = {}
    foreign: dict[str, Any] = {}
    finance: dict[str, Any] = {}
    notes: list[str] = []

    if not topics:
        topics = ["ai_rd"] if "эконом" in normalized or "econom" in normalized else []
        if topics:
            notes.append("No direct lever keyword was found; defaulted to growth/innovation interpretation.")

    if "ai_rd" in topics:
        domestic["rd_investment_change"] = direction * (0.002 + 0.004 * intensity_scale)

    if "social" in topics:
        domestic["social_spending_change"] = direction * (0.004 + 0.008 * intensity_scale)

    if "military" in topics:
        domestic["military_spending_change"] = direction * (0.002 + 0.008 * intensity_scale)
        if direction > 0 and rival_id is not None:
            foreign["security_actions"] = {
                "type": "arms_buildup" if intensity_label != "low" else "military_exercise",
                "target": rival_id,
            }

    if "tax" in topics:
        domestic["tax_fuel_change"] = direction * (0.08 + 0.20 * intensity_scale)

    if "climate" in topics:
        domestic["climate_policy"] = {
            "low": "weak",
            "medium": "moderate",
            "high": "strong",
        }[intensity_label] if direction > 0 else "none"

    if "trade_open" in topics and partner_id is not None and direction > 0:
        foreign["proposed_trade_deals"] = [
            {
                "partner": partner_id,
                "resource": "energy",
                "direction": "import",
                "volume_change": 6.0 + 12.0 * intensity_scale,
                "price_preference": "fair",
            }
        ]

    if "trade_restrict" in topics and rival_id is not None:
        foreign.setdefault("trade_restrictions", []).append(
            {
                "target": rival_id,
                "level": "hard" if direction > 0 and intensity_label == "high" else "soft",
                "reason": "human intent trade restriction",
            }
        )

    if "sanctions" in topics and rival_id is not None:
        foreign.setdefault("sanctions_actions", []).append(
            {
                "target": rival_id,
                "type": "strong" if direction > 0 and intensity_label == "high" else ("mild" if direction > 0 else "none"),
                "reason": "human intent sanctions posture",
            }
        )

    if "deescalate" in topics and rival_id is not None:
        foreign["security_actions"] = {"type": "none", "target": rival_id}
        if direction > 0:
            foreign.setdefault("proposed_trade_deals", []).append(
                {
                    "partner": rival_id,
                    "resource": "energy",
                    "direction": "import",
                    "volume_change": 4.0 + 6.0 * intensity_scale,
                    "price_preference": "fair",
                }
            )
        notes.append("Applied a de-escalation interpretation: no kinetic action, optional limited economic normalization.")

    if "finance" in topics:
        debt_stress = float(obs.self_state.get("competitive", {}).get("debt_stress", 0.4))
        if direction > 0 and debt_stress >= 0.5:
            finance["use_fx_reserves_change"] = 0.02 + 0.03 * intensity_scale
            finance["borrow_from_global_markets"] = 0.01 + 0.015 * intensity_scale
        elif direction < 0:
            domestic["tax_fuel_change"] = float(domestic.get("tax_fuel_change", 0.0) or 0.0) + 0.10
            domestic["social_spending_change"] = float(domestic.get("social_spending_change", 0.0) or 0.0) - 0.004
            notes.append("Interpreted finance/debt intent as fiscal consolidation.")

    payload = {
        "agent_id": agent_id,
        "domestic_policy": domestic,
        "foreign_policy": foreign,
        "finance": finance,
        "explanation": f"{mode.lower()} intent: {text}",
    }
    notes.extend(_apply_fiscal_guardrails(payload, obs))
    if not topics and not domestic and not foreign and not finance:
        payload = _neutral_payload(agent_id, text)
        notes.append("Fell back to a no-op action because the intent could not be mapped safely.")

    normalized_action = action_from_intent(payload, agent_id=agent_id, time=world.time)
    confidence = min(0.95, 0.35 + 0.15 * len(topics) + (0.20 if bool(domestic or foreign or finance) else 0.0))
    return HybridIntent(
        agent_id=agent_id,
        agent_name=world.agents[agent_id].name,
        raw_text=text,
        mode=mode,
        confidence=confidence,
        intensity=intensity_label,
        matched_topics=topics,
        notes=notes,
        raw_payload=payload,
        normalized_action=normalized_action,
    )


def compile_human_intent(
    *,
    world: WorldState,
    agent_id: str,
    intent: str | Mapping[str, Any] | Action,
    mode: str = HUMAN_MODE_WHAT_IF,
) -> HybridIntent:
    if isinstance(intent, Action):
        action = action_from_intent(intent, agent_id=agent_id, time=world.time)
        return HybridIntent(
            agent_id=agent_id,
            agent_name=world.agents[agent_id].name,
            raw_text=action.explanation or "structured action",
            mode=mode,
            confidence=1.0,
            intensity="structured",
            matched_topics=["structured_action"],
            notes=["Structured action was provided directly; parser stage was skipped."],
            raw_payload=asdict(action),
            normalized_action=action,
        )
    if isinstance(intent, Mapping):
        action = action_from_intent(intent, agent_id=agent_id, time=world.time)
        return HybridIntent(
            agent_id=agent_id,
            agent_name=world.agents[agent_id].name,
            raw_text=str(intent.get("explanation", "structured intent")),
            mode=mode,
            confidence=1.0,
            intensity="structured",
            matched_topics=["structured_intent"],
            notes=["Structured intent payload was provided directly; text parser stage was skipped."],
            raw_payload=dict(intent),
            normalized_action=action,
        )
    return _compile_text_intent(world=world, agent_id=agent_id, mode=mode, text=str(intent))


def _build_round_scenario(world: WorldState, focus_agent_ids: list[str], round_years: int, title: str) -> ScenarioDefinition:
    base_year = int(getattr(world.global_state, "_calendar_year_base", 2023)) + int(world.time)
    actor_names = [world.agents[agent_id].name for agent_id in focus_agent_ids if agent_id in world.agents]
    return ScenarioDefinition(
        id=f"hybrid-round-{base_year}-{world.time}",
        title=title,
        template_id="hybrid_policy_round",
        source_prompt=title,
        base_year=base_year,
        display_year=base_year,
        horizon_months=max(1, round_years) * 12,
        actor_ids=focus_agent_ids,
        actor_names=actor_names,
        monitored_indicators=list(DEFAULT_MONITORED_INDICATORS),
        assumptions=[
            "Human-controlled tables keep one policy intent fixed for the full round.",
            "Non-table countries use the configured autonomous policy layer.",
            "The round is simulated as yearly internal steps on top of the unchanged core model.",
        ],
        narrative="Hybrid human-in-the-loop policy gaming round.",
        calibration_guardrails=CalibrationGuardrails(),
    )


def _metrics_for_agent(
    dashboard: CrisisDashboard,
    world: WorldState,
    agent_id: str,
) -> AgentRoundMetrics:
    agent = world.agents[agent_id]
    report = dashboard.agents[agent_id]
    trade_fragmentation = dashboard.global_context.metrics["global_trade_fragmentation"].value
    gdp = float(agent.economy.gdp)
    debt_to_gdp = float(agent.economy.public_debt / max(gdp, 1e-6))
    climate_factor = float(getattr(agent.economy, "climate_damage_factor", 1.0))
    return AgentRoundMetrics(
        gdp=gdp,
        debt_to_gdp=debt_to_gdp,
        trust_gov=float(agent.society.trust_gov),
        social_tension=float(agent.society.social_tension),
        conflict_escalation=float(report.metrics["conflict_escalation_pressure"].level),
        trade_fragmentation=float(trade_fragmentation),
        climate_damage_proxy=float(max(0.0, 1.0 - climate_factor)),
    )


def _utility(metrics: AgentRoundMetrics) -> float:
    return (
        0.40 * math.log(max(metrics.gdp, 1e-9))
        - 0.18 * metrics.debt_to_gdp
        + 0.16 * metrics.trust_gov
        - 0.12 * metrics.social_tension
        - 0.08 * metrics.conflict_escalation
        - 0.06 * metrics.trade_fragmentation
        - 0.06 * metrics.climate_damage_proxy
    )


def _delta_metrics(policy: AgentRoundMetrics, baseline: AgentRoundMetrics) -> dict[str, float]:
    return {
        "gdp": policy.gdp - baseline.gdp,
        "gdp_pct": (policy.gdp - baseline.gdp) / max(abs(baseline.gdp), 1e-9),
        "debt_to_gdp": policy.debt_to_gdp - baseline.debt_to_gdp,
        "trust_gov": policy.trust_gov - baseline.trust_gov,
        "social_tension": policy.social_tension - baseline.social_tension,
        "conflict_escalation": policy.conflict_escalation - baseline.conflict_escalation,
        "trade_fragmentation": policy.trade_fragmentation - baseline.trade_fragmentation,
        "climate_damage_proxy": policy.climate_damage_proxy - baseline.climate_damage_proxy,
    }


class HybridSimulator:
    def __init__(self) -> None:
        self.bridge = SimBridge()
        self.metrics_engine = CrisisMetricsEngine()

    def resolve_tables(
        self,
        world: WorldState,
        tables: list[str],
    ) -> tuple[list[str], list[str]]:
        table_ids, table_names, unresolved = resolve_actor_names(world, tables)
        if unresolved:
            raise ValueError(f"Unresolved table actors: {', '.join(unresolved)}")
        if not table_ids:
            raise ValueError("At least one table actor must be resolved.")
        return table_ids, table_names

    def compile_intents(
        self,
        world: WorldState,
        intents_by_actor: Mapping[str, str | Mapping[str, Any] | Action],
        *,
        mode: str,
    ) -> list[HybridIntent]:
        compiled: list[HybridIntent] = []
        for raw_actor, intent in intents_by_actor.items():
            actor_ids, _names, unresolved = resolve_actor_names(world, [raw_actor])
            if unresolved or not actor_ids:
                raise ValueError(f"Unresolved intent actor: {raw_actor}")
            compiled.append(
                compile_human_intent(world=world, agent_id=actor_ids[0], intent=intent, mode=mode)
            )
        if not compiled:
            raise ValueError("No human intents were provided.")
        return compiled

    def _policy_map_with_humans(
        self,
        world: WorldState,
        *,
        compiled_intents: list[HybridIntent],
        default_mode: str,
        llm_refresh: str,
        llm_refresh_years: int,
    ) -> dict[str, Any]:
        policy_map = self.bridge.build_policy_map(
            world,
            game_def=None,
            default_mode=default_mode,
            llm_refresh=llm_refresh,
            llm_refresh_years=llm_refresh_years,
        )
        for item in compiled_intents:
            policy_map[item.agent_id] = make_human_policy(item.normalized_action)
        return policy_map

    def _run_simulation(
        self,
        world: WorldState,
        *,
        policy_map: dict[str, Any],
        scenario: ScenarioDefinition,
        round_years: int,
        seed: int,
        channel_overrides: dict[str, bool] | None = None,
        enable_extreme_events: bool = True,
        capture_logs: bool = True,
    ) -> RoundRunArtifacts:
        sim_world = copy.deepcopy(world)
        action_log: list[dict[str, Any]] = []
        institution_log: list[dict[str, Any]] = []
        trajectory = [copy.deepcopy(sim_world)]
        phase_traces: list[dict[str, Any]] = []
        memory: dict[str, list[dict[str, Any]]] = {}

        sim_world.global_state._temperature_variability_seed = int(seed)
        for year_offset in range(round_years):
            random.seed(int(seed) + year_offset)
            phase_trace: dict[str, Any] = {}
            sim_world = step_world(
                sim_world,
                policy_map,
                memory=memory,
                enable_extreme_events=enable_extreme_events,
                action_log=action_log if capture_logs else None,
                institution_log=institution_log if capture_logs else None,
                phase_trace=phase_trace,
                channel_overrides=channel_overrides,
            )
            phase_traces.append(phase_trace)
            trajectory.append(copy.deepcopy(sim_world))

        evaluation = self.bridge.score_trajectory(trajectory, scenario)
        return RoundRunArtifacts(
            seed=seed,
            trajectory=trajectory,
            evaluation=evaluation,
            action_log=action_log,
            institution_log=institution_log,
            phase_traces=phase_traces,
        )

    def _benchmark_intents(self, world: WorldState, table_ids: list[str], mode: str) -> list[HybridIntent]:
        compiled: list[HybridIntent] = []
        for agent_id in table_ids:
            obs = build_observation(world, agent_id)
            debt_stress = float(obs.self_state.get("competitive", {}).get("debt_stress", 0.4))
            protest_risk = float(obs.self_state.get("competitive", {}).get("protest_risk", 0.4))
            rival = _primary_rival(obs)
            rival_conflict = 0.0
            for neighbor in obs.external_actors.get("neighbors", []):
                if str(neighbor.get("agent_id")) == str(rival):
                    rival_conflict = float(neighbor.get("conflict_level", 0.0))
                    break
            if protest_risk >= 0.65:
                template = BENCHMARK_INTENTS["social_stability"]
            elif debt_stress >= 0.65:
                template = BENCHMARK_INTENTS["fiscal_resilience"]
            elif rival_conflict >= 0.60:
                template = BENCHMARK_INTENTS["deterrence_with_restraint"]
            else:
                template = BENCHMARK_INTENTS["balanced_innovation"]
            compiled.append(compile_human_intent(world=world, agent_id=agent_id, intent=template, mode=mode))
        return compiled

    def _effective_actions(self, action_log: list[dict[str, Any]], focus_agent_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        payload: dict[str, list[dict[str, Any]]] = {agent_id: [] for agent_id in focus_agent_ids}
        for row in action_log:
            agent_id = str(row.get("agent_id", ""))
            if agent_id not in payload:
                continue
            payload[agent_id].append(
                {
                    "time": int(row.get("time", 0)),
                    "domestic_policy": {
                        "tax_fuel_change": float(row.get("dom_tax_fuel_change", 0.0)),
                        "social_spending_change": float(row.get("dom_social_spending_change", 0.0)),
                        "military_spending_change": float(row.get("dom_military_spending_change", 0.0)),
                        "rd_investment_change": float(row.get("dom_rd_investment_change", 0.0)),
                        "climate_policy": row.get("dom_climate_policy", "none"),
                    },
                    "security_applied": {
                        "type": row.get("security_applied_type", "none"),
                        "target": row.get("security_applied_target"),
                    },
                    "avg_trade_barrier": float(row.get("avg_trade_barrier", 0.0)),
                    "avg_relation_conflict": float(row.get("avg_relation_conflict", 0.0)),
                    "explanation": str(row.get("explanation", "")),
                }
            )
        return payload

    def _ensemble_bands(
        self,
        *,
        world: WorldState,
        scenario: ScenarioDefinition,
        compiled_intents: list[HybridIntent],
        round_years: int,
        ensemble_size: int,
        seed: int,
        default_mode: str,
        llm_refresh: str,
        llm_refresh_years: int,
    ) -> dict[str, dict[str, MetricBand]]:
        focus_agent_ids = [item.agent_id for item in compiled_intents]
        deltas: dict[str, dict[str, list[float]]] = {
            agent_id: {metric: [] for metric in DEFAULT_MONITORED_INDICATORS}
            for agent_id in focus_agent_ids
        }

        for member_index in range(max(1, ensemble_size)):
            member_seed = seed + 1000 * member_index
            baseline_policy_map = self.bridge.build_policy_map(
                world,
                game_def=None,
                default_mode=default_mode,
                llm_refresh=llm_refresh,
                llm_refresh_years=llm_refresh_years,
            )
            policy_map = self._policy_map_with_humans(
                world,
                compiled_intents=compiled_intents,
                default_mode=default_mode,
                llm_refresh=llm_refresh,
                llm_refresh_years=llm_refresh_years,
            )
            baseline_run = self._run_simulation(
                world,
                policy_map=baseline_policy_map,
                scenario=scenario,
                round_years=round_years,
                seed=member_seed,
                capture_logs=False,
            )
            policy_run = self._run_simulation(
                world,
                policy_map=policy_map,
                scenario=scenario,
                round_years=round_years,
                seed=member_seed,
                capture_logs=False,
            )
            baseline_dashboard = baseline_run.evaluation.crisis_dashboard
            policy_dashboard = policy_run.evaluation.crisis_dashboard
            for agent_id in focus_agent_ids:
                baseline_metrics = _metrics_for_agent(baseline_dashboard, baseline_run.trajectory[-1], agent_id)
                policy_metrics = _metrics_for_agent(policy_dashboard, policy_run.trajectory[-1], agent_id)
                delta = _delta_metrics(policy_metrics, baseline_metrics)
                deltas[agent_id]["gdp"].append(delta["gdp"])
                deltas[agent_id]["debt_to_gdp"].append(delta["debt_to_gdp"])
                deltas[agent_id]["trust_gov"].append(delta["trust_gov"])
                deltas[agent_id]["social_tension"].append(delta["social_tension"])
                deltas[agent_id]["conflict_escalation_pressure"].append(delta["conflict_escalation"])
                deltas[agent_id]["global_trade_fragmentation"].append(delta["trade_fragmentation"])
                deltas[agent_id]["climate_damage_proxy"].append(delta["climate_damage_proxy"])

        return {
            agent_id: {metric: _metric_band(values) for metric, values in metrics.items()}
            for agent_id, metrics in deltas.items()
        }

    def _channel_contributions(
        self,
        *,
        world: WorldState,
        scenario: ScenarioDefinition,
        compiled_intents: list[HybridIntent],
        round_years: int,
        seed: int,
        default_mode: str,
        llm_refresh: str,
        llm_refresh_years: int,
        full_policy_run: RoundRunArtifacts,
    ) -> dict[str, list[ChannelContribution]]:
        focus_agent_ids = [item.agent_id for item in compiled_intents]
        policy_map = self._policy_map_with_humans(
            world,
            compiled_intents=compiled_intents,
            default_mode=default_mode,
            llm_refresh=llm_refresh,
            llm_refresh_years=llm_refresh_years,
        )
        ablations = {
            "External pressure": {"sanctions_channel": False, "trade_barrier_channel": False},
            "Domestic instability feedback": {"migration_feedback": False, "social_instability_feedback": False},
            "Climate extremes": None,
        }
        contributions: dict[str, list[ChannelContribution]] = {agent_id: [] for agent_id in focus_agent_ids}
        full_dashboard = full_policy_run.evaluation.crisis_dashboard

        for label, overrides in ablations.items():
            ablated = self._run_simulation(
                world,
                policy_map=policy_map,
                scenario=scenario,
                round_years=round_years,
                seed=seed,
                channel_overrides=overrides,
                enable_extreme_events=(label != "Climate extremes"),
                capture_logs=False,
            )
            ablated_dashboard = ablated.evaluation.crisis_dashboard
            for agent_id in focus_agent_ids:
                full_metrics = _metrics_for_agent(full_dashboard, full_policy_run.trajectory[-1], agent_id)
                ablated_metrics = _metrics_for_agent(ablated_dashboard, ablated.trajectory[-1], agent_id)
                contributions[agent_id].append(
                    ChannelContribution(
                        label=label,
                        delta_vs_full_policy={
                            "gdp": full_metrics.gdp - ablated_metrics.gdp,
                            "debt_to_gdp": full_metrics.debt_to_gdp - ablated_metrics.debt_to_gdp,
                            "trust_gov": full_metrics.trust_gov - ablated_metrics.trust_gov,
                            "social_tension": full_metrics.social_tension - ablated_metrics.social_tension,
                            "conflict_escalation": full_metrics.conflict_escalation - ablated_metrics.conflict_escalation,
                            "trade_fragmentation": full_metrics.trade_fragmentation - ablated_metrics.trade_fragmentation,
                            "climate_damage_proxy": full_metrics.climate_damage_proxy - ablated_metrics.climate_damage_proxy,
                        },
                    )
                )
        return contributions

    def run_round(
        self,
        world: WorldState,
        *,
        intents_by_actor: Mapping[str, str | Mapping[str, Any] | Action],
        mode: str = HUMAN_MODE_WHAT_IF,
        round_years: int = 4,
        ensemble_size: int = 3,
        seed: int = 2026,
        default_mode: str = "compiled-llm",
        llm_refresh: str = "trigger",
        llm_refresh_years: int = 2,
        artifact_dir: str | None = None,
    ) -> HybridRoundResult:
        resolved_mode = str(mode or HUMAN_MODE_WHAT_IF).upper()
        if resolved_mode not in {HUMAN_MODE_ACTION, HUMAN_MODE_WHAT_IF}:
            raise ValueError("mode must be ACTION or WHAT_IF")

        compiled_intents = self.compile_intents(world, intents_by_actor, mode=resolved_mode)
        focus_agent_ids = [item.agent_id for item in compiled_intents]
        scenario = _build_round_scenario(
            world,
            focus_agent_ids=focus_agent_ids,
            round_years=round_years,
            title=f"Hybrid policy round ({resolved_mode.lower()})",
        )

        baseline_policy_map = self.bridge.build_policy_map(
            world,
            game_def=None,
            default_mode=default_mode,
            llm_refresh=llm_refresh,
            llm_refresh_years=llm_refresh_years,
        )
        policy_map = self._policy_map_with_humans(
            world,
            compiled_intents=compiled_intents,
            default_mode=default_mode,
            llm_refresh=llm_refresh,
            llm_refresh_years=llm_refresh_years,
        )
        robust_intents = self._benchmark_intents(world, focus_agent_ids, resolved_mode)
        robust_policy_map = self._policy_map_with_humans(
            world,
            compiled_intents=robust_intents,
            default_mode=default_mode,
            llm_refresh=llm_refresh,
            llm_refresh_years=llm_refresh_years,
        )

        baseline_run = self._run_simulation(
            world,
            policy_map=baseline_policy_map,
            scenario=scenario,
            round_years=round_years,
            seed=seed,
            capture_logs=True,
        )
        policy_run = self._run_simulation(
            world,
            policy_map=policy_map,
            scenario=scenario,
            round_years=round_years,
            seed=seed,
            capture_logs=True,
        )
        robust_run = self._run_simulation(
            world,
            policy_map=robust_policy_map,
            scenario=scenario,
            round_years=round_years,
            seed=seed,
            capture_logs=False,
        )

        ensemble_bands = self._ensemble_bands(
            world=world,
            scenario=scenario,
            compiled_intents=compiled_intents,
            round_years=round_years,
            ensemble_size=ensemble_size,
            seed=seed,
            default_mode=default_mode,
            llm_refresh=llm_refresh,
            llm_refresh_years=llm_refresh_years,
        )
        channel_contributions = self._channel_contributions(
            world=world,
            scenario=scenario,
            compiled_intents=compiled_intents,
            round_years=round_years,
            seed=seed,
            default_mode=default_mode,
            llm_refresh=llm_refresh,
            llm_refresh_years=llm_refresh_years,
            full_policy_run=policy_run,
        )

        baseline_dashboard = baseline_run.evaluation.crisis_dashboard
        policy_dashboard = policy_run.evaluation.crisis_dashboard
        robust_dashboard = robust_run.evaluation.crisis_dashboard
        delta_by_agent, crisis_delta_summary = self.bridge._compute_crisis_delta(
            baseline_dashboard=baseline_dashboard,
            terminal_dashboard=policy_dashboard,
        )
        del delta_by_agent

        comparisons: list[AgentRoundComparison] = []
        for item in compiled_intents:
            baseline_metrics = _metrics_for_agent(baseline_dashboard, baseline_run.trajectory[-1], item.agent_id)
            policy_metrics = _metrics_for_agent(policy_dashboard, policy_run.trajectory[-1], item.agent_id)
            robust_metrics = _metrics_for_agent(robust_dashboard, robust_run.trajectory[-1], item.agent_id)
            comparisons.append(
                AgentRoundComparison(
                    agent_id=item.agent_id,
                    agent_name=item.agent_name,
                    baseline=baseline_metrics,
                    policy=policy_metrics,
                    delta=_delta_metrics(policy_metrics, baseline_metrics),
                    ensemble_delta_bands=ensemble_bands[item.agent_id],
                    regret_vs_baseline=_utility(baseline_metrics) - _utility(policy_metrics),
                    regret_vs_robust_benchmark=_utility(robust_metrics) - _utility(policy_metrics),
                    dominant_outcomes=list(policy_run.evaluation.dominant_outcomes),
                )
            )

        effective_actions_by_agent = self._effective_actions(policy_run.action_log, focus_agent_ids)

        policy_world_csv = None
        baseline_world_csv = None
        policy_actions_csv = None
        baseline_actions_csv = None
        policy_institutions_csv = None
        baseline_institutions_csv = None
        if artifact_dir:
            policy_world_csv = log_world_to_csv(policy_run.trajectory, "hybrid_policy_round", base_dir=artifact_dir)
            baseline_world_csv = log_world_to_csv(baseline_run.trajectory, "hybrid_baseline_round", base_dir=artifact_dir)
            policy_actions_csv = log_actions_to_csv(policy_run.action_log, "hybrid_policy_round", base_dir=artifact_dir)
            baseline_actions_csv = log_actions_to_csv(
                baseline_run.action_log,
                "hybrid_baseline_round",
                base_dir=artifact_dir,
            )
            policy_institutions_csv = log_institutions_to_csv(
                policy_run.institution_log,
                "hybrid_policy_round",
                base_dir=artifact_dir,
            )
            baseline_institutions_csv = log_institutions_to_csv(
                baseline_run.institution_log,
                "hybrid_baseline_round",
                base_dir=artifact_dir,
            )

        return HybridRoundResult(
            mode=resolved_mode,
            round_years=round_years,
            ensemble_size=max(1, ensemble_size),
            background_policy=default_mode,
            llm_refresh=llm_refresh,
            llm_refresh_years=llm_refresh_years,
            scenario=scenario,
            intents=compiled_intents,
            baseline_run=baseline_run,
            policy_run=policy_run,
            robust_benchmark_run=robust_run,
            actor_comparisons=comparisons,
            crisis_delta_summary=crisis_delta_summary,
            channel_contributions=channel_contributions,
            effective_actions_by_agent=effective_actions_by_agent,
            policy_world_csv=policy_world_csv,
            baseline_world_csv=baseline_world_csv,
            policy_actions_csv=policy_actions_csv,
            baseline_actions_csv=baseline_actions_csv,
            policy_institutions_csv=policy_institutions_csv,
            baseline_institutions_csv=baseline_institutions_csv,
        )


def hybrid_result_payload(result: HybridRoundResult) -> dict[str, Any]:
    summary = {
        "mode": result.mode,
        "round_years": result.round_years,
        "ensemble_size": result.ensemble_size,
        "background_policy": result.background_policy,
        "llm_refresh": result.llm_refresh,
        "llm_refresh_years": result.llm_refresh_years,
        "intents": [
            {
                "agent_id": item.agent_id,
                "agent_name": item.agent_name,
                "raw_text": item.raw_text,
                "mode": item.mode,
                "confidence": item.confidence,
                "intensity": item.intensity,
                "matched_topics": list(item.matched_topics),
                "notes": list(item.notes),
                "raw_payload": item.raw_payload,
                "normalized_action": asdict(item.normalized_action),
            }
            for item in result.intents
        ],
        "actor_comparisons": [asdict(item) for item in result.actor_comparisons],
        "crisis_delta_summary": dict(result.crisis_delta_summary),
        "channel_contributions": {
            agent_id: [asdict(item) for item in contributions]
            for agent_id, contributions in result.channel_contributions.items()
        },
        "effective_actions_by_agent": copy.deepcopy(result.effective_actions_by_agent),
        "baseline_seed": result.baseline_run.seed,
        "policy_seed": result.policy_run.seed,
        "robust_benchmark_seed": result.robust_benchmark_run.seed if result.robust_benchmark_run is not None else None,
        "robust_benchmark_dominant_outcomes": (
            list(result.robust_benchmark_run.evaluation.dominant_outcomes)
            if result.robust_benchmark_run is not None
            else []
        ),
        "policy_world_csv": result.policy_world_csv,
        "baseline_world_csv": result.baseline_world_csv,
        "policy_actions_csv": result.policy_actions_csv,
        "baseline_actions_csv": result.baseline_actions_csv,
        "policy_institutions_csv": result.policy_institutions_csv,
        "baseline_institutions_csv": result.baseline_institutions_csv,
    }
    return {
        "scenario": asdict(result.scenario),
        "evaluation": asdict(result.policy_run.evaluation),
        "baseline_evaluation": asdict(result.baseline_run.evaluation),
        "trajectory": [asdict(state) for state in result.policy_run.trajectory],
        "baseline_trajectory": [asdict(state) for state in result.baseline_run.trajectory],
        "hybrid_result": summary,
    }


def format_hybrid_result(result: HybridRoundResult) -> str:
    lines = [
        f"Hybrid round: {result.mode} | horizon={result.round_years}y | ensemble={result.ensemble_size}",
        f"Background policy: {result.background_policy} ({result.llm_refresh}/{result.llm_refresh_years}y)",
        "",
    ]
    for item, comparison in zip(result.intents, result.actor_comparisons):
        gdp_band = comparison.ensemble_delta_bands["gdp"]
        lines.extend(
            [
                f"{comparison.agent_name}",
                f"  intent: {item.raw_text}",
                f"  matched topics: {', '.join(item.matched_topics) or 'none'} | confidence={item.confidence:.2f}",
                f"  ΔGDP vs baseline: {comparison.delta['gdp_pct'] * 100.0:+.2f}% "
                f"(P10/P90 {100.0 * gdp_band.p10 / max(abs(comparison.baseline.gdp), 1e-9):+.2f}% / "
                f"{100.0 * gdp_band.p90 / max(abs(comparison.baseline.gdp), 1e-9):+.2f}%)",
                f"  Δdebt/GDP: {comparison.delta['debt_to_gdp']:+.3f} | "
                f"Δtrust: {comparison.delta['trust_gov']:+.3f} | "
                f"Δtension: {comparison.delta['social_tension']:+.3f}",
                f"  regret vs baseline: {comparison.regret_vs_baseline:+.4f} | "
                f"regret vs robust benchmark: {comparison.regret_vs_robust_benchmark:+.4f}",
                "",
            ]
        )
    lines.append(
        "Crisis delta summary: "
        + ", ".join(f"{key}={value:+.3f}" for key, value in result.crisis_delta_summary.items())
    )
    return "\n".join(lines)


def render_hybrid_report_markdown(result: HybridRoundResult) -> str:
    top_outcomes = sorted(
        result.policy_run.evaluation.risk_probabilities.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:5]
    top_drivers = sorted(
        result.policy_run.evaluation.driver_scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:5]
    lines = [
        "## Decision-Maker Interpretation",
        f"The round was simulated in `{result.mode}` mode for {result.round_years} internal yearly steps.",
        "Policy actions were compared against the unchanged baseline and a deterministic robust benchmark.",
        "",
        "## Executive Summary",
        f"- Background policy layer: `{result.background_policy}` (`{result.llm_refresh}` refresh, every {result.llm_refresh_years} years when periodic).",
        f"- Ensemble size: `{result.ensemble_size}` matched-seed replications.",
        f"- Human tables: {', '.join(item.agent_name for item in result.intents)}.",
        "",
        "## Outcome Distribution",
    ]
    lines.extend(
        f"{index}. {name.replace('_', ' ').title()}: {100.0 * probability:.1f}%"
        for index, (name, probability) in enumerate(top_outcomes, start=1)
    )
    lines.extend(["", "## Main Drivers"])
    lines.extend(
        f"{name.replace('_', ' ').title()}: {value:.2f}"
        for name, value in top_drivers
    )
    lines.extend(["", "## Human Intents"])
    for item in result.intents:
        lines.append(f"- **{item.agent_name}**: {item.raw_text}")
        lines.append(
            f"  topics={', '.join(item.matched_topics) or 'none'} | intensity={item.intensity} | confidence={item.confidence:.2f}"
        )
        if item.notes:
            lines.append(f"  notes: {'; '.join(item.notes)}")
    lines.extend(["", "## Baseline Vs Policy"])
    for comparison in result.actor_comparisons:
        lines.append(f"### {comparison.agent_name}")
        lines.append(
            f"- GDP: {comparison.baseline.gdp:.2f} -> {comparison.policy.gdp:.2f} "
            f"({100.0 * comparison.delta['gdp_pct']:+.2f}%)"
        )
        lines.append(
            f"- Debt/GDP: {comparison.baseline.debt_to_gdp:.3f} -> {comparison.policy.debt_to_gdp:.3f} "
            f"({comparison.delta['debt_to_gdp']:+.3f})"
        )
        lines.append(
            f"- Trust/Tension: {comparison.baseline.trust_gov:.3f}/{comparison.baseline.social_tension:.3f} "
            f"-> {comparison.policy.trust_gov:.3f}/{comparison.policy.social_tension:.3f}"
        )
        lines.append(
            f"- Conflict/Trade/Climate: {comparison.policy.conflict_escalation:.3f} / "
            f"{comparison.policy.trade_fragmentation:.3f} / {comparison.policy.climate_damage_proxy:.3f}"
        )
        lines.append(
            f"- Regret: baseline {comparison.regret_vs_baseline:+.4f}, "
            f"robust benchmark {comparison.regret_vs_robust_benchmark:+.4f}"
        )
    lines.extend(["", "## Channel Decomposition"])
    for comparison in result.actor_comparisons:
        lines.append(f"### {comparison.agent_name}")
        for contribution in result.channel_contributions.get(comparison.agent_id, []):
            lines.append(
                f"- {contribution.label}: "
                f"ΔGDP={contribution.delta_vs_full_policy['gdp']:+.2f}, "
                f"Δdebt/GDP={contribution.delta_vs_full_policy['debt_to_gdp']:+.3f}, "
                f"Δtrust={contribution.delta_vs_full_policy['trust_gov']:+.3f}, "
                f"Δtension={contribution.delta_vs_full_policy['social_tension']:+.3f}"
            )
    return "\n".join(lines) + "\n"
