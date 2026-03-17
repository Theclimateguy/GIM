# GIM15 Release Readiness (15.1)

## Scope

This note captures release-readiness status for `15.1`, including baseline switch decisions and post-switch rolling re-check.

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
- `results/validation/non_llm/wp3_wp5_package_2026-03-17/unittest.log`
- `results/validation/non_llm/wp3_wp5_package_2026-03-17/calibrate_simple.json`
- `results/validation/non_llm/wp3_wp5_package_2026-03-17/calibrate_growth.json`
- `results/validation/non_llm/wp3_wp5_package_2026-03-17/summary.md`
