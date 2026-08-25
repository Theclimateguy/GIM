from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any

from .game_runner import OBJECTIVE_TO_RISK_UTILITY
from .scenario_compiler import compile_question, resolve_actor_names
from .scenario_library import TEMPLATE_REGISTRY
from .types import AVAILABLE_ACTIONS, GameDefinition, PlayerDefinition

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None
    REQUESTS_AVAILABLE = False


DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
AVAILABLE_OBJECTIVES = tuple(OBJECTIVE_TO_RISK_UTILITY)
AVAILABLE_TEMPLATES = tuple(template_id for template_id in TEMPLATE_REGISTRY if template_id != "generic_tail_risk")


@dataclass(frozen=True)
class CaseBuildResult:
    game: GameDefinition
    payload: dict[str, Any]
    source: str
    note: str | None = None

    @property
    def source_label(self) -> str:
        if self.source == "llm":
            return "DeepSeek compiler"
        return "Deterministic fallback"


def build_case_from_text(
    description: str,
    world,
    *,
    prefer_llm: bool = True,
    max_players: int = 6,
) -> CaseBuildResult:
    cleaned_description = description.strip()
    if not cleaned_description:
        raise ValueError("Scenario description must not be empty")

    if prefer_llm:
        llm_payload = _try_llm_case(cleaned_description, max_players=max_players)
        if llm_payload is not None:
            game = _validate_and_clean(llm_payload, world, description=cleaned_description, max_players=max_players)
            payload = serialize_game_definition(game)
            return CaseBuildResult(game=game, payload=payload, source="llm")

    fallback_payload = _deterministic_case_payload(cleaned_description, world, max_players=max_players)
    game = _validate_and_clean(fallback_payload, world, description=cleaned_description, max_players=max_players)
    payload = serialize_game_definition(game)
    note = None
    if prefer_llm:
        note = "DeepSeek key unavailable or builder call failed, so the case was compiled deterministically."
    return CaseBuildResult(game=game, payload=payload, source="deterministic", note=note)


def write_case_payload(payload: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def serialize_game_definition(game: GameDefinition) -> dict[str, Any]:
    return {
        "id": game.id,
        "title": game.title,
        "tags": list(game.tags),
        "constraints": list(game.constraints),
        "assumptions": list(game.assumptions),
        "scenario": {
            "question": game.scenario.source_prompt,
            "actors": list(game.scenario.actor_names),
            "horizon_months": int(game.scenario.horizon_months),
            "template": game.scenario.template_id,
            "base_year": int(game.scenario.base_year),
        },
        "players": [
            {
                "actor": player.display_name,
                "objectives": dict(player.objectives),
                "allowed_actions": list(player.allowed_actions),
                "constraints": list(player.constraints),
            }
            for player in game.players
        ],
    }


def _validate_and_clean(
    raw: dict[str, Any],
    world,
    *,
    description: str,
    max_players: int,
) -> GameDefinition:
    scenario_raw = raw.get("scenario") if isinstance(raw.get("scenario"), dict) else {}
    raw_template = scenario_raw.get("template")
    template_id = raw_template if raw_template in TEMPLATE_REGISTRY else None
    raw_actor_names = [
        str(name).strip()
        for name in scenario_raw.get("actors", [])
        if str(name).strip()
    ]
    question = str(scenario_raw.get("question") or description).strip()
    horizon_months = _clean_horizon(scenario_raw.get("horizon_months"))

    scenario = compile_question(
        question=question,
        world=world,
        actors=raw_actor_names or None,
        horizon_months=horizon_months,
        template_id=template_id,
    )

    players: list[PlayerDefinition] = []
    seen_player_ids: set[str] = set()
    for player_raw in raw.get("players", [])[:max_players]:
        actor_token = str(
            player_raw.get("actor") or player_raw.get("name") or player_raw.get("player_id") or ""
        ).strip()
        if not actor_token:
            continue
        actor_ids, actor_names, unresolved = resolve_actor_names(world, [actor_token])
        if unresolved or not actor_ids:
            continue
        player_id = actor_ids[0]
        if player_id in seen_player_ids:
            continue
        seen_player_ids.add(player_id)
        display_name = actor_names[0]
        objectives = _clean_objectives(player_raw.get("objectives"))
        allowed_actions = _clean_actions(
            player_raw.get("allowed_actions"),
            template_id=scenario.template_id,
            objective_keys=list(objectives),
        )
        players.append(
            PlayerDefinition(
                player_id=player_id,
                display_name=display_name,
                objectives=objectives,
                allowed_actions=allowed_actions,
                constraints=[str(item) for item in player_raw.get("constraints", []) if str(item).strip()],
            )
        )

    if not players:
        players = _fallback_players(world, scenario, max_players=max_players)

    actor_names = list(scenario.actor_names)
    for player in players:
        if player.display_name not in actor_names:
            actor_names.append(player.display_name)

    scenario = compile_question(
        question=scenario.source_prompt,
        world=world,
        actors=actor_names or None,
        horizon_months=scenario.horizon_months,
        template_id=scenario.template_id,
    )

    title = _clean_title(str(raw.get("title") or scenario.title or "Generated policy game").strip())
    case_id = _clean_id(str(raw.get("id") or title), description=description)
    return GameDefinition(
        id=case_id,
        title=title,
        scenario=scenario,
        players=players[:max_players],
        constraints=[str(item) for item in raw.get("constraints", []) if str(item).strip()],
        assumptions=[str(item) for item in raw.get("assumptions", []) if str(item).strip()],
        tags=_clean_tags(raw.get("tags"), scenario.template_id),
    )


def _clean_horizon(raw_horizon: Any) -> int:
    try:
        value = int(raw_horizon)
    except (TypeError, ValueError):
        value = 24
    return max(12, min(60, value))


def _clean_objectives(raw_objectives: Any) -> dict[str, float]:
    cleaned: dict[str, float] = {}
    if isinstance(raw_objectives, dict):
        for key, value in raw_objectives.items():
            if key not in AVAILABLE_OBJECTIVES:
                continue
            try:
                cleaned[key] = max(-2.0, min(2.0, float(value)))
            except (TypeError, ValueError):
                continue
    if not cleaned:
        return {"reduce_war_risk": 1.0}
    ranked = sorted(cleaned.items(), key=lambda item: abs(item[1]), reverse=True)[:4]
    return dict(ranked)


def _clean_actions(
    raw_actions: Any,
    *,
    template_id: str,
    objective_keys: list[str],
) -> list[str]:
    cleaned: list[str] = []
    for action_name in raw_actions or []:
        action_key = str(action_name).strip()
        if action_key in AVAILABLE_ACTIONS and action_key not in cleaned:
            cleaned.append(action_key)
    for action_name in _suggest_actions(template_id, objective_keys):
        if action_name not in cleaned:
            cleaned.append(action_name)
        if len(cleaned) >= 6:
            break
    return cleaned[:6] or ["signal_restraint"]


def _suggest_actions(template_id: str, objective_keys: list[str]) -> list[str]:
    suggestions: list[str] = []
    template_defaults = {
        "trade_war": [
            "impose_tariffs",
            "export_controls",
            "lift_sanctions",
            "capital_controls",
            "currency_intervention",
            "backchannel_offer",
        ],
        "cyber_disruption": [
            "cyber_probe",
            "cyber_disruption_attack",
            "cyber_espionage",
            "cyber_defense_posture",
            "signal_restraint",
            "backchannel_offer",
        ],
        "sanctions_spiral": [
            "export_controls",
            "capital_controls",
            "lift_sanctions",
            "backchannel_offer",
        ],
        "alliance_fragmentation": [
            "information_campaign",
            "signal_deterrence",
            "accept_mediation",
            "backchannel_offer",
        ],
        "maritime_deterrence": [
            "signal_deterrence",
            "maritime_interdiction",
            "accept_mediation",
            "backchannel_offer",
        ],
        "regional_pressure": [
            "signal_deterrence",
            "arm_proxy",
            "restrain_proxy",
            "backchannel_offer",
        ],
        "resource_competition": [
            "export_controls",
            "impose_tariffs",
            "backchannel_offer",
            "accept_mediation",
        ],
        "tech_blockade": [
            "export_controls",
            "cyber_espionage",
            "cyber_defense_posture",
            "backchannel_offer",
        ],
        "regime_stress": [
            "domestic_crackdown",
            "debt_restructuring",
            "currency_intervention",
            "signal_restraint",
        ],
        "general_tail_risk": [
            "signal_restraint",
            "backchannel_offer",
            "information_campaign",
            "cyber_defense_posture",
        ],
        "generic_tail_risk": [
            "signal_restraint",
            "backchannel_offer",
            "information_campaign",
            "cyber_defense_posture",
        ],
    }
    suggestions.extend(template_defaults.get(template_id, template_defaults["general_tail_risk"]))

    if "reduce_war_risk" in objective_keys:
        suggestions.extend(["signal_restraint", "accept_mediation", "backchannel_offer", "cyber_defense_posture"])
    if "sanctions_resilience" in objective_keys:
        suggestions.extend(["lift_sanctions", "debt_restructuring", "currency_intervention", "capital_controls"])
    if "resource_access" in objective_keys:
        suggestions.extend(["lift_sanctions", "backchannel_offer", "impose_tariffs", "export_controls"])
    if "regional_influence" in objective_keys or "bargaining_power" in objective_keys:
        suggestions.extend(["signal_deterrence", "export_controls", "cyber_probe", "information_campaign"])
    if "regime_retention" in objective_keys:
        suggestions.extend(["debt_restructuring", "currency_intervention", "domestic_crackdown"])

    deduped: list[str] = []
    for action_name in suggestions:
        if action_name in AVAILABLE_ACTIONS and action_name not in deduped:
            deduped.append(action_name)
    return deduped


def _fallback_players(world, scenario, *, max_players: int) -> list[PlayerDefinition]:
    fallback_names = list(scenario.actor_names)[:max_players]
    players: list[PlayerDefinition] = []
    template_objectives = {
        "alliance_fragmentation": ["bargaining_power", "regional_influence", "reduce_war_risk"],
        "trade_war": ["sanctions_resilience", "resource_access", "bargaining_power"],
        "cyber_disruption": ["reduce_war_risk", "bargaining_power", "regime_retention"],
        "maritime_deterrence": ["resource_access", "reduce_war_risk", "bargaining_power"],
        "regional_pressure": ["regional_influence", "reduce_war_risk", "bargaining_power"],
        "sanctions_spiral": ["sanctions_resilience", "regime_retention", "reduce_war_risk"],
        "resource_competition": ["resource_access", "sanctions_resilience", "reduce_war_risk"],
        "tech_blockade": ["bargaining_power", "sanctions_resilience", "reduce_war_risk"],
        "regime_stress": ["regime_retention", "reduce_war_risk", "sanctions_resilience"],
        "general_tail_risk": ["reduce_war_risk", "bargaining_power", "resource_access"],
        "generic_tail_risk": ["reduce_war_risk", "bargaining_power", "resource_access"],
    }
    objective_keys = template_objectives.get(scenario.template_id, template_objectives["general_tail_risk"])
    for actor_name in fallback_names:
        actor_ids, actor_names, unresolved = resolve_actor_names(world, [actor_name])
        if unresolved or not actor_ids:
            continue
        players.append(
            PlayerDefinition(
                player_id=actor_ids[0],
                display_name=actor_names[0],
                objectives={key: 1.0 / len(objective_keys) for key in objective_keys},
                allowed_actions=_clean_actions([], template_id=scenario.template_id, objective_keys=objective_keys)[:4],
            )
        )
    return players


def _clean_title(raw_title: str) -> str:
    normalized = re.sub(r"\s+", " ", raw_title).strip()
    return normalized[:80] or "Generated policy game"


def _clean_id(raw_id: str, *, description: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", raw_id.lower()).strip("_") or "generated_case"
    slug = slug[:30].strip("_") or "generated_case"
    digest = hashlib.sha1(description.encode("utf-8")).hexdigest()[:6]
    return f"{slug}_{digest}"[:40]


def _clean_tags(raw_tags: Any, template_id: str) -> list[str]:
    cleaned: list[str] = []
    for tag in raw_tags or []:
        tag_text = re.sub(r"[^a-z0-9_-]+", "-", str(tag).lower()).strip("-")
        if tag_text and tag_text not in cleaned:
            cleaned.append(tag_text)
    for required in [template_id, "policy-gaming", "generated"]:
        if required not in cleaned:
            cleaned.append(required)
    return cleaned[:6]


def _try_llm_case(description: str, *, max_players: int) -> dict[str, Any] | None:
    if not REQUESTS_AVAILABLE:
        return None
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a geopolitical scenario compiler for GIM_13, an integrated world model. "
                    "Return only valid JSON for the requested case schema."
                ),
            },
            {
                "role": "user",
                "content": _llm_prompt(description, max_players=max_players),
            },
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    timeout_sec = float(os.getenv("LLM_TIMEOUT_SEC", "120"))
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "1"))
    retry_backoff_sec = float(os.getenv("LLM_RETRY_BACKOFF_SEC", "2.0"))

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=timeout_sec,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"].strip()
            return json.loads(content)
        except Exception:
            if attempt >= max_retries:
                return None
            time.sleep(retry_backoff_sec * (2**attempt))
    return None


def _llm_prompt(description: str, *, max_players: int) -> str:
    schema = {
        "id": "<snake_case_id>",
        "title": "<short English title>",
        "tags": ["<tag>"],
        "scenario": {
            "question": "<one sentence describing the scenario>",
            "actors": ["<country name>"],
            "horizon_months": 24,
            "template": "<template_key>",
        },
        "players": [
            {
                "actor": "<country name>",
                "objectives": {"reduce_war_risk": 1.0},
                "allowed_actions": ["signal_restraint", "backchannel_offer"],
            }
        ],
        "constraints": ["<hard rule>"],
        "assumptions": ["<premise held fixed>"],
    }
    return (
        "Parse the user scenario and return only JSON.\n\n"
        f"SCHEMA:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        f"AVAILABLE TEMPLATES: {', '.join(AVAILABLE_TEMPLATES)}\n"
        f"AVAILABLE OBJECTIVES: {', '.join(AVAILABLE_OBJECTIVES)}\n"
        f"AVAILABLE ACTIONS: {', '.join(AVAILABLE_ACTIONS)}\n\n"
        "RULES:\n"
        "- actors list must include all players plus relevant bystanders\n"
        "- horizon_months must be between 12 and 60\n"
        "- each player should have 2 to 4 objectives\n"
        "- each player should have 3 to 6 allowed actions\n"
        "- use economic and cyber actions for economic or technology conflict scenarios\n"
        "- use military actions for security conflict scenarios\n"
        f"- return at most {max_players} players\n"
        "- action keys and objective keys must come only from the lists above\n"
        "- title should be short and in English\n"
        "- return JSON only, with no markdown fences and no prose\n\n"
        f"USER DESCRIPTION:\n{description}"
    )


def _deterministic_case_payload(description: str, world, *, max_players: int) -> dict[str, Any]:
    scenario = compile_question(description, world)
    actor_names = list(scenario.actor_names)[:max_players]
    template_id = scenario.template_id
    player_payloads = []
    objective_map = {
        "alliance_fragmentation": {"bargaining_power": 0.35, "regional_influence": 0.35, "reduce_war_risk": 0.30},
        "trade_war": {"sanctions_resilience": 0.40, "resource_access": 0.35, "bargaining_power": 0.25},
        "cyber_disruption": {"reduce_war_risk": 0.40, "bargaining_power": 0.35, "regime_retention": 0.25},
        "maritime_deterrence": {"resource_access": 0.40, "reduce_war_risk": 0.35, "bargaining_power": 0.25},
        "regional_pressure": {"regional_influence": 0.40, "reduce_war_risk": 0.35, "bargaining_power": 0.25},
        "sanctions_spiral": {"sanctions_resilience": 0.45, "regime_retention": 0.35, "reduce_war_risk": 0.20},
        "resource_competition": {"resource_access": 0.45, "sanctions_resilience": 0.30, "reduce_war_risk": 0.25},
        "tech_blockade": {"bargaining_power": 0.40, "sanctions_resilience": 0.35, "reduce_war_risk": 0.25},
        "regime_stress": {"regime_retention": 0.45, "reduce_war_risk": 0.35, "sanctions_resilience": 0.20},
        "general_tail_risk": {"reduce_war_risk": 0.50, "bargaining_power": 0.30, "resource_access": 0.20},
        "generic_tail_risk": {"reduce_war_risk": 0.50, "bargaining_power": 0.30, "resource_access": 0.20},
    }
    objectives = objective_map.get(template_id, objective_map["general_tail_risk"])
    for actor_name in actor_names:
        player_payloads.append(
            {
                "actor": actor_name,
                "objectives": objectives,
                "allowed_actions": _suggest_actions(template_id, list(objectives))[:4],
            }
        )

    return {
        "id": _clean_id(scenario.title, description=description),
        "title": scenario.title,
        "tags": [template_id, "policy-gaming", "generated"],
        "scenario": {
            "question": description,
            "actors": list(scenario.actor_names),
            "horizon_months": int(scenario.horizon_months),
            "template": template_id,
        },
        "players": player_payloads,
        "constraints": [],
        "assumptions": [
            "Case built from free-text description.",
            "Weights and action sets are heuristically inferred from the scenario template.",
        ],
    }
