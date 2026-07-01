"""Welfare accounting: CRRA utility + Ramsey discounting (Phase 3-A).

Adds the DICE/RICE valuation layer on top of the forward simulator. Consumption is derived
from GDP and the model's endogenous savings rate (C = Y - I); per-capita consumption feeds a
constant-relative-risk-aversion (CRRA) utility, and Ramsey discounting gives a discounted
utilitarian social-welfare functional:

    W = sum_t  L_t * U(c_t) / (1 + rho)^t,    U(c) = (c^(1-eta) - 1)/(1-eta)   [ln c if eta=1]

with eta = ``ELASTICITY_MARGINAL_UTILITY`` and rho = ``PURE_TIME_PREFERENCE`` (DICE-2016R2
defaults 1.45 and 0.015), both carried in the per-run ParameterSet.
"""

from __future__ import annotations

import math
from typing import Sequence

from .core.country_params import get_savings_rate
from .core.core import clamp01
from .core.params import resolve_params


def _agent_savings_rate(agent, params) -> float:
    base = get_savings_rate(agent.name, params)
    stability = clamp01(agent.risk.regime_stability)
    tension = clamp01(agent.society.social_tension)
    rate = base * (
        params.SAVINGS_BASELINE_OFFSET
        + params.SAVINGS_STABILITY_SENS * stability
        - params.SAVINGS_TENSION_SENS * tension
    )
    return max(params.SAVINGS_MIN, min(params.SAVINGS_MAX, rate))


def world_consumption(world, params=None) -> float:
    """Aggregate world consumption (T$) = sum_i GDP_i * (1 - savings_rate_i)."""
    p = params or resolve_params(world)
    return sum(
        max(0.0, a.economy.gdp) * (1.0 - _agent_savings_rate(a, p)) for a in world.agents.values()
    )


def world_population(world) -> float:
    return sum(max(0.0, a.economy.population) for a in world.agents.values())


def per_capita_consumption(world, params=None) -> float:
    """Per-capita consumption in $ / person (GDP is in T$)."""
    pop = world_population(world)
    if pop <= 0.0:
        return 0.0
    return world_consumption(world, params) * 1e12 / pop


def crra_utility(consumption: float, eta: float) -> float:
    c = max(consumption, 1e-9)
    if abs(eta - 1.0) < 1e-9:
        return math.log(c)
    return (c ** (1.0 - eta) - 1.0) / (1.0 - eta)


def marginal_utility(consumption: float, eta: float) -> float:
    """U'(c) = c^(-eta) — the welfare weight on a marginal unit of consumption."""
    return max(consumption, 1e-9) ** (-eta)


def discounted_welfare(
    consumption_pc: Sequence[float], population: Sequence[float], params
) -> float:
    eta = params.ELASTICITY_MARGINAL_UTILITY
    rho = params.PURE_TIME_PREFERENCE
    n = min(len(consumption_pc), len(population))
    return sum(
        population[t] * crra_utility(consumption_pc[t], eta) / ((1.0 + rho) ** t) for t in range(n)
    )


__all__ = [
    "world_consumption",
    "world_population",
    "per_capita_consumption",
    "crra_utility",
    "marginal_utility",
    "discounted_welfare",
]
