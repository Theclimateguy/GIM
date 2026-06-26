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

- [`CALIBRATION_REFERENCE.md`](calibration/CALIBRATION_REFERENCE.md) — authoritative baseline values (ledger).
- [`CALIBRATION_LAYER.md`](calibration/CALIBRATION_LAYER.md), [`PARAMETER_CHANGE_POLICY.md`](calibration/PARAMETER_CHANGE_POLICY.md) — workflow + guardrails.
- [`INVARIANTS.md`](calibration/INVARIANTS.md) — enforceable accounting/integrity invariants (debt & resource identities).
- [`DETERMINISM.md`](calibration/DETERMINISM.md) — world-scoped randomness and reproducibility.
- [`PRIORS.md`](calibration/PRIORS.md) / [`UNCERTAINTY.md`](calibration/UNCERTAINTY.md) / [`VALIDATION.md`](calibration/VALIDATION.md) — priors, ensembles, sensitivity, history matching, skill scoring.
- [`CRISIS_VALIDATION_PROTOCOL.md`](calibration/CRISIS_VALIDATION_PROTOCOL.md) — operational crisis-scenario validation.
- [`INTEGRATION_BENCHMARK.md`](INTEGRATION_BENCHMARK.md) — literature-anchored benchmark of the integration claim vs sectoral models (carbon/DICE, oil/MESSAGEix, crop/AgMIP); the paper's Appendix B.
- [`GEO_ON_REVALIDATION.md`](calibration/GEO_ON_REVALIDATION.md) — re-validation of all headline numbers (2015–2023 backtest RMSE, conflict AUC, Morris sensitivity) under the geo-coupling-on headline; all hold, plus two resolved bookkeeping drifts.

## Climate & damages

- [`CLIMATE_BACKTEST.md`](climate/CLIMATE_BACKTEST.md) — 1990–2023 climate calibration.
- [`SCENARIO_ALIGNMENT.md`](climate/SCENARIO_ALIGNMENT.md) / [`BENCHMARK_ALIGNMENT.md`](climate/BENCHMARK_ALIGNMENT.md) — scenario warming envelopes + emulator/SCC benchmark.
- [`MULTI_GHG_FORCING.md`](climate/MULTI_GHG_FORCING.md) — non-carbon-dioxide greenhouse-gas forcing.
- [`CLIMATE_BENCHMARKS.md`](climate/CLIMATE_BENCHMARKS.md) — non-CO₂/feedback/SCC benchmark standing & decisions (E3.4).
- [`CARBON_CYCLE_FEEDBACK.md`](climate/CARBON_CYCLE_FEEDBACK.md) — land-use emissions + permafrost/peat + abrupt-release feedbacks.
- [`CARBON_PRICE_CHANNEL.md`](climate/CARBON_PRICE_CHANNEL.md) — carbon price → energy substitution → emissions (validated vs empirical).
- [`DAMAGE_FUNCTION.md`](climate/DAMAGE_FUNCTION.md) / [`GROWTH_DAMAGE.md`](climate/GROWTH_DAMAGE.md) / [`WELFARE_SCC.md`](climate/WELFARE_SCC.md) — damages + social cost of carbon.

## Economy

- [`ECONOMICS_BENCHMARK.md`](ECONOMICS_BENCHMARK.md) — honest economics review vs industry models + the depth roadmap (D1–D5).
- [`LABOR_MARKET.md`](LABOR_MARKET.md) — endogenous inflation, unemployment, central-bank rate.
- [`MONEY_PRICES.md`](MONEY_PRICES.md) — money→prices transmission (E4.1): the quantity-theory Phillips term, calibrated λ.
- [`GROWTH_FOUNDATIONS.md`](GROWTH_FOUNDATIONS.md) — growth foundations (E4.2): R&D-stock (Jones) TFP-growth channel + SSP1–5 drift presets.
- [`EXPECTATIONS.md`](EXPECTATIONS.md) — near-rational (model-consistent) expectations (E4.3): the level-1 forward-projection operator (investment + inflation-anchor sites, off by default).

## Unique social / geopolitical / cultural layers

- [`SOCIAL_GEO_METRICS.md`](SOCIAL_GEO_METRICS.md) — mapping each unique-layer variable to an external index.
- [`SOCIAL_VALIDATION_PROGRAM.md`](calibration/SOCIAL_VALIDATION_PROGRAM.md) — S1–S6: lifting the social/political/geopolitical priors onto literature-anchored, reproducible footing (war-size exponent, migration gravity, trust→growth, conflict forecast skill, switchable geographic coupling).
- [`GEO_PRIOR_ANCHORS.md`](calibration/GEO_PRIOR_ANCHORS.md) — literature anchors + a delivered reproduction benchmark for the geographic-coupling weights (conflict / tension / climate): emergent Moran's I and a dyadic neighbour-conflict premium vs the empirical spatial-dependence literature.
- [`UNIQUE_LAYER_AUDIT.md`](UNIQUE_LAYER_AUDIT.md) — which inputs actually move outputs (culture wire/remove decision).
- [`STRESS_AUDIT.md`](STRESS_AUDIT.md) — threshold-gated inputs re-audited under stress.
- [`WEAK_SIGNAL.md`](WEAK_SIGNAL.md) — analyst-tier weak-signal detection (Mahalanobis anomaly + structural break + critical slowing-down) for what-if / early-warning.

## Risk

- [`CRITICALITY_RISK.md`](CRITICALITY_RISK.md) — fat-tailed crisis severity + early-warning indicators.

## Finalization record

- [`RE_ANCHOR.md`](RE_ANCHOR.md) — the headline activation decision + the new golden.
- [`OBJECTIVE_RELATIONSHIPS.md`](OBJECTIVE_RELATIONSHIPS.md) — objective definitions and linkage map.
- [`UI_WORKSPACE.md`](UI_WORKSPACE.md) — local analytical dashboard layout and API surface.
