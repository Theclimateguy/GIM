# Causal Reconciliation Plan (Post-GIM16)

## Context

GIM16 has strong operational maturity (tests/calibration/CLI/release package), but the core transition layer still reflects a transition state:

- formal contract targets canonical reconcile finalization,
- effective runtime ordering is preserved from legacy flow,
- critical fields are still documented as multi-writer in active step-order notes.

## Goal

Move from "phase scaffold over legacy order" to strict causal accounting where critical fields are finalized canonically in reconcile, with auditable channel deltas.

## Workstream A: Documentation Normalization (completed in 15.1 docs sync)

- align command/version/calibration/audit docs to current runtime and baseline values,
- keep release/readiness/audit references consistent with produced artifacts,
- remove stale references to pre-15.1 defaults.

Acceptance:

- no stale version/value references in active docs,
- full-suite output and release baseline in docs match current code.

## Workstream B: Critical-field Single-writer Migration

Target fields:

- `economy.gdp`
- `economy.capital`
- `economy.public_debt`
- `society.trust_gov`
- `society.social_tension`

Tasks:

1. Replace direct field writes in channel modules with typed pending deltas.
2. Keep baseline computation in phase-specific builders.
3. Finalize target fields only in `reconcile`.
4. Extend write-guard to fail on direct non-reconcile writes.

Acceptance:

- write-audit test reports only reconcile as canonical final writer for target fields,
- phase trace contains `pre`, `baseline`, per-channel deltas, reconcile adjustment, `final`.

## Workstream C: Order-invariance Hardening

Tasks:

1. Add weak-order perturbation smoke tests for channel application order.
2. Define tolerance thresholds per critical field.
3. Track drift budget in CI regression report.

Acceptance:

- perturbation tests pass under documented tolerances,
- no systematic dependence on channel permutation for critical outcomes.

## Workstream D: Calibration Coherence After Migration

Tasks:

1. Re-run historical backtest envelope.
2. Re-run operational_v1/operational_v2 suites.
3. Re-run rolling pairwise + block4 (`2015->2023`).
4. Refresh release validation package (`results/validation/non_llm/...`).

Acceptance:

- no regression vs current release envelopes,
- near-miss suite remains 5/5,
- rolling one-step metrics remain within release guard bands.

## Exit Criteria for "Causal Refactor Complete"

- `SIMULATION_STEP_ORDER.md` no longer states critical fields are intentionally multi-writer.
- `CORE_TRANSITION_CONTRACT.md` and runtime behavior are fully aligned.
- write-audit + trace-completeness + order-invariance tests all green.
- release docs state "canonical reconcile finalization enforced in runtime."
