# GIM15 Documentation Index

This directory is split into:

- active runtime documentation (`docs/*.md`, `docs/*.csv`)
- archived planning and release-history notes (`docs/legacy/`)

## Active Core Docs

- `MODEL_METHODOLOGY.md` - runtime behavior and module-level methodology.
- `GIM15_UNIFIED_MODEL_SPEC.md` - unified model equations and state/evolution specification.
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

## Active Interface and Objective Docs

- `agent_state_data_contract.md` - CSV/state artifact contract for loaders.
- `OBJECTIVE_RELATIONSHIPS.md` - objective definitions and linkage map.
- `UI_WORKSPACE.md` - production local dashboard layout, bindings, and API surface.

## Legacy Docs

`docs/legacy/` contains superseded planning, migration, and release-readiness notes that are preserved for traceability but are not source-of-truth for current runtime behavior.
