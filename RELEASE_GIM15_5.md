# GIM 15.5.0 Release Notes

Release date: 2026-03-18  
Base comparison: `origin/GIM15` (`1335178`) -> `GIM15` (`15.5.0 release commit`)

## Scope

This release closes two validator-facing gaps in the current GIM15 line:

- conservative coercion wording in the legacy LLM prompt path
- missing explicit, separately tracked FX-crisis pathway semantics

## What Changed

### 1. Legacy LLM prompt remediation

- Replaced the conservative `use sparingly` wording in `gim/core/policy.py` with severity-proportional foreign-policy guidance.
- Added prompt regression coverage in `tests/test_policy_prompt.py`.

### 2. Explicit FX crisis pathway

- Added a separate `risk.fx_crisis_active_years` state alongside debt crisis state.
- Implemented FX crisis trigger logic in `gim/core/social.py` with explicit components:
  - external-debt proxy \(> 0.50\)
  - current-account proxy \(< -4\%\) of GDP
  - reserve cover \(< 3\) months of imports
- Debt and FX crises now can co-occur in the same country-year.
- First-year FX crisis shock is calibrated to a 15% GDP hit (`FX_CRISIS_GDP_MULT = 0.85`), with recovery opening once reserve cover exceeds 3 months.
- Surfaced FX crisis state in:
  - crisis flags (`gim/core/metrics.py`)
  - monitor/propagation cards (`gim/core/simulation.py`)
  - credit risk update (`gim/core/credit_rating.py`)
  - crisis validation outputs (`gim/crisis_validation.py`)

### 3. Parameter and documentation synchronization

- Exported FX crisis parameters into:
  - `data/parameters_v15.csv`
  - `data/parameters_v15.lock.json`
- Updated active documentation:
  - `README.md`
  - `docs/CALIBRATION_REFERENCE.md`
  - `docs/MODEL_METHODOLOGY.md`
  - `docs/SIMULATION_STEP_ORDER.md`
  - `docs/CRISIS_VALIDATION_PROTOCOL.md`
  - `docs/state_registry.csv`
- Added a closure addendum to `docs/legacy/VALIDATOR_REMEDIATION_PLAN_GIM15.md`.

## Validation Snapshot

- Targeted regression suite:
  - `python3 -m unittest tests.test_crisis_persistence tests.test_core_modules tests.test_observation_contract tests.test_policy_prompt`
  - result: `34 tests`, `OK`
- Crisis harness smoke run:
  - `PYTHONPATH=. python3 -m gim.crisis_validation --max-agents 21`
  - result: bundled cases passed and artifact written to `results/crisis_validation/crisis_validation_20260318-121644.json`

## Compatibility Notes

- Package version is now `15.5.0`.
- No CLI surface break was introduced.
- `check_debt_crisis()` remains available, while runtime orchestration now routes through `check_financial_crises()`.
