# Cross-block coupling map (GIM 19, `gim/core`)

Derived by reading the transition code, not by keyword search. Each channel lists the
calibration parameters that carry it; zeroing exactly those parameters severs the channel
and leaves every intra-block dynamic intact. This is the operational definition of the
null models in E1-E4.

Crisis triggers (the objects of the Section 6 "late clustering" claim), `gim/core/social.py`:

| crisis | trigger condition | block of the trigger variables |
|---|---|---|
| debt   | `debt/gdp > DEBT_CRISIS_DEBT_THRESHOLD` AND `r_eff > DEBT_CRISIS_RATE_THRESHOLD` | economy |
| fx     | `external_debt_ratio >` thr AND `current_account_ratio <` thr AND `fx_cover_months <` thr | economy |
| regime | `trust < REGIME_COLLAPSE_TRUST_THRESHOLD` AND `tension > REGIME_COLLAPSE_TENSION_THRESHOLD` | society |

So "slow accumulators mature together" is, concretely: do the *economic* accumulators
(debt, reserves) and the *social* accumulators (trust, tension) cross their thresholds in
the same decade, and is that co-timing a consequence of the coupling or of each block's
own clock?

## C1. economy -> society
`gim/core/social.py::update_social_state`
- trust:   `TRUST_GDP_PC_SENS`, `TRUST_UNEMPLOYMENT_SENS`, `TRUST_INFLATION_SENS`
- tension: `SOCIAL_STRESS_UNEMPLOYMENT_SENS`, `SOCIAL_STRESS_INFLATION_SENS`
- gini:    `GINI_GROWTH_SENS`, `GINI_RECESSION_SENS`

## C2. society -> economy
- `gim/core/economy.py:341` sovereign spread on regime fragility: `DEBT_SPREAD_FRAGILITY_SENS`
- `gim/core/economy.py:131` savings rate on tension: `SAVINGS_TENSION_SENS`

## C3. climate -> economy
- `gim/core/climate.py:522` level damage: `DAMAGE_QUAD_COEFF`
- growth damage (off by default): `GROWTH_DAMAGE_TFP_COEFF = 0.0`
- `gim/core/climate.py:530` risk-adjusted damage: `DAMAGE_RISK_ADJ`

## C4. climate -> society
NONE DIRECT. Verified: `climate_risk` does not appear in `social.py`. Climate reaches
trust/tension only through C3 -> economy -> C1. The reverse leg exists:
- `gim/core/climate.py:82` society -> climate resilience: `RESILIENCE_TRUST_W`,
  `RESILIENCE_STABILITY_W`
This asymmetry matters for the Section 6 "convex food-driven escalation" claim, which is
therefore a *composition through the economy*, not a direct climate-society link.

## C5. resources -> economy
Energy cost-push into inflation (`update_inflation_unemployment`), then C1 into society.
Price formation: `MARKET_DEMAND_ELASTICITY`, `ENERGY_DEMAND_PRICE_RESPONSE`.

## C6. cross-country (spatial / trade)
- tension spillover: `GEOGRAPHY_TENSION_LINKS`, `GEO_TENSION_SPILLOVER_W = 0.05`
- climate-risk spillover: `GEOGRAPHY_CLIMATE_LINKS`, `GEO_CLIMATE_SPILLOVER_W = 0.10`
- conflict contiguity: `GEO_CONTAGION_W = 0.03`
- TFP diffusion / trade spillover: `TFP_DIFFUSION_SENS`, `TFP_TRADE_SPILLOVER_SENS`
- sovereign contagion spread: `CONTAGION_DEBT_THRESHOLD` and the partner loop at
  `gim/core/economy.py:344-360`

## Intra-block (must NOT be zeroed by a cross-block null)
`TRUST_GINI_SENS`, `TRUST_TENSION_SENS`, `INEQUALITY_EFFECT_SENS`,
`SOCIAL_TRUST_ANCHOR_SENS`, `GINI_TENSION_SENS`, `DEBT_SPREAD_LINEAR`,
`DEBT_SPREAD_QUADRATIC`, Taylor rule terms.

## Existing ablation machinery
`gim/core/economy.py:93 _channel_disabled(world, name)` reading
`world.global_state._ablation_disabled_channels`. Only three channels are wired
(`debt_spread_feedback`, `monetary_policy_feedback`, `credit_zone_premium`) and all three
are intra-economy. Cross-block nulls therefore go through `ParameterSet.with_overrides`,
which has the advantage of being a reportable parameter diff.
