# Simulation Step Order

This note documents the effective yearly write order in [`simulation.py`](/Users/theclimateguy/Documents/jupyter_lab/GIM18/gim/core/simulation.py) and the runtime contract for critical-field finalization.

## Yearly Order

0. `apply_block_policy_bridge` — [GIM19 §11 / THE-127] block-model policy contour (rate, military share) refines flagged agents before policy generation (default no-op)
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
22. `check_financial_crises` (`check_debt_crisis` + `check_fx_crisis`)
23. `apply_block_layer_substep` — [GIM19 §11 / THE-128] intra-country block layer social deltas for agents in `BLOCK_LAYER_AGENTS` (default empty => no-op)
25. `update_inflation_unemployment` (Phillips curve + Okun + energy cost-push -> inflation/unemployment; P4-A/P4-C feed the social block)
24. `update_migration_flows`
26. `update_population`
27. `update_social_state`
28. `check_regime_stability`
29. `compute_relative_metrics`
30. `update_agent_memory`
31. `update_credit_ratings`
32. increment `world.time`

## Phase Grouping (GIM18 canonical reconcile runtime)

`step_world()` uses an explicit 4-phase scaffold while preserving the same effective operation order:

1. `baseline`: metrics refresh, political update, institution update, policy generation and political filters
2. `detect`: foreign-policy resolution (`resolve_foreign_policy`)
3. `propagate`: sanctions/security/conflict/trade/action/resource/climate/economy/social propagation
4. `reconcile`: canonical finalization of critical fields, final metrics refresh, memory update, credit update, policy records, time increment

An optional `phase_trace` dict can be passed into `step_world()` to capture aggregate snapshots (`pre`, `baseline`, `detect`, `propagate`, `reconcile`) for phase-level diagnostics.

## Authorized Writers

Critical fields are computed as deltas/signals during propagate and finalized only in reconcile.

| Field | Authorized writers |
| --- | --- |
| `economy.gdp` | `gim/core/transitions/reconcile.py` |
| `economy.capital` | `gim/core/transitions/reconcile.py` |
| `economy.public_debt` | `gim/core/transitions/reconcile.py` |
| `society.trust_gov` | `gim/core/transitions/reconcile.py` (propagate-phase contributions: `gim/core/social.py`, `gim/core/transitions/block_substep.py`) |
| `society.social_tension` | `gim/core/transitions/reconcile.py` (propagate-phase contributions: `gim/core/social.py`, `gim/core/transitions/block_substep.py`) |
| `risk.debt_crisis_active_years` | `social.py` only |
| `risk.fx_crisis_active_years` | `social.py` only |
| `risk.regime_crisis_active_years` | `social.py` only |

Implementation note:
- channel modules write pending deltas only; `simulation.py` snapshots propagate state via effective baseline+pending views, and reconcile applies canonical clamped final values.
