# Core Transition Contract (GIM15)

## Purpose

This contract defines the strict write discipline for yearly state transitions:

- `pre` -> `baseline` -> `detect` -> `propagate` -> `reconcile`
- critical fields have a single canonical finalization phase (`reconcile`)
- non-reconcile modules may only produce deltas/signals for critical fields

## Critical Fields

Phase target for final yearly write:

- `economy.gdp` -> `reconcile`
- `economy.capital` -> `reconcile`
- `economy.public_debt` -> `reconcile`
- `society.trust_gov` -> `reconcile`
- `society.social_tension` -> `reconcile`

## Phase Contract

### Baseline

- allowed: structural trend calculators
- output: baseline snapshots, trend components
- not allowed: final crisis-driven writes of critical fields

### Detect

- allowed: event probabilities, threshold crossings, onset/persistence flags
- output: typed event detection payload
- not allowed: direct writes of critical field finals

### Propagate

- allowed: channel-level delta production (sanctions/conflict/debt/social/climate/trade)
- output: typed propagation deltas
- not allowed: final writes of critical fields

### Reconcile

- canonical finalization phase for critical fields
- formula shape:
  - `final = baseline + sum(channel_deltas) + bounded_adjustments`
- runs invariant checks and clamps

## Causal Accounting Requirement

`phase_trace` must be able to expose, for each critical field:

- `pre`
- `baseline`
- channel contributions
- `reconcile_adjustment`
- `final`

## Enforcement (Iteration Path)

1. Registry contract (`gim/core/contracts/critical_fields.py` + CSV registry)
2. Typed transition schemas (`gim/core/transitions/schemas.py`)
3. Static/runtime guards against direct writes outside reconcile
4. Test gates:
   - canonical write audit
   - trace completeness
   - weak order invariance smoke checks
