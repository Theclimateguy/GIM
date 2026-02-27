# Country Creditworthiness Rating (1-26)

This model computes a yearly **next-year creditworthiness rating** for each country.

- Scale: `1..26` where `1` is strongest and `26` is default.
- Zones:
  - Green: `1..12`
  - Yellow: `13..20`
  - Red: `21..26`

## Core Formula

1. Build normalized risk components in `[0,1]` from model state.
2. Aggregate to total risk score:

`total_risk = 0.25*financial + 0.20*war + 0.22*social + 0.13*sanctions + 0.20*macro`

3. Map risk to rating:

`rating = round(1 + total_risk * 25)` then clamp to `1..26`.

## Components and Source Variables

### 1) Financial risk (25%)
- Current stress:
  - `public_debt / gdp`
  - effective interest rate (`compute_effective_interest_rate`)
  - debt stress (`compute_debt_stress`)
  - debt crisis flag (`_debt_crisis_this_step`)
- Next-year pressure:
  - debt stress + GDP trend deterioration from memory summary.

### 2) War risk (20%)
- Current war status from bilateral relations (`relation.at_war`).
- Next-year escalation pressure from:
  - relation conflict level,
  - low bilateral trust,
  - military pressure,
  - own conflict-proneness and hawkishness.

### 3) Social instability risk (22%)
- Revolution/overthrow proximity (next-year):
  - protest risk (`compute_protest_risk`),
  - social tension,
  - low trust,
  - regime fragility,
  - worsening tension vs trust trend.
- Structural drivers:
  - inequality (`inequality_gini`),
  - unemployment,
  - inflation,
  - water stress,
  - food stress (reserve years).
- Risk management capacity (risk reducer):
  - trust,
  - political policy space,
  - regime stability,
  - social spending share.

### 4) Sanctions risk (13%)
- Current sanctions pressure:
  - inbound mild/strong active sanctions from other countries.
- Next-year sanctions preconditions:
  - bilateral hostility (conflict + low trust),
  - counterpart sanction propensity.

### 5) Macro stability risk (20%)
- GDP trend deterioration,
- unemployment,
- inflation,
- FX buffer (`fx_reserves / gdp`),
- resource reserve stress (energy/food/metals reserve years).

## Outputs

Per country per year:
- `credit_rating` (1-26)
- `credit_zone` (`green|yellow|red`)
- `credit_risk_score` (`0..1`)
- component details (`financial/war/social/sanctions/macro` and subfactors)

These are computed in `gim_11_1/credit_rating.py` and updated each simulation year.
