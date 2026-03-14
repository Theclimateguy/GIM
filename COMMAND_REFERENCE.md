# GIM_13 Command Reference v13.1.2

This file is the quick operational reference for the CLI.  
The full model logic, formulas, reporting contract, and data contract remain in [README.md](/Users/theclimateguy/Documents/jupyter_lab/GIM_13/README.md).

## Version

```bash
python -m GIM_13 --version
```

## Core Commands

```bash
python -m GIM_13 question "Will Red Sea tensions escalate?"
python -m GIM_13 question --question "Will war start between the United States and Iran?" --actors "United States" Iran --horizon 3 --sim --background-policy compiled-llm --dashboard
python -m GIM_13 game --case misc/cases/maritime_pressure_game.json --dashboard
python -m GIM_13 game --description "China imposes export controls and the United States responds with tariffs." --save-case misc/local/cases/trade_case.json --dashboard
python -m GIM_13 game --case misc/cases/maritime_pressure_game.json --equilibrium --episodes 50 --trust-alpha 0.5
python -m GIM_13 metrics --agents "United States" "China" "Iran"
python -m GIM_13 calibrate --runs 5 --horizon 3 --sim --background-policy compiled-llm
python -m GIM_13 brief --from-json evaluation.json --output decision_brief.md
python -m GIM_13 console
```

## `question`

Purpose: compile one question-driven scenario and evaluate it.

Main flags:
- `--question` or positional question text
- `--actors`
- `--template`
- `--horizon`
- `--sim` / `--no-sim`
- `--background-policy compiled-llm|llm|simple|growth`
- `--llm-refresh trigger|periodic|never`
- `--llm-refresh-years`
- `--dashboard`
- `--brief`
- `--json`

Example:

```bash
python -m GIM_13 question \
  --question "Will war start between the United States and Iran?" \
  --actors "United States" Iran \
  --horizon 3 \
  --sim \
  --background-policy compiled-llm \
  --llm-refresh never \
  --dashboard \
  --brief
```

## `game`

Purpose: run a policy game from case JSON or free text.

Inputs:
- `--case <json>`
- or `--description "<text>"`

Main flags:
- `--save-case`
- `--horizon`
- `--sim` / `--no-sim`
- `--background-policy compiled-llm|llm|simple|growth`
- `--llm-refresh trigger|periodic|never`
- `--llm-refresh-years`
- `--equilibrium`
- `--episodes`
- `--threshold`
- `--trust-alpha`
- `--max-combinations`
- `--dashboard`
- `--brief`
- `--json`

Example:

```bash
python -m GIM_13 game \
  --case misc/local/cases/us_iran_war_game.json \
  --horizon 3 \
  --sim \
  --background-policy compiled-llm \
  --llm-refresh never \
  --equilibrium \
  --dashboard \
  --brief
```

## `metrics`

Purpose: compute crisis metrics directly from the current world snapshot.

Example:

```bash
python -m GIM_13 metrics --agents "United States" Iran "Saudi Arabia"
```

## `calibrate`

Purpose: run the bundled historical validation suite.

Main flags:
- `--suite`
- `--runs`
- `--horizon`
- `--sim` / `--no-sim`
- `--background-policy`
- `--llm-refresh`
- `--llm-refresh-years`
- `--json`

Example:

```bash
python -m GIM_13 calibrate --runs 3 --horizon 2 --sim --background-policy compiled-llm
```

## `brief`

Purpose: rebuild a standalone Markdown brief from `evaluation.json`.

Example:

```bash
python -m GIM_13 brief --from-json evaluation.json --output decision_brief.md
```

## `console`

Purpose: interactive menu over `question` and `game`.

Example:

```bash
python -m GIM_13 console
```

## Output Artifacts

- `dashboard.html`: main LPR-facing artifact
- `decision_brief.md`: standalone Markdown export
- `evaluation.json`: machine-readable artifact used for post-processing

## Background Policy Modes

- `compiled-llm`: rare LLM doctrine refresh, yearly deterministic controller
- `llm`: live LLM policy calls inside the yearly loop
- `simple`: deterministic baseline rule policy
- `growth`: deterministic growth-seeking rule policy
