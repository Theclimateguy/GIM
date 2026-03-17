# GIM15 Release Readiness (Pre-Release-1)

## Scope

This note captures what is fixed as the working baseline for the first GIM15 release candidate.

## Fixed baseline candidate

Source artifact:

- `results/backtest/stage_bc_block4_2015_2023/stage_bc_block4.json`

Selected robust parameters:

- `TFP_RD_SHARE_SENS = 0.300000`
- `GAMMA_ENERGY = 0.042000`
- `DECARB_RATE_STRUCTURAL = 0.031200`
- `HEAT_CAP_SURFACE = 18.000000`

Selection rule:

- Stage B (block-4 walk-forward): per-window train selection on `2015..origin`, validate `origin->origin+1`.
- Stage C (single robust set): minimize `mean(validation objective) + 0.5 * std(validation objective)`.

Objective weights:

- GDP RMSE weight: `0.10`
- global CO2 RMSE weight: `1.00`
- temperature RMSE weight: `10.00`

## Out-of-sample comparison

Source artifact:

- `results/backtest/stage_bc_block4_2015_2023/oos_compare_baseline_vs_robust.json`

One-step OOS windows: `2015->2016 ... 2022->2023` (8 windows)

Baseline vs robust:

- objective: `1.8357 -> 1.8125` (improved)
- GDP RMSE: `0.3108 -> 0.3109` (neutral)
- global CO2 RMSE: `1.0286 -> 1.0286` (neutral)
- temperature RMSE: `0.0776 -> 0.0753` (improved)

Per-window objective delta:

- robust better in `5/8` windows
- robust worse in `3/8` windows

## Baseline switch status (2026-03-17)

Applied to operational defaults:

- `TFP_RD_SHARE_SENS = 0.300000`
- `GAMMA_ENERGY = 0.042000`
- `HEAT_CAP_SURFACE = 18.000000`

Kept artifact-bound (not switched to robust constant):

- `DECARB_RATE_STRUCTURAL = 0.052000` (from `data/agent_states_operational.artifacts.json`)

Reason:

- forcing `DECARB_RATE_STRUCTURAL=0.0312` causes historical CO2 fit failure (`Global CO2 RMSE ≈ 3.656` vs release envelope `< 1.70`).

Rolling re-check artifacts after switch:

- `results/backtest/rolling_pairwise_2015_2023_reswitch_final_2026-03-17/`
- `results/backtest/stage_bc_block4_2015_2023_reswitch_final_2026-03-17/`

Stage B/C robust candidate from re-check:

- `TFP_RD_SHARE_SENS = 0.180000`
- `GAMMA_ENERGY = 0.025200`
- `DECARB_RATE_STRUCTURAL = 0.031200`
- `HEAT_CAP_SURFACE = 18.000000`

## Release hardening checklist

- [x] P1-P4 deliverables completed
- [x] rolling OOS baseline selected
- [x] apply approved baseline switch values to `gim/core/calibration_params.py`
- [x] refresh `data/parameters_v15.csv` and `data/parameters_v15.lock.json`
- [x] run full non-LLM verification suite and archive run report

Archived non-LLM validation package:

- `results/validation/non_llm/wp3_wp5_2026-03-17/unittest.log`
- `results/validation/non_llm/wp3_wp5_2026-03-17/calibrate_simple.json`
- `results/validation/non_llm/wp3_wp5_2026-03-17/calibrate_growth.json`
- `results/validation/non_llm/wp3_wp5_2026-03-17/summary.md`
