# Methodic Map (V10.3)

This document maps the model structure, actors, mechanics, and equations for the V10.3 global economic and social simulator.

**Scope**
Covers the production code in `v10_3_prod/` and the wrapper entrypoint `V10_3_prod.py`.

**Core Objects**
`WorldState` is the full state at time `t`:
- `agents`: `Dict[str, AgentState]` (countries)
- `global_state`: `GlobalState` (CO2, temperature, global reserves, prices)
- `relations`: directed bilateral relations with trade, trust, conflict

`AgentState` contains:
- `economy`: GDP, capital, population, debt, reserves, spending, net exports
- `resources`: energy, food, metals (stocks + flows)
- `society`: trust, social tension, inequality (Gini)
- `climate`: emissions, risk, biodiversity
- `culture`: Hofstede-style cultural parameters
- `technology`: tech level, military power, security index
- `risk`: water stress, regime stability, debt-crisis propensity, conflict propensity

**Initialization**
World is built from `agent_states.csv` using `v10_3_prod/world_factory.py`.
- GDP and population load from CSV.
- Capital is initialized as `K = 3.0 * GDP`.
- Global biodiversity is initialized as the population-weighted mean of local biodiversity.
- `global_state.baseline_gdp_pc` is computed once at start:

```
baseline_gdp_pc = (sum_i GDP_i) * 1e12 / (sum_i Pop_i)
```

**Model Boundaries**
External inputs are the initial conditions (CSV state, global constants, and initial relations), exogenous policy actions chosen by the policy module (simple, growth, or LLM), and stochastic climate extreme events; all macro outcomes thereafter (GDP, capital, debt, resource stocks and prices, emissions, temperature, biodiversity, social dynamics, migration, and geopolitics) are endogenously produced by the model’s update rules.

**Simulation Loop (Order of Operations)**
1. Build observations for each agent.
2. Generate actions via policy (LLM, simple, or growth).
3. Apply sanctions and security actions.
4. Apply domestic actions.
5. Apply trade deals and enforce global net exports balance.
6. Update resources and global resource prices.
7. Update global climate, climate risks, and extreme events.
8. Update economy output and capital.
9. Update public finances and check for debt crisis.
10. Update population, social state, and regime stability.
11. Update relative metrics and agent memory.
12. Increment time.

**Policy and Actions**
Policies output an `Action` object with:
- Domestic policy: fuel tax, social spending, military spending, R&D, climate policy.
- Foreign policy: trade deals, sanctions, security actions.
- Finance policy: borrowing and FX use (available for future expansion).

Actions are normalized for stability in `v10_3_prod/actions.py` and `v10_3_prod/policy.py`.

**Economy Module**
File: `v10_3_prod/economy.py`

Production function (Cobb-Douglas):

```
GDP_potential = TFP * K^α * L^β * E^γ
α = 0.30, β = 0.60, γ = 0.10
L = population / 1e9
E = energy_consumption / 1000
```

GDP update (partial adjustment to potential):

```
scale = GDP_observed / GDP_potential (initialized once)
GDP_target = GDP_potential * scale * damage_multiplier
GDP_{t+1} = (1 - a) * GDP_t + a * GDP_target

where a = 0.20 + 0.25 * clamp01(max(0, gap))
      gap = (GDP_target - GDP_t) / GDP_t
```

Capital accumulation:

```
K_{t+1} = (1 - δ) * K_t + s * GDP_t
δ = 0.05
s = base_savings * (0.7 + 0.6*stability - 0.4*tension), clamped to [0.05, 0.40]
base_savings = 0.24
```

TFP dynamics (baseline drift, R&D, and trade/tech diffusion):

```
TFP_t initialized from observed GDP
rd_share = R&D / GDP
spillover = 1 + ψ * avg_trade
diffusion = η * avg_trade_weighted(max(0, tech_gap))
TFP_{t+1} = TFP_t * (1 + clamp(μ + φ * rd_share * spillover + diffusion, -0.05, 0.05))
μ = 0.01, φ = 0.25, ψ = 0.30, η = 0.02
```

**Public Finance and Debt**
File: `v10_3_prod/economy.py`

Baseline government spending drivers (always on):

```
baseline_spend = GDP * (0.15 + 0.035 + (0.005 + 0.015*climate_risk))
policy_spend = social_spending + military_spending + rd_spending
GovSpending = baseline_spend + policy_spend
Taxes = 0.22 * GDP
```

Debt service and borrowing:

```
interest_rate = 0.02 + spread + contagion
spread = min(0.25, (0.03*excess + 0.10*excess^2) * (0.5+0.5*debt_crisis_prone) * (0.7+0.6*fragility))
excess = max(0, debt_gdp - 0.6)
contagion = 0.02 * trade-weighted partner debt stress (cap 0.05)

primary_deficit = GovSpending - Taxes
interest_payments = interest_rate * public_debt
total_deficit = primary_deficit + interest_payments

if total_deficit > 0:
    new_borrowing = min(total_deficit, 0.05*GDP)
else:
    public_debt += total_deficit

public_debt += new_borrowing
```

Debt crisis trigger (in `v10_3_prod/social.py`):
- Trigger if `debt_gdp > 1.2` and `interest_rate > 0.12`.
- Applies debt haircut, GDP shock, unemployment increase, and trust/tension shocks.

**Trade Module**
File: `v10_3_prod/actions.py`

Trade deals move goods and FX, and update `net_exports` (value-based). For each deal:
- `export` adds to initiator net exports and FX reserves; subtracts from partner.
- `import` does the reverse.

Global balance constraint:

```
Σ_i net_exports_i = 0
```

After deals are applied, any residual (numerical drift) is redistributed across agents to enforce balance.

**Resources Module**
File: `v10_3_prod/resources.py`

Resource stock update per agent:
- Energy: production capped by global annual limit and local reserves.
- Food: reserves regenerate.
- Metals: recycling adds supply without depleting reserves; substitution reduces demand when prices rise.

Metals recycling and substitution:

```
consumption' = consumption * (price / price_ref)^(-elasticity)
recycled = recycling_rate * consumption'
production_total = primary_production + recycled
reserve_{t+1} = reserve_t - primary_production + regen + tech_expansion
```

Global resource prices:

```
imbalance = (demand - supply) / (supply + ε)
price_{t+1} = clamp(price_t * (1 + α * imbalance), min_price, max_price)
```

**Climate Module**
File: `v10_3_prod/climate.py`

CO2 stock update with airborne fraction enforcement:

```
Emissions = Σ_i emissions_i
SinkCapacity = base + slope * max(0, CO2 - CO2_preindustrial)
Absorption = min(SinkCapacity, Emissions * (1 - airborne_fraction))
CO2_{t+1} = max(CO2_t + Emissions - Absorption, CO2_preindustrial)
```

Temperature and biodiversity:

```
T_{t+1} = T_t + climate_sensitivity * (CO2 - CO2_preindustrial) - temp_inertia
```

Biodiversity index is population-weighted mean of local biodiversity; local biodiversity declines with higher temperature and climate risk, buffered by resilience (institutions, tech, trust).

Extreme events (probabilistic) reduce capital, population, and trust, and increase tension based on climate risk and resilience.

**Social Module**
File: `v10_3_prod/social.py`

Trust dynamics:

```
trust_change = gdp_pc_effect + unemployment_effect + inflation_effect
              - 0.0004 * gini - 0.08 * max(0, tension - 0.3)
```

Tension dynamics:

```
tension_change = inequality_effect + stress_effect + 0.06 * (0.5 - trust)
```

Inequality (Gini) dynamics:

```
Δgini = 6.0 * gdp_growth
        + 4.0 * |min(0, gdp_growth)| * (0.5 + tension)
        - 60.0 * social_spending_change
        + 1.2 * (tension - 0.4)

gini = clamp(gini + Δgini, 20, 70)
```

Population update (food, inequality, prosperity):

```
availability = (food_prod + 0.2*food_reserve) / food_cons
scarcity = max(0, 1 - availability)

prosperity = sigmoid(1.2 * ln(gdp_pc / baseline_gdp_pc))

birth_rate = (0.025 - 1e-6*gdp_pc) * (1 - 0.5*prosperity) * (1 - 0.6*scarcity) * (1 - 0.3*gini)

death_rate = (0.012 - 0.5e-6*gdp_pc) * (1 + 1.0*scarcity + 0.4*gini) * (1 - 0.2*prosperity)
```

Migration flows (GDP and conflict driven, trade-weighted corridors):

```
push = 0.6*income_gap + 0.4*conflict_proneness
outflow = min(max_share, base_rate * push) * population
inflows distributed to higher-GDP partners by trade_intensity * GDP_gap
```

Regime stability collapse trigger:
- `trust_gov < 0.2` and `social_tension > 0.8` causes capital/GDP/debt shocks and a stability drop.

**Geopolitics and Security**
File: `v10_3_prod/geopolitics.py`

- Sanctions reduce trade intensity and GDP.
- Security actions shift conflict level, trust, and military posture.

**Metrics and Observations**
File: `v10_3_prod/metrics.py`

Key metrics:

```
GDP_share = GDP_i / Σ GDP
Influence = log(1+GDP) + log(1+Pop/1e6) + 0.5*log(1+trade_degree)
Security_margin = own_military / avg_neighbor_military
```

Observations (for policies) include:
- Full agent state.
- Resource balances.
- Competitive metrics (debt stress, reserve years, protest risk).
- Neighbor relations.
- Global state snapshot.

**Memory and Logging**
Files: `v10_3_prod/memory.py` and `v10_3_prod/logging_utils.py`

- Each step is logged to CSV, keyed by `time` and `agent_id`.
- Memory summarizes history for LLM policies.

**Recent Calibration Changes (V10.3)**
- Trade: enforce global net exports balance each step.
- Metals: recycling supply and price-based substitution to avoid universal depletion.
- Carbon cycle: enforce ~50% airborne fraction by capping absorption.
- Debt: baseline fiscal drivers (social, military, climate adaptation) added to spending.
- Inequality: dynamic Gini linked to growth, fiscal policy, and tension.
- Population: food, inequality, and prosperity now shape births and deaths.
- Trust/tension: coupling added to prevent both rising together in aggregate.
