# GIM13 Parity Audit

This document records the local inspection and restoration work performed to align `GIM_14` with the `GIM_13` operational and calibration surface.

## 1. Compared Targets

- local repo: [GIM_13](/Users/theclimateguy/Documents/jupyter_lab/GIM_13)
- local repo: [GIM_14](/Users/theclimateguy/Documents/jupyter_lab/GIM_14)
- remote branch reference: `origin/main`
- remote branch reference: `origin/GIM14`

The branch-tree comparison inside `GIM_14` showed:

- `123` files present in `origin/main` but absent from `origin/GIM14`
- `54` files present in `origin/GIM14` but absent from `origin/main`

In practice, the missing `origin/main` surface was dominated by the entire `GIM_13` orchestration layer plus its tests, cases, calibration cases, and reporting assets.

## 2. What Was Missing In GIM14

Before the local restore, `GIM_14` had:

- the unified world core under [gim/core](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core)
- the data pipeline under [data/agent_state_pipeline](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/data/agent_state_pipeline)
- the compact `21`-actor runtime state under [data/agent_states.csv](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/data/agent_states.csv)
- only smoke tests in [tests/test_smoke.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/tests/test_smoke.py)

It did not have the `GIM_13` operational layer:

- scenario compilation
- question answering
- policy-game execution
- `SimBridge`
- crisis dashboards
- analytical briefing
- equilibrium tooling
- geo-calibration tables
- packaged cases and operational calibration cases

## 3. What Was Restored Locally

The following modules were restored into [gim](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim):

- [runtime.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/runtime.py)
- [scenario_compiler.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/scenario_compiler.py)
- [scenario_library.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/scenario_library.py)
- [types.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/types.py)
- [crisis_metrics.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/crisis_metrics.py)
- [game_runner.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/game_runner.py)
- [sim_bridge.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/sim_bridge.py)
- [compiled_policy.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/compiled_policy.py)
- [dashboard.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/dashboard.py)
- [briefing.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/briefing.py)
- [console_app.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/console_app.py)
- [calibration.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/calibration.py)
- [calibration_validator.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/calibration_validator.py)
- [geo_calibration.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/geo_calibration.py)
- [game_theory/](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/game_theory)
- [historical_backtest.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/historical_backtest.py)
- [decarb_sensitivity.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/decarb_sensitivity.py)
- [gim/core/calibration_params.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/calibration_params.py)
- [gim/core/state_artifact.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/state_artifact.py)
- [gim/core/country_params.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/country_params.py)

Compatibility inputs were also restored:

- [misc/data/agent_states_gim13.csv](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/misc/data/agent_states_gim13.csv)
- [misc/data/agent_states_gim13.artifacts.json](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/misc/data/agent_states_gim13.artifacts.json)
- [misc/cases/maritime_pressure_game.json](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/misc/cases/maritime_pressure_game.json)
- [misc/calibration_cases/operational_v1](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/misc/calibration_cases/operational_v1)
- [misc/assets/credit_map](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/misc/assets/credit_map)
- [misc/calibration/refresh_state_artifact_manifest.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/misc/calibration/refresh_state_artifact_manifest.py)
- [misc/calibration/refresh_historical_backtest_fixtures.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/misc/calibration/refresh_historical_backtest_fixtures.py)

## 4. Integration Adjustments

The restored layer was not copied blindly. The following integration changes were required:

- runtime imports were switched from vendored `gim_11_1` to [gim/core](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core)
- [gim/core/simulation.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/simulation.py) was extended with:
  - `policy_progress`
  - async-policy detection via `__gim_async_policy__`
  - memory-summary delivery to non-LLM policy functions
- [gim/__main__.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/__main__.py) was made hybrid:
  - `python -m gim` keeps the world-simulation behavior
  - `python -m gim world` also routes to the world simulator
  - `python -m gim question|game|metrics|console|brief|calibrate` routes to the restored orchestration layer

## 5. Validation

Local validation completed successfully:

- `python3 -m unittest tests.test_gim_13_mvp tests.test_sim_bridge tests.test_dashboard tests.test_briefing -v`
- `python3 -m unittest tests.test_dashboard tests.test_briefing tests.test_crisis_metrics tests.test_geo_calibration tests.test_equilibrium tests.test_case_builder tests.test_compiled_policy -v`
- `python3 -m unittest tests.test_state_artifact_binding tests.test_state_artifact_manifest tests.test_state_csv_contract -v`
- `python3 -m unittest tests.test_calibration_baseline tests.test_climate_forcing tests.test_country_params -v`
- `python3 -m unittest tests.test_historical_backtest tests.test_decarb_sensitivity tests.test_calibration -v`
- `python3 -m unittest discover -s tests -v`
- `python3 -m gim`
- `python3 -m gim question --question "Will war start between the United States and Iran?" --actors "United States" Iran --dashboard --brief --background-policy simple`
- `python3 -m gim calibrate --runs 1`

Current result:

- full local suite: `85 tests`, `OK`, `3 skipped`
- world CLI: passes
- scenario/game/reporting CLI: passes
- historical backtest: passes
- decarb sensitivity: passes
- artifact manifest and state contract tests: pass
- operational calibration suite: `7/7` cases passed

## 6. Remaining Gaps

`GIM_14` now covers the main `GIM_13` operational and calibration surface locally.

Still pending if full parity is required:

- replace transitional naming like `agent_states_gim13` where that is no longer semantically correct
- decide whether any remaining refresh helpers should move from `misc/calibration` into a more stable public tooling surface

## 7. Recommended Next Step

The next safe step is to work only inside [GIM_14](/Users/theclimateguy/Documents/jupyter_lab/GIM_14) and treat [GIM_13](/Users/theclimateguy/Documents/jupyter_lab/GIM_13) as the comparison baseline, not as the active development line.
