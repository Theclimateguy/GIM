from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product as iproduct
from typing import Dict, List, Tuple

from ..game_runner import GameRunner
from ..runtime import WorldState
from ..types import GameCombinationResult, GameDefinition


def action_key(actions: Dict[str, str]) -> str:
    return "|".join(f"{player_id}:{action_name}" for player_id, action_name in sorted(actions.items()))


@dataclass
class RegretRecord:
    episode: int
    actions: Dict[str, str]
    payoffs: Dict[str, float]
    external_regret: Dict[str, float]
    coalition_regret: Dict[str, float]
    swap_regret: Dict[str, Dict[str, float]]


@dataclass
class RegretHistory:
    records: List[RegretRecord] = field(default_factory=list)

    def mean_external_regret(self) -> Dict[str, float]:
        if not self.records:
            return {}
        player_ids = list(self.records[0].external_regret.keys())
        episode_count = len(self.records)
        return {
            player_id: sum(record.external_regret[player_id] for record in self.records) / episode_count
            for player_id in player_ids
        }

    def has_converged(self, threshold: float = 0.02) -> bool:
        means = self.mean_external_regret()
        return bool(means) and all(value <= threshold for value in means.values())


def seed_profile_cache(game_result) -> Dict[str, GameCombinationResult]:
    return {action_key(combo.actions): combo for combo in game_result.combinations}


def _ensure_profile_combo(
    runner: GameRunner,
    game: GameDefinition,
    actions: Dict[str, str],
    cache: Dict[str, GameCombinationResult],
) -> GameCombinationResult:
    key = action_key(actions)
    cached = cache.get(key)
    if cached is not None:
        return cached

    evaluation = runner.evaluate_scenario(game.scenario, selected_actions=actions)
    player_payoffs = {
        player.player_id: runner._score_player(
            player,
            evaluation=evaluation,
            action_name=actions[player.player_id],
        )
        for player in game.players
    }
    combo = GameCombinationResult(
        actions=dict(actions),
        evaluation=evaluation,
        player_payoffs=player_payoffs,
        total_payoff=sum(player_payoffs.values()),
    )
    cache[key] = combo
    return combo


def compute_external_regret(
    runner: GameRunner,
    game: GameDefinition,
    combo: GameCombinationResult,
    cache: Dict[str, GameCombinationResult],
    action_options: Dict[str, List[str]] | None = None,
) -> Dict[str, float]:
    regret: Dict[str, float] = {}
    for player in game.players:
        player_id = player.player_id
        best_response_payoff = combo.player_payoffs[player_id]
        candidate_actions = action_options.get(player_id, player.allowed_actions) if action_options else player.allowed_actions
        for alt_action in candidate_actions:
            if alt_action == combo.actions[player_id]:
                continue
            alt_profile = {**combo.actions, player_id: alt_action}
            alt_combo = _ensure_profile_combo(runner, game, alt_profile, cache)
            alt_payoff = alt_combo.player_payoffs[player_id]
            if alt_payoff > best_response_payoff:
                best_response_payoff = alt_payoff
        regret[player_id] = best_response_payoff - combo.player_payoffs[player_id]
    return regret


def compute_coalition_regret(
    runner: GameRunner,
    game: GameDefinition,
    combo: GameCombinationResult,
    world: WorldState,
    cache: Dict[str, GameCombinationResult],
    action_options: Dict[str, List[str]] | None = None,
) -> Dict[str, float]:
    blocks: Dict[str, List] = {}
    for player in game.players:
        agent = world.agents.get(player.player_id)
        block = agent.alliance_block if agent is not None else "NonAligned"
        blocks.setdefault(block, []).append(player)

    coalition_regret: Dict[str, float] = {}
    for block, members in blocks.items():
        current_welfare = sum(combo.player_payoffs.get(member.player_id, 0.0) for member in members)
        best_welfare = current_welfare
        action_spaces = [
            action_options.get(member.player_id, member.allowed_actions) if action_options else member.allowed_actions
            for member in members
        ]
        for joint_actions in iproduct(*action_spaces):
            alt_profile = dict(combo.actions)
            for member, action_name in zip(members, joint_actions):
                alt_profile[member.player_id] = action_name
            alt_combo = _ensure_profile_combo(runner, game, alt_profile, cache)
            alt_welfare = sum(alt_combo.player_payoffs.get(member.player_id, 0.0) for member in members)
            if alt_welfare > best_welfare:
                best_welfare = alt_welfare
        coalition_regret[block] = best_welfare - current_welfare

    return coalition_regret


def compute_swap_regret(
    runner: GameRunner,
    game: GameDefinition,
    history: List[Tuple[Dict[str, str], Dict[str, float]]],
    cache: Dict[str, GameCombinationResult],
    action_options: Dict[str, List[str]] | None = None,
) -> Dict[str, Dict[str, float]]:
    swap: Dict[str, Dict[str, float]] = {player.player_id: {} for player in game.players}
    for player in game.players:
        player_id = player.player_id
        candidate_actions = action_options.get(player_id, player.allowed_actions) if action_options else player.allowed_actions
        for action_from in candidate_actions:
            for action_to in candidate_actions:
                if action_from == action_to:
                    continue
                total = 0.0
                for actions_e, payoffs_e in history:
                    if actions_e.get(player_id) != action_from:
                        continue
                    alt_profile = {**actions_e, player_id: action_to}
                    alt_combo = _ensure_profile_combo(runner, game, alt_profile, cache)
                    alt_payoff = alt_combo.player_payoffs[player_id]
                    total += max(0.0, alt_payoff - payoffs_e[player_id])
                swap[player_id][f"{action_from}->{action_to}"] = total
    return swap
