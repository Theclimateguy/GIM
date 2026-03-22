# P1-P4 Completion Status

## P1 State registry and causal map

Status: completed (operational)

Artifacts:

- `docs/MODEL_STATE_MAP.md`
- `docs/state_registry.csv`
- `docs/state_registry_coverage.md`

Coverage:

- transition-relevant expected fields covered (`missing=0`)

## P2 4-phase kernel refactor

Status: completed (phase scaffold + diagnostics + ablation switches)

Artifacts:

- `gim/core/simulation.py` (`baseline/detect/propagate/reconcile`)
- `docs/SIMULATION_STEP_ORDER.md`

Capabilities:

- phase trace snapshots
- detect/propagate event cards
- invariant report
- channel-level ablation toggles

## P3 Crisis validation harness

Status: completed (MVP+)

Artifacts:

- `docs/CRISIS_VALIDATION_PROTOCOL.md`
- `tests/crisis_cases/*.json`
- `gim/crisis_validation.py`
- `results/crisis_validation/*.json`

Capabilities:

- directional + ordering + magnitude checks
- baseline vs ablation deltas (`delta_vs_baseline`)

## P4 Formal model and parameter governance

Status: completed (documentation baseline)

Artifacts:

- `docs/MODEL_SPEC_V15.md`
- `docs/GIM16_UNIFIED_MODEL_SPEC.md`
- `data/parameters_gim16.csv`
- `data/parameters_gim16.lock.json`
- `docs/PARAMETER_CHANGE_POLICY.md`

Capabilities:

- equation index and phase mapping
- parameter registry with source/uncertainty/status
- lock + recalibration decision rule

## Post-P4 release validation

Status: completed (rolling OOS baseline selected and re-checked after 15.1 baseline switch)

Artifacts:

- `results/backtest/rolling_pairwise_2015_2023/rolling_backtest_stepwise.json`
- `results/backtest/stage_bc_block4_2015_2023/stage_bc_block4.json`
- `results/backtest/rolling_pairwise_2015_2023_reswitch_final_2026-03-17/rolling_backtest_stepwise.json`
- `results/backtest/stage_bc_block4_2015_2023_reswitch_final_2026-03-17/stage_bc_block4.json`

Outcome:

- v16.0 active baseline defaults:
  - `TFP_RD_SHARE_SENS=0.300000`
  - `GAMMA_ENERGY=0.042000`
  - `DECARB_RATE_STRUCTURAL=0.052000` (artifact-bound)
  - `HEAT_CAP_SURFACE=18.000000`

- post-switch block-4 robust candidate (reference):
  - `TFP_RD_SHARE_SENS=0.180000`
  - `GAMMA_ENERGY=0.025200`
  - `DECARB_RATE_STRUCTURAL=0.031200`
  - `HEAT_CAP_SURFACE=18.000000`
