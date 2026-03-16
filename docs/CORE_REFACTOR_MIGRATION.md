# Core Refactor Migration Notes (GIM15)

This file tracks migration from multi-writer yearly mutation to causal four-phase accounting.

## Iteration Log

## I1 (current)

- Added core transition contract:
  - `docs/CORE_TRANSITION_CONTRACT.md`
- Added critical field registry:
  - `docs/critical_field_registry.csv`
  - `gim/core/contracts/critical_fields.py`
- Added typed transition schemas and phase adapters:
  - `gim/core/transitions/schemas.py`
  - `gim/core/transitions/{baseline,detect,propagate,reconcile}.py`

Behavior intent:

- no model-output changes in this iteration
- only typed scaffolding and explicit contracts

## I2

- Integrated `TransitionEnvelope` into `step_world()` phase trace.
- Added typed snapshots for `pre/baseline/detect/propagate/reconcile`.

## I3

- Added centralized reconcile finalization for critical fields:
  - `economy.gdp`
  - `economy.capital`
  - `economy.public_debt`
  - `society.trust_gov`
  - `society.social_tension`
- Final values now pass through one canonical reconcile path per yearly step.

## I4

- Extended `critical_field_accounting` with channel decomposition:
  - `sanctions_conflict`
  - `policy_trade`
  - `climate_macro`
  - `social_feedback`
  - `net_propagation`
- Added reconcile adjustment and final value blocks in trace accounting.

## I5

- Added transition contract tests:
  - `tests/test_transition_contracts.py`
- Added static critical-write audit test:
  - `tests/test_critical_write_audit.py`
- Current policy: legacy critical writes are explicitly allow-listed while migration is in progress; unexpected new writer modules fail tests.
- Added runtime critical write guard:
  - `gim/core/transitions/write_guard.py`
  - integrated into `step_world()` with phase-aware write tracing.
  - `phase_trace["critical_write_guard"]` now records counts by phase/module/field.
  - env control: `GIM15_CRITICAL_WRITE_GUARD=off|observe|strict`.

## I6

- Regression floor run completed:
  - `python3 -m unittest discover -s tests -v`
  - result: `140 tests`, `OK` (`3 skipped`)
- Crisis harness run completed:
  - `python3 -m gim.crisis_validation --max-agents 21`
  - result: case cards saved and all baseline labels pass.

## I7

- Completed hard-phase migration for institutional critical writes:
  - `gim/core/institutions.py` no longer mutates:
    - `economy.public_debt`
    - `society.trust_gov`
    - `society.social_tension`
  - institutional effects on critical fields are now queued as deltas.
  - queued deltas are applied in propagation via:
    - `gim/core/transitions/propagate.py::apply_institution_pending_deltas()`
- Updated runtime writer allow-list:
  - removed `gim/core/institutions.py`
  - added `gim/core/transitions/propagate.py`
- Validation after migration:
  - `python3 -m unittest tests.test_critical_write_audit tests.test_transition_contracts -v` -> `OK`
  - `python3 -m unittest tests.test_historical_backtest -v` -> `OK`
  - guard trace no longer shows `institutions.py` as critical-field writer.

## I8

- Completed hard-phase migration for social critical writes:
  - `gim/core/social.py` no longer directly mutates:
    - `economy.gdp`
    - `economy.capital`
    - `economy.public_debt`
    - `society.trust_gov`
    - `society.social_tension`
  - social/debt/regime effects now accumulate in an internal pending critical-delta layer.
  - pending social deltas are applied in propagation via:
    - `gim/core/transitions/propagate.py::apply_social_pending_deltas()`
- Updated runtime writer allow-list:
  - removed `gim/core/social.py`
- Validation after migration:
  - `python3 -m py_compile gim/core/social.py gim/core/transitions/propagate.py gim/core/transitions/write_guard.py gim/core/simulation.py` -> `OK`
  - `python3 -m unittest tests.test_transition_contracts tests.test_critical_write_audit -v` -> `OK`
  - `python3 -m unittest tests.test_historical_backtest -v` -> `OK`
  - guard trace no longer shows `social.py`; active writer modules:
    - `actions.py`
    - `economy.py`
    - `transitions/propagate.py`
    - `transitions/reconcile.py`

## I9

- Completed hard-phase migration for action/economy critical writes:
  - `gim/core/actions.py` now uses internal pending critical deltas plus `pop_actions_critical_deltas()`.
  - `gim/core/economy.py` now uses internal pending critical deltas plus `pop_economy_critical_deltas()`.
  - central application remains in `gim/core/transitions/propagate.py`:
    - `apply_actions_pending_deltas()`
    - `apply_economy_pending_deltas()`
- Propagation wiring updated in `step_world()` to preserve within-year sequence:
  - apply action deltas before/after trade-deal pass
  - apply economy deltas after each `update_economy_output` and `update_public_finances`
- Backward compatibility for standalone unit calls:
  - `apply_action`, `apply_trade_deals`, `update_economy_output`, `update_public_finances`, and `check_debt_crisis` keep immediate-write behavior by default.
  - `simulation.py` uses explicit defer flags for phase-aware centralized writes.
- Updated runtime writer allow-list:
  - removed `gim/core/actions.py`
  - removed `gim/core/economy.py`
- Validation after migration:
  - `python3 -m unittest discover -s tests -v` -> `140 tests`, `OK` (`3 skipped`)
  - `python3 -m unittest tests.test_historical_backtest -v` -> `OK`
  - historical RMSE unchanged:
    - GDP `1.049`
    - CO2 `1.629`
    - Temperature `0.136`
  - runtime critical writers now:
    - `gim/core/transitions/propagate.py`
    - `gim/core/transitions/reconcile.py`

## I10

- Completed hard-phase migration for remaining channel writers:
  - `gim/core/geopolitics.py` now accumulates critical-field deltas and exports:
    - `pop_geopolitics_critical_deltas()`
  - `gim/core/climate.py` now accumulates critical-field deltas and exports:
    - `pop_climate_critical_deltas()`
  - no direct critical writes remain in either module.
- Added centralized application in propagation:
  - `apply_geopolitics_pending_deltas()`
  - `apply_climate_pending_deltas()`
- Propagation wiring updated to preserve causal order:
  - apply geopolitical deltas after sanctions, security actions, and active-conflict updates.
  - apply climate deltas immediately after extreme-event pass.
- Updated runtime writer allow-list:
  - removed `gim/core/geopolitics.py`
  - removed `gim/core/climate.py`
- Validation after migration:
  - `python3 -m unittest discover -s tests -v` -> `140 tests`, `OK` (`3 skipped`)
  - `python3 -m unittest tests.test_historical_backtest -v` -> `OK`
  - historical RMSE unchanged:
    - GDP `1.049`
    - CO2 `1.629`
    - Temperature `0.136`
  - runtime critical writers remain:
    - `gim/core/transitions/propagate.py`
    - `gim/core/transitions/reconcile.py`

## Final State

- Migration of module-level critical writers is complete.
- Runtime contract is now explicit:
  - `transitions/propagate.py` applies queued channel deltas.
  - `transitions/reconcile.py` performs canonical finalization/clamping.
- Static critical-write audit has no unexpected offenders.
- Remaining optional hardening:
  - add weak order-invariance smoke tests for intra-phase channel ordering.
