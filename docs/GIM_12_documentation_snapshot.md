# GIM_12 Unified Documentation

This document is the single merged documentation for `GIM_12` and its legacy compatibility core behavior.

## Overview

`GIM_12` is the active production layout. The simulation core remains the `gim_11_1` package, now sourced from:
- `legacy/GIM_11_1/gim_11_1/`

Main entrypoints in `GIM_12/`:
- `GIM_12.py` (wrapper)
- `scripts/run_10y_llm.sh` (default 10-year LLM run)
- `credit_map_leaflet.py` (offline HTML map from final-year credit ratings)

## Repository Layout

- `GIM_12/` - active runtime scripts, configs, docs, and map tooling.
- `legacy/GIM_11_1/` - legacy compatibility core package and archived wrapper/docs.
- `legacy/V10_3_prod/` - older model generation.

## Setup

From repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
```

Optional dependencies:

```bash
pip install requests
pip install matplotlib
```

## Run Commands

### 1. Default production run (LLM, 10 years)

```bash
cd GIM_12
export DEEPSEEK_API_KEY="..."
./scripts/run_10y_llm.sh
```

### 2. Deterministic baseline (no LLM)

```bash
PYTHONPATH=legacy/GIM_11_1 POLICY_MODE=simple SIM_YEARS=5 SIM_SEED=7 python3 -m gim_11_1
```

### 3. Growth-seeking deterministic baseline (no LLM)

```bash
PYTHONPATH=legacy/GIM_11_1 POLICY_MODE=growth SIM_YEARS=5 SIM_SEED=7 python3 -m gim_11_1
```

### 4. Diagnostic run without extreme events

```bash
PYTHONPATH=legacy/GIM_11_1 POLICY_MODE=simple SIM_YEARS=5 SIM_SEED=7 DISABLE_EXTREME_EVENTS=1 python3 -m gim_11_1
```

### 5. Wrapper entrypoint

```bash
python3 GIM_12/GIM_12.py
```

## Simulation Flow (Yearly)

1. Update political state.
2. Update global institutions and generate reports.
3. Build agent observations.
4. Generate actions (simple, growth, LLM, or auto).
5. Resolve sanctions and trade barriers from policy intents.
6. Apply geopolitics/security effects.
7. Apply domestic actions and trade deals.
8. Enforce global net-exports balance.
9. Update resources and global prices.
10. Update climate and extreme events.
11. Update economy and public finance.
12. Update social state, risks, metrics, and memory.
13. Compute next-year credit rating and advance time.

## Inputs and Outputs

Input:
- `agent_states.csv` (or `STATE_CSV`)

Outputs (when `SAVE_CSV_LOGS=1`):
- `logs/GIM_12_<timestamp>_t0-tN.csv`
- `logs/GIM_12_<timestamp>_actions.csv`
- `logs/GIM_12_<timestamp>_institutions.csv`
- `logs/GIM_12_<timestamp>_t0-tN_credit_map.html` (if `GENERATE_CREDIT_MAP=1`)

## Credit Rating (Next-Year)

- Range: `1..26` (`26` is worst/default risk tier)
- Zones:
  - Green: `1..12`
  - Yellow: `13..20`
  - Red: `21..26`

Implementation and methodology:
- `legacy/GIM_11_1/gim_11_1/credit_rating.py`
- `GIM_12/credit_rating_methodology.md`

## Main Environment Variables

- `STATE_CSV` default `agent_states.csv`
- `MAX_COUNTRIES` default `100`
- `SIM_YEARS` default `10` in `run_10y_llm.sh`
- `SIM_SEED` reproducibility seed
- `POLICY_MODE` = `llm|simple|growth|auto`
- `LLM_MAX_CONCURRENCY` default `12`
- `LLM_BATCH_SIZE` default `20`
- `LLM_TIMEOUT_SEC` default `120`
- `LLM_MAX_RETRIES` default `2`
- `LLM_RETRY_BACKOFF_SEC` default `2.0`
- `DEEPSEEK_API_KEY` required for `POLICY_MODE=llm`
- `DISABLE_EXTREME_EVENTS=1` disable stochastic climate shocks
- `VERBOSE_COUNTRY_DETAILS=0` compact console output
- `USE_SIMPLE_POLICIES=1` hard-disable LLM
- `NO_LLM=1` hard-disable LLM
- `SAVE_CSV_LOGS` default `1`
- `GENERATE_CREDIT_MAP` default `1`

## Core Module Map (Compatibility Core)

- `core.py`: data structures, constants, shared types
- `world_factory.py`: world initialization from CSV
- `observation.py`: observation builder
- `policy.py`: simple/growth/LLM policy generation
- `actions.py`: domestic policy and trade execution
- `geopolitics.py`: sanctions and security interactions
- `political_dynamics.py`: endogenous political changes and relation updates
- `institutions.py`: global institution coordination and reporting
- `resources.py`: stocks, flows, and global resource prices
- `climate.py`: emissions, carbon cycle, forcing, temperature, extreme events
- `economy.py`: production, capital accumulation, public finance
- `social.py`: social tension, legitimacy, debt-crisis effects
- `metrics.py`: comparative/risk metrics
- `memory.py`: agent memory updates
- `simulation.py`: per-step and multi-year loop
- `logging_utils.py`: run IDs and CSV logging
- `cli.py`: command-line runtime entry

## Programmatic Usage

```python
import gim_11_1 as m

world = m.make_world_from_csv('agent_states.csv')
policies = m.make_policy_map(world.agents.keys(), mode='simple')

for _ in range(5):
    world = m.step_world(world, policies)

print(world.time)
```

If the package is not installed globally, run with:

```bash
PYTHONPATH=legacy/GIM_11_1 python3 your_script.py
```

## Additional Notes

- Only countries present in input CSV are simulated.
- Rows after `MAX_COUNTRIES` are ignored.
- `Rest of World` may be simulated but is excluded from map coloring.
- Offline map generation uses local assets in `GIM_12/data` and `GIM_12/vendor/leaflet`.
- For full equations/mechanics, see `GIM_12/methodic.md`.
