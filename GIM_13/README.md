# GIM_13 MVP

`GIM_13` is the first policy-gaming layer built on top of the existing `GIM_12` world model.

Current MVP scope:

- compile a natural-language question into a structured scenario;
- preserve calibrated baseline behavior from `GIM_12`;
- keep critical tail-risk states in the distribution;
- enforce soft guardrails instead of silent threshold clipping;
- compute crisis metrics with archetype-specific relevance routing;
- run small policy games over a shared world state;
- explain why a crisis or escalation path appears.

## CLI

Run a question-driven scenario:

```bash
python3 -m GIM_13 question \
  --question "Could sanctions pressure and maritime coercion destabilize Saudi Arabia and Turkey in 2026?" \
  --actors "Saudi Arabia" Turkey "United States"
```

Run the bundled policy-game case:

```bash
python3 -m GIM_13 game --case maritime_pressure_game.json
```

Launch the interactive console menu:

```bash
python3 -m GIM_13 console
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

## Temporal note

`GIM_12` is still an annual core.
The quarterly-readiness assessment is documented in `GIM_12_quarterly_readiness.md`.
