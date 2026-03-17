# GIM 15.1.0 Release Notes

Release date: 2026-03-17  
Base comparison: `origin/GIM15` (`338bf45`) -> `GIM15` (current)

## Scope

This release hardens GIM15 after validator-driven remediation and adds reproducible release validation packaging.

## What Changed

### 1. Validator remediation packages completed (WP1-WP5)

- LLM strategic activation tuning and policy-space damping update.
- Scenario compiler actor-inference coverage expanded with confidence metadata.
- Crisis pathways updated with explicit FX-trigger branch and debt/FX mode handling.
- Outcome taxonomy expanded with two economic crisis classes:
  - `sovereign_financial_crisis`
  - `social_unrest_without_military`
- Bilateral trust/conflict asymmetry damping and stronger long-horizon mean reversion in political dynamics.

### 2. Calibration and baseline alignment

Operational baseline defaults switched to:

- `TFP_RD_SHARE_SENS = 0.300000`
- `GAMMA_ENERGY = 0.042000`
- `HEAT_CAP_SURFACE = 18.000000`

`DECARB_RATE_STRUCTURAL` remains artifact-bound (`0.052` from `data/agent_states_operational.artifacts.json`) to preserve historical CO2 fit envelope.

Parameter artifacts synchronized:

- `data/parameters_v15.csv`
- `data/parameters_v15.lock.json`

### 3. Validation package automation

Added one-command release validation runner:

- `scripts/run_validation_package_v15.sh`

Documentation:

- `docs/VALIDATION_PACKAGE_V15.md`

Generated local package example:

- `results/validation/non_llm/wp3_wp5_package_2026-03-17/`

### 4. Documentation synchronization

Updated/added:

- `docs/V15_RELEASE_READINESS.md`
- `docs/VALIDATOR_REMEDIATION_PLAN_GIM15.md`
- `README.md` (version and baseline notes)

## Validation Snapshot

- Regression sets (core/scenario/calibration/crisis/historical): passing.
- Validation package run:
  - `51 tests`, `OK`
  - `operational_v2`: `5/5` pass (`simple`) and `5/5` pass (`growth`)
- Rolling re-check (2015->2023, one-step windows):
  - pairwise mean RMSE: GDP `0.305`, CO2 `1.029`, temperature `0.075`
  - block4 mean RMSE: GDP `0.305`, CO2 `1.029`, temperature `0.078`

## Compatibility Notes

- CLI surface remains unchanged (`python3 -m gim ...`).
- Release package now reports `15.1.0`.
