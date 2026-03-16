# GIM_14 Command Reference v14.2.0

Operational CLI reference for `python -m gim`.

## Version

```bash
python -m gim --version
```

## Full Command List

- `python -m gim` (default world core mode)
- `python -m gim world`
- `python -m gim question`
- `python -m gim game`
- `python -m gim metrics`
- `python -m gim calibrate`
- `python -m gim brief`
- `python -m gim console`

## Quick Start Commands

```bash
# World simulation from a specific snapshot year
python -m gim world \
  --state-csv data/agent_states_operational_2026_calibrated.csv \
  --state-year 2026

# Question scenario (sim path)
python -m gim question \
  --question "How will the Iran-US conflict evolve in 2026?" \
  --actors Iran "United States" Israel \
  --state-csv data/agent_states_operational_2026_calibrated.csv \
  --state-year 2026 \
  --horizon 3 \
  --sim \
  --dashboard \
  --brief

# Game from a case file (sim path + equilibrium)
python -m gim game \
  --case misc/cases/maritime_pressure_game.json \
  --state-csv data/agent_states_operational_2026_calibrated.csv \
  --state-year 2026 \
  --horizon 3 \
  --sim \
  --equilibrium \
  --dashboard \
  --brief

# Crisis metrics snapshot
python -m gim metrics \
  --agents "United States" Iran Israel \
  --state-csv data/agent_states_operational_2026_calibrated.csv \
  --state-year 2026

# Calibration suite
python -m gim calibrate --suite operational_v1 --runs 3

# Rebuild brief from saved evaluation json
python -m gim brief --from-json results/<run-id>/evaluation.json --output decision_brief.md
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
python -m gim world --state-csv data/agent_states_operational.csv --state-year 2023
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
python -m gim metrics --agents Iran "United States" --json
```

### `calibrate`

Runs bundled historical calibration suite.

```bash
python -m gim calibrate --suite operational_v2 --runs 5 --horizon 2 --sim
```

### `brief`

Generates standalone markdown brief from existing evaluation artifact.

```bash
python -m gim brief --from-json results/<run-id>/evaluation.json --output decision_brief.md
```

### `console`

Interactive menu wrapper for question/game flows.

```bash
python -m gim console --state-csv data/agent_states_operational.csv --state-year 2026
```

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
