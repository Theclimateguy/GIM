# GIM15 Command Reference v15.1.0

Operational CLI reference for `python3 -m gim`.

## Version

```bash
python3 -m gim --version
```

## Full Command List

- `python3 -m gim` (default world core mode)
- `python3 -m gim world`
- `python3 -m gim question`
- `python3 -m gim game`
- `python3 -m gim metrics`
- `python3 -m gim calibrate`
- `python3 -m gim brief`
- `python3 -m gim console`
- `python3 -m gim ui`

## Quick Start Commands

```bash
# World simulation from a specific snapshot year
python3 -m gim world \
  --state-csv data/agent_states_operational_2026_calibrated.csv \
  --state-year 2026

# Question scenario (sim path)
python3 -m gim question \
  --question "How will the Iran-US conflict evolve in 2026?" \
  --actors Iran "United States" Israel \
  --state-csv data/agent_states_operational_2026_calibrated.csv \
  --state-year 2026 \
  --horizon 3 \
  --sim \
  --dashboard \
  --brief

# Game from a case file (sim path + equilibrium)
python3 -m gim game \
  --case misc/cases/maritime_pressure_game.json \
  --state-csv data/agent_states_operational_2026_calibrated.csv \
  --state-year 2026 \
  --horizon 3 \
  --sim \
  --equilibrium \
  --dashboard \
  --brief

# Crisis metrics snapshot
python3 -m gim metrics \
  --agents "United States" Iran Israel \
  --state-csv data/agent_states_operational_2026_calibrated.csv \
  --state-year 2026

# Calibration suite
python3 -m gim calibrate --suite operational_v1 --runs 3

# Rebuild brief from saved evaluation json
python3 -m gim brief --from-json results/<run-id>/evaluation.json --output decision_brief.md
```

## Common Runtime Flags

`question`, `game`, `metrics`, `calibrate`, `console`:

- `--state-csv <path>`
- `--state-year <year>`
- `--max-countries <n>`

Simulation path flags (`question`, `game`, `calibrate`):

- `--horizon <years>`
- `--sim` / `--no-sim`
- `--background-policy compiled-llm|llm|simple|growth`
- `--llm-refresh trigger|periodic|never`
- `--llm-refresh-years <n>`

Report flags (`question`, `game`):

- `--dashboard` / `--dashboard-output <name.html>`
- `--brief` / `--brief-output <name.md>`
- `--narrative`
- `--json`

## Command Details

### `world`

Runs core yearly simulator (`gim/core/cli.py`) directly.

```bash
python3 -m gim world --state-csv data/agent_states_operational.csv --state-year 2023
```

Environment variable equivalents: `STATE_CSV`, `STATE_YEAR`, `MAX_COUNTRIES`, `SIM_YEARS`, `POLICY_MODE`, `SAVE_CSV_LOGS`, `SIM_SEED`.

### `question`

Compiles and evaluates one question-driven scenario.

Key flags:

- question input: positional text or `--question`
- actor control: `--actors`, `--template`
- calendar control: `--base-year`, `--horizon-months`
- simulation control: `--horizon`, `--sim`/`--no-sim`
- outputs: `--dashboard`, `--brief`, `--json`, `--narrative`

### `game`

Runs policy game from:

- `--case <path>` or
- `--description "<text>"` (auto-build case; optional `--save-case`)

Adds game-specific flags:

- `--equilibrium`
- `--episodes`
- `--threshold`
- `--trust-alpha`
- `--max-combinations`

### `metrics`

Builds crisis metrics dashboard from current state snapshot.

```bash
python3 -m gim metrics --agents Iran "United States" --json
```

### `calibrate`

Runs bundled historical calibration suite.

```bash
python3 -m gim calibrate --suite operational_v2 --runs 5 --horizon 2 --sim
```

### `brief`

Generates standalone markdown brief from existing evaluation artifact.

```bash
python3 -m gim brief --from-json results/<run-id>/evaluation.json --output decision_brief.md
```

### `console`

Interactive menu wrapper for question/game flows.

```bash
python3 -m gim console --state-csv data/agent_states_operational.csv --state-year 2026
```

### `ui`

Launch local analytical web UI bound to this repository and local runtime.

```bash
python3 -m gim ui --host 127.0.0.1 --port 8090
```

Behavior:

- `Simulation Modes` builds real `python3 -m gim <command>` invocations from UI controls.
- actor selection is sourced from `data/agent_states_operational_2026_calibrated.csv`.
- leaving `Template` blank enables backend auto-detection.
- `Run chosen modes` starts a real local run and tracks progress against the phase pipeline.
- export buttons map to actual run artifacts and only enable when the artifact exists.
- `Analytics` reads the executed run's `evaluation.json`, `run_manifest.json`, and `decision_brief.md`.

Primary UI-backed endpoints:

- `GET /api/docs`
- `GET /api/state-csvs`
- `GET /api/actors`
- `POST /api/run`
- `GET /api/run/<id>/status`
- `GET /api/run/<id>/artifacts`
- `GET /api/run/<id>/analytics`
- `GET /api/analytics/latest`
- `GET /api/download?path=...`

## Artifacts and Paths

Each orchestration run writes to `results/<command>-YYYYMMDD-HHMMSS/` with `run_manifest.json`.

Typical files:

- `evaluation.json` (question)
- `game_result.json` (game)
- `metrics.json` (metrics)
- `dashboard.html` (when `--dashboard`)
- `decision_brief.md` (when `--brief`)
- `run_manifest.json` (all orchestration runs)

`--dashboard-output` and `--brief-output` set filenames inside the run folder.

## Year Semantics

- `state_year` is the calendar year represented by the loaded state CSV.
- Simulation horizon runs as `state_year + tau`.
- Scenario `display_year` can differ (via `--base-year`) and is shown in dashboard/brief.
