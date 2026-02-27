# Methodic Map (GIM_11_1)

This document maps the model structure, actors, mechanics, and equations for the GIM_11_1 global economic and social simulator.

**Scope**
Covers the production code in `gim_11_1/` and the wrapper entrypoint `GIM_11_1.py`.

**Core Objects**
`WorldState` is the full state at time `t`:
- `agents`: `Dict[str, AgentState]` (countries)
- `global_state`: `GlobalState` (CO2, temperature, global reserves, prices)
- `relations`: directed bilateral relations with trade, trust, conflict, barriers
- `institutions`: `Dict[str, InstitutionState]` (global organizations)
- `institution_reports`: per-step reports from institutions

`AgentState` contains:
- `economy`: GDP, capital, population, debt, reserves, spending, net exports
- `resources`: energy, food, metals (stocks + flows)
- `society`: trust, social tension, inequality (Gini)
- `climate`: emissions, risk, biodiversity
- `culture`: Hofstede-style cultural parameters
- `technology`: tech level, military power, security index
- `risk`: water stress, regime stability, debt-crisis propensity, conflict propensity
- `political`: legitimacy, protest pressure, hawkishness, protectionism, coalition openness
- `active_sanctions`: current sanctions map by target

`InstitutionState` contains:
- `id`, `name`, `org_type`, `mandate`, `members`
- `legitimacy`, `budget`, `active_rules`

**Initialization**
World is built from `agent_states.csv` using `gim_11_1/world_factory.py`.
- GDP and population load from CSV.
- Capital is initialized as `K = 3.0 * GDP`.
- Global biodiversity is initialized as the population-weighted mean of local biodiversity.
- `global_state.baseline_gdp_pc` is computed once at start:

```
baseline_gdp_pc = (sum_i GDP_i) * 1e12 / (sum_i Pop_i)
```

**Model Boundaries**
External inputs are the initial conditions (CSV state, global constants, and initial relations), policy actions chosen by the policy module (simple, growth, or LLM), and stochastic climate extreme events; all macro outcomes thereafter (GDP, capital, debt, resource stocks and prices, emissions, temperature, biodiversity, social dynamics, migration, and geopolitics) are endogenously produced by the model’s update rules.

**Simulation Loop (Order of Operations)**
1. Update political state for each agent.
2. Update global institutions and generate institution reports.
3. Build observations for each agent (includes institution reports).
4. Generate actions via policy (LLM, simple, or growth).
5. Resolve sanctions and trade barriers from policy intents.
6. Apply sanctions effects and security actions.
7. Apply trade-barrier effects to trade intensity.
8. Apply domestic actions.
9. Apply trade deals and enforce global net exports balance.
10. Update endogenous relations (trust/conflict) from trade, tension, and power gaps.
11. Update resources and global resource prices.
12. Update global climate, climate risks, and extreme events.
13. Update economy output and capital.
14. Update public finances and check for debt crisis.
15. Update population, social state, and regime stability.
16. Update relative metrics and agent memory.
17. Increment time.

**Policy and Actions**
Policies output an `Action` object with:
- Domestic policy: fuel tax, social spending, military spending, R&D, climate policy.
- Foreign policy: trade deals, sanctions (intent), trade restrictions (intent), security actions.
- Finance policy: borrowing and FX use (available for future expansion).

Actions are normalized for stability in `gim_11_1/actions.py` and `gim_11_1/policy.py`.

**Economy Module**
File: `gim_11_1/economy.py`

Production function (Cobb-Douglas):

```
GDP_potential = TFP * TechFactor * K^α * L^β * E^γ
α = 0.30, β = 0.60, γ = 0.10
L = population / 1e9
E = (energy_consumption / 1000) * energy_efficiency
TechFactor = 1 + 0.6 * max(0, tech_level - 1)
```

GDP update (partial adjustment to potential):

```
scale = GDP_observed / GDP_potential (initialized once)
GDP_target = GDP_potential * scale * damage_multiplier
GDP_{t+1} = (1 - a) * GDP_t + a * GDP_target

where a = 0.30 + 0.35 * clamp01(max(0, gap))
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
μ = 0.01, φ = 3.5, ψ = 0.30, η = 0.02
```

R&D also increases resource efficiency in `gim_11_1/actions.py`, which raises
effective energy input in the production function.

**Public Finance and Debt**
File: `gim_11_1/economy.py`

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

Debt crisis trigger (in `gim_11_1/social.py`):
- Trigger if `debt_gdp > 1.2` and `interest_rate > 0.12`.
- Applies debt haircut, GDP shock, unemployment increase, and trust/tension shocks.

**Trade Module**
File: `gim_11_1/actions.py`

Trade deals move goods and FX, and update `net_exports` (value-based). For each deal:
- `export` adds to initiator net exports and FX reserves; subtracts from partner.
- `import` does the reverse.
- Exports can use a share of reserves (buffer) as capacity.
- FX limit includes trade credit (share of GDP).
- Trade effects are logged as realized trades.

Global balance constraint:

```
Σ_i net_exports_i = 0
```

After deals are applied, any residual (numerical drift) is redistributed across agents to enforce balance.

Trade side-effects:
- Metals import modestly boosts capital.
- Food import modestly reduces tension and increases trust.
- Trade intensity updates per realized volume, capped for stability.

**Political Dynamics and Geopolitics**
Files: `gim_11_1/political_dynamics.py`, `gim_11_1/geopolitics.py`

Sanctions and trade restrictions are intent-based:
- Sanctions only apply if selected by policy intent (`sanctions_actions`).
- Trade restrictions only apply if selected by intent or under high conflict.

Trade barriers and intensity:
- Trade barriers adjust slowly based on intent, conflict, and trust.
- Trade intensity decays with trade barriers plus friction from conflict and social tension.

Endogenous relations update:
- `conflict_level` rises with trade shortfall, tension, military gap, barriers, and sanctions.
- `trust` rises with trade intensity and falls with conflict, tension, and barriers.
- Small drifts keep relations near baseline absent shocks.

Security actions:
- Security actions are applied only if chosen by policy and can be down-shifted
  by escalation gates (avoid immediate catastrophic conflict).

**Institutions Module**
File: `gim_11_1/institutions.py`

Global institutions are modeled as a light coordination layer that:
- Issues reports per step (global state + measures).
- Applies small, bounded effects (trade barrier easing, mediation, liquidity, social support).

Built-in institutions:
- UN, UNSC, IMF, WorldBank, FSB, WTO, EU, USMCA, ASEAN, UNFCCC, GCF, IPCC,
  NATO, WHO, ILO, UNEP/UNESCO.

Institution outputs are included in agent observations:
`external_actors["institutions"]` and `external_actors["institution_reports"]`.

**Resources Module**
File: `gim_11_1/resources.py`

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
File: `gim_11_1/climate.py`

Carbon cycle (4-pool impulse response, GtCO2):

```
E_t = Σ_i emissions_i
B_i(t+1) = B_i(t) * exp(-dt / τ_i) + a_i * E_t
CO2_t = CO2_preindustrial + Σ_i B_i(t)
```

Radiative forcing:

```
C_ppm = CO2_t / GTCO2_PER_PPM
F_CO2 = 5.35 * ln(C_ppm / C0_ppm)
F_total = F_CO2 + F_nonCO2
```

Two-layer energy balance (surface + deep ocean):

```
λ = F2x / ECS
T_s(t+1) = T_s + (dt/Cs) * (F_total - λ*T_s - κ*(T_s - T_d))
T_d(t+1) = T_d + (dt/Cd) * (κ*(T_s - T_d))
```

Climate risk (relaxes toward a temperature-driven target):

```
base = clamp01(c0 + c1 * water_stress + c2 * gini_share)
temp_component = 1 - exp(-k * max(0, ΔT))
target = base + (1 - base) * temp_component
risk' = risk + ρ * (target - risk)
```

Emissions are recalculated from economic scale and tech/efficiency:

```
intensity = intensity_base * exp(-k_tech * max(0, tech - 1)) / efficiency
tax_effect = clamp(1 - k_tax * fuel_tax_change, min, max)
E_t = GDP * intensity * (1 - policy_reduction) * tax_effect
```

Biodiversity index is population-weighted mean of local biodiversity; local biodiversity declines with higher temperature and climate risk, buffered by resilience (institutions, tech, trust).

Climate adaptation spending improves resilience:

```
adapt_share = climate_adaptation_spending / GDP
adapt_res = clamp01(adapt_share / target_share)
resilience = f(regime_stability, tech, trust, adapt_res)
```

R&D spending decays over time (to avoid permanent accumulation):

```
rd_spending_{t+1} = rd_spending_t * (1 - decay_rate)
```

Extreme events add a persistent (2-year) output penalty:

```
if event:
    shock_years = 2
    shock_penalty = min(0.10, 0.5 * severity)
while shock_years > 0:
    GDP_target *= (1 - shock_penalty)
    shock_years -= 1
```

Extreme events (probabilistic) reduce capital, population, and trust, and increase tension based on climate risk and resilience.

**Social Module**
File: `gim_11_1/social.py`

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

**Geopolitics & Conflict**
Files: `gim_11_1/geopolitics.py`, `gim_11_1/political_dynamics.py`

Conflict propagation:

```
propagation = a * (trade_conflict_actor + trade_conflict_target)
block_rivalry = b * block_conflict(block_a, block_b)
conflict_push += propagation + block_rivalry - mediation(SecurityOrg)
```

Sanctions persistence & support:

```
if support < threshold: no sanction
else: type = min(intent, desired_support_level)
sanctions persist for min_duration years even if intent disappears
```

Endogenous escalation (resource stress + conflict):

```
trigger = f(conflict, trust, resource_stress, fragility, tension)
if trigger high -> military_exercise / arms_buildup / border_incident
```

LLM policy guidance uses an escalation ladder (exercise -> buildup -> incident -> conflict)
to reduce excessive passivity in foreign policy decisions.

Active conflicts (war state) incur annual losses and end on exhaustion:

```
if at_war:
  GDP *= (1 - gdp_loss); Capital *= (1 - cap_loss)
  if GDP < 0.7*start or Pop < 0.9*start or Resources < 0.5*start:
     war ends (victory/defeat or mutual exhaustion)
```
push = 0.6*income_gap + 0.4*conflict_proneness
outflow = min(max_share, base_rate * push) * population
inflows distributed to higher-GDP partners by trade_intensity * GDP_gap
```

Regime stability collapse trigger:
- `trust_gov < 0.2` and `social_tension > 0.8` causes capital/GDP/debt shocks and a stability drop.

**Geopolitics and Security**
File: `gim_11_1/geopolitics.py`

- Sanctions reduce trade intensity and GDP (aggregated per target to avoid compounding).
- Security actions shift conflict level, trust, and military posture.

**Metrics and Observations**
File: `gim_11_1/metrics.py`

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
- Institution reports and measures (in `external_actors`).

**Memory and Logging**
Files: `gim_11_1/memory.py` and `gim_11_1/logging_utils.py`

- Each step is logged to CSV, keyed by `time` and `agent_id`.
- Memory summarizes history for LLM policies.

**Recent Calibration Changes (GIM_11_1)**
- Trade: enforce global net exports balance each step; log realized trade volumes.
- Trade capacity: exports can draw on reserve buffers; FX limit includes trade credit.
- Trade frictions: conflict and social tension reduce trade intensity endogenously.
- Political dynamics: sanctions and restrictions only apply when selected by intent.
- R&D: increases tech level and resource efficiency (effective energy input).
- TFP: higher responsiveness to R&D with a bounded drift.
- Geopolitics: sanctions effects aggregated per target to avoid compounding GDP hits.
- Institutions: add global bodies with small, bounded coordination measures each step.
