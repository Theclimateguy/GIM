from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from hashlib import sha1
from threading import Lock
from typing import Any, Callable

from .core.core import (
    Action,
    DomesticPolicy,
    FinancePolicy,
    ForeignPolicy,
    Observation,
    SanctionsAction,
    SecurityActions,
    TradeDeal,
    TradeRestriction,
)
from .core.policy import (
    _normalize_action_for_stability,
    call_llm,
    growth_seeking_policy,
    llm_enablement_status,
    simple_rule_based_policy,
)


COMPILED_DOCTRINE_SCHEMA = """
Return ONLY one JSON object with these fields:
{
  "domestic_priority": 0.0,
  "escalation_bias": 0.0,
  "sanctions_tolerance": 0.0,
  "trade_openness": 0.0,
  "mediation_openness": 0.0,
  "reserve_protection": 0.0,
  "military_readiness": 0.0,
  "finance_defensiveness": 0.0,
  "climate_pragmatism": 0.0,
  "explanation": ""
}

All scalar fields must be in [0.0, 1.0].
The output is a multi-year governing doctrine, not a yearly action.
"""

COMPILED_DOCTRINE_PROMPT = (
    "You are compiling a medium-term doctrine for one government.\n"
    "Do not output a yearly policy action. Output latent strategic preferences that will be reused for several years.\n"
    "The doctrine must reflect the country's own regime, culture, macro fragility, resource exposure, security posture and nearby rivals.\n"
    "Use higher escalation_bias only when conflict exposure and hawkishness justify it.\n"
    "Use higher domestic_priority when unrest, debt stress or low policy space constrain external ambition.\n"
    "Use higher reserve_protection when energy/food/metals exposure is acute.\n"
    "Use higher finance_defensiveness when debt stress, protest risk or low trust constrain aggressive borrowing.\n"
    "Use higher mediation_openness when coalition openness and trust support de-escalation.\n\n"
    "Context:\n{context_json}\n\n"
    "{schema_hint}\n"
)


def _clamp01(value: Any, default: float = 0.5) -> float:
    try:
        numeric = float(value)
    except Exception:
        numeric = default
    return max(0.0, min(1.0, numeric))


def _bounded(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _bucket(value: float, thresholds: list[float]) -> int:
    for index, threshold in enumerate(thresholds):
        if value < threshold:
            return index
    return len(thresholds)


def _first_non_zero(values: dict[str, float]) -> tuple[str, float]:
    if not values:
        return "energy", 0.0
    return max(values.items(), key=lambda item: item[1])


def _top_rival(obs: Observation) -> dict[str, Any] | None:
    rivals = sorted(
        obs.external_actors.get("neighbors", []),
        key=lambda item: (
            float(item.get("conflict_level", 0.0)) - float(item.get("trust", 0.5)),
            float(item.get("gdp", 0.0)),
        ),
        reverse=True,
    )
    return rivals[0] if rivals else None


def _top_partner(obs: Observation, *, allow_primary_rival: str | None) -> dict[str, Any] | None:
    candidates = []
    for neighbor in obs.external_actors.get("neighbors", []):
        if allow_primary_rival and neighbor.get("agent_id") == allow_primary_rival:
            continue
        trust = float(neighbor.get("trust", 0.5))
        conflict = float(neighbor.get("conflict_level", 0.0))
        barrier = float(neighbor.get("trade_barrier", 0.0))
        score = (trust * 0.6) + ((1.0 - conflict) * 0.3) + ((1.0 - barrier) * 0.1)
        candidates.append((score, neighbor))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _context_payload(obs: Observation, memory_summary: dict[str, Any] | None) -> dict[str, Any]:
    resources = obs.self_state.get("resources", {})
    compact_resources = {
        name: {
            "reserve": float(resource.get("own_reserve", 0.0)),
            "production": float(resource.get("production", 0.0)),
            "consumption": float(resource.get("consumption", 0.0)),
        }
        for name, resource in resources.items()
    }
    rival = _top_rival(obs)
    partner = _top_partner(obs, allow_primary_rival=rival.get("agent_id") if rival else None)
    return {
        "agent_id": obs.agent_id,
        "time": obs.time,
        "economy": {
            "gdp": obs.self_state.get("economy", {}).get("gdp"),
            "gdp_per_capita": obs.self_state.get("economy", {}).get("gdp_per_capita"),
            "public_debt": obs.self_state.get("economy", {}).get("public_debt"),
            "fx_reserves": obs.self_state.get("economy", {}).get("fx_reserves"),
        },
        "society": {
            "trust_gov": obs.self_state.get("society", {}).get("trust_gov"),
            "social_tension": obs.self_state.get("society", {}).get("social_tension"),
            "inequality_gini": obs.self_state.get("society", {}).get("inequality_gini"),
        },
        "political": obs.self_state.get("political", {}),
        "culture": obs.self_state.get("culture", {}),
        "risk": obs.self_state.get("risk", {}),
        "competitive": obs.self_state.get("competitive", {}),
        "alliance_block": obs.self_state.get("alliance_block"),
        "active_sanctions": obs.self_state.get("active_sanctions", {}),
        "resources": compact_resources,
        "resource_balance": obs.resource_balance,
        "primary_rival": rival,
        "best_available_partner": partner,
        "memory_summary": memory_summary or {"horizon": 0},
    }


@dataclass(frozen=True)
class CompiledDoctrine:
    agent_id: str
    compiled_at_time: int
    context_signature: str
    source: str
    domestic_priority: float
    escalation_bias: float
    sanctions_tolerance: float
    trade_openness: float
    mediation_openness: float
    reserve_protection: float
    military_readiness: float
    finance_defensiveness: float
    climate_pragmatism: float
    explanation: str


class CompiledLLMPolicyManager:
    def __init__(
        self,
        *,
        refresh_mode: str = "trigger",
        refresh_years: int = 2,
        prefer_llm: bool = True,
    ) -> None:
        normalized_mode = (refresh_mode or "trigger").strip().lower()
        if normalized_mode not in {"trigger", "periodic", "never"}:
            raise ValueError("refresh_mode must be trigger, periodic, or never")
        self.refresh_mode = normalized_mode
        self.refresh_years = max(int(refresh_years), 1)
        self.prefer_llm = prefer_llm
        self._doctrine_cache: dict[tuple[str, str], CompiledDoctrine] = {}
        self._policy_cache: dict[str, Callable[..., Action]] = {}
        self._cache_lock = Lock()

    def policy_for_agent(self, agent_id: str) -> Callable[..., Action]:
        policy = self._policy_cache.get(agent_id)
        if policy is not None:
            return policy

        def _compiled_policy(obs: Observation, memory_summary: dict[str, Any] | None = None) -> Action:
            doctrine = self.get_or_compile_doctrine(agent_id, obs, memory_summary)
            return self._action_from_doctrine(obs, doctrine, memory_summary)

        setattr(_compiled_policy, "__gim_async_policy__", True)
        setattr(_compiled_policy, "__gim_policy_mode__", "compiled-llm")
        self._policy_cache[agent_id] = _compiled_policy
        return _compiled_policy

    def cache_size(self) -> int:
        return len(self._doctrine_cache)

    def get_or_compile_doctrine(
        self,
        agent_id: str,
        obs: Observation,
        memory_summary: dict[str, Any] | None = None,
    ) -> CompiledDoctrine:
        signature = self._context_signature(obs)
        cache_key = (agent_id, signature)
        with self._cache_lock:
            cached = self._doctrine_cache.get(cache_key)
        if cached is not None:
            return cached

        llm_enabled, reason = self._llm_status()
        if self.prefer_llm and llm_enabled:
            try:
                doctrine = self._compile_doctrine_with_llm(obs, signature, memory_summary)
            except Exception as exc:
                doctrine = self._heuristic_doctrine(obs, signature, f"LLM compile failed: {exc}")
        else:
            doctrine = self._heuristic_doctrine(obs, signature, reason)

        with self._cache_lock:
            existing = self._doctrine_cache.get(cache_key)
            if existing is not None:
                return existing
            self._doctrine_cache[cache_key] = doctrine
        return doctrine

    def _llm_status(self) -> tuple[bool, str]:
        return llm_enablement_status("llm")

    def _context_signature(self, obs: Observation) -> str:
        if self.refresh_mode == "never":
            return "never"
        if self.refresh_mode == "periodic":
            return f"periodic:{obs.time // self.refresh_years}"

        competitive = obs.self_state.get("competitive", {})
        active_sanctions = obs.self_state.get("active_sanctions", {})
        neighbor_conflict = max(
            (float(item.get("conflict_level", 0.0)) for item in obs.external_actors.get("neighbors", [])),
            default=0.0,
        )
        min_reserve_years = min(
            (
                float(value)
                for value in competitive.get("reserve_years", {}).values()
                if value is not None
            ),
            default=1.0,
        )
        regime_payload = {
            "security_margin": _bucket(float(competitive.get("security_margin", 1.0)), [0.9, 1.05, 1.2]),
            "neighbor_conflict": _bucket(neighbor_conflict, [0.25, 0.45, 0.65]),
            "protest_risk": _bucket(float(competitive.get("protest_risk", 0.0)), [0.3, 0.55, 0.75]),
            "debt_stress": _bucket(float(competitive.get("debt_stress", 0.0)), [0.25, 0.5, 0.75]),
            "reserve_years": _bucket(min_reserve_years, [0.75, 1.5, 3.0]),
            "sanctions": min(3, len(active_sanctions)),
        }
        encoded = json.dumps(regime_payload, sort_keys=True)
        return sha1(encoded.encode("utf-8")).hexdigest()[:12]

    def _compile_doctrine_with_llm(
        self,
        obs: Observation,
        signature: str,
        memory_summary: dict[str, Any] | None,
    ) -> CompiledDoctrine:
        payload = _context_payload(obs, memory_summary)
        prompt = COMPILED_DOCTRINE_PROMPT.format(
            context_json=json.dumps(payload, ensure_ascii=False),
            schema_hint=COMPILED_DOCTRINE_SCHEMA,
        )
        raw = call_llm(prompt)
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError(f"No JSON doctrine found in LLM output: {raw!r}")
        data = json.loads(raw[start : end + 1])
        return self._doctrine_from_payload(
            obs=obs,
            signature=signature,
            source="compiled-llm",
            payload=data,
        )

    def _heuristic_doctrine(self, obs: Observation, signature: str, reason: str) -> CompiledDoctrine:
        political = obs.self_state.get("political", {})
        society = obs.self_state.get("society", {})
        culture = obs.self_state.get("culture", {})
        climate = obs.self_state.get("climate", {})
        competitive = obs.self_state.get("competitive", {})
        rival = _top_rival(obs)
        rival_conflict = float(rival.get("conflict_level", 0.0)) if rival else 0.0
        reserve_years = competitive.get("reserve_years", {})
        min_reserve_years = min(
            (float(value) for value in reserve_years.values() if value is not None),
            default=2.0,
        )
        scarcity = _clamp01((2.0 - min_reserve_years) / 2.0, default=0.0)
        hawkish = _clamp01(political.get("hawkishness", 0.5))
        protectionism = _clamp01(political.get("protectionism", 0.5))
        coalition_openness = _clamp01(political.get("coalition_openness", 0.5))
        sanction_propensity = _clamp01(political.get("sanction_propensity", 0.5))
        policy_space = _clamp01(political.get("policy_space", 0.5))
        trust_gov = _clamp01(society.get("trust_gov", 0.5))
        social_tension = _clamp01(society.get("social_tension", 0.5))
        protest_risk = _clamp01(competitive.get("protest_risk", 0.4))
        debt_stress = _clamp01(competitive.get("debt_stress", 0.4))
        security_margin = float(competitive.get("security_margin", 1.0))
        mas = _clamp01(float(culture.get("mas", 50.0)) / 100.0)
        climate_risk = _clamp01(climate.get("climate_risk", 0.5))
        wealth_signal = _clamp01(
            float(obs.self_state.get("economy", {}).get("gdp_per_capita", 15000.0)) / 50000.0
        )

        payload = {
            "domestic_priority": _clamp01(
                0.35 * protest_risk
                + 0.25 * debt_stress
                + 0.20 * social_tension
                + 0.20 * (1.0 - policy_space)
            ),
            "escalation_bias": _clamp01(
                0.35 * hawkish
                + 0.25 * rival_conflict
                + 0.20 * max(0.0, 1.0 - security_margin)
                + 0.20 * mas
            ),
            "sanctions_tolerance": _clamp01(
                0.45 * sanction_propensity
                + 0.30 * protectionism
                + 0.25 * rival_conflict
            ),
            "trade_openness": _clamp01(
                0.50 * coalition_openness
                + 0.25 * (1.0 - protectionism)
                + 0.25 * trust_gov
            ),
            "mediation_openness": _clamp01(
                0.45 * coalition_openness
                + 0.30 * trust_gov
                + 0.25 * (1.0 - hawkish)
            ),
            "reserve_protection": _clamp01(0.55 * scarcity + 0.20 * debt_stress + 0.25 * rival_conflict),
            "military_readiness": _clamp01(
                0.40 * hawkish
                + 0.35 * max(0.0, 1.0 - security_margin)
                + 0.25 * rival_conflict
            ),
            "finance_defensiveness": _clamp01(
                0.45 * debt_stress
                + 0.25 * protest_risk
                + 0.15 * (1.0 - trust_gov)
                + 0.15 * (1.0 - policy_space)
            ),
            "climate_pragmatism": _clamp01(
                0.50 * climate_risk + 0.25 * wealth_signal + 0.15 * trust_gov + 0.10 * (1.0 - social_tension)
            ),
            "explanation": f"Heuristic doctrine fallback ({reason}).",
        }
        return self._doctrine_from_payload(
            obs=obs,
            signature=signature,
            source="heuristic",
            payload=payload,
        )

    def _doctrine_from_payload(
        self,
        *,
        obs: Observation,
        signature: str,
        source: str,
        payload: dict[str, Any],
    ) -> CompiledDoctrine:
        return CompiledDoctrine(
            agent_id=obs.agent_id,
            compiled_at_time=obs.time,
            context_signature=signature,
            source=source,
            domestic_priority=_clamp01(payload.get("domestic_priority")),
            escalation_bias=_clamp01(payload.get("escalation_bias")),
            sanctions_tolerance=_clamp01(payload.get("sanctions_tolerance")),
            trade_openness=_clamp01(payload.get("trade_openness")),
            mediation_openness=_clamp01(payload.get("mediation_openness")),
            reserve_protection=_clamp01(payload.get("reserve_protection")),
            military_readiness=_clamp01(payload.get("military_readiness")),
            finance_defensiveness=_clamp01(payload.get("finance_defensiveness")),
            climate_pragmatism=_clamp01(payload.get("climate_pragmatism")),
            explanation=str(payload.get("explanation", "")).strip(),
        )

    def _action_from_doctrine(
        self,
        obs: Observation,
        doctrine: CompiledDoctrine,
        memory_summary: dict[str, Any] | None,
    ) -> Action:
        competitive = obs.self_state.get("competitive", {})
        political = obs.self_state.get("political", {})
        society = obs.self_state.get("society", {})
        base_action = (
            growth_seeking_policy(obs)
            if doctrine.trade_openness >= 0.55 and doctrine.domestic_priority < 0.60
            else simple_rule_based_policy(obs)
        )
        action = copy.deepcopy(base_action)
        domestic = action.domestic_policy
        foreign = action.foreign_policy
        finance = action.finance

        protest_risk = _clamp01(competitive.get("protest_risk", 0.4))
        debt_stress = _clamp01(competitive.get("debt_stress", 0.4))
        security_margin = float(competitive.get("security_margin", 1.0))
        trust_gov = _clamp01(society.get("trust_gov", 0.5))
        hawkishness = _clamp01(political.get("hawkishness", 0.5))
        resource_gaps = {
            resource_name: float(resource_state.get("net_imports", 0.0))
            for resource_name, resource_state in obs.resource_balance.items()
        }
        largest_gap_resource, largest_gap_value = _first_non_zero(resource_gaps)
        primary_rival = _top_rival(obs)
        rival_id = primary_rival.get("agent_id") if primary_rival else None
        rival_conflict = float(primary_rival.get("conflict_level", 0.0)) if primary_rival else 0.0
        rival_trust = float(primary_rival.get("trust", 0.5)) if primary_rival else 0.5
        best_partner = _top_partner(obs, allow_primary_rival=rival_id)
        partner_id = best_partner.get("agent_id") if best_partner else None

        memory_penalty = 0.0
        if memory_summary:
            memory_penalty += 0.12 if float(memory_summary.get("trust_trend", 0.0)) < 0.0 else 0.0
            memory_penalty += 0.10 if float(memory_summary.get("tension_trend", 0.0)) > 0.0 else 0.0
            memory_penalty += 0.10 if float(memory_summary.get("security_trend", 0.0)) < 0.0 else 0.0

        domestic_push = doctrine.domestic_priority + memory_penalty
        conflict_pressure = _clamp01((rival_conflict * 0.6) + ((1.0 - rival_trust) * 0.4), default=0.0)

        domestic.social_spending_change = _bounded(
            0.010 * domestic_push - 0.006 * doctrine.finance_defensiveness + 0.002 * (1.0 - protest_risk),
            -0.004,
            0.012,
        )
        domestic.military_spending_change = _bounded(
            0.012 * (
                0.45 * doctrine.military_readiness
                + 0.30 * doctrine.escalation_bias
                + 0.25 * conflict_pressure
            )
            - 0.004 * doctrine.mediation_openness,
            -0.003,
            0.012,
        )
        domestic.rd_investment_change = _bounded(
            0.001
            + 0.003 * doctrine.trade_openness
            + 0.002 * doctrine.reserve_protection
            + 0.001 * max(0.0, 1.0 - doctrine.domestic_priority),
            0.0,
            0.007,
        )
        domestic.tax_fuel_change = _bounded(
            0.18 * doctrine.finance_defensiveness
            + 0.06 * doctrine.reserve_protection
            - 0.07 * doctrine.domestic_priority,
            -0.12,
            0.28,
        )

        if doctrine.climate_pragmatism >= 0.72 and trust_gov >= 0.45 and doctrine.domestic_priority < 0.65:
            domestic.climate_policy = "strong"
        elif doctrine.climate_pragmatism >= 0.58 and doctrine.domestic_priority < 0.75:
            domestic.climate_policy = "moderate"
        elif doctrine.climate_pragmatism >= 0.42:
            domestic.climate_policy = "weak"
        else:
            domestic.climate_policy = "none"

        finance.borrow_from_global_markets = _bounded(
            0.025 * doctrine.domestic_priority * (1.0 - debt_stress),
            0.0,
            0.03,
        )
        finance.use_fx_reserves_change = _bounded(
            0.06 * doctrine.finance_defensiveness
            + 0.02 * doctrine.reserve_protection
            - 0.01 * debt_stress,
            0.0,
            0.06,
        )

        if partner_id and largest_gap_value > 0.0 and doctrine.trade_openness >= 0.45:
            foreign.proposed_trade_deals.append(
                TradeDeal(
                    partner=partner_id,
                    resource=largest_gap_resource,
                    direction="import",
                    volume_change=_bounded(4.0 + largest_gap_value * 2.0, 2.0, 18.0),
                    price_preference="fair",
                )
            )

        if rival_id and conflict_pressure >= 0.48:
            if doctrine.sanctions_tolerance >= 0.50:
                foreign.sanctions_actions.append(
                    SanctionsAction(
                        target=rival_id,
                        type="strong" if doctrine.sanctions_tolerance >= 0.78 else "mild",
                        reason="compiled doctrine coercive pressure",
                    )
                )
            if doctrine.sanctions_tolerance >= 0.42 or hawkishness >= 0.60:
                foreign.trade_restrictions.append(
                    TradeRestriction(
                        target=rival_id,
                        level="hard" if doctrine.sanctions_tolerance >= 0.72 else "soft",
                        reason="compiled doctrine strategic restriction",
                    )
                )

        if rival_id:
            if rival_conflict >= 0.82 and security_margin >= 1.15 and doctrine.escalation_bias >= 0.78:
                foreign.security_actions = SecurityActions(type="conflict", target=rival_id)
            elif rival_conflict >= 0.65 and doctrine.escalation_bias >= 0.62:
                foreign.security_actions = SecurityActions(type="border_incident", target=rival_id)
            elif security_margin < 1.0 or (
                rival_conflict >= 0.42 and doctrine.military_readiness >= 0.55
            ):
                foreign.security_actions = SecurityActions(type="arms_buildup", target=rival_id)
            elif rival_conflict >= 0.30 and doctrine.escalation_bias >= 0.45:
                foreign.security_actions = SecurityActions(type="military_exercise", target=rival_id)

        if doctrine.mediation_openness >= 0.72 and rival_id and rival_trust >= 0.18:
            foreign.sanctions_actions = []
            if foreign.security_actions.type in {"border_incident", "conflict"}:
                foreign.security_actions = SecurityActions(type="military_exercise", target=rival_id)
            if not any(deal.partner == rival_id for deal in foreign.proposed_trade_deals):
                foreign.proposed_trade_deals.append(
                    TradeDeal(
                        partner=rival_id,
                        resource=largest_gap_resource,
                        direction="import",
                        volume_change=_bounded(3.0 + largest_gap_value, 1.0, 10.0),
                        price_preference="fair",
                    )
                )

        action.explanation = (
            f"compiled-{doctrine.source} doctrine "
            f"(domestic={doctrine.domestic_priority:.2f}, escalation={doctrine.escalation_bias:.2f}, "
            f"trade={doctrine.trade_openness:.2f}, mediation={doctrine.mediation_openness:.2f}, "
            f"finance={doctrine.finance_defensiveness:.2f}); "
            f"{doctrine.explanation or 'deterministic yearly controller applied'}"
        )
        return _normalize_action_for_stability(action)
