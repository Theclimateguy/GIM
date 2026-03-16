# GIM 15.0.0 Release Notes

Release date: 2026-03-16  
Base comparison: `origin/GIM14` (`5e057dc`) -> `GIM15` (`c59692b`)

## Diff Summary (GIM14 -> GIM15)

- 73 files changed
- 6208 insertions, 276 deletions
- 4 branch-level commits since `origin/GIM14`

## What Changed

### 1. Core kernel refactor to explicit 4-phase step

`step_world()` in `gim/core/simulation.py` now follows explicit phases with trace support:

1. `baseline`
2. `detect`
3. `propagate`
4. `reconcile`

Added typed transition package:

- `gim/core/transitions/schemas.py`
- `gim/core/transitions/baseline.py`
- `gim/core/transitions/detect.py`
- `gim/core/transitions/propagate.py`
- `gim/core/transitions/reconcile.py`
- `gim/core/transitions/write_guard.py`

### 2. Critical-field write centralization

For critical macro-social fields:

- `economy.gdp`
- `economy.capital`
- `economy.public_debt`
- `society.trust_gov`
- `society.social_tension`

direct multi-writer mutations were migrated to queued deltas in channel modules, with centralized application in `transitions/propagate.py` and canonical finalization in `transitions/reconcile.py`.

Runtime writer guard trace now shows only:

- `gim/core/transitions/propagate.py`
- `gim/core/transitions/reconcile.py`

### 3. Contracts and audit layer

Added explicit contract and registry artifacts:

- `docs/CORE_TRANSITION_CONTRACT.md`
- `docs/critical_field_registry.csv`
- `gim/core/contracts/critical_fields.py`

Added tests:

- `tests/test_transition_contracts.py`
- `tests/test_critical_write_audit.py`

### 4. Calibration/backtest/doc stack update for V15

- new parameter artifacts (`data/parameters_v15.csv`, `data/parameters_v15.lock.json`)
- rolling/backtest and validation tooling updates (`gim/rolling_backtest.py`, `gim/crisis_validation.py`)
- docs aligned to V15 nomenclature and methodology
- historical baseline envelope maintained during refactor

## Validation Snapshot

- Full suite: `140 tests`, `OK` (`3 skipped`)
- Historical backtest (2015-2023):
  - GDP RMSE: `1.049`
  - CO2 RMSE: `1.629`
  - Temperature RMSE: `0.136`

## Compatibility Notes

- Orchestration CLI remains under `python3 -m gim ...`
- World simulation CLI remains under `python3 -m gim world ...` / `python3 -m gim.core.cli`
- Public workflows for scenario/game/dashboard are preserved; main changes are internal write-order governance and traceability.
