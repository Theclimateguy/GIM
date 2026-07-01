from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from ..types import GameCombinationResult, GameDefinition


def _action_key(actions: Dict[str, str]) -> str:
    return "|".join(f"{player_id}:{action_name}" for player_id, action_name in sorted(actions.items()))


@dataclass
class CorrelatedEquilibrium:
    distribution: Dict[str, float]
    social_welfare: float
    utilitarian_welfare: float
    objective_description: str
    is_feasible: bool
    max_incentive_deviation: float
    solver_status: str


def solve_correlated_equilibrium(
    game: GameDefinition,
    combinations: list[GameCombinationResult],
    trust_weights: Optional[Dict[str, float]] = None,
) -> CorrelatedEquilibrium:
    if not combinations:
        return CorrelatedEquilibrium(
            distribution={},
            social_welfare=0.0,
            utilitarian_welfare=0.0,
            objective_description=(
                "Maximize trust-weighted welfare subject to standard correlated-equilibrium "
                "incentive constraints."
            ),
            is_feasible=False,
            max_incentive_deviation=float("inf"),
            solver_status="no combinations",
        )

    try:
        from scipy.optimize import linprog
        import numpy as np
    except ImportError:
        return CorrelatedEquilibrium(
            distribution={},
            social_welfare=0.0,
            utilitarian_welfare=0.0,
            objective_description=(
                "Maximize trust-weighted welfare subject to standard correlated-equilibrium "
                "incentive constraints."
            ),
            is_feasible=False,
            max_incentive_deviation=float("inf"),
            solver_status="scipy not available",
        )

    weights = trust_weights or {player.player_id: 1.0 for player in game.players}
    count = len(combinations)
    keys = [_action_key(combo.actions) for combo in combinations]
    combo_map = {keys[index]: combinations[index] for index in range(count)}

    objective = np.array(
        [
            -sum(weights.get(player_id, 1.0) * combo.player_payoffs.get(player_id, 0.0) for player_id in weights)
            for combo in combinations
        ],
        dtype=float,
    )
    utilitarian = np.array([-combo.total_payoff for combo in combinations], dtype=float)

    a_eq = np.ones((1, count), dtype=float)
    b_eq = np.array([1.0], dtype=float)

    ic_rows = []
    for player in game.players:
        player_id = player.player_id
        for action_from in player.allowed_actions:
            for action_to in player.allowed_actions:
                if action_from == action_to:
                    continue
                row = np.zeros(count, dtype=float)
                for index, combo in enumerate(combinations):
                    if combo.actions.get(player_id) != action_from:
                        continue
                    alt = combo_map.get(_action_key({**combo.actions, player_id: action_to}))
                    if alt is None:
                        continue
                    row[index] = alt.player_payoffs.get(player_id, 0.0) - combo.player_payoffs.get(player_id, 0.0)
                ic_rows.append(row)

    a_ub = np.array(ic_rows, dtype=float) if ic_rows else None
    b_ub = np.zeros(len(ic_rows), dtype=float) if ic_rows else None
    result = linprog(
        objective,
        A_ub=a_ub,
        b_ub=b_ub,
        A_eq=a_eq,
        b_eq=b_eq,
        bounds=[(0.0, 1.0)] * count,
        method="highs",
    )

    if not result.success:
        uniform = np.full(count, 1.0 / count, dtype=float)
        return CorrelatedEquilibrium(
            distribution={key: float(probability) for key, probability in zip(keys, uniform)},
            social_welfare=float(-objective @ uniform),
            utilitarian_welfare=float(-utilitarian @ uniform),
            objective_description=(
                "Maximize trust-weighted welfare subject to standard correlated-equilibrium "
                "incentive constraints."
            ),
            is_feasible=False,
            max_incentive_deviation=float("inf"),
            solver_status=str(result.message),
        )

    sigma = result.x.clip(min=0.0)
    sigma_sum = float(sigma.sum()) or 1.0
    sigma = sigma / sigma_sum
    max_dev = 0.0
    if a_ub is not None and len(ic_rows) > 0:
        max_dev = float((a_ub @ sigma).max(initial=0.0))
    return CorrelatedEquilibrium(
        distribution={key: float(probability) for key, probability in zip(keys, sigma)},
        social_welfare=float(-objective @ sigma),
        utilitarian_welfare=float(-utilitarian @ sigma),
        objective_description=(
            "Maximize trust-weighted welfare subject to standard correlated-equilibrium "
            "incentive constraints."
        ),
        is_feasible=True,
        max_incentive_deviation=max_dev,
        solver_status="optimal",
    )
