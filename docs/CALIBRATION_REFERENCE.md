# GIM15 Calibration Reference

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
| Rolling walk-forward backtest | `gim/rolling_backtest.py`, `misc/calibration/run_rolling_origin_backtest.py` | Origin windows + stepwise recalibration + out-of-sample validation (`2015->2023`) |
| Decarb sensitivity | `gim/decarb_sensitivity.py` | Compares active structural decarb rate against observed/alternative candidates |
| Geopolitical calibration | `gim/geo_calibration.py`, `gim/calibration_validator.py` | Outcome/action/shift weight priors and sanity guards |
| Operational suite | `gim/calibration.py`, `misc/calibration_cases/operational_v1` | Regression suite for crisis and control cases |
| Near-miss suite | `gim/calibration.py`, `misc/calibration_cases/operational_v2` | Historical near-miss discrimination suite |
| Outcome sensitivity sweep | `gim/sensitivity_sweep.py`, `misc/calibration/sensitivity_sweep.py` | Weight perturbation sensitivity report |
| Crisis persistence search | `misc/calibration/calibrate_crisis_persistence.py` | Debt/regime crisis persistence tuning |

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

### 2.1b Release baseline overrides (v15 working baseline)

Source: rolling walk-forward Stage B/C artifacts

- `TFP_RD_SHARE_SENS = 0.300000`
- `GAMMA_ENERGY = 0.042000`
- `DECARB_RATE_STRUCTURAL = 0.031200`
- `HEAT_CAP_SURFACE = 18.000000`

Rule: until the operational state artifact pipeline is restamped for v15, these are treated as release baseline calibration targets for validation and documentation.

### 2.2 Climate/macro tuned parameters

Source: `gim/core/calibration_params.py`

- `GAMMA_ENERGY = 0.07` (`[XSECTION]`)
- `TFP_RD_SHARE_SENS = 0.5` (`[BACKTEST]`)
- `HEAT_CAP_SURFACE = 30.0` (`[BACKTEST]`)
- `TEMP_NATURAL_VARIABILITY_SIGMA = 0.08` (`[BACKTEST]`)
- `TEMP_BACKTEST_ENSEMBLE_SIZE = 8` (`[BACKTEST]`)

`DECARB_RATE_STRUCTURAL` is intentionally a compound parameter today (artifact-bound residual). The empirical intensity decline reference is stored separately as `DECARB_RATE_OBSERVED_REFERENCE`.

### 2.3 Crisis persistence tuned parameters

Source: `gim/core/calibration_params.py`, provenance in `misc/calibration/crisis_persistence_calibration.json`

- `DEBT_CRISIS_PERSIST_GDP_MULT = 0.965`
- `DEBT_CRISIS_PERSIST_TRUST_HIT = 0.025`
- `DEBT_CRISIS_PERSIST_TENSION_HIT = 0.02`
- `DEBT_CRISIS_EXIT_THRESHOLD = 0.70`
- `DEBT_CRISIS_EXIT_RATE = 0.08`
- `DEBT_CRISIS_MAX_YEARS = 6`
- `REGIME_CRISIS_PERSIST_GDP_MULT = 0.96`
- `REGIME_CRISIS_PERSIST_CAPITAL_MULT = 0.975`
- `REGIME_CRISIS_MAX_YEARS = 5`

## 3. Regression Baselines

### 3.1 Historical backtest

Bundled fixture baseline (`tests/fixtures/historical_backtest_baseline.json`):

- GDP RMSE: `1.0743145212488447`
- global CO2 RMSE: `1.6319623035587012`
- temperature RMSE: `0.1362784326304756`
- temperature bias: `-0.005237543190706324`
- temperature std (predicted/observed): `0.09308561945984438 / 0.1030600790014023`
- ensemble size: `8`

Current golden regression target (`tests/test_historical_backtest.py`):

- GDP RMSE `1.053 ± 0.005`
- global CO2 RMSE `1.630 ± 0.005`
- temperature RMSE `0.136 ± 0.005`

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

- `results/backtest/rolling_pairwise_2015_2023/rolling_backtest_stepwise.json`
- `results/backtest/stage_bc_block4_2015_2023/stage_bc_block4.json`
- `results/backtest/stage_bc_block4_2015_2023/oos_compare_baseline_vs_robust.json`

Current Stage B/C block-4 robust candidate:

- `TFP_RD_SHARE_SENS = 0.300000`
- `GAMMA_ENERGY = 0.042000`
- `DECARB_RATE_STRUCTURAL = 0.031200`
- `HEAT_CAP_SURFACE = 18.000000`

Out-of-sample summary on one-step windows (`2015->2016 ... 2022->2023`):

- objective improved (`1.8357 -> 1.8125`, lower is better)
- GDP RMSE ~ unchanged (`0.3108 -> 0.3109`)
- global CO2 RMSE unchanged (`1.0286 -> 1.0286`)
- temperature RMSE improved (`0.0776 -> 0.0753`)

## 4. Refresh and Rebuild Commands

Manifest refresh:

```bash
python3 misc/calibration/refresh_state_artifact_manifest.py
```

Historical fixture refresh:

```bash
python3 misc/calibration/refresh_historical_backtest_fixtures.py
python3 misc/calibration/refresh_historical_backtest_baseline.py
```

Focused calibration helpers:

```bash
python3 misc/calibration/calibrate_decarb_rate.py
python3 misc/calibration/calibrate_gamma_energy.py
python3 misc/calibration/calibrate_gamma_cross_section.py
python3 misc/calibration/calibrate_tfp_rd_share_sens.py
python3 misc/calibration/calibrate_heat_cap_surface.py
python3 misc/calibration/calibrate_temperature_variability.py
python3 misc/calibration/calibrate_crisis_persistence.py
python3 misc/calibration/run_rolling_origin_backtest.py --stage pairwise --output-dir results/backtest/rolling_pairwise_2015_2023
python3 misc/calibration/run_rolling_origin_backtest.py --stage block4 --output-dir results/backtest/stage_bc_block4_2015_2023
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
python3 misc/calibration/sensitivity_sweep.py --suite operational_v1 --out misc/calibration/geo_sensitivity_operational_v1.json
python3 misc/calibration/sensitivity_sweep.py --suite operational_v2
```

## 6. Guardrails

- Treat `EMISSIONS_SCALE` and `DECARB_RATE_STRUCTURAL` as manifest-bound artifacts.
- Keep crisis persistence parameters synchronized with `misc/calibration/crisis_persistence_calibration.json`.
- If refresh scripts change baseline fixtures, update tests and this file in the same commit.
