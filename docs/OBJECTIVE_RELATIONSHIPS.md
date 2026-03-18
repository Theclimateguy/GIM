# Objective Relationship Contract (GIM15)

This document defines the objective-layer mappings used by the scenario/game engine.
Source of truth is `gim/geo_calibration.py` (consumed by `gim/game_runner.py`).

## 1. Objective Space

Supported objective keys:

- `regime_retention`
- `reduce_war_risk`
- `regional_influence`
- `sanctions_resilience`
- `resource_access`
- `bargaining_power`

Player utility in the game layer is composed from:

\[
U_i \;=\; \sum_o w_{i,o}\,u_o(\text{risk probs}) \;+\; \sum_o w_{i,o}\,u_o(\Delta \text{crisis}) \;+\; \sum_o w_{i,o}\,b_o(\text{action})
\]

where:

- \(w_{i,o}\) is player \(i\)'s objective weight,
- \(u_o(\cdot)\) are objective-conditioned utility maps for risk/crisis channels,
- \(b_o(\cdot)\) is per-action objective bonus.

## 2. Objective -> Risk Utility

`OBJECTIVE_TO_RISK_UTILITY` defines how each objective values scenario outcomes.
Positive values reward an outcome; negative values penalize it.

- `regime_retention`: rewards `status_quo`, `controlled_suppression`, `negotiated_deescalation`; strongly penalizes `internal_destabilization`, `broad_regional_escalation`.
- `reduce_war_risk`: strongest reward on `negotiated_deescalation`; strongest penalties on `direct_strike_exchange` and `broad_regional_escalation`.
- `regional_influence`: rewards `limited_proxy_escalation` and moderately `negotiated_deescalation`; penalizes `broad_regional_escalation`.
- `sanctions_resilience`: rewards `status_quo` and `negotiated_deescalation`; penalizes `internal_destabilization`, `direct_strike_exchange`, `broad_regional_escalation`.
- `resource_access`: strongest penalty on `maritime_chokepoint_crisis`; also penalizes `broad_regional_escalation`; rewards `status_quo` and `negotiated_deescalation`.
- `bargaining_power`: rewards `negotiated_deescalation` and slightly escalation signaling channels; penalizes `broad_regional_escalation`.

## 3. Objective -> Crisis Utility (Actor Level)

`OBJECTIVE_TO_CRISIS_UTILITY` maps objectives to crisis metrics in `crisis_dashboard`.
These coefficients are applied to actor-level crisis deltas.

- `regime_retention`: penalizes `regime_fragility`, `protest_pressure`, `inflation`, `sanctions_strangulation`.
- `reduce_war_risk`: penalizes `conflict_escalation_pressure`, `chokepoint_exposure`, `oil_vulnerability`.
- `regional_influence`: mildly penalizes `regime_fragility`, `conflict_escalation_pressure`.
- `sanctions_resilience`: penalizes `sanctions_strangulation`, `fx_stress`, `inflation`, `sovereign_stress`.
- `resource_access`: penalizes `oil_vulnerability`, `strategic_dependency`, `chokepoint_exposure`, `food_affordability_stress`.
- `bargaining_power`: penalizes `regime_fragility`, `sanctions_strangulation`.

## 4. Objective -> Global Crisis Utility

`OBJECTIVE_TO_GLOBAL_CRISIS_UTILITY` maps objectives to global stress shifts:

- `regime_retention`: rewards reductions in `stability_stress_shift` and `net_crisis_shift`.
- `reduce_war_risk`: strongest reward for lower `geopolitical_stress_shift` and lower `net_crisis_shift`.
- `regional_influence`: rewards lower `net_crisis_shift`.
- `sanctions_resilience`: rewards lower `macro_stress_shift` and `geopolitical_stress_shift`.
- `resource_access`: rewards lower `macro_stress_shift` and `geopolitical_stress_shift`.
- `bargaining_power`: rewards lower `net_crisis_shift`.

## 5. Action -> Objective Bonus

`ACTION_OBJECTIVE_BONUS` adds direct objective utility for selected actions.
Representative links:

- De-escalation actions (`signal_restraint`, `accept_mediation`, `backchannel_offer`) boost `reduce_war_risk`.
- Domestic hardening (`domestic_crackdown`) boosts `regime_retention`.
- Economic shielding (`debt_restructuring`, `currency_intervention`, `capital_controls`) boosts `regime_retention` and/or `sanctions_resilience`.
- Coercive economic/cyber actions (`impose_tariffs`, `export_controls`, `cyber_*`) boost `bargaining_power` / `regional_influence`.
- `lift_sanctions` jointly boosts `reduce_war_risk`, `sanctions_resilience`, and `resource_access`.

## 6. Template -> Objective Priors

Case generation (`gim/case_builder.py`) initializes objective mixes by template:

- `alliance_fragmentation`: `bargaining_power`, `regional_influence`, `reduce_war_risk`
- `cyber_disruption`: `reduce_war_risk`, `bargaining_power`, `regime_retention`
- `maritime_deterrence`: `resource_access`, `reduce_war_risk`, `bargaining_power`
- `regional_pressure`: `regional_influence`, `reduce_war_risk`, `bargaining_power`
- `resource_competition`: `resource_access`, `sanctions_resilience`, `reduce_war_risk`
- `sanctions_spiral`: `sanctions_resilience`, `regime_retention`, `reduce_war_risk`
- `tech_blockade`: `bargaining_power`, `sanctions_resilience`, `reduce_war_risk`
- `regime_stress`: `regime_retention`, `reduce_war_risk`, `sanctions_resilience`
- `general_tail_risk`: `reduce_war_risk`, `bargaining_power`, `resource_access`
- `generic_tail_risk`: `reduce_war_risk`, `bargaining_power`, `resource_access`

## 7. Practical Guardrails

- If objective weights are missing, fallback defaults are inserted by `case_builder`.
- Objective keys and action keys are whitelisted (`gim/types.py`).
- Numerical coefficients are confidence-bounded `GeoWeight` values in `gim/geo_calibration.py`; update these centrally, not in runtime code.
