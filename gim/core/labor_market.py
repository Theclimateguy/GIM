"""Endogenous inflation and unemployment: Phillips curve + Okun's law (P4-A).

Previously `economy.unemployment` and `economy.inflation` were effectively static
(set at the initial state, moved only by discrete crisis hits) yet they *drive*
social tension, government trust and political stability. This module gives them a
law of motion so they respond to the macro state and - crucially for the model's
thesis - to climate/resource price shocks:

    Okun's law (unemployment):
        growth_gap = real GDP growth - potential growth
        u_target   = NAIRU - OKUN_COEFF * growth_gap
        u_t        = u_{t-1} + UNEMP_ADJ_SPEED * (u_target - u_{t-1})

    Expectations-augmented Phillips curve (inflation):
        pi_expected = ANCHOR*INFLATION_TARGET + (1-ANCHOR)*pi_{t-1}
        cost_push   = COSTPUSH_COEFF * (energy price change this year)
        money_term  = MONEY_INFLATION_PASS * (broad-money growth - (g* + pi*))   # [E4.1], off by default
        pi_t        = pi_expected + PHILLIPS_SLOPE*(NAIRU - u_t) + cost_push + money_term

The optional [E4.1] money term is the quantity-theory channel: excess broad-money growth
(deposits from the SFC block, above the stable-velocity reference) passes through to prices.
It is computed only when MONEY_INFLATION_PASS != 0, so the default run is golden bit-identical.

Both are clamped to plausible bounds. Inflation and unemployment are *non-critical*
fields, so they are written directly (no transition/critical-pending machinery).

The energy cost-push term is the climate/natural-capital channel into inflation:
resource stress and climate damage raise the global energy price
(`world.global_state.prices['energy']`), which passes through to consumer inflation,
which in turn raises social tension via the existing social block.
"""

from __future__ import annotations

from . import calibration_params as cal
from .core import WorldState
from .params import resolve_params
from .expectations import expected_inflation

_GDP_PREV_ATTR = "_macro_gdp_prev"
_ENERGY_PRICE_PREV_ATTR = "_macro_energy_price_prev"
_MONEY_PREV_ATTR = "_macro_money_prev"


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def update_inflation_unemployment(world: WorldState) -> None:
    """Advance every agent's unemployment (Okun) and inflation (Phillips) one year."""
    params = resolve_params(world)

    # Energy price change (cost-push driver), shared across agents.
    energy_price = float(world.global_state.prices.get("energy", 1.0))
    energy_prev = getattr(world.global_state, _ENERGY_PRICE_PREV_ATTR, None)
    if energy_prev is None or energy_prev <= 0.0:
        energy_change = 0.0
    else:
        energy_change = (energy_price - energy_prev) / energy_prev
    setattr(world.global_state, _ENERGY_PRICE_PREV_ATTR, energy_price)

    for agent in world.agents.values():
        econ = agent.economy

        # Real GDP growth vs potential -> Okun target for unemployment.
        gdp = max(float(econ.gdp), 1e-9)
        gdp_prev = getattr(econ, _GDP_PREV_ATTR, None)
        if gdp_prev is None or gdp_prev <= 0.0:
            growth = params.POTENTIAL_OUTPUT_GROWTH  # neutral on the first step
        else:
            growth = (gdp - gdp_prev) / gdp_prev
        setattr(econ, _GDP_PREV_ATTR, gdp)

        growth_gap = growth - params.POTENTIAL_OUTPUT_GROWTH
        u_target = params.NAIRU - params.OKUN_COEFF * growth_gap
        u_new = econ.unemployment + params.UNEMP_ADJ_SPEED * (u_target - econ.unemployment)
        u_new = _clamp(u_new, params.UNEMPLOYMENT_MIN, params.UNEMPLOYMENT_MAX)
        econ.unemployment = u_new

        # Expectations-augmented Phillips curve with an energy cost-push term.
        pi_expected = (
            params.INFLATION_EXPECTATION_ANCHOR * params.INFLATION_TARGET
            + (1.0 - params.INFLATION_EXPECTATION_ANCHOR) * econ.inflation
        )
        # [E4.3] Near-rational: blend the model-consistent expected inflation from the forward
        # projection (gim/core/expectations.py) into the anchor when EXPECTATIONS_INFLATION_WEIGHT>0 and
        # a forecast is cached. w=0 (default) -> pure adaptive -> golden bit-identical. Falls back to
        # adaptive when no forecast is available (e.g. inside the projection itself, under the guard).
        infl_weight = getattr(params, "EXPECTATIONS_INFLATION_WEIGHT", 0.0)
        if infl_weight > 0.0 and int(getattr(params, "EXPECTATIONS_HORIZON", 0)) > 0:
            forecast = expected_inflation(world, agent.id)
            if forecast is not None:
                pi_expected = (1.0 - infl_weight) * pi_expected + infl_weight * forecast
        unemployment_gap = params.NAIRU - u_new  # positive when u below NAIRU -> inflationary
        cost_push = params.INFLATION_COSTPUSH_COEFF * energy_change
        pi_new = pi_expected + params.PHILLIPS_SLOPE * unemployment_gap + cost_push

        # [E4.1] Quantity-theory money->price transmission (switchable, default off). EXCESS
        # broad-money growth above the stable-velocity reference (g* + pi*) feeds into inflation.
        # MONEY_INFLATION_PASS=0 -> this whole block is skipped (no term, no extra agent state)
        # -> golden bit-identical. Broad money is the SFC deposit stock (set before this step).
        money_pass = getattr(params, "MONEY_INFLATION_PASS", 0.0)
        if money_pass != 0.0:
            money = getattr(econ, "_money_supply", None)
            money_prev = getattr(econ, _MONEY_PREV_ATTR, None)
            if money and money_prev and money_prev > 0.0:
                money_growth = (money - money_prev) / money_prev
                ref_growth = params.POTENTIAL_OUTPUT_GROWTH + params.INFLATION_TARGET
                pi_new += money_pass * (money_growth - ref_growth)
            if money is not None:
                setattr(econ, _MONEY_PREV_ATTR, money)

        econ.inflation = _clamp(pi_new, params.INFLATION_MIN, params.INFLATION_MAX)
