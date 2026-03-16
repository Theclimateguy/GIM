# GIM_14 Command Reference v14.0.0

This file is the quick operational reference for the CLI.  
The full model logic, formulas, reporting contract, and data contract remain in [README.md](README.md).

## Version

```bash
python -m gim --version
```

## Core Commands

```bash
# Static scenario evaluation (no simulation)
python -m gim question "Will Red Sea tensions escalate?"

# Sim-path scenario with LLM agents from a 2026 state snapshot
python -m gim question \
  --question "Will war between the United States and Iran escalate?" \
  --actors "United States" Iran Israel \
  --state-csv data/agent_states_operational_2026_calibrated.csv \
  --state-year 2026 \
  --horizon 5 \
  --sim \
  --background-policy compiled-llm \
  --llm-refresh trigger \
  --dashboard \
  --brief

# Policy game from a case JSON file
python -m gim game \
  --case misc/cases/maritime_pressure_game.json \
  --state-csv data/agent_states_operational_2026_calibrated.csv \
  --state-year 2026 \
  --horizon 5 \
  --sim \
  --background-policy compiled-llm \
  --dashboard \
  --brief

# Policy game from free text (case is auto-generated via LLM then saved)
python -m gim game \
  --description "China imposes export controls and the United States responds with tariffs." \
  --save-case misc/local/cases/trade_case.json \
  --state-year 2026 \
  --dashboard

# Policy game with equilibrium analysis
python -m gim game \
  --case misc/cases/maritime_pressure_game.json \
  --equilibrium \
  --episodes 50 \
  --trust-alpha 0.5 \
  --dashboard \
  --brief

# Crisis metrics dashboard
python -m gim metrics --agents "United States" China Iran

# Historical calibration suite
python -m gim calibrate --runs 5 --horizon 3 --sim --background-policy compiled-llm

# Rebuild a Markdown brief from a saved evaluation JSON
python -m gim brief --from-json runs/<run_id>/evaluation.json --output decision_brief.md

# Interactive console
python -m gim console
```

---

## `world`

Purpose: run the raw yearly simulation core directly (no scenario layer).  
State is controlled via environment variables or CLI flags.

```bash
python -m gim world \
  --state-csv data/agent_states_operational_2026_calibrated.csv \
  --state-year 2026
```

Environment variable equivalents: `STATE_CSV`, `STATE_YEAR`, `SIM_YEARS`, `POLICY_MODE`, `SAVE_CSV_LOGS`, `SIM_SEED`.

---

## `question`

Purpose: compile one question-driven scenario and evaluate it.

Main flags:

| Flag | Default | Description |
|---|---|---|
| positional or `--question` | required | Question text |
| `--actors` | auto-inferred | Space-separated actor names |
| `--template` | auto-detected | Scenario template ID |
| `--base-year` | `state_year` | Override scenario base year |
| `--horizon-months` | `24` | Scenario horizon in months (used by static scorer) |
| `--state-csv` | `misc/data/agent_states_gim13.csv` | Path to compiled world state CSV |
| `--state-year` | `2023` | Calendar year the state CSV represents; sets simulation start as `t₀` |
| `--max-countries` | `100` | Limit number of agents loaded |
| `--horizon` | `0` | Years to simulate via `step_world`; `0` keeps static scorer |
| `--sim` | off | Enable sim path; requires `--horizon > 0` |
| `--no-sim` | off | Force static path even if `--horizon > 0` |
| `--background-policy` | `compiled-llm` | Autonomous policy mode for non-player countries: `compiled-llm\|llm\|simple\|growth` |
| `--llm-refresh` | `trigger` | LLM doctrine refresh cadence: `trigger\|periodic\|never` |
| `--llm-refresh-years` | `2` | Periodic refresh interval in years (used when `--llm-refresh periodic`) |
| `--dashboard` | off | Write `dashboard.html` to run artifacts directory |
| `--dashboard-output` | `dashboard.html` | Filename for the dashboard inside the run artifacts directory |
| `--brief` | off | Write `decision_brief.md` to run artifacts directory |
| `--brief-output` | `decision_brief.md` | Filename for the brief inside the run artifacts directory |
| `--json` | off | Print evaluation JSON to stdout |
| `--narrative` | off | Include extended narrative section in dashboard/brief |

Example:

```bash
python -m gim question \
  --question "How will the 2026 Iran war evolve?" \
  --actors "Iran" "United States" "Israel" "Saudi Arabia" "United Arab Emirates" \
  --state-csv data/agent_states_operational_2026_calibrated.csv \
  --state-year 2026 \
  --horizon 5 \
  --sim \
  --background-policy compiled-llm \
  --llm-refresh trigger \
  --dashboard \
  --dashboard-output iran_war_2026.html \
  --brief \
  --brief-output iran_war_2026_brief.md
```

---

## `game`

Purpose: run a policy game from case JSON or free text.

Inputs (mutually exclusive, one required):

- `--case <path>` — load an existing JSON case file
- `--description "<text>"` — build a case from free text via `case_builder.py`

Main flags:

| Flag | Default | Description |
|---|---|---|
| `--save-case` | none | Save auto-generated case JSON to this path |
| `--state-csv` | default state CSV | Path to compiled world state CSV |
| `--state-year` | `2023` | Calendar year the state CSV represents |
| `--max-countries` | `100` | Limit number of agents loaded |
| `--horizon` | `0` | Years to simulate; `0` keeps static scorer |
| `--sim` | off | Enable sim path; requires `--horizon > 0` |
| `--no-sim` | off | Force static path |
| `--background-policy` | `compiled-llm` | Non-player policy mode: `compiled-llm\|llm\|simple\|growth` |
| `--llm-refresh` | `trigger` | LLM doctrine refresh: `trigger\|periodic\|never` |
| `--llm-refresh-years` | `2` | Periodic refresh interval in years |
| `--equilibrium` | off | Run regret minimisation and trust-weighted CE on top of game matrix |
| `--episodes` | `50` | No-regret episode count for equilibrium search |
| `--threshold` | `0.02` | Convergence threshold on mean external regret |
| `--trust-alpha` | `0.5` | Interpolation between utilitarian (`0`) and trust-weighted (`1`) welfare |
| `--max-combinations` | `256` | Max strategy combinations; truncates to 3 actions/player above limit |
| `--dashboard` | off | Write dashboard HTML to run artifacts directory |
| `--dashboard-output` | `dashboard.html` | Dashboard filename inside run artifacts directory |
| `--brief` | off | Write Markdown brief to run artifacts directory |
| `--brief-output` | `decision_brief.md` | Brief filename inside run artifacts directory |
| `--json` | off | Print game result JSON to stdout |
| `--narrative` | off | Include extended narrative in dashboard/brief |

Example:

```bash
python -m gim game \
  --description "$(cat misc/local/cases/iran_war_game_2026.txt)" \
  --state-csv data/agent_states_operational_2026_calibrated.csv \
  --state-year 2026 \
  --horizon 5 \
  --sim \
  --background-policy compiled-llm \
  --llm-refresh trigger \
  --equilibrium \
  --save-case misc/local/cases/iran_war_game_2026_generated.json \
  --dashboard \
  --dashboard-output iran_war_game_2026.html \
  --brief \
  --brief-output iran_war_game_2026_brief.md
```

---

## `metrics`

Purpose: compute crisis metrics directly from the current world snapshot without scenario scoring.

Main flags:

| Flag | Default | Description |
|---|---|---|
| `--agents` | top 5 by GDP | Space-separated agent names |
| `--state-csv` | default state CSV | Path to compiled world state CSV |
| `--state-year` | `2023` | Calendar year the state CSV represents |
| `--json` | off | Print dashboard JSON to stdout |

Example:

```bash
python -m gim metrics \
  --agents "United States" Iran "Saudi Arabia" Israel "United Arab Emirates" \
  --state-csv data/agent_states_operational_2026_calibrated.csv \
  --state-year 2026
```

---

## `calibrate`

Purpose: run the bundled historical validation suite against the current model.

Main flags:

| Flag | Default | Description |
|---|---|---|
| `--suite` | default suite | Suite ID |
| `--runs` | `1` | Repetitions per case |
| `--horizon` | `0` | Years to simulate per run |
| `--sim` / `--no-sim` | off | Enable/force-off sim path |
| `--background-policy` | `compiled-llm` | Non-player policy mode |
| `--llm-refresh` | `trigger` | LLM doctrine refresh cadence |
| `--llm-refresh-years` | `2` | Periodic refresh interval |
| `--state-csv` | default state CSV | Path to compiled world state CSV |
| `--state-year` | `2023` | Calendar year the state CSV represents |
| `--json` | off | Print calibration result JSON to stdout |

Example:

```bash
python -m gim calibrate \
  --runs 3 \
  --horizon 2 \
  --sim \
  --background-policy compiled-llm
```

---

## `brief`

Purpose: rebuild a standalone Markdown brief from a saved `evaluation.json` artifact.

```bash
python -m gim brief \
  --from-json runs/<run_id>/evaluation.json \
  --output decision_brief.md
```

---

## `console`

Purpose: interactive menu over `question` and `game`.

```bash
python -m gim console \
  --state-csv data/agent_states_operational_2026_calibrated.csv \
  --state-year 2026
```

---

## Output Artifacts

All artifacts are written to an auto-created run directory `runs/<run_id>/`.  
The actual paths are printed to stdout on completion.

| Artifact | Flag | Description |
|---|---|---|
| `dashboard.html` | `--dashboard` | Main HTML dashboard with scenario results, crisis overlay, optional trajectory and equilibrium |
| `decision_brief.md` | `--brief` | Standalone Markdown analytical brief |
| `evaluation.json` | always | Machine-readable evaluation artifact; input for `brief --from-json` |
| `game_result.json` | always (game) | Game result and optional equilibrium JSON |
| `run_manifest.json` | always | Full provenance: inputs, outputs, run ID, timestamp |

`--dashboard-output` and `--brief-output` control the **filename** inside the run directory, not an absolute path.

---

## Background Policy Modes

| Mode | Behaviour |
|---|---|
| `compiled-llm` | LLM sets doctrine at start (and on trigger/periodically); yearly step is deterministic — best balance of quality and speed |
| `llm` | Live LLM call inside every yearly step — most faithful, slowest |
| `simple` | Deterministic baseline rule policy — no LLM calls |
| `growth` | Deterministic growth-maximising rule policy — no LLM calls |

Default is `compiled-llm` for `question`, `game`, and `calibrate`.

---

## State CSV and Calendar Year

From GIM_14, the simulation start year is no longer hardcoded to `2023`.  
Pass `--state-year <year>` to match the snapshot in your CSV; the model then runs as `t = state_year + τ`.

```bash
# Project a 2026 operational state snapshot and run from it
python -m gim question "..." \
  --state-csv data/agent_states_operational_2026_calibrated.csv \
  --state-year 2026 \
  --horizon 5 \
  --sim
```

To build a projected operational state from a base CSV:

```bash
python scripts/project_operational_state.py \
  --state-csv data/agent_states_operational.csv \
  --state-year 2026 \
  --years 3
```
