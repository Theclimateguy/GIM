from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Dict, Optional

from ..game_runner import GameRunner
from ..runtime import WorldState
from ..types import GameCombinationResult, GameDefinition
from .correlated_eq import CorrelatedEquilibrium, solve_correlated_equilibrium
from .regret import (
    RegretHistory,
    RegretRecord,
    action_key,
    compute_coalition_regret,
    compute_external_regret,
    compute_swap_regret,
    seed_profile_cache,
)
from .welfare import WelfareAnalysis, analyse_welfare, compute_trust_weights


@dataclass
class EquilibriumResult:
    game: GameDefinition
    episodes: int
    regret_history: RegretHistory
    correlated_equilibrium: CorrelatedEquilibrium
    welfare: WelfareAnalysis | None
    converged: bool
    mean_external_regret: Dict[str, float]
    mean_coalition_regret: Dict[str, float]
    recommended_profile: Dict[str, str]
    price_of_anarchy: float | None
    ccE_empirical: Dict[str, float]


def run_equilibrium_search(
    runner: GameRunner,
    game: GameDefinition,
    world: WorldState,
    max_episodes: int = 50,
    convergence_threshold: float = 0.02,
    max_combinations: int = 256,
    eta: float = 0.1,
    exploration_eps: float = 0.1,
    trust_alpha: float = 0.5,
    stage_game: object | None = None,
) -> EquilibriumResult:
    history = RegretHistory()
    action_history = []
    weights: Dict[str, Dict[str, float]] = {
        player.player_id: {action_name: 1.0 for action_name in player.allowed_actions}
        for player in game.players
    }
    episode_keys: list[str] = []

    # The stage game is static for a fixed scenario, so reuse the same payoff matrix across episodes.
    stage_game = stage_game or runner.run_game(game, max_combinations=max_combinations)
    profile_cache = seed_profile_cache(stage_game)
    action_options = _available_actions(stage_game)

    for episode in range(max_episodes):
        selected = _hedge_select(stage_game, weights, exploration_eps)
        external_regret = compute_external_regret(
            runner,
            game,
            selected,
            profile_cache,
            action_options=action_options,
        )
        coalition_regret = compute_coalition_regret(
            runner,
            game,
            selected,
            world,
            profile_cache,
            action_options=action_options,
        )
        _hedge_update(weights, game, stage_game, selected, eta, action_options=action_options)

        history.records.append(
            RegretRecord(
                episode=episode,
                actions=selected.actions,
                payoffs=selected.player_payoffs,
                external_regret=external_regret,
                coalition_regret=coalition_regret,
                swap_regret={},
            )
        )
        action_history.append((selected.actions, selected.player_payoffs))
        episode_keys.append(action_key(selected.actions))

        if history.has_converged(convergence_threshold):
            break

    if history.records:
        history.records[-1].swap_regret = compute_swap_regret(
            runner,
            game,
            action_history,
            profile_cache,
            action_options=action_options,
        )

    empirical_cce = _empirical_distribution(episode_keys)
    trust_weights = compute_trust_weights(game, world, alpha=trust_alpha)
    ce = solve_correlated_equilibrium(game, stage_game.combinations, trust_weights=trust_weights)

    recommended_profile = dict(stage_game.best_combination.actions)
    if ce.distribution:
        recommended_key = max(ce.distribution, key=ce.distribution.get)
        recommended_profile = _parse_action_key(recommended_key)

    recommended_combo = profile_cache.get(action_key(recommended_profile), stage_game.best_combination)
    welfare = analyse_welfare(
        game=game,
        world=world,
        combo=recommended_combo,
        ce_distribution=ce.distribution,
        cce_empirical=empirical_cce,
        combinations=stage_game.combinations,
        alpha=trust_alpha,
    )

    mean_coalition_regret = _mean_coalition_regret(history)
    price_of_anarchy = _price_of_anarchy(
        stage_game.best_combination,
        ce,
        trust_weights,
    )

    return EquilibriumResult(
        game=game,
        episodes=len(history.records),
        regret_history=history,
        correlated_equilibrium=ce,
        welfare=welfare,
        converged=history.has_converged(convergence_threshold),
        mean_external_regret=history.mean_external_regret(),
        mean_coalition_regret=mean_coalition_regret,
        recommended_profile=recommended_profile,
        price_of_anarchy=price_of_anarchy,
        ccE_empirical=empirical_cce,
    )


def _hedge_select(
    game_result,
    weights: Dict[str, Dict[str, float]],
    exploration_eps: float,
) -> GameCombinationResult:
    scored = sorted(
        [
            (
                sum(math.log(weights.get(player_id, {}).get(action_name, 1.0) + 1e-12) for player_id, action_name in combo.actions.items()),
                combo,
            )
            for combo in game_result.combinations
        ],
        key=lambda item: item[0],
        reverse=True,
    )
    if not scored:
        raise ValueError("No combinations available for equilibrium search")
    if random.random() > exploration_eps:
        return scored[0][1]
    return random.choice(game_result.combinations)


def _hedge_update(
    weights: Dict[str, Dict[str, float]],
    game: GameDefinition,
    game_result,
    selected: GameCombinationResult,
    eta: float,
    action_options: Dict[str, list[str]] | None = None,
) -> None:
    for player in game.players:
        player_id = player.player_id
        current_payoff = selected.player_payoffs.get(player_id, 0.0)
        candidate_actions = action_options.get(player_id, player.allowed_actions) if action_options else player.allowed_actions
        for action_name in candidate_actions:
            payoffs = [
                combo.player_payoffs.get(player_id, 0.0)
                for combo in game_result.combinations
                if combo.actions.get(player_id) == action_name
            ]
            average_payoff = sum(payoffs) / len(payoffs) if payoffs else 0.0
            weights[player_id][action_name] = weights[player_id].get(action_name, 1.0) * math.exp(
                -eta * (current_payoff - average_payoff)
            )


def _empirical_distribution(keys: list[str]) -> Dict[str, float]:
    if not keys:
        return {}
    total = len(keys)
    empirical: Dict[str, float] = {}
    for key in keys:
        empirical[key] = empirical.get(key, 0.0) + 1.0 / total
    return empirical


def _available_actions(game_result) -> Dict[str, list[str]]:
    action_options: Dict[str, set[str]] = {}
    for combo in game_result.combinations:
        for player_id, action_name in combo.actions.items():
            action_options.setdefault(player_id, set()).add(action_name)
    return {player_id: sorted(options) for player_id, options in action_options.items()}


def _parse_action_key(key: str) -> Dict[str, str]:
    profile: Dict[str, str] = {}
    if not key:
        return profile
    for part in key.split("|"):
        player_id, action_name = part.split(":", 1)
        profile[player_id] = action_name
    return profile


def _mean_coalition_regret(history: RegretHistory) -> Dict[str, float]:
    if not history.records:
        return {}
    all_blocks = set()
    for record in history.records:
        all_blocks.update(record.coalition_regret.keys())
    episode_count = len(history.records)
    return {
        block: sum(record.coalition_regret.get(block, 0.0) for record in history.records) / episode_count
        for block in sorted(all_blocks)
    }


def _price_of_anarchy(
    best_combo: GameCombinationResult,
    ce: CorrelatedEquilibrium,
    trust_weights: Dict[str, float],
) -> Optional[float]:
    if not ce.is_feasible or abs(ce.social_welfare) < 1e-9:
        return None
    best_weighted = sum(
        trust_weights.get(player_id, 1.0) * best_combo.player_payoffs.get(player_id, 0.0)
        for player_id in trust_weights
    )
    return best_weighted / ce.social_welfare
