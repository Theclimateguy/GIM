# Simulation Step Order

This note documents the effective yearly write order in [`simulation.py`](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/simulation.py) and the currently authorized writer sets for the most calibration-sensitive fields.

## Yearly Order

1. `compute_relative_metrics`
2. `update_political_states`
3. `update_institutions`
4. generate policies
5. `apply_political_constraints`
6. `resolve_foreign_policy`
7. `apply_sanctions_effects`
8. `apply_security_actions`
9. `update_active_conflicts`
10. `apply_trade_barrier_effects`
11. `apply_action`
12. `apply_trade_deals`
13. `update_relations_endogenous`
14. `allocate_energy_reserves_and_caps`
15. `update_resource_stocks`
16. `update_global_resource_prices`
17. `update_global_climate`
18. `update_climate_risks`
19. `apply_climate_extreme_events`
20. `update_economy_output`
21. `update_public_finances`
22. `check_debt_crisis`
23. `update_migration_flows`
24. `update_population`
25. `update_social_state`
26. `check_regime_stability`
27. `compute_relative_metrics`
28. `update_agent_memory`
29. `update_credit_ratings`
30. increment `world.time`

## Phase Grouping (GIM15 refactor scaffold)

`step_world()` now exposes an explicit 4-phase scaffold while preserving the same effective operation order:

1. `baseline`: metrics refresh, political update, institution update, policy generation and political filters
2. `detect`: foreign-policy resolution (`resolve_foreign_policy`)
3. `propagate`: sanctions/security/conflict/trade/action/resource/climate/economy/social propagation
4. `reconcile`: final metrics refresh, memory update, credit update, policy records, time increment

An optional `phase_trace` dict can be passed into `step_world()` to capture aggregate snapshots (`pre`, `baseline`, `detect`, `propagate`, `reconcile`) for phase-level diagnostics.

## Authorized Writers

These fields are intentionally multi-writer today. The contract is "document the allowed writers and keep `simulation.py` orchestration-only".

| Field | Authorized writers |
| --- | --- |
| `economy.gdp` | `actions.py`, `economy.py`, `geopolitics.py`, `social.py` |
| `economy.capital` | `economy.py`, `climate.py`, `geopolitics.py`, `social.py` |
| `economy.public_debt` | `actions.py`, `economy.py`, `institutions.py`, `social.py` |
| `society.trust_gov` | `actions.py`, `climate.py`, `geopolitics.py`, `institutions.py`, `social.py` |
| `society.social_tension` | `actions.py`, `climate.py`, `geopolitics.py`, `institutions.py`, `social.py` |
| `risk.debt_crisis_active_years` | `social.py` only |
| `risk.regime_crisis_active_years` | `social.py` only |

Implementation note:
- write sites in the core modules now carry `WRITES:` comments so state deltas can be traced during calibration work without doing a full grep pass.
