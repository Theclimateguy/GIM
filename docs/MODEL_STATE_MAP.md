# MODEL_STATE_MAP (GIM15 draft)

## 1. State vector

\[
X_t = \{A_t, R_t, G_t, I_t, T_t\}
\]

where:

- \(A_t\): agent states
- \(R_t\): bilateral relation states
- \(G_t\): global physical/macro states
- \(I_t\): institution states
- \(T_t\): simulation time index

Agent state decomposition:

\[
A_t^i = \{E_t^i, S_t^i, C_t^i, K_t^i, P_t^i, Q_t^i, U_t^i\}
\]

- \(E_t^i\): economy stocks/flows
- \(S_t^i\): social + political latent scores
- \(C_t^i\): climate + resource states
- \(K_t^i\): risk/event flags
- \(P_t^i\): technology capacity
- \(Q_t^i\): credit/risk diagnostics
- \(U_t^i\): active policy/event action state

## 2. Four-phase transition map

\[
X_{t+1} = \mathcal{R}\left(\mathcal{P}\left(\mathcal{D}\left(\mathcal{B}(X_t, u_t, \theta),\theta\right),u_t,\theta\right),\theta\right)
\]

### Phase B: baseline structural update

Target variables:

- trend economy: \(gdp, capital, gdp\_per\_capita, taxes, spending, debt\)
- demography: \(birth\_rate, death\_rate, population\)
- resources and prices: reserves, production, consumption, global prices
- climate core: emissions, carbon pools, forcing, temperatures, biodiversity
- latent political scores: legitimacy, protest pressure, hawkishness, policy space

Canonical forms:

\[
GDP_{i,t}^{base} = (1-\lambda_g)GDP_{i,t} + \lambda_g \cdot GDP^{target}_{i,t}
\]

\[
Debt_{i,t}^{base} = Debt_{i,t} + PrimaryDeficit_{i,t} + r_{i,t}Debt_{i,t}
\]

\[
CO2_{t}^{base} = CO2_{pre} + \sum_m Pool_{m,t+1}, \quad Pool_{m,t+1}=Pool_{m,t}e^{-1/\tau_m}+\phi_m Emissions_t
\]

### Phase D: event detection

Event onset/persistence rules are computed from baseline states:

\[
p^{debt}_i = \sigma\left(\alpha_0 + \alpha_1 \frac{Debt_i}{GDP_i} + \alpha_2 r_i + \alpha_3 fragility_i\right)
\]

\[
p^{regime}_i = \sigma\left(\beta_0 + \beta_1(1-trust_i)+\beta_2 tension_i+\beta_3 protest_i\right)
\]

\[
p^{war}_{ij} = \sigma\left(\gamma_0 + \gamma_1 conflict_{ij}+\gamma_2(1-trust_{ij})+\gamma_3 mil\_imbalance_{ij}\right)
\]

Outputs:

- event flags: debt/regime crisis, sanctions pressure, war state, climate extreme activation
- event intensity and persistence counters

### Phase P: event propagation

Event deltas are applied as channel-tagged shocks:

\[
X_t^{post} = X_t^{base} + \sum_c \Delta X_t^{(c)}
\]

Main channels:

- sanctions \(\rightarrow\) trade intensity/barriers \(\rightarrow\) GDP/trust/tension
- conflict \(\rightarrow\) capital/GDP/population \(\rightarrow\) social destabilization
- debt crisis \(\rightarrow\) debt, output, unemployment \(\rightarrow\) trust/tension
- climate extreme \(\rightarrow\) capital/population/shock penalty \(\rightarrow\) social stress

### Phase R: accounting and reconciliation

Reconciliation step finalizes year outputs and constraints:

- bounds: non-negativity and [0,1] clamps where required
- stock-flow consistency checks
- recompute relative metrics and credit ratings
- write audit payload with per-phase contribution tags

## 3. Event set for GIM15 refactor

- Debt crisis: onset + persistence + recovery windows
- Regime crisis: low trust + high tension trigger
- War/conflict escalation: bilateral conflict state machine
- Sanctions regime: bilateral sanction state with persistence
- Climate extreme event: stochastic draw conditional on risk and warming

## 4. Anti-double-counting rules

- Rule A: each crisis effect is applied only in Phase P.
- Rule B: baseline GDP/debt/climate equations must exclude crisis multipliers.
- Rule C: every delta in Phase P has a single `channel_id`.
- Rule D: reconciliation cannot re-apply structural or event penalties.

## 5. Required observability outputs

Per agent-year and global-year, persist:

- baseline values
- event detection probabilities and trigger decisions
- propagation deltas by channel
- final reconciled values
- invariant residuals

## 6. Implementation linkage

- Registry: `docs/state_registry.csv`
- Current orchestration source: `gim/core/simulation.py`
- Current write-order baseline: `docs/SIMULATION_STEP_ORDER.md`

