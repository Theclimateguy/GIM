# v1 (the exploratory app line) — not included in this release

The GIM18 branch ships **only the v2 app** (`gim2/`, this directory's parent) on top of the v18 model
core (`../../gim`). The earlier "v1" line — a macOS app under `macapp/` plus a softmax/LLM engine
surface (`gim/engine_service.py`, `gim/assistant.py`, `gim/scenario_composer.py`,
`gim/scenario_ontology.py`) — is **not present here**: it was never used by the real, shipped v2 app
(confirmed by dependency trace — nothing in `gim2/` imports it), so it was dropped to keep this release
to a single, unambiguous app surface.

That code is not deleted from the project's history — it remains reproducible on the `GIM_app` branch
of the repository, where the full v1 app source and its own archival notes live. `gim/core` (the model)
and the validated analysis modules (`ensemble`, `sensitivity`, `weak_signal`, `scc`,
`historical_backtest`, `conflict_benchmark`, `criticality`) are the shared substrate both app lines run
on; v2 reuses them unchanged.
