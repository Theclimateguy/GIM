# GIM17 Unified Model Specification

> **Scope note (Tier-1 + Phase 4):** since this spec was written the model gained endogenous inflation/unemployment (Phillips+Okun), Taylor-rule monetary policy, multi-GHG non-CO2 forcing, AR(1) temperature variability, and enforceable debt/resource accounting identities; the climate core was recalibrated (ECS 3.0, HEAT_CAP_SURFACE 8, OCEAN_EXCHANGE 1.0, TCR 1.79). See docs/README.md (GIM17 Modernization) for the per-area docs and calibration_params.py for the authoritative parameters.

## 1. Purpose

This document is the single consolidated specification for GIM17:

- full state vector
- yearly transition equations
- event detection and propagation equations
- reconciliation and invariant checks
- linkage to parameter and state registries

Authoritative registries:

- state registry: [`docs/state_registry.csv`](/Users/theclimateguy/Documents/jupyter_lab/GIM17/docs/state_registry.csv)
- parameter registry: [`data/parameters_gim17.csv`](/Users/theclimateguy/Documents/jupyter_lab/GIM17/data/parameters_gim17.csv)
- parameter lock: [`data/parameters_gim17.lock.json`](/Users/theclimateguy/Documents/jupyter_lab/GIM17/data/parameters_gim17.lock.json)

## 2. Global notation

\[
X_t = \{T_t, A_t, R_t, G_t, I_t\}
\]

- \(T_t\): simulation time index (`world.time`)
- \(A_t = \{A_t^i\}_{i=1}^N\): agent state set
- \(R_t = \{R_t^{ij}\}_{i\neq j}\): directed relation states
- \(G_t\): global physical/resource/macroeconomic state
- \(I_t\): institution states

Year transition:

\[
X_{t+1}=\mathcal{R}\left(\mathcal{P}\left(\mathcal{D}(\mathcal{B}(X_t,u_t,\theta),\theta),u_t,\theta\right),\theta\right)
\]

- \(\mathcal{B}\): baseline structural update
- \(\mathcal{D}\): event detection
- \(\mathcal{P}\): event propagation
- \(\mathcal{R}\): accounting/reconciliation

## 3. Full state vector

## 3.1 Agent state \(A_t^i\)

\[
A_t^i = \{E_t^i, S_t^i, C_t^i, K_t^i, P_t^i, Q_t^i, U_t^i\}
\]

Economy block \(E_t^i\):

\[
E_t^i = \{gdp, capital, population, public\_debt, fx\_reserves, taxes, gov\_spending, social\_spending, military\_spending, rd\_spending,
climate\_adaptation\_spending, climate\_shock\_years, climate\_shock\_penalty, interest\_payments, net\_exports,
gdp\_per\_capita, unemployment, inflation, birth\_rate, death\_rate\}
\]

Social/political latent block \(S_t^i\):

\[
S_t^i = \{trust\_gov, social\_tension, inequality\_gini, legitimacy, protest\_pressure, hawkishness, protectionism, coalition\_openness, sanction\_propensity, policy\_space\}
\]

Climate/resources block \(C_t^i\):

\[
C_t^i = \{climate\_risk, co2\_annual\_emissions, biodiversity\_local,
(energy,food,metals)\times(own\_reserve,production,consumption,efficiency)\}
\]

Risk/event block \(K_t^i\):

\[
K_t^i = \{water\_stress, regime\_stability, debt\_crisis\_prone, conflict\_proneness, debt\_crisis\_active\_years, regime\_crisis\_active\_years\}
\]

Technology/credit/policy block \(P_t^i,Q_t^i,U_t^i\):

\[
P_t^i=\{tech\_level, military\_power, security\_index\}
\]
\[
Q_t^i=\{credit\_rating, credit\_zone, credit\_risk\_score\}
\]
\[
U_t^i=\{alliance\_block, active\_sanctions, sanction\_years\}
\]

## 3.2 Relation state \(R_t^{ij}\)

\[
R_t^{ij} = \{trade\_intensity, trust, conflict\_level, trade\_barrier, at\_war, war\_years, war\_start\_gdp, war\_start\_pop, war\_start\_resource\}
\]

Effective trade intensity:

\[
\widetilde{trade}_{ij,t}=trade\_intensity_{ij,t}\cdot(1-\text{clamp01}(trade\_barrier_{ij,t}))
\]

## 3.3 Global state \(G_t\)

\[
G_t = \{co2, temperature\_global, temperature\_ocean, forcing\_total, carbon\_pools, biodiversity\_index,
baseline\_gdp\_pc, prices_{energy,food,metals}, global\_reserves_{energy,food,metals}, temp\_history, temp\_trend\_3yr\}
\]

## 3.4 Institution state \(I_t\)

\[
I_t^k = \{legitimacy, budget, active\_rules\}
\]

## 4. Baseline equations \(\mathcal{B}\)

## EQ-ECO-001 Output update

\[
Y_{i,t+1}=(1-\lambda_i)Y_{i,t}+\lambda_iY^*_{i,t}
\]

\[
Y^*_{i,t}=TFP_{i,t}\cdot(1+TECH\_OUTPUT\_SENS\cdot\max(0,tech_i-1))\cdot K_{i,t}^{\alpha}L_{i,t}^{\beta}En_{i,t}^{\gamma}\cdot Dmg_{i,t}
\]

## EQ-ECO-002 Capital accumulation

\[
K_{i,t+1}=(1-\delta)K_{i,t}+s_{i,t}Y_{i,t}
\]

## EQ-ECO-003 TFP growth (R&D + diffusion + conditional convergence)

\[
\frac{\Delta TFP_{i,t}}{TFP_{i,t}}=\underbrace{g^{drift}_t}_{\text{baseline}}
+\underbrace{\eta\,\frac{RD_{i,t}}{Y_{i,t}}(1+\sigma\,\overline{trade}_i)}_{\text{R\&D}}
+\underbrace{\theta\,\overline{gap}^{tech}_i}_{\text{diffusion}}
+\underbrace{\nu\,\min\!\Big(\ln\tfrac{y^{frontier}_t}{y_{i,t}},\,\bar g\Big)}_{\text{conditional convergence}}
-growthDrag_{i,t}
\]

with per-capita output \(y_{i,t}=Y_{i,t}/Pop_{i,t}\), frontier \(y^{frontier}_t=\max_j y_{j,t}\), and
\(\nu=\) `TFP_CONVERGENCE_SENS` \(=0.0093\), cap \(\bar g=\) `TFP_CONVERGENCE_GAP_CAP` \(=4\). The
convergence slope is fit to the 2015--2023 real-PPP-GDP growth cross-section (World Bank
`NY.GDP.MKTP.PP.KD`; \(R^2=0.38\), see `calibration/growth_decarb_calibration.py`): poorer economies
catch up faster, so the model reproduces the China/India growth gap that a single drift misses.

## EQ-FIN-001 Public finance / debt

\[
PrimaryDeficit_{i,t}=GovSpend_{i,t}-Taxes_{i,t}
\]
\[
Debt_{i,t+1}=Debt_{i,t}+PrimaryDeficit_{i,t}+r_{i,t}Debt_{i,t}
\]

## EQ-FIN-002 Effective interest rate

\[
r_{i,t}=r_0+\min(Spread_{i,t},RATE\_SPREAD\_CAP)+Contagion_{i,t}+ZonePremium_{i,t}
\]

## EQ-DEM-001 Population dynamics

\[
Pop_{i,t+1}=Pop_{i,t}(1+b_{i,t}-d_{i,t})+Mig_{i,t}
\]

## EQ-CLI-001 Emissions (development-dependent decarbonisation)

\[
Em_{i,t}=Y_{i,t}\cdot Intensity_{i,t}\cdot(1-policyReduction_{i,t})\cdot EMISSIONS\_SCALE
\]
\[
Intensity_{i,t}=Intensity^{base}_i\cdot e^{-DECARB_i\cdot t}\cdot \text{(tech, efficiency, tax terms)}
\]
\[
DECARB_i=\operatorname{clip}\!\big(b_{0}+b_{1}\ln y_{i,t},\;0,\;0.06\big),\qquad
b_{0}=-0.0779,\; b_{1}=0.0107
\]

The structural decarbonisation rate \(DECARB_i\) scales with development (per-capita output
\(y_{i,t}\)): richer/post-industrial economies decarbonise faster (renewables, offshoring of heavy
industry). It is the mirror image of the TFP convergence term (EQ-ECO-003) and is fit to the
2015--2023 per-country CO\(_2\)/real-PPP-GDP intensity-decline cross-section (World Bank CO\(_2\)
`EN.GHG.CO2.MT.CE.AR5`; \(R^2=0.46\), `calibration/growth_decarb_calibration.py`). The single global
`DECARB_RATE_STRUCTURAL`\(=0.016\) is the emissions-weighted aggregate (used when the per-country
switch is off); the per-country median is \(\approx 0.031\).

## EQ-CLI-002 Carbon cycle (impulse-response pools, aged 2023 initialisation)

\[
Pool_{m,t+1}=Pool_{m,t}e^{-1/\tau_m}+\phi_m\sum_iEm_{i,t},\qquad
CO2_t=CO2_{pre}+\sum_mPool_{m,t}
\]

The four IPCC-AR6 pools use *flow* fractions \(\phi_m\) for newly emitted CO\(_2\). The 2023 forward
state, however, initialises the pools from the *aged* partition of the historical excess (mostly in
the long-lived pools), obtained from a 1750\(\to\)2023 spin-up on observed emissions:
\[
Pool_{m,2023}=\psi_m\,(CO2_{2023}-CO2_{pre}),\quad
\boldsymbol{\psi}=(0.380,0.352,0.224,0.044)\;\text{for}\;\tau=(\infty,394,36.5,4.3)\,\text{yr}.
\]
Partitioning the excess by the flow fractions instead over-loads the fast 4.3-yr pool (\(0.28\) vs the
aged \(0.044\)) and produces a phantom \(\sim\!50\) GtCO\(_2\)/yr sink that makes the no-policy
baseline concentration *fall*; the aged initialisation reproduces the observed \(\approx+2.4\)
ppm/yr growth.

## EQ-CLI-003 Forcing and temperature (self-consistent 2023 anchor)

\[
F_t=5.35\ln(C_t/C_0)+F^{nonCO2}_t
\]
\[
\Delta T_s=\frac{F_t-\lambda T_s-\kappa(T_s-T_d)}{C_s}+\varepsilon_t,
\quad
\Delta T_d=\frac{\kappa(T_s-T_d)}{C_d}
\]

The 2023 initial conditions are taken from the same spin-up so the two-box EBM starts in
self-consistent disequilibrium: surface \(T_s^{2023}=1.333\,^\circ\text{C}\) (which is also the zero
point for incremental damage), deep ocean \(T_d^{2023}=0.404\,^\circ\text{C}\) (gap \(\approx0.93\),
the warming-in-the-pipeline). \(\lambda=F_{2\times}/ECS\) with \(ECS=3.0\) (the 1990--2023 backtest
RMSE minimum).

## EQ-RSK-001 Climate risk response

\[
Risk^{clim}_{i,t+1}=Risk^{clim}_{i,t}+\rho\left(Risk^{target}_{i,t}-Risk^{clim}_{i,t}\right)
\]

## EQ-POL-001 Political latent update

\[
legitimacy_i = clamp01(0.6\cdot trust_i + 0.4\cdot(1-tension_i))
\]
\[
protest\_pressure_i = clamp01(0.5\cdot protest\_risk_i + 0.5\cdot tension_i)
\]

and analogous weighted updates for `hawkishness`, `protectionism`, `coalition_openness`, `sanction_propensity`, `policy_space`.

## 5. Event detection equations \(\mathcal{D}\)

## EQ-EVT-001 Debt crisis onset

\[
\left(\frac{Debt_i}{Y_i}>DEBT\_CRISIS\_DEBT\_THRESHOLD\right)
\land
\left(r_i>DEBT\_CRISIS\_RATE\_THRESHOLD\right)
\]

## EQ-EVT-002 Regime crisis onset

\[
trust_i<REGIME\_COLLAPSE\_TRUST\_THRESHOLD
\land
tension_i>REGIME\_COLLAPSE\_TENSION\_THRESHOLD
\]

## EQ-EVT-003 Sanctions regime detection

Sanctions are activated via policy intent resolution and persistence (`resolve_sanctions`) with severity ladder `none/mild/strong`.

## EQ-EVT-004 Conflict/war detection

Conflict escalation uses bilateral conflict/trust/power conditions and war state transition in `apply_security_actions` and `update_active_conflicts`.

## EQ-EVT-005 Climate extreme detection

\[
p^{extreme}_{i,t}=(EVENT\_BASE\_PROB+EVENT\_MAX\_EXTRA\_PROB\cdot climate\_risk_{i,t})\cdot tempFactor_t\cdot(1-resilience_i\cdot EVENT\_RESILIENCE\_DAMP)
\]

## 6. Event propagation equations \(\mathcal{P}\)

## EQ-CH-001 Sanctions channel

For sanctioning pair \((i,j)\):

\[
trade\_intensity_{ij}\leftarrow trade\_intensity_{ij}\cdot m^{san}_{type}
\]
\[
trust_{ij}\leftarrow trust_{ij}\cdot q^{san}_{type}
\]
\[
trade\_barrier_{ij}\leftarrow \min(1,trade\_barrier_{ij}+b^{san}_{type})
\]

Target GDP/trust/tension penalties are applied as nonlinear functions of sanction pressure counts.

## EQ-CH-002 Conflict channel

Border/conflict events apply multiplicative losses to GDP/capital and additive shifts to trust/tension; war persistence applies yearly attrition and exhaustion exit rules.

## EQ-CH-003 Debt crisis channel

On crisis onset and persistence years, model applies debt/GDP/unemployment/trust/tension/stability shocks using `DEBT_CRISIS_*` parameters.

## EQ-CH-004 Regime crisis channel

On regime crisis onset/persistence, model applies capital/GDP/debt/trust/tension/stability shocks using `REGIME_COLLAPSE_*` and `REGIME_CRISIS_*`.

## EQ-CH-005 Trade-barrier friction channel

\[
trade\_intensity_{ij,t+1}=trade\_intensity_{ij,t}\cdot(1-decay_{ij,t})
\]
with
\[
decay_{ij,t}=0.05\cdot trade\_barrier_{ij,t}+0.04\cdot conflict_{ij,t}+0.02\cdot avgTension_{ij,t}
\]

## 7. Reconciliation equations \(\mathcal{R}\)

## EQ-CRD-001 Credit risk aggregation

\[
RiskScore_i=w_fR^f_i+w_wR^w_i+w_sR^s_i+w_{san}R^{san}_i+w_mR^m_i
\]

with weights now parameterized as `CR_TOTAL_*` in `calibration_params.py`.

Rating map:

\[
rating_i = \text{round}(CR\_RATING\_MIN + RiskScore_i\cdot(CR\_RATING\_MAX-CR\_RATING\_MIN))
\]

## EQ-INV-001 Invariant checks

The model logs:

- bounds checks (`gdp`, `capital`, `population`, `debt` non-negative; bounded shares in `[0,1]`)
- debt accounting residual:

\[
\epsilon^{debt}_{i,t}=Debt_{i,t+1}-Debt_{i,t}-(GovSpend_{i,t}-Taxes_{i,t}+Interest_{i,t})
\]

## 8. Parameterization and recalibration policy

Parameterization-only refactor (moving constants to registry with identical values) does not require full recalibration.

Recalibration is required when numeric values, equation structure, or free parameter count changes.

Policy document:

- [`docs/calibration/PARAMETER_CHANGE_POLICY.md`](calibration/PARAMETER_CHANGE_POLICY.md)

## 9. Implementation pointers

- kernel phases and tracing: [`gim/core/simulation.py`](/Users/theclimateguy/Documents/jupyter_lab/GIM17/gim/core/simulation.py)
- full state list: [`docs/state_registry.csv`](/Users/theclimateguy/Documents/jupyter_lab/GIM17/docs/state_registry.csv)
- parameter list: [`data/parameters_gim17.csv`](/Users/theclimateguy/Documents/jupyter_lab/GIM17/data/parameters_gim17.csv)
- crisis validation harness: [`gim/crisis_validation.py`](/Users/theclimateguy/Documents/jupyter_lab/GIM17/gim/crisis_validation.py)

