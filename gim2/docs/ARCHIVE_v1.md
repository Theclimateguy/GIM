# Archiving v1 (the exploratory app line)

v2 keeps v1 **reproducible**, not deleted. v1 = the macOS app under
[`../../macapp`](../../macapp) + the softmax engine surface
(`gim/engine_service.py`, `gim/assistant.py`, `game_runner`, `hybrid_simulator`).

## Status at v2 kickoff (2026-06-28)

The v1 app + engine were developed **in the working tree but never committed**
(see git status: `macapp/`, `gim/engine_service.py`, `gim/assistant.py`,
`gim/scenario_composer.py`, `gim/scenario_ontology.py`, the v1 tests). They are
therefore **not yet archivable by tag** — a tag can only point at a commit.

## Procedure (run once, on the v2 line branch)

```bash
# 1. Snapshot v1 exactly as it stands (engine + app + composer + tests).
git add macapp gim/engine_service.py gim/assistant.py \
        gim/scenario_composer.py gim/scenario_ontology.py \
        tests/test_assistant_recovery.py tests/test_engine_composed.py \
        tests/test_engine_service.py tests/test_scenario_composer.py \
        docs/mac_app
git commit -m "archive(v1): freeze the exploratory softmax/LLM app line"

# 2. Tag the snapshot and keep a branch pointer.
git tag -a v1-archive -m "GIM17 v1 — exploratory softmax/game/LLM app (reproducible)"
git branch v1-archive-line   # optional: a named line to check out later
```

> The commit step is **intentionally left for an explicit go-ahead** — v2 tooling
> does not auto-commit the user's in-progress work. Until then, v1 lives in the
> working tree and is preserved by the v2 line branch (`gim17-v2`).

## Reproducing v1 after archival

```bash
git checkout v1-archive
bash macapp/freeze/freeze_engine.sh
cp macapp/freeze/dist/gim-engine macapp/Resources/gim-engine
bash macapp/build_app.sh           # -> macapp/GIM17.app
```

## What stays shared (not archived away)

`gim/core` (the model) and the validated modules (`ensemble`, `sensitivity`,
`weak_signal`, `scc`, `historical_backtest`, `conflict_benchmark`, `criticality`)
are the **shared substrate** both lines run on. v2 reuses them unchanged; the
parity guard (`tests/test_gim2_parity.py`) ensures v2 never drifts from the frozen
math. The exploratory modules remain importable but are gated behind
`GIM_EXPLORATORY` in v2 (THE-71).
