# GIM17 Documentation Index

This directory is split into:

- active runtime documentation (`docs/*.md`, `docs/*.csv`)
- archived planning and release-history notes (`docs/legacy/`)

## Active Core Docs

- `MODEL_METHODOLOGY.md` - runtime behavior and module-level methodology.
- `GIM17_UNIFIED_MODEL_SPEC.md` - unified model equations and state/evolution specification.
- `CORE_TRANSITION_CONTRACT.md` - phase contract and canonical finalize rules.
- `SIMULATION_STEP_ORDER.md` - effective yearly order and runtime writer contract.
- `MODEL_STATE_MAP.md` - state vector map and transition links.
- `critical_field_registry.csv` - canonical critical-field contract table.
- `state_registry.csv` - full state inventory.
- `state_registry_coverage.md` - state registry coverage status.

## Active Calibration and Validation Docs

- `CALIBRATION_REFERENCE.md` - active baseline values and interpretation.
- `CALIBRATION_LAYER.md` - calibration workflow and guardrails.
- `CRISIS_VALIDATION_PROTOCOL.md` - operational scenario validation protocol.
- `PARAMETER_CHANGE_POLICY.md` - rules for changing calibrated parameters.

## GIM17 Modernization (Tier-1 + Phases 1–4)

Engineering spine and per-area docs for the GIM16 → GIM17 work (see `WORKLOG_GIM17.md` first).

- `WORKLOG_GIM17.md` - lean per-stage engineering log (read first when resuming).
- `STATUS.md` - current state snapshot + roadmap.
- `INVARIANTS.md` - enforceable accounting/integrity invariants (incl. debt & resource identities).
- `DETERMINISM.md` - world-scoped RNG and reproducibility.
- `PRIORS.md` / `UNCERTAINTY.md` - literature priors, ensembles, Morris/Sobol sensitivity.
- `VALIDATION.md` - skill scoring, history-matching/NROY.
- `CLIMATE_BACKTEST.md` - 1990–2023 climate calibration window (+ T1.3b recalibration).
- `WELFARE_SCC.md` - CRRA welfare + Social Cost of Carbon (multi-horizon).
- `DAMAGE_FUNCTION.md` - damage-function empirical cross-validation (T1.4).
- `LABOR_MARKET.md` - endogenous inflation/unemployment (Phillips + Okun + Taylor rule).
- `MULTI_GHG_FORCING.md` - AR6-anchored non-CO2 forcing components + scenario levers.
- `SCENARIO_ALIGNMENT.md` - SSP/RCP alignment + FAIR/MAGICC emulator benchmark (ECS/TCR).
- `ECONOMICS_BENCHMARK.md` - honest economics review vs industry IAM/macro models.

## Active Interface and Objective Docs

- `agent_state_data_contract.md` - CSV/state artifact contract for loaders.
- `OBJECTIVE_RELATIONSHIPS.md` - objective definitions and linkage map.
- `UI_WORKSPACE.md` - production local dashboard layout, bindings, and API surface.

## Legacy Docs

`docs/legacy/` contains superseded planning, migration, and release-readiness notes that are preserved for traceability but are not source-of-truth for current runtime behavior.
