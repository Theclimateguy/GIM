# GIM18 D1 — Carbon-Price → Emissions via CES Factor Substitution (THE-36)

The economically-meaningful half of D1 (nested-CES). The F2.1 scaffold swapped the production
*output aggregator*; this adds the channel that makes carbon/energy prices actually reduce
emissions — derived from producer cost-minimization, switchable, golden-safe by construction.

## Mechanism (producer theory, not imposed)

The inner KE CES (capital, energy) implies a cost-minimizing energy demand per unit output that
falls with the relative energy price with elasticity `sigma_KE`:

```
(E/Y)*  ∝  p_E^(-sigma_KE)          # conditional factor demand, inner CES
```

A carbon price raises the effective energy price by a fractional markup, and fossil emission
intensity (∝ energy use) inherits the same elasticity:

```
markup            = CARBON_PRICE_PASSTHROUGH * carbon_price_usd_per_tco2
emission_intensity *= (1 + markup)^(-sigma_KE)
```

Implemented in `gim/core/climate.update_emissions_from_economy` behind `ENERGY_PRICE_SUBSTITUTION`
(default off). The markup — not the absolute market price — drives it, so at `carbon=0` the factor is
1 → **golden bit-identical by construction**, independent of the endogenous energy-price path.

Parameters (`calibration_params.py`): `ENERGY_PRICE_SUBSTITUTION` (switch), `CES_SIGMA_KE`=0.4
(shared with F2.1; van der Werf 2008 / Koetse 2008), `CARBON_PRICE_PASSTHROUGH`=0.003 (~15% energy-
price rise at $50/tCO2 economy-wide), `CARBON_PRICE_USD_PER_TCO2` (policy lever, 0 by default).

## Emergent elasticity vs empirical (the result)

GIM's carbon-price → CO2 response is **derived** from `sigma_KE` × pass-through, then *measured* on
the 2015-2023 backtest (`scripts/measure_carbon_price_elasticity.py`); it was not fitted to emission
data:

| carbon price | GIM emission cut | semi-elasticity |
|---|---|---|
| $10/tCO2 | 1.0% | 0.104 %/$ |
| $25/tCO2 | 2.5% | 0.101 %/$ |
| $50/tCO2 | 4.8% | 0.097 %/$ |
| $100/tCO2 | 8.8% | 0.088 %/$ |
| $200/tCO2 | 15.2% | 0.076 %/$ |

**Empirical benchmark** (ex-post ETS / carbon-tax studies): average introduction effect ~1–2.5%;
significant schemes −5% to −21% (−4 to −15% bias-corrected); semi-elasticity ~0.05 %/$. Sources:
[RFF/Cambridge — Carbon pricing and the elasticity of CO₂ emissions](https://www.rff.org/publications/working-papers/carbon-pricing-and-the-elasticity-of-co2-emissions/);
[Nature Communications meta-analysis (2024)](https://www.nature.com/articles/s41467-024-48512-w).

GIM lands **in the empirical band**: low prices ($10–25) reproduce the ~1–2.5% average effect; higher
prices ($50–200) reproduce the −5 to −21% significant-scheme range — from a production parameter, not
an emissions fit. This is a real cross-validation of the structural channel.

## The novel angle: a long-run / short-run friction wedge

GIM's semi-elasticity (~0.08–0.10 %/$) is a touch above the pooled empirical central (~0.05 %/$).
That is expected and informative: the CES channel is the **frictionless, long-run equilibrium**
substitution, whereas observed ETS effects are **short-run** and damped by incomplete pass-through,
capital/infrastructure inertia, free allocation and exemptions. The gap is the *adjustment-friction
wedge*. GIM thus offers the structural long-run carbon-price elasticity, and the comparison to the
short-run data quantifies the friction. A short-run calibration is available by lowering
`CARBON_PRICE_PASSTHROUGH` or `sigma_KE`.

## Status & relation to nested-CES

This delivers the **policy-relevant value of D1** (carbon price → emissions) independent of activating
the disruptive nested-CES *output aggregator* (`NESTED_CES`, still off pending its own recalibration).
Validated: `tests/test_carbon_price_channel.py` (golden-safe at carbon=0; monotone reductions;
flag-gated). Default off → headline golden unchanged; enable for carbon-policy scenarios / ensemble.
