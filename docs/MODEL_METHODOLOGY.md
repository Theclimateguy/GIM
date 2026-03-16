# GIM Model Methodology

This document describes the model implemented in the current `GIM_14` codebase.

It is a runtime methodology document, not a historical changelog.

## 1. Source of Truth

Primary runtime modules:

- `gim/core/world_factory.py`
- `gim/core/simulation.py`
- `gim/core/policy.py`
- `gim/core/actions.py`
- `gim/core/political_dynamics.py`
- `gim/core/geopolitics.py`
- `gim/core/resources.py`
- `gim/core/climate.py`
- `gim/core/economy.py`
- `gim/core/social.py`
- `gim/core/metrics.py`
- `gim/core/credit_rating.py`

Scenario/game/reporting layer:

- `gim/scenario_compiler.py`
- `gim/game_runner.py`
- `gim/sim_bridge.py`
- `gim/dashboard.py`
- `gim/briefing.py`

## 2. Model Boundary

### Exogenous inputs

- initial actor state from CSV
- actor limit (`MAX_COUNTRIES` / loader max)
- policy mode (`simple`, `growth`, `llm`, `auto` or orchestration `compiled-llm`)
- runtime flags (`DISABLE_EXTREME_EVENTS`, `SAVE_CSV_LOGS`, etc.)
- stochastic seed (`SIM_SEED`) for temperature variability and stochastic channels

### Endogenous outputs

- GDP, capital, debt, fiscal balances, FX reserves
- energy/food/metals reserves, production, consumption, global prices
- trust, tension, inequality, migration, demography, crisis flags
- bilateral trust/conflict/trade barriers, sanctions, wars
- emissions, carbon pools, forcing, temperature, climate risk
- credit rating (`1..26`), risk score, and zone

## 3. State Representation

Core dataclasses are defined in `gim/core/core.py`.

Top-level state:

- `WorldState.time`
- `WorldState.agents`
- `WorldState.global_state`
- `WorldState.relations`
- `WorldState.institutions`
- `WorldState.institution_reports`

Each `AgentState` includes:

- economy block
- resource block
- society block
- climate block
- technology block
- risk block
- political block
- sanctions, credit, and policy history fields

Relations are directed (`RelationState`) and include:

- `trade_intensity`
- `trust`
- `conflict_level`
- `trade_barrier`
- war state and war duration fields

Effective trade intensity is:

```text
effective_trade_intensity = trade_intensity * (1 - clamp01(trade_barrier))
```

## 4. Initialization

`world_factory.make_world_from_csv()` performs:

1. schema/type/range checks for required and optional CSV fields
2. default filling for optional fields
3. derived fields (`capital`, debt from debt/GDP if provided, GDP per capita)
4. relation graph initialization
5. global baseline initialization
6. initial political-state update, institution build, and credit update

Data contract details are maintained in `docs/agent_state_data_contract.md`.

## 5. Yearly Update Order

`step_world()` in `gim/core/simulation.py` executes in this order:

1. `compute_relative_metrics`
2. `update_political_states`
3. `update_institutions`
4. generate actions (rule-based or LLM/compiled-LLM)
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
19. `apply_climate_extreme_events` (if enabled)
20. `update_economy_output`
21. `update_public_finances`
22. `check_debt_crisis`
23. `update_migration_flows`
24. `update_population`
25. `update_social_state`
26. `check_regime_stability`
27. `compute_relative_metrics` (post-step refresh)
28. `update_agent_memory`
29. `update_credit_ratings`
30. append policy records, persist trend baselines, increment `world.time`

This ordering is intentional and path-dependent.

## 6. Behavioral Blocks

### 6.1 Political and action layer

- political latent variables (legitimacy/protest/hawkishness/policy space) are updated from current macro-social-risk state
- actions are generated per actor and filtered by political constraints before execution
- external actions (sanctions/security/trade restrictions/deals) and domestic actions feed into relations, macro, and social outcomes

### 6.2 Resource layer

For `energy`, `food`, and `metals`, the model updates:

- reserve stocks
- production/consumption balance
- efficiency
- global prices

Energy allocation/caps are computed before resource stock updates and then feed downstream economic and climate channels.

### 6.3 Climate layer

Climate module behavior includes:

- actor-level emissions updates
- global carbon pool updates
- forcing and temperature updates
- climate risk propagation back to actors

Key properties:

- non-CO2 forcing schedule is calendar-year based
- annual natural variability can be injected (`TEMP_NATURAL_VARIABILITY_SIGMA`)
- structural decarbonization and tech/efficiency channels are modeled separately

### 6.4 Economy and finance layer

The economy block updates GDP/capital with production, TFP, resource/climate effects, and spillovers.

Public-finance update then applies:

- revenue and spending dynamics
- debt accumulation and rates/spreads
- reserve pressures
- debt crisis checks

### 6.5 Social and crisis layer

Social dynamics update trust, tension, inequality, migration, demography, and crisis persistence counters.

Debt and regime crises have explicit:

- onset logic
- persistence penalties
- recovery/exit logic
- max-duration caps

### 6.6 Credit layer

`update_credit_ratings()` computes yearly sovereign-style ratings from macro/social/war/sanction risk components and stores:

- `credit_rating`
- `credit_zone`
- `credit_risk_score`
- detailed component breakdown

## 7. Policy Modes

Core world loop (`gim/core/cli.py`) supports:

- `simple`
- `growth`
- `llm`
- `auto`

Orchestration simulation path (`question`/`game`/`calibrate` with `--sim`) supports background policy:

- `compiled-llm`
- `llm`
- `simple`
- `growth`

`compiled-llm` refresh policy is controlled by:

- `--llm-refresh trigger|periodic|never`
- `--llm-refresh-years <n>`

## 8. Scenario and Game Overlay

The overlay uses the same world state and scoring basis as the yearly model.

Pipeline:

1. compile question or load case
2. evaluate combinations statically or through simulation horizon (`SimBridge`)
3. optionally run equilibrium search
4. emit JSON/dashboard/brief artifacts

Main entrypoint: `python3 -m gim question|game|metrics|brief|calibrate|console`.

### 8.1 Objective relationship layer

Objective-conditioned game utility is defined by three calibrated mappings:

- `OBJECTIVE_TO_RISK_UTILITY`
- `OBJECTIVE_TO_CRISIS_UTILITY`
- `OBJECTIVE_TO_GLOBAL_CRISIS_UTILITY`

plus action-conditioned objective terms:

- `ACTION_OBJECTIVE_BONUS`

The full objective contract and template priors are documented in:

- `docs/OBJECTIVE_RELATIONSHIPS.md`

## 9. Calibration Contracts

Calibration contracts are documented in:

- `docs/CALIBRATION_REFERENCE.md`
- `docs/CALIBRATION_LAYER.md`

Important hard contract:

- `EMISSIONS_SCALE` and `DECARB_RATE_STRUCTURAL` are manifest-bound (`data/agent_states_operational.artifacts.json`) and should only change via refresh scripts.

## 10. Known Modeling Boundaries

Current implementation intentionally keeps several simplifications:

- no explicit multi-sector energy transition module yet
- no explicit micro-founded financial sector balance-sheet model
- crisis/political outcome scoring remains calibrated via case suites, not fully estimated structural equations
- several parameters remain prior-weighted and are tracked as calibration debt in `calibration_params.py`

Use this document together with `docs/SIMULATION_STEP_ORDER.md` when reviewing write-order-sensitive changes.
