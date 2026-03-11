# GIM Repository

This repository is now organized by model generation.

## Active Version

- `GIM_12/` is the current production model.
- `GIM_13/` is the new policy-gaming MVP layer built over the same calibrated world core.
- Run from `GIM_12/`.

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
- `GIM_13/` : policy-gaming MVP with scenario compilation, explainability and small game search.
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
