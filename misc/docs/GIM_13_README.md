# GIM_13 MVP

`GIM_13` is the first policy-gaming layer built on top of the existing `GIM_12` world model.

Current MVP scope:

- compile a natural-language question into a structured scenario;
- preserve calibrated baseline behavior from `GIM_12`;
- expose both a static scorer and an optional sim path over legacy `step_world(...)`;
- keep critical tail-risk states in the distribution;
- enforce soft guardrails instead of silent threshold clipping;
- compute crisis metrics with archetype-specific relevance routing;
- run small policy games over a shared world state;
- explain why a crisis or escalation path appears.

Execution paths:

- static path: default for `question` and `game`; fast, deterministic, snapshot-based;
- sim path: enabled with `--horizon N`; slower, runs the vendored `GIM_11_1` world engine for `N` yearly steps and then scores the terminal state.

## CLI

Run a question-driven scenario:

```bash
python3 -m GIM_13 question \
  --question "Could sanctions pressure and maritime coercion destabilize Saudi Arabia and Turkey in 2026?" \
  --actors "Saudi Arabia" Turkey "United States"
```

Run the same question through the yearly simulation loop:

```bash
python3 -m GIM_13 question \
  --question "Will Red Sea tensions escalate?" \
  --horizon 3
```

Write a self-contained decision dashboard after a question or game run.
The HTML already includes the full `Decision Brief` section rendered from the same run:

```bash
python3 -m GIM_13 question \
  "Will Red Sea tensions escalate?" \
  --horizon 3 \
  --dashboard \
  --dashboard-output dashboard.html
```

If `--json` is passed together with `--dashboard`, the CLI still prints JSON to stdout and also writes `evaluation.json` next to the HTML file.

If you also want a standalone Markdown export of that same brief:

```bash
python3 -m GIM_13 question \
  "Will Red Sea tensions escalate?" \
  --horizon 3 \
  --brief \
  --brief-output decision_brief.md
```

Generate the brief later from a saved JSON artifact:

```bash
python3 -m GIM_13 brief --from-json evaluation.json --output decision_brief.md
```

Run the bundled policy-game case:

```bash
python3 -m GIM_13 game --case maritime_pressure_game.json
```

Run the bundled policy-game case through the simulation loop:

```bash
python3 -m GIM_13 game --case maritime_pressure_game.json --horizon 5
```

Force the old static scorer even when a horizon is provided:

```bash
python3 -m GIM_13 question --question "Will Red Sea tensions escalate?" --horizon 3 --no-sim
```

Launch the interactive console menu:

```bash
python3 -m GIM_13 console
```

In `console` mode, both Q&A and Policy Gaming now offer an optional "Write dashboard" step after evaluation.
That dashboard already contains the embedded brief.
They also offer an optional standalone Markdown brief export.

Run the bundled operational calibration pass:

```bash
python3 -m GIM_13 calibrate
```

Run the calibration suite through the sim path:

```bash
python3 -m GIM_13 calibrate --sim --horizon 3 --runs 5
```

Run the crisis metrics dashboard:

```bash
python3 -m GIM_13 metrics --agents "United States" "Saudi Arabia" Turkey
```

## Guardrails

This MVP is intentionally designed around calibrated extreme outcomes:

- wars, conflicts, sanctions spirals and crises are allowed as tail events;
- they must remain causally grounded;
- hard legacy thresholds are treated as soft constraints;
- impossible states are still forbidden.

## Operational note

On the current sim path, non-player countries default to legacy `llm` mode when invoked from the CLI. This is behaviorally faithful but can be slow in `game` mode because each strategy profile runs its own trajectory.

## Temporal note

`GIM_12` is still an annual core.
The quarterly-readiness assessment is documented in `GIM_12_quarterly_readiness.md`.
