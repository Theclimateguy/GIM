# GIM_14 Migration Notes

This document records the move from the older split workspace into the unified `GIM_14`
repository that is now the active development base.

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
- `GIM_13` operational layer -> `gim/`, `misc/`, `tests/`, and calibration docs

## Deliberately Excluded

- `legacy/V10_3_prod/`
- `archive/`
- historical log outputs
- the source repository `.git` history

## Adaptations Made

- introduced a top-level installable package `gim`
- added `gim/paths.py` so the CLI resolves data and asset paths from the new repo layout
- updated the CLI display name and default state CSV location for `GIM_14`
- restored the `GIM_13` scenario, game, dashboard, briefing, and calibration surface into the active repo
- renamed the large operational state artifact to `agent_states_operational.*`
- removed documentation snapshots from the public docs surface and kept only active `GIM_14` docs
- added a regression suite to verify world loading, scenario/game flows, dashboards, and calibration harnesses

## Current Outcome

`GIM_14` now contains:

- the active yearly simulation core
- the active data pipeline
- the operational scenario/game/reporting layer
- the calibration harness and manifests
- the active public documentation set

The older versioned folders remain useful as provenance, but `GIM_14` is now the intended
working repository.
