from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import math

from ..runtime import WorldState
from ..types import GameCombinationResult, GameDefinition


def action_key(actions: Dict[str, str]) -> str:
    return "|".join(f"{player_id}:{action_name}" for player_id, action_name in sorted(actions.items()))


@dataclass
class WelfareAnalysis:
    alpha: float
    utilitarian_sw: float
    trust_weighted_sw: float
    payoff_gini: float
    positive_normative_kl: Optional[float]
    action_correlations: Dict[str, float]


def compute_trust_weights(
    game: GameDefinition,
    world: WorldState,
    alpha: float = 0.5,
) -> Dict[str, float]:
    player_ids = [player.player_id for player in game.players]
    weights: Dict[str, float] = {}
    for player_id in player_ids:
        trusts = []
        for other_id in player_ids:
            if other_id == player_id:
                continue
            relation = world.relations.get(player_id, {}).get(other_id)
            if relation is not None:
                trusts.append(relation.trust)
        avg_trust = sum(trusts) / len(trusts) if trusts else 0.5
        weights[player_id] = 1.0 + alpha * avg_trust

    total = sum(weights.values()) or float(len(player_ids) or 1)
    player_count = len(player_ids) or 1
    return {player_id: weight * player_count / total for player_id, weight in weights.items()}


def gini(values: List[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(abs(value) for value in values)
    count = len(sorted_values)
    numerator = sum((2 * (index + 1) - count - 1) * value for index, value in enumerate(sorted_values))
    denominator = count * sum(sorted_values)
    return numerator / denominator if denominator else 0.0


def kl_divergence(p: Dict[str, float], q: Dict[str, float], eps: float = 1e-9) -> float:
    keys = set(p) | set(q)
    result = 0.0
    for key in keys:
        pk = max(p.get(key, 0.0), 0.0)
        qk = max(q.get(key, 0.0), eps)
        if pk > 0.0:
            result += pk * math.log(pk / qk)
    return result


def compute_action_correlations(
    combinations: List[GameCombinationResult],
    ce_distribution: Dict[str, float],
    top_n: int = 5,
) -> Dict[str, float]:
    del combinations
    pair_weights: Dict[str, float] = {}
    for key, probability in ce_distribution.items():
        if probability < 1e-6:
            continue
        parts = key.split("|")
        for index, part_left in enumerate(parts):
            for part_right in parts[index + 1 :]:
                pair_key = f"{part_left} || {part_right}"
                pair_weights[pair_key] = pair_weights.get(pair_key, 0.0) + probability
    return dict(sorted(pair_weights.items(), key=lambda item: item[1], reverse=True)[:top_n])


def analyse_welfare(
    game: GameDefinition,
    world: WorldState,
    combo: GameCombinationResult,
    ce_distribution: Dict[str, float],
    cce_empirical: Dict[str, float],
    combinations: List[GameCombinationResult],
    alpha: float = 0.5,
) -> WelfareAnalysis:
    trust_weights = compute_trust_weights(game, world, alpha)
    player_ids = [player.player_id for player in game.players]
    payoffs = [combo.player_payoffs.get(player_id, 0.0) for player_id in player_ids]
    utilitarian_sw = sum(payoffs)
    trust_weighted_sw = sum(
        trust_weights.get(player_id, 1.0) * combo.player_payoffs.get(player_id, 0.0)
        for player_id in player_ids
    )
    return WelfareAnalysis(
        alpha=alpha,
        utilitarian_sw=utilitarian_sw,
        trust_weighted_sw=trust_weighted_sw,
        payoff_gini=gini(payoffs),
        positive_normative_kl=kl_divergence(cce_empirical, ce_distribution) if cce_empirical else None,
        action_correlations=compute_action_correlations(combinations, ce_distribution),
    )
