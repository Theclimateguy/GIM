# GIM_14 Calibration Reference

This document is the calibration ledger for the active `GIM_14` repo.

`GIM_14` now carries both calibration tracks inherited from `GIM_13`:

- world physics / macro calibration
- crisis / political calibration

## 1. Active Calibration Surfaces

| Surface | Location | Role | Status |
| --- | --- | --- | --- |
| Parameter registry | [gim/core/calibration_params.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/calibration_params.py) | Central source-tagged constants and calibration status | active |
| State artifact binding | [gim/core/state_artifact.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/state_artifact.py) | Hash-locked manifest for `EMISSIONS_SCALE` and `DECARB_RATE_STRUCTURAL` | active |
| Country macro priors | [gim/core/country_params.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/country_params.py) | Country-level savings, tax, and social-spend overrides | active |
| Climate block | [gim/core/climate.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/climate.py) | Carbon cycle, non-CO2 forcing, decarb channels, damages, extremes | active |
| Macro block | [gim/core/economy.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/economy.py) | Production, TFP, debt spreads, public finance | active |
| Social block | [gim/core/social.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/social.py) | Demography, trust, Gini, crises, migration | active |
| Metric block | [gim/core/metrics.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/metrics.py) | Debt stress, protest risk, TFP diffusion, reserve metrics | active |
| Historical backtest | [gim/historical_backtest.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/historical_backtest.py) | Structural replay over `2015-2023` against GDP / CO2 / temperature | active |
| Decarb sensitivity | [gim/decarb_sensitivity.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/decarb_sensitivity.py) | Compares alternative structural decarb priors | active |
| Geo calibration | [gim/geo_calibration.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/geo_calibration.py) | Bayesian-style calibrated geopolitical weights | active |
| Operational suite | [gim/calibration.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/calibration.py) | Scenario regression suite over packaged historical cases | active |
| Manifest refresh | [misc/calibration/refresh_state_artifact_manifest.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/misc/calibration/refresh_state_artifact_manifest.py) | Rebuilds the artifact manifest from observed references | active |
| Backtest refresh | [misc/calibration/refresh_historical_backtest_fixtures.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/misc/calibration/refresh_historical_backtest_fixtures.py) | Rebuilds bundled historical fixtures and stamps the primary manifest | active |

## 2. What Is Calibrated To What

### 2.1 World Physics / Macro

- GDP path:
  - target data: `20`-country annual GDP series from bundled WDI-derived fixture in [historical_backtest_observed.json](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/tests/fixtures/historical_backtest_observed.json)
  - runtime harness: [run_historical_backtest(...)](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/historical_backtest.py)
- Global CO2:
  - target data: GCP fossil CO2 series in the same observed fixture
  - artifact binding: `EMISSIONS_SCALE` comes from [agent_states_operational.artifacts.json](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/misc/data/agent_states_operational.artifacts.json), not a free knob
- Temperature:
  - target data: HadCRUT5-based preindustrial anomaly series in the same observed fixture
  - forcing logic: non-CO2 forcing schedule is calendar-based inside [climate.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/climate.py)
- Country fiscal structure:
  - target data: WDI/OECD-style country averages captured in [country_params.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/country_params.py)
  - current behavior: `tax` and `social spend` are country overrides; `savings` is capped as a conservative downward correction until the full econometric pass

### 2.2 Crisis / Political Layer

- Scenario regression suite:
  - packaged cases: [misc/calibration_cases/operational_v1](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/misc/calibration_cases/operational_v1)
  - runner: [run_operational_calibration(...)](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/calibration.py)
- Geo priors:
  - source tables: [gim/geo_calibration.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/geo_calibration.py)
  - validator: [gim/calibration_validator.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/calibration_validator.py)

## 3. Current Baselines

Current structural backtest baseline from [historical_backtest_baseline.json](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/tests/fixtures/historical_backtest_baseline.json):

- GDP RMSE: `1.266` trillion USD
- Global CO2 RMSE: `2.115` GtCO2
- Temperature RMSE: `0.105` C

Current decarb sensitivity result:

- active structural decarb rate: `0.049`
- observed comparison prior: `0.022`
- observed prior currently worsens CO2 fit materially and is not the active manifest rate

Current operational scenario suite:

- suite id: `operational_v1`
- packaged historical cases: `7`
- latest local run: `7/7` passed

## 4. Artifact Rules

Two coefficients remain artifact-bound:

- `EMISSIONS_SCALE`
- `DECARB_RATE_STRUCTURAL`

Their active values must come from [agent_states_operational.artifacts.json](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/misc/data/agent_states_operational.artifacts.json), and should only change through the refresh path, not by hand-editing [calibration_params.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/calibration_params.py).

## 5. Validation Commands

Structural backtest:

```bash
cd /Users/theclimateguy/Documents/jupyter_lab/GIM_14
python3 -m unittest tests.test_historical_backtest -v
```

Decarb sensitivity:

```bash
cd /Users/theclimateguy/Documents/jupyter_lab/GIM_14
python3 -m unittest tests.test_decarb_sensitivity -v
```

Operational suite:

```bash
cd /Users/theclimateguy/Documents/jupyter_lab/GIM_14
python3 -m gim calibrate --runs 1
```

Full local suite:

```bash
cd /Users/theclimateguy/Documents/jupyter_lab/GIM_14
python3 -m unittest discover -s tests -v
```

## 6. What Still Remains Prior-Heavy

The following are still active calibration priorities rather than finished empirical estimates:

- `GAMMA_ENERGY`
- `TFP_RD_SHARE_SENS`
- `GINI_FISCAL_SENS`
- `CRISK_TEMP_SENSITIVITY`
- `STRUCTURAL_TRANSITION_POLICY_SENS`
- `STRUCTURAL_TRANSITION_TAX_SENS`

Those are the right next targets for the next econometric or historical calibration passes inside `GIM_14`.
