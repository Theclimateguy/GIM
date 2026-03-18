# GIM15

`GIM15` is the active repository for the yearly geopolitical-economy simulator and its scenario/game tooling.

The codebase combines:

- the core yearly world model (`gim/core/*`)
- the scenario/game/orchestration layer (`gim/__main__.py`, `gim/game_runner.py`, `gim/sim_bridge.py`)
- the local analytical workspace UI (`gim/ui_server.py`, `ui_prototype/gim15_dashboard_prototype.html`)
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
python3 -m gim ui --host 127.0.0.1 --port 8090
```

Supported subcommands are:

- `question`
- `game`
- `metrics`
- `calibrate`
- `brief`
- `console`
- `ui`

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

## Local Analytical Workspace

Launch the production local dashboard with:

```bash
python3 -m gim ui --host 127.0.0.1 --port 8090
```

The UI is bound directly to this repository and local model runtime:

- `Simulation Modes` builds real `python3 -m gim ...` runs from UI controls.
- actors are selected from `data/agent_states_operational_2026_calibrated.csv`
- template is optional; blank means backend auto-detect
- exports are tied to real run artifacts (`run_manifest.json`, `dashboard.html`, `decision_brief.md`, `evaluation.json`)
- `Analytics` renders run-specific outputs, not static placeholders

Current analytics layout:

- top summary block from `decision_brief.md` / narrative-derived brief
- scenario distribution and crisis criticality gauge
- grouped bar charts for GDP by actor, social tension by actor, and inflation / price stress
- normalized crisis scale cards with raw-unit notes
- separate `Outcome Distribution` and `Main Drivers` briefing panels

Implementation reference:

- `gim/ui_server.py`
- `ui_prototype/gim15_dashboard_prototype.html`
- `tests/test_ui_server.py`

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
  - GDP RMSE `~1.025`
  - global CO2 RMSE `~1.605`
  - temperature RMSE `~0.138`
- rolling walk-forward OOS artifacts:
  - `results/backtest/rolling_pairwise_2015_2023/rolling_backtest_stepwise.json`
  - `results/backtest/stage_bc_block4_2015_2023/stage_bc_block4.json`
  - `results/backtest/stage_bc_block4_2015_2023/oos_compare_baseline_vs_robust.json`
- v15 working baseline calibration (Stage B/C robust set):
  - `TFP_RD_SHARE_SENS = 0.300000`
  - `GAMMA_ENERGY = 0.042000`
  - `DECARB_RATE_STRUCTURAL = 0.052000` (artifact-bound operational manifest value)
  - `HEAT_CAP_SURFACE = 18.000000`
  - note: forcing `DECARB_RATE_STRUCTURAL = 0.031200` fails historical CO2 envelope in current release tests

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

Active docs index:

- `docs/README.md`
- `docs/UI_WORKSPACE.md`

Core runtime and contracts:

- `docs/MODEL_METHODOLOGY.md`
- `docs/GIM15_UNIFIED_MODEL_SPEC.md`
- `docs/CORE_TRANSITION_CONTRACT.md`
- `docs/SIMULATION_STEP_ORDER.md`
- `docs/MODEL_STATE_MAP.md`
- `docs/critical_field_registry.csv`
- `docs/state_registry.csv`

Calibration and validation:

- `docs/CALIBRATION_REFERENCE.md`
- `docs/CALIBRATION_LAYER.md`
- `docs/CRISIS_VALIDATION_PROTOCOL.md`
- `docs/PARAMETER_CHANGE_POLICY.md`

Data contract and objectives:

- `docs/agent_state_data_contract.md`
- `docs/OBJECTIVE_RELATIONSHIPS.md`
- `COMMAND_REFERENCE.md`

Archived/superseded docs:

- `docs/legacy/`
- `misc/old_docs/`

## Test Commands

Full suite:

```bash
python3 -m unittest discover -s tests -v
```

Release validation package (non-LLM by default):

```bash
./scripts/run_validation_package_v15.sh
```

Optional LLM package:

```bash
RUN_LLM=1 DEEPSEEK_API_KEY=... ./scripts/run_validation_package_v15.sh
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

Current package version: `15.1.0`
