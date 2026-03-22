# GIM16 UI Workspace

Production local dashboard for running GIM16 scenarios and reading run-specific analytics.

## Entry Point

```bash
python3 -m gim ui --host 127.0.0.1 --port 8090
```

Backend entry point: `gim/ui_server.py`  
Frontend shell: `ui_prototype/gim16_dashboard_prototype.html`

## Screen Structure

### 1. Simulation Modes

Purpose: build and launch a real local `python3 -m gim <command>` invocation without hiding the underlying runtime contract.

Current control model:

- command selector: `question | game | metrics | calibrate | brief | world | console`
- actors: dropdown checklist sourced from `data/agent_states_operational_2026_calibrated.csv`
- template: optional; blank means backend auto-detect
- state CSV selector: repository CSV picker
- numeric runtime fields: `state_year`, `horizon`, `max_countries`, `llm_refresh_years`
- categorical runtime fields: `background_policy`, `llm_refresh`
- binary flags: `--sim`, `--dashboard`, `--brief`, `--narrative`, `--json`
- `DEEPSEEK_API_KEY` input
- `Run chosen modes` trigger

Execution panel:

- phase list mirrors the `step_world` pipeline
- progress bar reflects aggregate run completion
- export buttons remain disabled until artifacts exist

Template catalog currently exposed in the UI:

- `general_tail_risk`
- `sanctions_spiral`
- `alliance_fragmentation`
- `regional_pressure`
- `maritime_deterrence`
- `resource_competition`
- `tech_blockade`
- `trade_war`
- `cyber_disruption`
- `regime_stress`

Legacy compatibility:

- `generic_tail_risk` remains accepted by runtime and historical fixtures as an alias of `general_tail_risk`

### 2. Analytics

Purpose: show the actual outputs of the executed run rather than static mock values.

Layout:

- summary block from `decision_brief.md` or generated narrative fallback
- scenario distribution
- crisis criticality gauge
- grouped bar charts:
  - actors GDP trajectory
  - social tension by actor
  - inflation / price stress
- normalized crisis metric scale cards with raw-unit notes
- separate lower briefing panels:
  - `Outcome Distribution`
  - `Main Drivers`

## Artifact Binding

The UI is bound to run folders under `results/<command>-YYYYMMDD-HHMMSS>/`.

Primary artifacts:

- `run_manifest.json`
- `evaluation.json`
- `dashboard.html`
- `decision_brief.md`
- `game_result.json`
- `metrics.json`
- `world.csv`

The analytics view is run-specific:

- `/api/run/<id>/analytics` reads the manifest associated with the launched UI run
- `/api/analytics/latest` resolves the latest run that actually produced `evaluation.json`

## API Surface

Primary routes:

- `GET /`
- `GET /api/docs`
- `GET /docs/view?path=...`
- `GET /api/state-csvs`
- `GET /api/actors`
- `POST /api/run`
- `GET /api/run/<id>/status`
- `GET /api/run/<id>/artifacts`
- `GET /api/run/<id>/analytics`
- `GET /api/analytics/latest`
- `GET /api/artifacts/latest`
- `GET /api/download?path=...`

## Runtime Rules

- UI fields start empty where a default would be misleading.
- Blank template does not emit `--template`; the model selects the template itself.
- Actor names are emitted from repository CSV metadata instead of free-text entry.
- Export buttons only activate after the corresponding artifact exists.
- Lower quantitative cards use normalized severity scale `0..1`; raw units remain in the note text.

## Validation

Regression coverage for the UI layer lives in:

- `tests/test_ui_server.py`

Baseline smoke coverage still runs through:

- `tests/test_smoke.py`
