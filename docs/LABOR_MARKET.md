# GIM18 Endogenous Inflation & Unemployment (P4-A)

`economy.unemployment` and `economy.inflation` drive social tension, government trust
and political stability, but until P4-A they were effectively **static** - fixed at the
initial state and moved only by discrete crisis hits. `gim/core/labor_market.py` gives
them a law of motion so they respond to the macro state and to climate/resource price
shocks, closing the loop **climate damage -> energy price -> inflation/unemployment ->
social tension -> political instability**.

## Equations (`update_inflation_unemployment`)

Run once per simulated year, after the economy/finance updates and before the social
block. Inflation and unemployment are non-critical fields, written directly.

**Okun's law (unemployment).** Real GDP growth relative to potential sets an
unemployment target; unemployment partially adjusts toward it:

```
growth_gap = real_GDP_growth - POTENTIAL_OUTPUT_GROWTH
u_target   = NAIRU - OKUN_COEFF * growth_gap
u_t        = u_{t-1} + UNEMP_ADJ_SPEED * (u_target - u_{t-1})     (clamped)
```

**Expectations-augmented Phillips curve (inflation).** Anchored adaptive
expectations, a flat unemployment-gap slope, and an energy cost-push term:

```
pi_expected = ANCHOR*INFLATION_TARGET + (1-ANCHOR)*pi_{t-1}
cost_push   = INFLATION_COSTPUSH_COEFF * (energy-price change this year)
pi_t        = pi_expected + PHILLIPS_SLOPE*(NAIRU - u_t) + cost_push   (clamped)
```

The **energy cost-push** term is the natural-capital channel into inflation: resource
stress and climate damage raise `world.global_state.prices['energy']`, which passes
through to consumer inflation and onward to social tension via the existing social block.

## Parameters (`calibration_params.py`)

| Param | Value | Basis |
|---|---|---|
| `POTENTIAL_OUTPUT_GROWTH` | 0.025 | trend real growth |
| `NAIRU` | 0.045 | natural rate |
| `OKUN_COEFF` | 0.3 | Okun's law (~0.3-0.5) |
| `UNEMP_ADJ_SPEED` | 0.5 | partial adjustment |
| `INFLATION_TARGET` | 0.02 | anchor |
| `INFLATION_EXPECTATION_ANCHOR` | 0.5 | expectations weight |
| `PHILLIPS_SLOPE` | 0.25 | flat modern Phillips |
| `INFLATION_COSTPUSH_COEFF` | 0.05 | +20% energy -> +1pp inflation |

Unemployment is clamped to [0.01, 0.35]; inflation to [-0.02, 0.30].

## Validation

`tests/test_labor_market.py` (7 tests): Okun direction (boom lowers, recession raises
unemployment), Phillips direction (tight labor market lifts inflation), energy cost-push
(quantified pass-through), bounds, determinism. The 2015-2023 economic backtest golden
values are **unchanged** (1.026 / 1.606 / 0.134) - the new dynamics do not disturb the
validated GDP/CO2/temperature predictions.

## Follow-ups

Country-specific potential growth and NAIRU (currently global constants); a monetary
policy reaction (interest rate responding to inflation/unemployment) to close the
central-bank loop; wage-price spiral via a second-round expectations term.
