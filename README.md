# GIM15

`GIM15` is the active repository for the yearly geopolitical-economy simulator and its scenario/game tooling.

The codebase combines:

- the core yearly world model (`gim/core/*`)
- the scenario/game/orchestration layer (`gim/__main__.py`, `gim/game_runner.py`, `gim/sim_bridge.py`)
- calibration harnesses and regression suites (`gim/calibration.py`, `gim/historical_backtest.py`, `misc/calibration/*`)

## What Runs Here

### 1. World simulation CLI

```bash
python3 -m gim
```

Equivalent explicit form:

```bash
python3 -m gim world
```

This path runs `gim/core/cli.py` and executes multi-year `step_world` simulation with optional CSV logging and credit-map rendering.

### 2. Orchestration commands

```bash
python3 -m gim question "Will Red Sea tensions escalate?"
python3 -m gim game --case misc/cases/maritime_pressure_game.json --dashboard
python3 -m gim metrics --agents Iran "United States"
python3 -m gim calibrate --suite operational_v1
python3 -m gim brief --from-json results/<run-id>/evaluation.json
python3 -m gim console
```

Supported subcommands are:

- `question`
- `game`
- `metrics`
- `calibrate`
- `brief`
- `console`

## Results Layout

Run artifacts are written to timestamped folders under `results/`:

- `results/world-YYYYMMDD-HHMMSS/`
- `results/question-YYYYMMDD-HHMMSS/`
- `results/game-YYYYMMDD-HHMMSS/`
- `results/metrics-YYYYMMDD-HHMMSS/`
- `results/brief-YYYYMMDD-HHMMSS/`

Each run writes a `run_manifest.json`. Depending on command flags, folders can include:

- `evaluation.json` / `game_result.json` / `metrics.json`
- `dashboard.html`
- `decision_brief.md`
- world/action/institution CSV logs
- credit map HTML

`calibrate` currently prints suite output to stdout and does not create a run folder.

## State Inputs and Defaults

There are two default-selection paths:

- world CLI (`python -m gim`):
  - uses `STATE_CSV` if set
  - otherwise `./agent_states.csv` if present
  - otherwise `data/agent_states.csv`
- orchestration layer (`question|game|metrics|calibrate|console`):
  - `gim.runtime.default_state_csv()` prefers `data/agent_states_operational.csv`
  - falls back to `data/agent_states.csv`

Key state artifacts:

- `data/agent_states.csv`
- `data/agent_states_operational.csv`
- `data/agent_states_operational.artifacts.json`

## Calibration Snapshot (Current Code/Fixtures)

Macro-climate:

- artifact-bound parameters come from `data/agent_states_operational.artifacts.json`
- active artifact values:
  - `EMISSIONS_SCALE = 0.9755424434247171`
  - `DECARB_RATE_STRUCTURAL = 0.052`
- observed decarb reference stamped in manifest:
  - `0.016025082589816386` (`2000-2023`)
- historical backtest golden targets used by tests:
  - GDP RMSE `~1.053`
  - global CO2 RMSE `~1.630`
  - temperature RMSE `~0.136`
- rolling walk-forward OOS artifacts:
  - `results/backtest/rolling_pairwise_2015_2023/rolling_backtest_stepwise.json`
  - `results/backtest/stage_bc_block4_2015_2023/stage_bc_block4.json`
  - `results/backtest/stage_bc_block4_2015_2023/oos_compare_baseline_vs_robust.json`
- v15 working baseline calibration (Stage B/C robust set):
  - `TFP_RD_SHARE_SENS = 0.300000`
  - `GAMMA_ENERGY = 0.042000`
  - `DECARB_RATE_STRUCTURAL = 0.031200`
  - `HEAT_CAP_SURFACE = 18.000000`

Crisis layer:

- `operational_v1`: 11 cases (includes stable `status_quo` controls)
- `operational_v2`: 5 near-miss cases (Brazil 2002, South Korea 1997, Turkey 2018, Argentina 2001, France 2018)
- regression expectations enforce:
  - `operational_v1` full pass under current tuned weights
  - `operational_v2` `5/5` pass and expected top outcomes
  - discriminating sensitivity sweep for `operational_v2` flags at least `6` high-sensitivity paths

## Repository Map

```text
GIM15/
├── gim/                    # installable package
│   ├── core/               # yearly simulator
│   ├── __main__.py         # orchestration CLI
│   └── results.py          # run artifact folder logic
├── data/                   # compiled states and manifest
├── docs/                   # active docs
├── misc/
│   ├── calibration/        # calibration scripts + artifacts
│   ├── calibration_cases/  # suite definitions
│   └── old_docs/           # archived superseded docs
├── scripts/                # helpers (pipeline, maps, long runs)
└── tests/                  # regression suite
```

Rolling backtest CLI:

```bash
python3 misc/calibration/run_rolling_origin_backtest.py --stage pairwise --output-dir results/backtest/rolling_pairwise_2015_2023
python3 misc/calibration/run_rolling_origin_backtest.py --stage block4 --output-dir results/backtest/stage_bc_block4_2015_2023
```

## Documentation Set

Active docs:

- `docs/MODEL_METHODOLOGY.md`
- `docs/OBJECTIVE_RELATIONSHIPS.md`
- `docs/CALIBRATION_REFERENCE.md`
- `docs/CALIBRATION_LAYER.md`
- `docs/SIMULATION_STEP_ORDER.md`
- `docs/agent_state_data_contract.md`
- `COMMAND_REFERENCE.md`

Archived/superseded docs:

- `misc/old_docs/`

## Test Commands

Full suite:

```bash
python3 -m unittest discover -s tests -v
```

Core calibration checks:

```bash
python3 -m unittest \
  tests.test_historical_backtest \
  tests.test_decarb_sensitivity \
  tests.test_calibration \
  tests.test_crisis_persistence \
  tests.test_sensitivity_sweep -v
```

## Version

Current package version: `15.0.0`
