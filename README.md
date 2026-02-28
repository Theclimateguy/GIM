# GIM Repository

This repository is now organized by model generation.

## Active Version

- `GIM_12/` is the current production model.

Quick start:

```bash
cd /YOUR_PATH_HERE/GIM_12
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
- `legacy/GIM_11_1/` : previous `GIM_11_1` codebase and docs.
- `legacy/V10_3_prod/` : previous `V10_3_prod` codebase and docs.
- `legacy/_workspace_extras/` : historical local helper assets from prior workspace state.

## Credit Rating Docs

In `GIM_12/`:
- `credit_rating_methodology.md`
- implementation in `gim_11_1/credit_rating.py`

## Notes

- Offline map generation does not require internet.
- Internet is only needed for LLM API calls during simulation.
