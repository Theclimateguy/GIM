# GIM17 Documentation Index

Source-of-truth documentation for version 17. (Engineering change-history and superseded planning
notes have been moved out of the repository to keep it clean.)

## Start here

- [`MODEL_LAYERS.md`](MODEL_LAYERS.md) — plain-language tour of every layer: what it does + limits.
- [`ROADMAP.md`](ROADMAP.md) — current standing, real limitations, and the priority order for next work.

## Specification & methodology

- [`GIM17_UNIFIED_MODEL_SPEC.md`](GIM17_UNIFIED_MODEL_SPEC.md) — state vector, yearly equations, events, reconciliation.
- [`MODEL_METHODOLOGY.md`](MODEL_METHODOLOGY.md) — runtime behaviour and module-level methodology.
- [`CORE_TRANSITION_CONTRACT.md`](CORE_TRANSITION_CONTRACT.md) / [`SIMULATION_STEP_ORDER.md`](SIMULATION_STEP_ORDER.md) — phase contract and yearly order.
- [`MODEL_STATE_MAP.md`](MODEL_STATE_MAP.md), [`state_registry.csv`](state_registry.csv), [`critical_field_registry.csv`](critical_field_registry.csv) — state inventory.
- [`agent_state_data_contract.md`](agent_state_data_contract.md) — CSV/state-artifact contract for loaders.

## Calibration & validation

- [`CALIBRATION_REFERENCE.md`](CALIBRATION_REFERENCE.md) — authoritative baseline values (ledger).
- [`CALIBRATION_LAYER.md`](CALIBRATION_LAYER.md), [`PARAMETER_CHANGE_POLICY.md`](PARAMETER_CHANGE_POLICY.md) — workflow + guardrails.
- [`INVARIANTS.md`](INVARIANTS.md) — enforceable accounting/integrity invariants (debt & resource identities).
- [`DETERMINISM.md`](DETERMINISM.md) — world-scoped randomness and reproducibility.
- [`PRIORS.md`](PRIORS.md) / [`UNCERTAINTY.md`](UNCERTAINTY.md) / [`VALIDATION.md`](VALIDATION.md) — priors, ensembles, sensitivity, history matching, skill scoring.
- [`CRISIS_VALIDATION_PROTOCOL.md`](CRISIS_VALIDATION_PROTOCOL.md) — operational crisis-scenario validation.

## Climate & damages

- [`CLIMATE_BACKTEST.md`](CLIMATE_BACKTEST.md) — 1990–2023 climate calibration.
- [`SCENARIO_ALIGNMENT.md`](SCENARIO_ALIGNMENT.md) / [`BENCHMARK_ALIGNMENT.md`](BENCHMARK_ALIGNMENT.md) — scenario warming envelopes + emulator/SCC benchmark.
- [`MULTI_GHG_FORCING.md`](MULTI_GHG_FORCING.md) — non-carbon-dioxide greenhouse-gas forcing.
- [`CLIMATE_BENCHMARKS.md`](CLIMATE_BENCHMARKS.md) — non-CO₂/feedback/SCC benchmark standing & decisions (E3.4).
- [`CARBON_CYCLE_FEEDBACK.md`](CARBON_CYCLE_FEEDBACK.md) — land-use emissions + permafrost/peat + abrupt-release feedbacks.
- [`CARBON_PRICE_CHANNEL.md`](CARBON_PRICE_CHANNEL.md) — carbon price → energy substitution → emissions (validated vs empirical).
- [`DAMAGE_FUNCTION.md`](DAMAGE_FUNCTION.md) / [`GROWTH_DAMAGE.md`](GROWTH_DAMAGE.md) / [`WELFARE_SCC.md`](WELFARE_SCC.md) — damages + social cost of carbon.

## Economy

- [`ECONOMICS_BENCHMARK.md`](ECONOMICS_BENCHMARK.md) — honest economics review vs industry models + the depth roadmap (D1–D5).
- [`LABOR_MARKET.md`](LABOR_MARKET.md) — endogenous inflation, unemployment, central-bank rate.

## Unique social / geopolitical / cultural layers

- [`SOCIAL_GEO_METRICS.md`](SOCIAL_GEO_METRICS.md) — mapping each unique-layer variable to an external index.
- [`UNIQUE_LAYER_AUDIT.md`](UNIQUE_LAYER_AUDIT.md) — which inputs actually move outputs (culture wire/remove decision).
- [`STRESS_AUDIT.md`](STRESS_AUDIT.md) — threshold-gated inputs re-audited under stress.
- [`WEAK_SIGNAL.md`](WEAK_SIGNAL.md) — analyst-tier weak-signal detection (Mahalanobis anomaly + structural break + critical slowing-down) for what-if / early-warning.

## Risk

- [`CRITICALITY_RISK.md`](CRITICALITY_RISK.md) — fat-tailed crisis severity + early-warning indicators.

## Finalization record

- [`RE_ANCHOR.md`](RE_ANCHOR.md) — the headline activation decision + the new golden.
- [`OBJECTIVE_RELATIONSHIPS.md`](OBJECTIVE_RELATIONSHIPS.md) — objective definitions and linkage map.
- [`UI_WORKSPACE.md`](UI_WORKSPACE.md) — local analytical dashboard layout and API surface.
