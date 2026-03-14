# GIM_14 Calibration Reference

This file carries the calibration context forward into `GIM_14`.

Important status note:

- `GIM_14` currently contains the active yearly simulation core and current data pipeline
- the richer calibration system built during the `GIM_13` workstream is not yet fully ported into this repo
- this document therefore plays two roles at once:
  - it records what calibration-relevant surfaces exist in `GIM_14` today
  - it preserves the calibration target state inherited from the `GIM_13` line so the next pass can continue without losing context

## 1. Current Calibration-Relevant Surfaces In GIM_14

| Surface | Location | Current role in GIM_14 | Status |
| --- | --- | --- | --- |
| Compiled runtime state | [data/agent_states.csv](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/data/agent_states.csv) | Active simulation input for world loading | active |
| Source-data pipeline | [data/agent_state_pipeline](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/data/agent_state_pipeline) | Raw and imputed panel data behind the compiled state | active |
| State data contract | [docs/agent_state_data_contract.md](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/docs/agent_state_data_contract.md) | Defines units, aggregation rules, and source expectations | active |
| Climate coefficients | [gim/core/climate.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/climate.py) | Active legacy climate and emissions logic | active, still hardcoded |
| Macro coefficients | [gim/core/economy.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/economy.py) | Active GDP, TFP, savings, and debt logic | active, still hardcoded |
| Credit methodology | [docs/credit_rating_methodology.md](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/docs/credit_rating_methodology.md) | Carried-forward sovereign-style rating logic | active |

## 2. What Is Already Implicitly Calibrated In This Repo

These are not yet wrapped in a dedicated calibration package, but they do encode empirical choices:

- `data/agent_states.csv` already embeds a compiled 2023 world state
- `data/agent_state_pipeline/generated/*.csv` embeds imputed WDI/WGI/ND-GAIN/Hofstede/FAOSTAT/WMD-derived source surfaces
- `world_factory.py` enforces the state CSV contract and unit bounds
- `climate.py` encodes hardcoded emissions and climate-response priors inherited from `GIM_11_1`
- `economy.py` encodes hardcoded Cobb-Douglas and TFP priors inherited from `GIM_11_1`

## 3. Calibration Knowledge Carried Forward From GIM_13

The previous `GIM_13` workstream had already developed a richer calibration understanding. That knowledge remains relevant for `GIM_14`, especially once we start porting the higher-level calibration harness again.

Key inherited conclusions:

- `EMISSIONS_SCALE` should be treated as a pipeline-bound or data-derived quantity rather than a free tuning knob
- decarbonization needs to be split conceptually into a technology/efficiency layer and a broader structural transition layer
- country-level fiscal priors materially improve macro backtest behavior
- historical backtesting against GDP, global CO2, and temperature is the right first objective measure before more advanced policy-layer calibration
- geo-political priors and crisis weights should remain a separate calibration track from the world-physics/macro track

## 4. GIM_13 Calibration Snapshot To Preserve

The last richer calibration line before this migration had the following shape:

- world physics and macro calibration
- crisis and political calibration
- historical backtest over 2015-2023
- data-derived emissions scaling
- explicit decarb sensitivity analysis
- country fiscal prior overrides

That stack is not yet executable inside `GIM_14`, but it is the intended calibration target state for future migration work.

## 5. Directly Relevant Files For The Next Port

When calibration work resumes, the most relevant `GIM_14` files will be:

- [gim/core/climate.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/climate.py)
- [gim/core/economy.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/economy.py)
- [gim/core/metrics.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/metrics.py)
- [data/agent_states.csv](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/data/agent_states.csv)
- [data/agent_state_pipeline/generated/actor_base_inputs.csv](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/data/agent_state_pipeline/generated/actor_base_inputs.csv)
- [docs/agent_state_data_contract.md](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/docs/agent_state_data_contract.md)

## 6. Known Gap Between Current GIM_14 And The Previous Calibration Stack

Not yet ported into this repository:

- historical backtest harness
- artifact manifest binding for climate coefficients
- calibration parameter registry
- country-prior helper module
- geo-calibration tables and validators
- `GIM_13` scenario/game scoring layer

## 7. Practical Reading Order

For the next calibration pass inside `GIM_14`, the recommended reading order is:

1. [README.md](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/README.md)
2. [docs/MIGRATION_NOTES.md](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/docs/MIGRATION_NOTES.md)
3. [docs/agent_state_data_contract.md](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/docs/agent_state_data_contract.md)
4. [gim/core/climate.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/climate.py)
5. [gim/core/economy.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/economy.py)
6. [CALIBRATION_LAYER.md](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/CALIBRATION_LAYER.md)

