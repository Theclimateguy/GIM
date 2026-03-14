# GIM_14 Migration Notes

This repository was created as a clean local successor to the current `GIM` workspace.

## Migration Principles

- no files were removed from the source repository
- the new repository was created side-by-side as `/Users/theclimateguy/Documents/jupyter_lab/GIM_14`
- only active code and data were imported
- archive/version ballast was intentionally left out

## Imported Sources

- `legacy/GIM_11_1/gim_11_1/` -> `gim/core/`
- `GIM_12/agent_states.csv` -> `data/agent_states.csv`
- `GIM_12/data/agent_state_pipeline/` -> `data/agent_state_pipeline/`
- `GIM_12/scripts/` -> `scripts/`
- `GIM_12/data/world_countries.geojson` -> `data/world_countries.geojson`
- `GIM_12/vendor/leaflet/` -> `vendor/leaflet/`

## Deliberately Excluded

- `legacy/V10_3_prod/`
- `archive/`
- historical log outputs
- the source repository `.git` history

## Adaptations Made

- introduced a top-level installable package `gim`
- added `gim/paths.py` so the CLI resolves data and asset paths from the new repo layout
- updated the CLI display name and default state CSV location for `GIM_14`
- added a smoke-test suite to verify world loading, one-step simulation, and CLI execution

