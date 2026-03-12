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
    "turkiye": "Turkey",
    "turkey": "Turkey",
    "rest of world": "Rest of World",
    "iran": "Iran",
    "israel": "Israel",
}


# Current country state inputs are compiled for 2023.
# Until the data pipeline becomes time-selectable, all scenario compilation
# should anchor on that snapshot year rather than inferred prompt dates.
FIXED_DATA_BASE_YEAR = 2023


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


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


def infer_actor_names(question: str, world: WorldState) -> list[str]:
    lowered = _normalize(question)
    inferred: list[str] = []

    for alias in sorted(COMMON_ALIASES, key=len, reverse=True):
        if _normalize(alias) and _normalize(alias) in lowered:
            inferred.append(COMMON_ALIASES[alias])

    for agent in world.agents.values():
        normalized_name = _normalize(agent.name)
        if normalized_name and normalized_name in lowered:
            inferred.append(agent.name)

    if inferred:
        deduped: list[str] = []
        seen: set[str] = set()
        for name in inferred:
            if name not in seen:
                seen.add(name)
                deduped.append(name)
        return deduped

    default_ids = sorted(
        world.agents.values(),
        key=lambda agent: agent.economy.gdp,
        reverse=True,
    )[:3]
    return [agent.name for agent in default_ids]


def compile_question(
    question: str,
    world: WorldState,
    base_year: int | None = None,
    actors: list[str] | None = None,
    horizon_months: int = 24,
    template_id: str | None = None,
) -> ScenarioDefinition:
    actor_inputs = actors or infer_actor_names(question, world)
    actor_ids, actor_names, unresolved = resolve_actor_names(world, actor_inputs)
    if not actor_ids:
        fallback = infer_actor_names(question, world)
        actor_ids, actor_names, fallback_unresolved = resolve_actor_names(world, fallback)
        unresolved.extend(fallback_unresolved)

    del base_year
    resolved_base_year = FIXED_DATA_BASE_YEAR
    selected_template = template_id or detect_template(question)

    return build_scenario_from_template(
        template_id=selected_template,
        question=question,
        base_year=resolved_base_year,
        horizon_months=horizon_months,
        actor_ids=actor_ids,
        actor_names=actor_names,
        unresolved_actor_names=unresolved,
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
