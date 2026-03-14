# GIM13 Calibration Reference

This document records what the repository is currently calibrated to, which data sources were used, how the calibration enters the code, and which items are still only guarded by priors or sensitivity checks.

Use this file as the calibration ledger.
Use [CALIBRATION_LAYER.md](./CALIBRATION_LAYER.md) for the operational regression harness.

## 1. Calibration Map

The current calibration work is split across two parallel tracks:

1. world physics and macro dynamics
2. crisis and political scoring

Those two tracks share the same repo, but they use different targets, artifacts, and validation logic.

## 2. World Physics and Macro Calibration

| Block | Target / source | Method | Code / artifact | Current status |
| --- | --- | --- | --- | --- |
| Production elasticities (`ALPHA_CAPITAL`, `BETA_LABOR`) | PWT10 cross-country medians | Fixed structural prior where equation family matches Cobb-Douglas legacy block | `legacy/GIM_11_1/gim_11_1/calibration_params.py` | validated |
| Capital depreciation (`CAPITAL_DEPRECIATION`) | PWT10 | Fixed structural prior | `legacy/GIM_11_1/gim_11_1/calibration_params.py` | validated |
| Baseline fiscal shares (`TAX_RATE_BASE`, `SOCIAL_SPEND_BASE`, `MILITARY_SPEND_BASE`) | WDI23, SIPRI23 | World-average prior for fallback countries | `legacy/GIM_11_1/gim_11_1/calibration_params.py` | validated fallback |
| Country fiscal priors | WDI23 / OECD-style 2015-2022 averages | Country overrides for 20-country historical backtest surface | `legacy/GIM_11_1/gim_11_1/country_params.py` | active |
| Country savings priors | WDI23-style 2015-2022 averages | Stored as country priors, but currently applied only as a downward correction to `SAVINGS_BASE` | `legacy/GIM_11_1/gim_11_1/country_params.py` | partial |
| Carbon cycle pools / timescales | IPCC AR6 | Direct structural import into legacy 4-pool cycle | `legacy/GIM_11_1/gim_11_1/calibration_params.py` | validated |
| ECS and forcing coefficient | IPCC AR6 | Direct structural import | `legacy/GIM_11_1/gim_11_1/calibration_params.py` | validated |
| Non-CO2 forcing | IPCC AR6 aggregate forcing path | Calendar-anchored linear schedule from 2015 baseline | `legacy/GIM_11_1/gim_11_1/climate.py` | active |
| `EMISSIONS_SCALE` | Global Carbon Project 2015 fossil CO2 plus 2015 state fixture | Data-derived ratio `observed_global_co2 / sum(agent co2_annual_emissions)` during manifest refresh | `misc/data/agent_states_gim13.artifacts.json`, `misc/calibration/refresh_state_artifact_manifest.py` | active |
| Tech decarb channel (`TECH_DECARB_K`, resource efficiency) | Internal technology and efficiency state | Emissions intensity falls with `tech_level` and `resource.efficiency`; this is the technology and energy-efficiency channel | `legacy/GIM_11_1/gim_11_1/climate.py`, `tests/test_climate_forcing.py` | active prior |
| Structural transition channel (`DECARB_RATE_STRUCTURAL`, alias `DECARB_RATE`) | Legacy pipeline value, plus observed candidate from IEA-style prior | Manifest carries source metadata; base structural transition is time-driven and can be accelerated by `climate_policy` plus `fuel_tax_change` | `misc/data/agent_states_gim13.artifacts.json`, `legacy/GIM_11_1/gim_11_1/climate.py`, `GIM_13/decarb_sensitivity.py` | active legacy / observed rejected for now |

## 3. Crisis and Political Calibration

| Block | Target / source | Method | Code / artifact | Current status |
| --- | --- | --- | --- | --- |
| Outcome intercepts | Historical baseline evaluations and internal scenario fit | Centralized geo prior weights | `GIM_13/geo_calibration.py` | active |
| Outcome drivers (`OUTCOME_DRIVERS`) | AI-GPR-style geo priors, scenario sanity constraints | Weight table plus validator bounds | `GIM_13/geo_calibration.py`, `GIM_13/calibration_validator.py` | active |
| Action risk shifts (`ACTION_RISK_SHIFTS`) | AI-GPR-style priors, scenario deltas, validator thresholds | Weight table plus action-shift sanity suite | `GIM_13/geo_calibration.py`, `GIM_13/calibration_validator.py` | active |
| Geo weight export | Auditability of current priors | Flat CSV export of all weights | `misc/calibration/export_geo_weights.py`, `misc/calibration/geo_weights_v1.csv` | active |
| Geo regression fixture | Regression lock on scenario-level baseline evaluation | Snapshot fixture | `tests/fixtures/baseline_evaluation.json` | active |

This track is not yet tied to ICEWS/GDELT episode-level Bayesian updates. The current weights are centralized and testable, but still mostly prior-driven.

## 4. Historical Backtest Targets

The structural backtest currently replays 2015-2023 yearly dynamics on the legacy 20-country surface plus `Rest of World`.

Targets:

- GDP by country: World Bank WDI current USD series for 20 countries
- Global fossil CO2: Global Carbon Project annual totals
- Temperature anomaly: HadCRUT5 annual global series rebased to preindustrial
- Atmospheric CO2: NOAA annual mean concentration, used for seeding the start state

Main files:

- `GIM_13/historical_backtest.py`
- `tests/test_historical_backtest.py`
- `tests/fixtures/historical_backtest_observed.json`
- `tests/fixtures/historical_backtest_state_2015.csv`
- `tests/fixtures/historical_backtest_baseline.json`

Current baseline after 4a-4d:

- GDP RMSE: `1.266` trillion USD
- Global CO2 RMSE: `2.115` GtCO2
- Temperature RMSE: `0.105` C

Interpretation:

- GDP fit improved materially after country fiscal priors.
- CO2 fit improved materially after data-derived `EMISSIONS_SCALE`.
- Temperature fit remains limited by the simplicity of the current climate/emissions dynamics, not by a missing `non-CO2` constant alone.

## 4A. Decarbonization Semantics

The emissions block now uses two distinct decarbonization layers:

- tech and efficiency decarbonization: `TECH_DECARB_K` plus `resource.efficiency`
- structural energy transition: `DECARB_RATE_STRUCTURAL` with backward-compatible alias `DECARB_RATE`

Operational meaning:

- the tech channel captures cleaner production, process efficiency, and energy-efficiency improvements that come from higher `tech_level` or better resource efficiency
- the structural channel captures broader energy-system transition that accumulates over time
- policy tools can move the structural channel further: `climate_policy` and `fuel_tax_change` now increase the structural-transition multiplier on top of their immediate direct effects

Guardrails:

- `tests/test_climate_forcing.py` proves the tech channel still lowers emissions even if structural decarb is set to zero
- the same test file also proves policy tools accelerate the structural transition more at `t=10` than at `t=0`, which distinguishes long-run transition from one-step abatement

## 5. Manifest-Bound Climate Coefficients

The compiled state now has a hash-locked sidecar manifest:

- `misc/data/agent_states_gim13.artifacts.json`

That manifest currently stores:

- `emissions_scale`
- `decarb_rate`
- `rebuild_source`
- `emissions_reference`
- `decarb_reference`

Important distinction:

- `EMISSIONS_SCALE` is now refreshed from data.
- `DECARB_RATE_STRUCTURAL` is still an artifact-controlled active coefficient with explicit provenance metadata.
- `DECARB_RATE` remains only as a backward-compatible alias while the legacy layer is being renamed.

This means the repo already knows how to stamp an observed decarb prior into a manifest, but the default manifest intentionally does not do so yet because the current structural backtest rejects it.

## 6. Refresh Procedures

Refresh historical fixtures and primary artifact manifest:

```bash
python3 misc/calibration/refresh_historical_backtest_fixtures.py
```

Refresh only the primary artifact manifest:

```bash
python3 misc/calibration/refresh_state_artifact_manifest.py
```

Stamp an observed decarb prior into a manifest candidate for inspection:

```bash
python3 misc/calibration/refresh_state_artifact_manifest.py --decarb-source observed
```

Stamp a manual decarb candidate:

```bash
python3 misc/calibration/refresh_state_artifact_manifest.py --decarb-source manual --decarb-rate 0.030
```

## 7. Validation Suite

Operational regression harness:

```bash
python3 -m GIM_13 calibrate
```

Structural backtest and manifest checks:

```bash
python3 -m unittest \
  tests.test_climate_forcing \
  tests.test_historical_backtest \
  tests.test_state_artifact_binding \
  tests.test_state_artifact_manifest \
  tests.test_decarb_sensitivity -v
```

Full test suite:

```bash
python3 -m unittest discover -s tests -v
```

## 8. What Is Still Not Calibrated

The following areas are still prior-heavy or intentionally held back:

- `DECARB_RATE_STRUCTURAL`: observed prior is measured but not activated
- `STRUCTURAL_TRANSITION_POLICY_SENS` / `STRUCTURAL_TRANSITION_TAX_SENS`: policy acceleration layer is active but still prior-set
- `GAMMA_ENERGY`: still a structural prior
- `TFP_RD_SHARE_SENS`: still a structural prior
- `DAMAGE_QUAD_COEFF`: still a structural prior
- `CRISK_TEMP_SENSITIVITY`: still a structural prior
- `GINI_FISCAL_SENS`: still a structural prior
- geo priors are centralized and tested, but not yet updated from historical crisis episode likelihoods

## 9. Practical Reading Order

If someone needs to understand the current calibration state quickly, the recommended order is:

1. this file
2. [CALIBRATION_LAYER.md](./CALIBRATION_LAYER.md)
3. `tests/test_historical_backtest.py`
4. `tests/test_state_artifact_manifest.py`
5. `GIM_13/decarb_sensitivity.py`
