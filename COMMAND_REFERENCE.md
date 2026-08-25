# GIM18 Command Reference v18.0.0

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
- `python3 -m gim hybrid`
- `python3 -m gim metrics`
- `python3 -m gim calibrate`
- `python3 -m gim brief`
- `python3 -m gim console`

The native app (`gim2/`, see below) has its own reproducible CLI, `python3 -m gim2`:

- `python3 -m gim2 ensemble` / `sensitivity` / `weak` / `scc` / `scenario` / `dose` / `answer` / `meta` / `engine`

## Quick Start Commands

```bash
# World simulation from a specific snapshot year
python3 -m gim world \
  --state-csv data/agent_states_operational.csv \
  --state-year 2026

# Question scenario (sim path)
python3 -m gim question \
  --question "How will the Iran-US conflict evolve in 2026?" \
  --actors Iran "United States" Israel \
  --state-csv data/agent_states_operational.csv \
  --state-year 2026 \
  --horizon 3 \
  --sim \
  --dashboard \
  --brief

# Game from a case file (sim path + equilibrium)
python3 -m gim game \
  --case scenarios/maritime_pressure_game.json \
  --state-csv data/agent_states_operational.csv \
  --state-year 2026 \
  --horizon 3 \
  --sim \
  --equilibrium \
  --dashboard \
  --brief

# Hybrid human + agent round
python3 -m gim hybrid \
  --tables "United States" \
  --intent "United States=Increase AI spending moderately." \
  --state-csv data/agent_states_operational.csv \
  --state-year 2026 \
  --round-years 4 \
  --background-policy simple \
  --dashboard \
  --brief

# Crisis metrics snapshot
python3 -m gim metrics \
  --agents "United States" Iran Israel \
  --state-csv data/agent_states_operational.csv \
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

Hybrid round flags (`hybrid`):

- `--tables <actor...>`
- `--intent ACTOR=TEXT` (repeatable) or `--intent-file <json>`
- `--mode ACTION|WHAT_IF`
- `--round-years <n>`
- `--ensemble-size <n>`
- `--seed <n>`
- `--background-policy compiled-llm|llm|simple|growth`
- `--llm-refresh trigger|periodic|never`
- `--llm-refresh-years <n>`
- `--dashboard`
- `--brief` / `--brief-output <name.md>`
- `--json`

`Game` tab in the local UI uses `hybrid` under the hood:

- one row per human-controlled table
- each row requires a distinct actor and natural-language intent
- UI forwards `DEEPSEEK_API_KEY` to the runtime when provided
- artifact panel exposes `dashboard.html`, `hybrid_report.md`, `evaluation.json`, `hybrid_result.json`, and policy/baseline CSV logs

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

### `hybrid`

Runs a mixed human/autopilot policy round on top of the same yearly `step_world` core.

Outputs include:

- `evaluation.json` with policy trajectory plus baseline trajectory
- `hybrid_result.json` with compiled intents, benchmark run and channel decomposition
- `hybrid_report.md` when `--brief`
- `dashboard.html` when `--dashboard`
- baseline/policy world, action and institution CSV logs
- `run_manifest.json` with exact round inputs and resolved artifact paths

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

### Native app (`gim2/`)

The graphical shell is the native macOS app **GIM2** (SwiftUI), not a web UI. Build and run:

```bash
gim2/app/freeze/freeze_engine.sh   # PyInstaller-freeze the engine (one-time; needs pyinstaller)
gim2/app/build_app.sh              # swift build -c release + assemble GIM2.app
open gim2/app/GIM2.app
```

The app talks to a deterministic Python engine sidecar (`python3 -m gim2 engine`, loopback HTTP+SSE,
schema `gim-engine/2`); every screen reports the equivalent `python3 -m gim2 …` CLI invocation for
reproducibility. Five areas: **Ассистент** (natural-language front end, tool-calling over the engine),
**Экспертный режим** (Сценарий / Ансамбли / Отклик / Чувствительность / Сигналы), **Сравнение**
(up to 3 runs vs. baseline + PDF export), **Документация**, **Валидация** (live backtest/AUC/Morris).
Persona archetypes (`gim/persona.py`) bias a country's compiled doctrine ("play as a country"); a
local LLM backend is available via `GIM_LLM_BACKEND=ollama` + `OLLAMA_MODEL`.

Engine bridge contract (endpoints, JSON shapes): [`gim2/docs/ENGINE_BRIDGE_CONTRACT_v2.md`](gim2/docs/ENGINE_BRIDGE_CONTRACT_v2.md).

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
