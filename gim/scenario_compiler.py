from __future__ import annotations

import json
import re
from pathlib import Path

from .runtime import WorldState
from .scenario_library import build_scenario_from_template, detect_template
from .types import AVAILABLE_ACTIONS, GameDefinition, PlayerDefinition, ScenarioDefinition


COMMON_ALIASES = {
    "us": "United States",
    "u s": "United States",
    "usa": "United States",
    "america": "United States",
    "china": "China",
    "japan": "Japan",
    "germany": "Germany",
    "saudi": "Saudi Arabia",
    "saudi arabia": "Saudi Arabia",
    "turkiye": "Turkiye",
    "turkey": "Turkiye",
    "rest of world": "Rest of World",
    "iran": "Iran",
    "israel": "Israel",
}

GROUP_ALIASES = {
    "brics": ["Brazil", "Russia", "India", "China", "South Africa"],
    "opec": [
        "Saudi Arabia",
        "Iran",
        "Iraq",
        "United Arab Emirates",
        "Kuwait",
        "Qatar",
        "Algeria",
        "Nigeria",
    ],
    "nato": [
        "United States",
        "United Kingdom",
        "Germany",
        "France",
        "Italy",
        "Canada",
        "Turkey",
        "Poland",
    ],
    "eu": [
        "Germany",
        "France",
        "Italy",
        "Spain",
        "Poland",
        "Netherlands",
        "Sweden",
    ],
    "g7": ["United States", "United Kingdom", "Germany", "France", "Italy", "Japan", "Canada"],
    "g20": [
        "United States",
        "China",
        "India",
        "Japan",
        "Germany",
        "France",
        "United Kingdom",
        "Saudi Arabia",
        "South Africa",
        "Brazil",
        "Turkey",
        "Indonesia",
        "Mexico",
        "Argentina",
        "Russia",
    ],
    "asean": ["Indonesia", "Thailand", "Vietnam", "Malaysia", "Philippines", "Singapore"],
    "sub saharan africa": ["Nigeria", "South Africa", "Kenya", "Ethiopia", "Ghana", "Tanzania"],
    "mena": ["Saudi Arabia", "Iran", "Israel", "Egypt", "Turkey", "United Arab Emirates", "Qatar"],
    "gulf states": ["Saudi Arabia", "United Arab Emirates", "Qatar", "Kuwait", "Oman", "Bahrain"],
}


# Fallback year if world state does not expose calendar base metadata.
DATA_SNAPSHOT_YEAR = 2023


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _contains_term(normalized_text: str, normalized_term: str) -> bool:
    if not normalized_text or not normalized_term:
        return False
    pattern = r"\b" + re.escape(normalized_term).replace(r"\ ", r"\s+") + r"\b"
    return re.search(pattern, normalized_text) is not None


def _extract_year(question: str) -> int | None:
    match = re.search(r"\b(?:19|20)\d{2}\b", question)
    if not match:
        return None
    return int(match.group(0))


def _build_name_index(world: WorldState) -> dict[str, str]:
    index: dict[str, str] = {}
    canonical_names = {agent.name: agent.id for agent in world.agents.values()}
    for agent in world.agents.values():
        index[_normalize(agent.name)] = agent.id
        index[_normalize(agent.id)] = agent.id
    for alias, target_name in COMMON_ALIASES.items():
        agent_id = canonical_names.get(target_name)
        if agent_id:
            index[_normalize(alias)] = agent_id
    return index


def resolve_actor_names(
    world: WorldState,
    raw_actor_names: list[str],
) -> tuple[list[str], list[str], list[str]]:
    index = _build_name_index(world)
    actor_ids: list[str] = []
    actor_names: list[str] = []
    unresolved: list[str] = []
    seen_ids: set[str] = set()

    for raw_name in raw_actor_names:
        normalized = _normalize(raw_name)
        agent_id = index.get(normalized)
        if agent_id is None:
            for agent in world.agents.values():
                candidate = _normalize(agent.name)
                if normalized and (normalized in candidate or candidate in normalized):
                    agent_id = agent.id
                    break
        if agent_id is None:
            unresolved.append(raw_name)
            continue
        if agent_id in seen_ids:
            continue
        seen_ids.add(agent_id)
        actor_ids.append(agent_id)
        actor_names.append(world.agents[agent_id].name)

    return actor_ids, actor_names, unresolved


def _dedupe_preserve(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _available_group_members(world: WorldState, members: list[str]) -> list[str]:
    name_index = {_normalize(agent.name): agent.name for agent in world.agents.values()}
    available: list[str] = []
    for member in members:
        resolved = name_index.get(_normalize(member))
        if resolved:
            available.append(resolved)
    return _dedupe_preserve(available)


def _infer_actor_names_with_metadata(question: str, world: WorldState) -> tuple[list[str], dict[str, int | bool]]:
    lowered = _normalize(question)
    inferred: list[str] = []
    alias_hits = 0
    explicit_hits = 0
    group_hits = 0

    for alias in sorted(COMMON_ALIASES, key=len, reverse=True):
        normalized_alias = _normalize(alias)
        if _contains_term(lowered, normalized_alias):
            inferred.append(COMMON_ALIASES[alias])
            alias_hits += 1

    for group_alias, members in GROUP_ALIASES.items():
        normalized_group = _normalize(group_alias)
        if _contains_term(lowered, normalized_group):
            inferred.extend(_available_group_members(world, members))
            group_hits += 1

    for agent in world.agents.values():
        normalized_name = _normalize(agent.name)
        if _contains_term(lowered, normalized_name):
            inferred.append(agent.name)
            explicit_hits += 1

    if inferred:
        return _dedupe_preserve(inferred), {
            "used_gdp_fallback": False,
            "explicit_hits": explicit_hits,
            "alias_hits": alias_hits,
            "group_hits": group_hits,
        }

    default_ids = sorted(
        world.agents.values(),
        key=lambda agent: agent.economy.gdp,
        reverse=True,
    )[:3]
    return [agent.name for agent in default_ids], {
        "used_gdp_fallback": True,
        "explicit_hits": 0,
        "alias_hits": 0,
        "group_hits": 0,
    }


def infer_actor_names(question: str, world: WorldState) -> list[str]:
    inferred, _meta = _infer_actor_names_with_metadata(question, world)
    return inferred


def _resolution_quality(
    *,
    actors_provided: bool,
    actor_inputs: list[str],
    actor_ids: list[str],
    unresolved: list[str],
    infer_meta: dict[str, int | bool],
) -> tuple[str, float, list[str]]:
    used_fallback = bool(infer_meta.get("used_gdp_fallback", False))
    explicit_hits = int(infer_meta.get("explicit_hits", 0))
    alias_hits = int(infer_meta.get("alias_hits", 0))
    group_hits = int(infer_meta.get("group_hits", 0))

    if actors_provided:
        method = "user_provided"
    elif used_fallback:
        method = "gdp_fallback"
    elif group_hits > 0:
        method = "group_expansion"
    elif alias_hits > 0:
        method = "alias_match"
    elif explicit_hits > 0:
        method = "explicit_match"
    else:
        method = "heuristic"

    requested = max(len(actor_inputs), 1)
    resolved_ratio = len(actor_ids) / requested
    unresolved_ratio = len(unresolved) / requested

    if actors_provided:
        base_conf = 0.95
    elif method == "gdp_fallback":
        base_conf = 0.35
    elif method == "group_expansion":
        base_conf = 0.78
    elif method == "alias_match":
        base_conf = 0.85
    else:
        base_conf = 0.88

    confidence = base_conf * resolved_ratio - 0.25 * unresolved_ratio
    if used_fallback:
        confidence -= 0.10
    confidence = max(0.05, min(0.99, confidence))

    notes: list[str] = []
    if used_fallback:
        notes.append("No explicit actor hits; used GDP-top fallback actors.")
    if group_hits > 0:
        notes.append(f"Expanded {group_hits} group alias(es) into concrete actors.")
    if unresolved:
        notes.append(f"Unresolved actor tokens: {', '.join(unresolved)}")
    return method, confidence, notes


def compile_question(
    question: str,
    world: WorldState,
    base_year: int | None = None,
    display_year: int | None = None,
    actors: list[str] | None = None,
    horizon_months: int = 24,
    template_id: str | None = None,
) -> ScenarioDefinition:
    actors_provided = bool(actors)
    infer_meta: dict[str, int | bool] = {
        "used_gdp_fallback": False,
        "explicit_hits": 0,
        "alias_hits": 0,
        "group_hits": 0,
    }
    if actors_provided:
        actor_inputs = actors or []
    else:
        actor_inputs, infer_meta = _infer_actor_names_with_metadata(question, world)
    actor_ids, actor_names, unresolved = resolve_actor_names(world, actor_inputs)
    if not actor_ids:
        fallback, fallback_meta = _infer_actor_names_with_metadata(question, world)
        infer_meta = fallback_meta
        actor_ids, actor_names, fallback_unresolved = resolve_actor_names(world, fallback)
        unresolved.extend(fallback_unresolved)

    data_snapshot_year = int(
        getattr(world.global_state, "_calendar_year_base", DATA_SNAPSHOT_YEAR)
    )
    # Backward-compatible semantics:
    # - `base_year` acts as scenario context/display year from CLI and case files.
    # - the data snapshot year comes from the loaded world state.
    resolved_display_year = display_year
    if resolved_display_year is None and base_year is not None:
        resolved_display_year = int(base_year)
    if resolved_display_year is None:
        inferred_year = _extract_year(question)
        resolved_display_year = inferred_year if inferred_year is not None else data_snapshot_year
    selected_template = template_id or detect_template(question)
    method, confidence, notes = _resolution_quality(
        actors_provided=actors_provided,
        actor_inputs=actor_inputs,
        actor_ids=actor_ids,
        unresolved=unresolved,
        infer_meta=infer_meta,
    )

    return build_scenario_from_template(
        template_id=selected_template,
        question=question,
        base_year=data_snapshot_year,
        display_year=resolved_display_year,
        horizon_months=horizon_months,
        actor_ids=actor_ids,
        actor_names=actor_names,
        unresolved_actor_names=unresolved,
        actor_resolution_method=method,
        actor_resolution_confidence=confidence,
        actor_resolution_notes=notes,
    )


def load_game_definition(path: str | Path, world: WorldState) -> GameDefinition:
    path_obj = Path(path)
    with path_obj.open() as file_obj:
        raw = json.load(file_obj)

    scenario_raw = raw.get("scenario", {})
    scenario = compile_question(
        question=scenario_raw.get("question", raw.get("title", path_obj.stem)),
        world=world,
        base_year=scenario_raw.get("base_year"),
        display_year=scenario_raw.get("display_year"),
        actors=scenario_raw.get("actors"),
        horizon_months=scenario_raw.get("horizon_months", 24),
        template_id=scenario_raw.get("template"),
    )

    players: list[PlayerDefinition] = []
    for player_raw in raw.get("players", []):
        actor_token = player_raw.get("actor") or player_raw.get("name") or player_raw.get("player_id")
        actor_ids, actor_names, unresolved = resolve_actor_names(world, [actor_token])
        if unresolved or not actor_ids:
            raise ValueError(f"Unresolved player actor in case file: {actor_token}")
        allowed_actions = [
            action
            for action in player_raw.get("allowed_actions", [])
            if action in AVAILABLE_ACTIONS
        ]
        players.append(
            PlayerDefinition(
                player_id=actor_ids[0],
                display_name=actor_names[0],
                objectives={
                    key: float(value)
                    for key, value in player_raw.get("objectives", {}).items()
                },
                allowed_actions=allowed_actions or ["signal_restraint"],
                constraints=list(player_raw.get("constraints", [])),
            )
        )

    return GameDefinition(
        id=str(raw.get("id", path_obj.stem)),
        title=raw.get("title", path_obj.stem),
        scenario=scenario,
        players=players,
        constraints=list(raw.get("constraints", [])),
        assumptions=list(raw.get("assumptions", [])),
        tags=list(raw.get("tags", [])),
    )
