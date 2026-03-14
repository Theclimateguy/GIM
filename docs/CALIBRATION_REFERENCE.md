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
| Outcome sensitivity sweep | [gim/sensitivity_sweep.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/sensitivity_sweep.py) | Perturbs outcome-layer weights and measures suite robustness | active |
| Manifest refresh | [misc/calibration/refresh_state_artifact_manifest.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/misc/calibration/refresh_state_artifact_manifest.py) | Rebuilds the artifact manifest from observed references | active |
| Backtest refresh | [misc/calibration/refresh_historical_backtest_fixtures.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/misc/calibration/refresh_historical_backtest_fixtures.py) | Rebuilds bundled historical fixtures and stamps the primary manifest | active |

## 2. What Is Calibrated To What

### 2.1 World Physics / Macro

- GDP path:
  - target data: `20`-country annual GDP series from bundled WDI-derived fixture in [historical_backtest_observed.json](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/tests/fixtures/historical_backtest_observed.json)
  - runtime harness: [run_historical_backtest(...)](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/historical_backtest.py)
- Global CO2:
  - target data: GCP fossil CO2 series in the same observed fixture
  - artifact binding: `EMISSIONS_SCALE` comes from [agent_states_operational.artifacts.json](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/data/agent_states_operational.artifacts.json), not a free knob
- Temperature:
  - target data: HadCRUT5-based preindustrial anomaly series in the same observed fixture
  - forcing logic: non-CO2 forcing schedule is calendar-based inside [climate.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/climate.py)
  - calibration mode: backtest now uses an `8`-member antithetic ensemble with annual temperature variability, because deterministic two-box physics alone cannot reproduce observed interannual GMST variance
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
- Chronic crisis state:
  - runtime logic: [gim/core/social.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/social.py)
  - visible outputs: [gim/core/metrics.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/metrics.py) and [gim/core/observation.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/observation.py)
  - current behavior: debt and regime crises now have explicit onset, persistence, recovery, and multi-year counters instead of one-step hidden flags

## 3. Current Baselines

Current structural backtest baseline from [historical_backtest_baseline.json](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/tests/fixtures/historical_backtest_baseline.json):

- GDP RMSE: `1.074` trillion USD
- Global CO2 RMSE: `1.632` GtCO2
- Temperature RMSE: `0.136` C
- Temperature bias: `-0.005` C
- Temperature interannual std: predicted `0.093` C vs observed `0.103` C
- Temperature ensemble: `8` members with `TEMP_NATURAL_VARIABILITY_SIGMA = 0.08`

Current decarb sensitivity result:

- active structural decarb rate: `0.052`
- observed fixture reference: `0.031241` over `2015-2023`
- the observed reference is stamped into the manifest, but the active residual structural rate stays above it because the current model splits decarbonization into tech/efficiency and structural-transition layers
- observed reference rates near `0.031-0.036` still worsen CO2 fit materially on the current structure and therefore are not yet safe as the active artifact rate

Current macro calibration result from the sequential `C1/C2/C3` pass:

- `DECARB_RATE_STRUCTURAL` is now artifact-bound at `0.052`, with observed reference metadata carried in the manifest
- `GAMMA_ENERGY` is now `0.07`; the historical replay is flat in time, so the active estimate comes from a separate bounded cross-sectional OLS on the bundled `2015` country slice
- the same cross-sectional pass gives an unconstrained `gamma ~= 0.084`, but the active value is clipped to the literature corridor `0.04-0.07`
- `TFP_RD_SHARE_SENS` moved from `2.0` to `0.5`, which materially improved both GDP and CO2 fit on the bundled `2015-2023` replay

Current temperature calibration result from the sequential `T1/T2/T3` pass:

- `historical_backtest.py` now seeds the deep ocean at `T_surface - 0.60` for the `2015` replay instead of the older ad hoc `-0.40`
- `HEAT_CAP_SURFACE` moved to `30.0`, which removed the old deterministic warming bias without freezing the surface box
- `TEMP_NATURAL_VARIABILITY_SIGMA = 0.08` is now active in the climate block, and the historical harness evaluates temperature on an antithetic ensemble rather than a single deterministic realization
- temperature calibration should now be read as a three-part target: mean bias, interannual std, and ensemble RMSE

Current operational scenario suite:

- suite id: `operational_v1`
- packaged historical cases: `11`
- suite mix: `7` crisis/historical stress cases + `4` stable negative-control cases
- latest local run: `11/11` passed

Current crisis-state calibration result:

- debt crises are now stateful and can persist for up to `8` years with repeated GDP / trust / tension damage
- regime crises are now stateful and can persist for up to `5` years with repeated GDP / capital damage
- crisis visibility is part of the observation contract through `competitive.crisis_flags` and the `CRISIS:` summary suffix
- credit-risk scoring now reads explicit crisis state from `RiskState` instead of transient private attributes

Current sensitivity-sweep result:

- the sweep now runs across `40` outcome-layer weights from `outcome_intercept`, `outcome_driver`, `outcome_link`, and `tail_risk`
- latest report: [geo_sensitivity_operational_v1.json](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/misc/calibration/geo_sensitivity_operational_v1.json)
- under `+-20%` perturbations, the current `11`-case suite produced no pass/fail flips
- the largest average-score movement on the present suite was `0.015`, concentrated in `direct_strike_exchange` conflict/military weights, `limited_proxy_escalation` conflict weight, and the `status_quo` intercept
- interpretation: the suite is now robust against small manual retuning, but several outcome weights are still only weakly identified and will need richer historical cases if we want sharper coefficient ranking

## 4. Artifact Rules

Two coefficients remain artifact-bound:

- `EMISSIONS_SCALE`
- `DECARB_RATE_STRUCTURAL`

Their active values must come from [agent_states_operational.artifacts.json](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/data/agent_states_operational.artifacts.json), and should only change through the refresh path, not by hand-editing [calibration_params.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/calibration_params.py).

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

Outcome sensitivity sweep:

```bash
cd /Users/theclimateguy/Documents/jupyter_lab/GIM_14
python3 misc/calibration/sensitivity_sweep.py --out misc/calibration/geo_sensitivity_operational_v1.json
```

Full local suite:

```bash
cd /Users/theclimateguy/Documents/jupyter_lab/GIM_14
python3 -m unittest discover -s tests -v
```

## 6. What Still Remains Prior-Heavy

The following are still active calibration priorities rather than finished empirical estimates:

- `GINI_FISCAL_SENS`
- `CRISK_TEMP_SENSITIVITY`
- `STRUCTURAL_TRANSITION_POLICY_SENS`
- `STRUCTURAL_TRANSITION_TAX_SENS`

`GAMMA_ENERGY` now has a cross-sectional working value rather than a pure prior, and `TFP_RD_SHARE_SENS` now has a backtest-calibrated working value, but both still deserve a fuller econometric pass rather than being treated as final.

Those are the right next targets for the next econometric or historical calibration passes inside `GIM_14`.
