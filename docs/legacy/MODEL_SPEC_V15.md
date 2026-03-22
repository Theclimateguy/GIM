# MODEL_SPEC_V15 (draft)

Canonical consolidated specification is maintained in:

- [`GIM16_UNIFIED_MODEL_SPEC.md`](/Users/theclimateguy/Documents/jupyter_lab/GIM16/docs/GIM16_UNIFIED_MODEL_SPEC.md)

## 1) Formal transition

\[
X_{t+1}=\mathcal{R}\left(\mathcal{P}\left(\mathcal{D}(\mathcal{B}(X_t,u_t,\theta),\theta),u_t,\theta\right),\theta\right)
\]

- \(X_t\): world state (`agents`, `relations`, `global_state`, `institutions`)
- \(u_t\): action vector after policy generation + political filters
- \(\theta\): parameter vector from [`data/parameters_gim16.csv`](/Users/theclimateguy/Documents/jupyter_lab/GIM16/data/parameters_gim16.csv)

## 2) Equation index (core)

## EQ-ECO-001 Output adjustment

\[
Y_{i,t+1}=(1-\lambda_i)Y_{i,t}+\lambda_i Y^{*}_{i,t}
\]

\[
\lambda_i=GDP\_ADJUST\_SPEED\_BASE+GDP\_ADJUST\_SPEED\_GAP\_SENS\cdot\max\{0,\text{gap}_i\}
\]

Parameters: `ALPHA_CAPITAL`, `BETA_LABOR`, `GAMMA_ENERGY`, `TECH_OUTPUT_SENS`, `GDP_ADJUST_SPEED_BASE`, `GDP_ADJUST_SPEED_GAP_SENS`.

## EQ-ECO-002 Capital accumulation

\[
K_{i,t+1}=(1-\delta)K_{i,t}+s_iY_{i,t}
\]

\[
s_i=\text{clip}(SAVINGS\_MIN,SAVINGS\_MAX,s_0(\eta_0+\eta_1\cdot stability_i-\eta_2\cdot tension_i))
\]

Parameters: `CAPITAL_DEPRECIATION`, `SAVINGS_*`.

## EQ-FIN-001 Public debt law of motion

\[
D_{i,t+1}=D_{i,t}+PrimaryDeficit_{i,t}+r_{i,t}D_{i,t}
\]

Constrained by borrowing cap:
\[
\Delta D^{+}_{i,t}\le MAX\_NEW\_DEBT\_GDP\cdot Y_{i,t}
\]

Parameters: `BASE_INTEREST_RATE`, `MAX_NEW_DEBT_GDP`, spending/tax shares.

## EQ-FIN-002 Effective interest rate

\[
r_{i,t}=r_0+\min(\text{spread}_i, RATE\_SPREAD\_CAP)+\text{contagion}_i+\text{zonePremium}_i
\]

\[
\text{spread}_i=f\left(\frac{D_i}{Y_i}-DEBT\_SPREAD\_THRESHOLD, debt\_crisis\_prone_i, regime\_fragility_i\right)
\]

Parameters: `DEBT_SPREAD_*`, `CONTAGION_*`, `RATE_*`.

## EQ-DEM-001 Population update

\[
N_{i,t+1}=N_{i,t}\left(1+b_{i,t}-d_{i,t}\right)+M_{i,t}
\]

Parameters: `BASE_BIRTH_RATE`, `BASE_DEATH_RATE`, `MIGRATION_*`, scarcity/prosperity sensitivities.

## EQ-CLI-001 Emissions flow

\[
E_{i,t}=Y_{i,t}\cdot I_{i,t}\cdot(1-policyReduction_i)\cdot EMISSIONS\_SCALE
\]

\[
I_{i,t}=I_{i,0}\cdot e^{-TECH\_DECARB\_K(tech_i-1)}\cdot e^{-DECARB\_RATE\_STRUCTURAL\cdot progress_i}\cdot taxEffect_i
\]

Parameters: `TECH_DECARB_K`, `DECARB_RATE_STRUCTURAL`, `EMISSIONS_SCALE`, `FUEL_TAX_*`.

## EQ-CLI-002 Carbon cycle and forcing

\[
Pool_{m,t+1}=Pool_{m,t}e^{-1/\tau_m}+\phi_m\sum_iE_{i,t}
\]

\[
CO2_t=CO2_{pre}+\sum_m Pool_{m,t}, \quad F_t=5.35\ln\frac{C_t}{C_0}+F^{nonCO2}_t
\]

Parameters: `CARBON_POOL_FRACTIONS`, `CARBON_POOL_TIMESCALES`, `FORCING_LOG_COEFF`, `F_NONCO2_*`.

## EQ-CLI-003 Two-box temperature dynamics

\[
\Delta T_s=\frac{F_t-\lambda T_s-\kappa(T_s-T_d)}{C_s}+\varepsilon_t, \quad
\Delta T_d=\frac{\kappa(T_s-T_d)}{C_d}
\]

Parameters: `ECS_DEFAULT`, `HEAT_CAP_SURFACE`, `HEAT_CAP_DEEP`, `OCEAN_EXCHANGE`, `TEMP_NATURAL_VARIABILITY_SIGMA`.

## EQ-RSK-001 Climate risk response

\[
R^{clim}_{i,t+1}=R^{clim}_{i,t}+\rho\left(R^{target}_{i,t}-R^{clim}_{i,t}\right)
\]

Parameters: `CRISK_RESPONSE_RATE`, `CRISK_TEMP_SENSITIVITY`, `CRISK_*_WEIGHT`.

## EQ-EVT-001 Debt crisis detection/propagation

Detection:
\[
\frac{D_i}{Y_i}>DEBT\_CRISIS\_DEBT\_THRESHOLD \land r_i>DEBT\_CRISIS\_RATE\_THRESHOLD
\]

Propagation (onset year): debt haircut/output and social shocks with persistence and exit conditions.

Parameters: `DEBT_CRISIS_*`.

## EQ-EVT-002 Regime crisis detection/propagation

Detection:
\[
trust_i<REGIME\_COLLAPSE\_TRUST\_THRESHOLD \land tension_i>REGIME\_COLLAPSE\_TENSION\_THRESHOLD
\]

Propagation: capital/GDP/debt multipliers, trust/tension bounds, persistence penalties.

Parameters: `REGIME_COLLAPSE_*`, `REGIME_CRISIS_*`.

## EQ-REL-001 Bilateral relation evolution

Trade, trust, conflict and barriers co-evolve via sanctions/security/trade restrictions and endogenous drift.

Parameters: implicit behavioral coefficients in `geopolitics.py` and `political_dynamics.py` (next iteration: externalize to parameter registry).

## EQ-CRD-001 Credit risk aggregation

\[
RiskScore_i=w_fR^f_i+w_wR^w_i+w_sR^s_i+w_{san}R^{san}_i+w_mR^m_i
\]

Mapped to ordinal rating `1..26` and zone buckets.

Parameters: internal weights in `credit_rating.py` (next iteration: externalize to parameter registry).

## 3) Phase ownership (current)

- Baseline: structural economy/climate/resources/demography updates
- Detect: event regime activation (`resolve_foreign_policy`, crisis triggers)
- Propagate: sanctions/conflict/crisis/social cascade deltas
- Reconcile: memory, ratings, invariant checks, `time += 1`

## 4) Parameter governance

Primary registry: [`data/parameters_gim16.csv`](/Users/theclimateguy/Documents/jupyter_lab/GIM16/data/parameters_gim16.csv)

Columns:
- `parameter`
- `value`
- `unit`
- `module`
- `source_tag`
- `uncertainty_level`
- `calibration_status`
