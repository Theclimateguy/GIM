# GIM Repository

This repository is now organized by model generation.

## Active Version

- `GIM_12/` is the current production model.
- `GIM_13/` is the new policy-gaming layer built over the same calibrated world core.
- `GIM_13/` now has two operative paths:
  - static path: fast snapshot scorer;
  - sim path: `SimBridge` over vendored `GIM_11_1 step_world(...)`.
- Unified technical documentation for the current stack is in `MODEL_DOCUMENTATION.md`.
- Run simulation-core workflows from `GIM_12/`.
- Run policy-gaming and Q&A workflows from `GIM_13/`.

Quick start:

```bash
cd GIM_12
export DEEPSEEK_API_KEY="..."
./scripts/run_10y_llm.sh
```

What `GIM_12` includes:
- scalable country input from CSV (up to `MAX_COUNTRIES`, default `100`),
- CSV validation,
- batched/parallel LLM decisions,
- yearly creditworthiness rating (`1..26`) with zones,
- offline Leaflet map generation from final simulation year.

## Version Layout

- `GIM_12/` : current production model and docs.
- `GIM_13/` : policy-gaming layer with scenario compilation, explainability, static scoring and optional sim-bridge execution.
- `GIM_13/` can also export a self-contained HTML decision dashboard from `question` and `game` via `--dashboard`; that HTML now embeds the full `Decision Brief`.
- `GIM_13/` can export the same analytical brief as standalone Markdown either directly via `--brief` or post-facto from `evaluation.json` via `python -m GIM_13 brief --from-json ...`.
- `GIM_13/` also contains the new crisis metrics layer and the quarterly-readiness assessment for `GIM_12`.
- `legacy/GIM_11_1/` : legacy compatibility core and archived docs.
- `legacy/V10_3_prod/` : previous `V10_3_prod` codebase and docs.
- `legacy/_workspace_extras/` : historical local helper assets from prior workspace state.

## Credit Rating Docs

In `GIM_12/`:
- `credit_rating_methodology.md`
- implementation in the legacy compatibility core at `legacy/GIM_11_1/gim_11_1/credit_rating.py`

## Notes

- Offline map generation does not require internet.
- Internet is only needed for LLM API calls during simulation.

## License

This repository is licensed under `Apache-2.0`.
Redistributions and derivative works must preserve `LICENSE`, `NOTICE`, and prominent modification notices.
