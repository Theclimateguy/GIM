# GIM18 Calibration Reference

> **Updated post-T1.3b/Phase-4:** `HEAT_CAP_SURFACE = 8.0`, `OCEAN_EXCHANGE = 1.0`, `ECS_DEFAULT = 3.0` (joint multi-window climate recalibration). New blocks since: labour market (Phillips+Okun), Taylor-rule monetary policy, multi-GHG non-CO2 forcing, AR(1) temperature variability. The authoritative source of truth is `gim/core/calibration_params.py` + `data/parameter_priors.csv`; see docs/LABOR_MARKET.md, MULTI_GHG_FORCING.md, SCENARIO_ALIGNMENT.md, DAMAGE_FUNCTION.md.

This file is the current calibration ledger for the code in this repository.

It documents:

- which calibration surfaces are active
- which values are currently authoritative
- how to reproduce the checks used in regression

## 1. Active Calibration Surfaces

| Surface | Primary files | Purpose |
| --- | --- | --- |
| Parameter registry | `gim/core/calibration_params.py` | Single place for model constants and provenance tags |
| Manifest-bound artifacts | `gim/core/state_artifact.py`, `data/agent_states_operational.artifacts.json` | Locks state-derived climate coefficients to the compiled operational state |
| Historical backtest | `gim/historical_backtest.py` | GDP/CO2/temperature replay over `2015-2023` |
| Rolling walk-forward backtest | `gim/rolling_backtest.py`, `calibration/run_rolling_origin_backtest.py` | Origin windows + stepwise recalibration + out-of-sample validation (`2015->2023`) |
| Decarb sensitivity | `gim/decarb_sensitivity.py` | Compares active structural decarb rate against observed/alternative candidates |
| Geopolitical calibration | `gim/geo_calibration.py`, `gim/calibration_validator.py` | Outcome/action/shift weight priors and sanity guards |
| Operational suite | `gim/calibration.py`, `calibration/cases/operational_v1` | Regression suite for crisis and control cases |
| Near-miss suite | `gim/calibration.py`, `calibration/cases/operational_v2` | Historical near-miss discrimination suite |
| Outcome sensitivity sweep | `gim/sensitivity_sweep.py`, `calibration/sensitivity_sweep.py` | Weight perturbation sensitivity report |
| Crisis persistence search | `calibration/calibrate_crisis_persistence.py` | Debt/regime crisis persistence tuning |

## 2. Authoritative Calibration Values

### 2.1 Artifact-bound climate coefficients

Source: `data/agent_states_operational.artifacts.json`

- `EMISSIONS_SCALE = 0.9755424434247171`
- `DECARB_RATE_STRUCTURAL = 0.052`
- manifest observed decarb reference:
  - `rate = 0.016025082589816386`
  - `start_year = 2000`
  - `end_year = 2023`

Rule: these values are loaded through `ACTIVE_STATE_ARTIFACT` and must be changed only via refresh scripts, not by direct hand-editing.

### 2.1b Release baseline defaults (v17.0 current; carried from the GIM16 baseline)

Source: rolling walk-forward Stage B/C artifacts

- `TFP_RD_SHARE_SENS = 0.300000`
- `GAMMA_ENERGY = 0.042000`
- `HEAT_CAP_SURFACE = 8.000000`
- `DECARB_RATE_STRUCTURAL = 0.052000` (kept artifact-bound from the operational manifest)

Rule: release `15.5` retains the hybrid baseline introduced in `15.1`: macro sensitivity and heat capacity use rolling-selected values, while structural decarb remains manifest-bound to preserve historical CO2 fit.

### 2.2 Climate/macro tuned parameters

Source: `gim/core/calibration_params.py`

- `GAMMA_ENERGY = 0.042` (`[BACKTEST]`)
- `TFP_RD_SHARE_SENS = 0.30` (`[BACKTEST]`)
- `HEAT_CAP_SURFACE = 8.0` (`[BACKTEST]`)
- `TEMP_NATURAL_VARIABILITY_SIGMA = 0.08` (`[BACKTEST]`)
- `TEMP_BACKTEST_ENSEMBLE_SIZE = 8` (`[BACKTEST]`)

`DECARB_RATE_STRUCTURAL` is intentionally a compound parameter today (artifact-bound residual). The empirical intensity decline reference is stored separately as `DECARB_RATE_OBSERVED_REFERENCE`.

### 2.3 Crisis persistence tuned parameters

Source: `gim/core/calibration_params.py`, provenance in `calibration/crisis_persistence_calibration.json`

- `DEBT_CRISIS_PERSIST_GDP_MULT = 0.965`
- `DEBT_CRISIS_PERSIST_TRUST_HIT = 0.025`
- `DEBT_CRISIS_PERSIST_TENSION_HIT = 0.02`
- `DEBT_CRISIS_EXIT_THRESHOLD = 0.70`
- `DEBT_CRISIS_EXIT_RATE = 0.08`
- `DEBT_CRISIS_MAX_YEARS = 6`
- `FX_CRISIS_EXTERNAL_DEBT_THRESHOLD = 0.50`
- `FX_CRISIS_CURRENT_ACCOUNT_DEFICIT_THRESHOLD = -0.04`
- `FX_CRISIS_RESERVE_MONTHS_THRESHOLD = 3.0`
- `FX_CRISIS_GDP_MULT = 0.85`
- `FX_CRISIS_RECOVERY_RESERVE_MONTHS = 3.0`
- `REGIME_CRISIS_PERSIST_GDP_MULT = 0.96`
- `REGIME_CRISIS_PERSIST_CAPITAL_MULT = 0.975`
- `REGIME_CRISIS_MAX_YEARS = 5`

## 3. Regression Baselines

### 3.1 Historical backtest

Bundled fixture baseline (`tests/fixtures/historical_backtest_baseline.json`), **17.3.0
development-structured recalibration** (re-pinned to the recalibrated headline):

- GDP RMSE: `0.62061758080248`
- global CO2 RMSE: `0.9326386833407672`
- temperature RMSE: `0.13500704173336117`
- temperature bias: `0.016279130918871433`

Current golden regression target (`tests/test_historical_backtest.py`):

- GDP RMSE `0.621 ± 0.01`
- global CO2 RMSE `0.933 ± 0.01`
- temperature RMSE `0.135 ± 0.01`

**Calibration history.** The objective + fully-closed economic core (nested-CES production +
cost-minimizing energy demand + resource & capital-market clearing + full SFC bank balance sheet)
first improved the fit vs the prior Cobb-Douglas golden (`1.026 / 1.606 / 0.134`) to `0.590 / 1.146 /
0.135`. The **17.3.0** recalibration then corrected a broken 2015-state capital init (~0.23× → ~3.0×
GDP, an error the legacy decarb rate 0.052 was silently cancelling), re-based the observed GDP series
to real-PPP growth (`NY.GDP.MKTP.PP.KD`), and added two development-structured mechanisms — TFP
conditional convergence (`TFP_CONVERGENCE_SENS = 0.0093`) and development-dependent decarbonisation
(`DECARB_RATE_STRUCTURAL` re-centred to `0.016`). Net effect on the golden: GDP 0.590→**0.621**, CO2
1.146→**0.933**, temperature ~unchanged. The capital-init fix lifts both production functions
equally, so the nested-CES advantage now shows in emissions (CO2 0.93 vs Cobb-Douglas ~1.87) rather
than in GDP. Emissions remain re-anchored via `NESTED_CES_EMISSIONS_NORM` (1.056) with the
data-derived `EMISSIONS_SCALE` (0.9755) artifact-bound; capital-clearing sensitivity 0.3.
Deep-uncertainty climate/risk channels remain ensemble-only (off in the headline).

### 3.2 Operational suites

Primary suite (`operational_v1`):

- cases: `11`
- includes `4` stable status-quo controls
- test expectation: suite stays green on current baseline (`tests/test_calibration.py`)

Near-miss suite (`operational_v2`):

- cases: `5` (YAML definitions)
- test expectation: `5/5` pass with fixed top outcomes
  - `argentina_default_2001 -> internal_destabilization`
  - `brazil_lula_crisis_2002 -> negotiated_deescalation`
  - `france_gilets_jaunes_2018 -> status_quo`
  - `south_korea_imf_1997 -> negotiated_deescalation`
  - `turkey_fx_crisis_2018 -> internal_destabilization`

Sensitivity sweep (`operational_v2`):

- defaults to suite discriminating weights when present
- test expectation: at least `6` entries flagged `high` (`tests/test_sensitivity_sweep.py`)

### 3.3 Rolling walk-forward (`2015->2023`)

Artifacts:

- `results/backtest/rolling_pairwise_2015_2023/rolling_backtest_stepwise.json` (original)
- `results/backtest/stage_bc_block4_2015_2023/stage_bc_block4.json` (original)
- `results/backtest/rolling_pairwise_2015_2023_reswitch_final_2026-03-17/rolling_backtest_stepwise.json` (post-switch re-check)
- `results/backtest/stage_bc_block4_2015_2023_reswitch_final_2026-03-17/stage_bc_block4.json` (post-switch re-check)

Post-switch one-step mean validation metrics (`2015->2016 ... 2022->2023`):

- GDP RMSE: `0.305`
- global CO2 RMSE: `1.029`
- temperature RMSE: `0.075` (pairwise) / `0.078` (block4)

Post-switch Stage B/C block-4 robust candidate (reference only; not fully promoted to defaults):

- `TFP_RD_SHARE_SENS = 0.180000`
- `GAMMA_ENERGY = 0.025200`
- `DECARB_RATE_STRUCTURAL = 0.031200`
- `HEAT_CAP_SURFACE = 8.000000`

## 4. Refresh and Rebuild Commands

Manifest refresh:

```bash
python3 calibration/refresh_state_artifact_manifest.py
```

Historical fixture refresh:

```bash
python3 calibration/refresh_historical_backtest_fixtures.py
python3 calibration/refresh_historical_backtest_baseline.py
```

Focused calibration helpers:

```bash
python3 calibration/calibrate_decarb_rate.py
python3 calibration/calibrate_gamma_energy.py
python3 calibration/calibrate_gamma_cross_section.py
python3 calibration/calibrate_tfp_rd_share_sens.py
python3 calibration/calibrate_heat_cap_surface.py
python3 calibration/calibrate_temperature_variability.py
python3 calibration/calibrate_crisis_persistence.py
python3 calibration/run_rolling_origin_backtest.py --stage pairwise --output-dir results/backtest/rolling_pairwise_2015_2023
python3 calibration/run_rolling_origin_backtest.py --stage block4 --output-dir results/backtest/stage_bc_block4_2015_2023
```

## 5. Validation Commands

```bash
python3 -m unittest tests.test_historical_backtest -v
python3 -m unittest tests.test_decarb_sensitivity -v
python3 -m unittest tests.test_calibration -v
python3 -m unittest tests.test_crisis_persistence -v
python3 -m unittest tests.test_sensitivity_sweep -v
```

CLI calibration run:

```bash
python3 -m gim calibrate --suite operational_v1
python3 -m gim calibrate --suite operational_v2
```

Sensitivity report generation:

```bash
python3 calibration/sensitivity_sweep.py --suite operational_v1 --out calibration/geo_sensitivity_operational_v1.json
python3 calibration/sensitivity_sweep.py --suite operational_v2
```

## 6. Guardrails

- Treat `EMISSIONS_SCALE` and `DECARB_RATE_STRUCTURAL` as manifest-bound artifacts.
- Keep crisis persistence parameters synchronized with `calibration/crisis_persistence_calibration.json`.
- If refresh scripts change baseline fixtures, update tests and this file in the same commit.
