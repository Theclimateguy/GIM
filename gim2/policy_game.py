"""Ролевая игра акторов — LLM-driven country policy, layered on the validated core.

Every other v2 mode drives ``step_world`` with ``make_policy_map(..., mode="simple")``
(deterministic, rule-based) — the model's own math, no LLM in the loop. This module is
the one deliberate exception: selected actors are handed to an LLM that *compiles a
multi-year governing doctrine* (:class:`gim.compiled_policy.CompiledLLMPolicyManager`,
part of the "exploratory" layer gim2 hides by default, see :func:`gim2.is_exploratory_enabled`)
instead of running the scripted policy. Everyone else keeps running the scripted policy,
so a request costs at most one LLM call per selected actor (compiled/cached by context
signature, not per simulated year) rather than one call per agent per year.

This is explicitly NOT validated the way the deterministic core is: the LLM's doctrine is
an emergent, non-calibrated behavior, not a literature-grounded parameter. It exists to
explore "what does an autonomous, reasoning actor do here", not to produce a trustworthy
forecast — treat the trajectory as illustrative and the per-year `decisions` log as the
actual point of the exercise.

A single deterministic trajectory (no ensemble): each simulated year is exactly one
``step_world`` call, and an LLM-compiled doctrine is inherently a single narrative, not
something to average over parameter priors.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional, Sequence

from gim.ensemble import _collect_metrics
from gim.runtime import default_state_csv

from . import SCHEMA, is_exploratory_enabled
from . import levers as L
from . import projections as P
from .assistant import AssistantConfig
from .scenario import _selection_from_items

_BAND_KEYS = ("p5", "p25", "p50", "p75", "p95", "mean")

# gim2's own provider surface (deterministic/ollama/openai) — kept independent from
# gim.core.policy's env-var-driven DeepSeek/Ollama defaults so the actor-policy LLM
# reuses whatever connection the user already configured for the Assistant.
_OLLAMA_DEFAULT_URL = "http://localhost:11434"


def _make_chat_fn(config: AssistantConfig) -> Callable[[str], str]:
    import requests

    timeout = float(os.getenv("LLM_TIMEOUT_SEC", "120"))
    system_message = {"role": "system", "content": "You are a policy decision engine that outputs ONLY JSON."}

    def chat(prompt: str) -> str:
        messages = [system_message, {"role": "user", "content": prompt}]
        if config.provider == "ollama":
            base = (config.base_url or _OLLAMA_DEFAULT_URL).rstrip("/")
            model = config.model or "qwen2.5-coder:7b"
            payload = {"model": model, "messages": messages, "stream": False, "format": "json",
                       "options": {"temperature": config.temperature}}
            resp = requests.post(f"{base}/api/chat", json=payload, timeout=timeout)
            resp.raise_for_status()
            return str(resp.json().get("message", {}).get("content", "")).strip()

        base = (config.base_url or "https://api.openai.com/v1").rstrip("/")
        key = (config.api_key or "").strip()
        model = config.model or "gpt-4o-mini"
        payload = {"model": model, "messages": messages, "temperature": config.temperature}
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        resp = requests.post(f"{base}/chat/completions", headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    return chat


def _fmt_pct(v: float) -> str:
    return f"{v * 100:+.1f}%"


def _domestic_summary(r: Dict[str, Any]) -> str:
    parts = [
        f"соц. расходы {_fmt_pct(r['dom_social_spending_change'])}",
        f"ВПК {_fmt_pct(r['dom_military_spending_change'])}",
        f"НИОКР {_fmt_pct(r['dom_rd_investment_change'])}",
        f"топливный налог {_fmt_pct(r['dom_tax_fuel_change'])}",
    ]
    climate = {"none": "нет", "weak": "слабая", "moderate": "умеренная", "strong": "сильная"}
    parts.append(f"климат: {climate.get(r['dom_climate_policy'], r['dom_climate_policy'])}")
    return ", ".join(parts)


def _foreign_summary(r: Dict[str, Any]) -> str:
    import json as _json

    parts: List[str] = []
    deals = _json.loads(r.get("trade_deals") or "[]")
    for d in deals:
        parts.append(f"торг. сделка с {d['partner']} ({d['direction']} {d['resource']})")
    sanctions = _json.loads(r.get("sanctions_intent") or "[]")
    for s in sanctions:
        parts.append(f"санкции ({s['type']}) против {s['target']}")
    restrictions = _json.loads(r.get("trade_restrictions_intent") or "[]")
    for tr in restrictions:
        parts.append(f"торг. ограничения ({tr['level']}) против {tr['target']}")
    sec_type = r.get("security_intent_type", "none")
    if sec_type != "none":
        target = r.get("security_intent_target")
        parts.append(f"силовая мера: {sec_type}" + (f" → {target}" if target else ""))
    return "; ".join(parts) if parts else "без внешнеполитических инициатив"


def compute_policy_game(
    *,
    state_csv: Optional[str] = None,
    llm_actors: Sequence[str],
    persona_by_actor: Optional[Dict[str, str]] = None,
    levers: Sequence[Any] = (),
    magnitude: Optional[float] = None,
    actors: Optional[Sequence[str]] = None,
    years: int = 8,
    max_agents: int = 57,
    seed: int = 2026,
    refresh_mode: str = "trigger",
    llm_config: Optional[AssistantConfig] = None,
) -> Dict[str, Any]:
    if not is_exploratory_enabled():
        raise ValueError(
            "policy_game is part of the exploratory layer (GIM_EXPLORATORY must be set); "
            "the packaged app enables it for its own engine subprocess."
        )
    if not llm_actors:
        raise ValueError("llm_actors must name at least one actor")

    from gim.compiled_policy import CompiledLLMPolicyManager
    from gim.core.params import default_params
    from gim.core.policy import simple_rule_based_policy
    from gim.core.rng import seed_world
    from gim.core.simulation import step_world
    from gim.core.world_factory import make_world_from_csv
    from gim.persona import get_persona

    csv = state_csv or default_state_csv()
    # forward_init: balance base-year resource markets so forward prices don't pin to a clamp.
    world = make_world_from_csv(csv, max_agents=int(max_agents), base_year=2023, forward_init=True)
    world.params = default_params()
    seed_world(world, int(seed))

    selection = _selection_from_items(levers, magnitude, actors) if levers else L.LeverSelection()
    lever_actor_ids = L.resolve_actors(world, selection.actors) if not selection.is_empty else []

    # Resolve name -> id one at a time (rather than batch-resolving the whole list) so we
    # keep the 1:1 correspondence needed to translate `persona_by_actor`'s keys, which arrive
    # as the same raw display names the UI showed, not resolved agent ids.
    id_by_raw_name: Dict[str, str] = {}
    for raw_name in llm_actors:
        resolved = L.resolve_actors(world, [raw_name])
        if resolved:
            id_by_raw_name[raw_name] = resolved[0]
    resolved_llm_ids = list(dict.fromkeys(id_by_raw_name.values()))
    if not resolved_llm_ids:
        raise ValueError(f"none of the requested actors resolved: {', '.join(llm_actors)}")
    llm_id_set = set(resolved_llm_ids)

    config = llm_config or AssistantConfig(provider="deterministic")
    chat_fn = _make_chat_fn(config) if config.provider != "deterministic" else None
    manager = CompiledLLMPolicyManager(refresh_mode=refresh_mode, chat_fn=chat_fn)
    for raw_name, agent_id in id_by_raw_name.items():
        persona_id = (persona_by_actor or {}).get(raw_name)
        manager.set_persona(agent_id, get_persona(persona_id))

    policies: Dict[str, Callable[..., Any]] = {
        agent_id: (manager.policy_for_agent(agent_id) if agent_id in llm_id_set else simple_rule_based_policy)
        for agent_id in world.agents.keys()
    }

    action_log: List[Dict[str, Any]] = []
    years_axis = list(range(int(years) + 1))
    trajectory: List[Dict[str, float]] = [_collect_metrics(world)]
    for t in range(1, int(years) + 1):
        step_world(world, policies, action_log=action_log)
        if not selection.is_empty:
            L.apply_pulses(world, t, selection, lever_actor_ids)
        trajectory.append(_collect_metrics(world))

    bands: Dict[str, Dict[str, List[float]]] = {}
    for metric in P.DEFAULT_FAN_METRICS:
        series = [float(pt.get(metric, 0.0)) for pt in trajectory]
        bands[metric] = {key: list(series) for key in _BAND_KEYS}

    agent_names = {aid: agent.name for aid, agent in world.agents.items()}
    decisions = [
        {
            "time": int(r["time"]),
            "agent_id": r["agent_id"],
            "agent_name": agent_names.get(r["agent_id"], r["agent_id"]),
            "explanation": r.get("explanation", ""),
            "domestic_summary": _domestic_summary(r),
            "foreign_summary": _foreign_summary(r),
        }
        for r in action_log
        if r["agent_id"] in llm_id_set
    ]

    actor_labels = ", ".join(agent_names.get(a, a) for a in resolved_llm_ids)
    brief = (
        f"ЛЛМ определяет политику для: {actor_labels} (остальные акторы — на штатных правилах); "
        f"горизонт {years} лет"
        + (f"; поверх сценария «{', '.join(selection.magnitudes)}»" if not selection.is_empty else "")
        + "."
    )

    return {
        "schema": SCHEMA,
        "mode": "policy_game",
        "config": {
            "state_csv": csv, "years": int(years), "max_agents": int(max_agents),
            "seed": int(seed), "refresh_mode": refresh_mode,
        },
        "llm_actors": resolved_llm_ids,
        "persona_by_actor": persona_by_actor or {},
        "selection": selection.to_dict(),
        "projection": P.ensemble_projection(bands, years_axis, 1),
        "decisions": decisions,
        "brief": brief,
    }


__all__ = ["compute_policy_game"]
