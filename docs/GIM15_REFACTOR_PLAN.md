# GIM15 Refactor Plan (4-Phase Kernel + Full State Equation Structure)

## 0) Scope and constraints

- Work mode: local only, no commits, no push.
- Base branch/worktree: `GIM15` in `/Users/theclimateguy/Documents/jupyter_lab/GIM15`.
- Objective: refactor simulation architecture to reduce execution-order artifacts and make crisis causality auditable.
- Primary focus: 4-phase yearly kernel and full descriptive equation structure of model state transitions.

## 1) Formal task statement

We define annual transition as:

\[
X_{t+1} = \mathcal{R}\Big(\mathcal{P}\big(\mathcal{D}(\mathcal{B}(X_t, U_t, \theta), \theta), U_t, \theta\big), \theta\Big),
\]

where:

- \(X_t\): full world state at year \(t\),
- \(U_t\): policy/action vector selected by agents at year \(t\),
- \(\theta\): model parameters,
- \(\mathcal{B}\): baseline structural update (no crisis switching),
- \(\mathcal{D}\): event detection (onset/intensity/duration updates),
- \(\mathcal{P}\): event propagation through channels,
- \(\mathcal{R}\): accounting/reconciliation and invariant enforcement.

The refactor target is to ensure that crisis effects are introduced in \(\mathcal{P}\), not duplicated across \(\mathcal{B}\) and downstream modules.

## 2) State vector decomposition (required for MODEL_STATE_MAP)

Represent:

\[
X_t = \{S_t, F_t, E_t, U_t, L_t, G_t, Q_t\},
\]

with:

- \(S_t\) (structural stocks): GDP level, capital, debt stock, population, reserves, carbon pools, temperatures, institutional capacity.
- \(F_t\) (annual flows): growth increments, fiscal deficit, migration flows, trade flows, emissions flow, conflict losses.
- \(E_t\) (event states): debt crisis, regime crisis, active sanctions, war/conflict regimes, climate extreme flags.
- \(U_t\) (policy actions): fiscal, trade, sanction, security, repression/subsidy decisions.
- \(L_t\) (latent indicators): legitimacy, grievance, social tension pressure, contagion/risk scores.
- \(G_t\) (global coupled states): prices, global CO2, forcing, global temperature, global reserves.
- \(Q_t\) (diagnostics/audit): phase-level contributions, event cards, invariant residuals.

Operational rule: each variable must have exactly one primary update phase and explicit authorized writers.

## 3) Four-phase yearly kernel design

## Phase 1. Baseline structural update (\(\mathcal{B}\))

Goal: update slow and continuous dynamics, excluding discrete crisis onsets.

Core transition blocks:

\[
S_t^{(b)}, F_t^{(b)}, L_t^{(b)}, G_t^{(b)} =
\mathcal{B}(S_t, F_t, L_t, G_t, U_t, \theta)
\]

Includes:

- trend macro update (production, baseline trade, baseline public finance),
- resources and climate physical core update,
- demographic baseline,
- institutional/political baseline scores.

Constraint: no switching of event flags in this phase.

## Phase 2. Event detection (\(\mathcal{D}\))

Goal: infer event onsets/intensities from baseline state.

For each event \(k\):

\[
p_{k,t} = \sigma\left(g_k(S_t^{(b)},F_t^{(b)},L_t^{(b)},G_t^{(b)},\theta)\right),
\]
\[
E_{k,t}^{(d)} = \text{onset/persist/exit rule}(p_{k,t}, E_{k,t-1}, \theta).
\]

Required outputs:

- event activation decisions,
- intensity/severity,
- expected duration/persistence counters.

## Phase 3. Event propagation (\(\mathcal{P}\))

Goal: apply event-induced causal cascades as isolated deltas.

\[
\Delta X_t^{(event)} = \mathcal{P}(X_t^{(b)}, E_t^{(d)}, U_t, \theta),
\]
\[
X_t^{(p)} = X_t^{(b)} + \Delta X_t^{(event)}.
\]

Canonical channels:

- sanctions \(\rightarrow\) trade \(\rightarrow\) GDP \(\rightarrow\) fiscal stress,
- conflict \(\rightarrow\) capital destruction \(\rightarrow\) migration \(\rightarrow\) social tension,
- debt stress \(\rightarrow\) spreads \(\rightarrow\) debt service \(\rightarrow\) rating/risk,
- climate extremes \(\rightarrow\) output loss \(\rightarrow\) budget/instability.

Constraint: event effects must be decomposable by channel and non-duplicated.

## Phase 4. Accounting and reconciliation (\(\mathcal{R}\))

Goal: finalize year, enforce bounds, log audit artifacts.

\[
X_{t+1} = \mathcal{R}(X_t^{(p)}, \theta)
\]

Includes:

- stock-flow consistency checks,
- bound/clamp checks,
- recomputation of derived indicators and ratings,
- phase attribution logs.

## 4) Invariants and anti-double-counting checks

Minimum invariant set per year:

- stock non-negativity: \(capital, population, reserves, debt \ge 0\),
- bounded rates/probabilities in \([0,1]\) when defined as shares/probabilities,
- accounting identity checks (example):
  \[
  Debt_{t+1} - Debt_t \approx Deficit_t + Interest_t + \epsilon_t,
  \]
- climate consistency (emissions to CO2 pool step),
- one-channel one-effect rule: each crisis delta tagged by source channel.

## 5) Refactor workplan (priority order)

## P1. State registry and causal map (fast, high ROI)

Deliverables:

- `docs/MODEL_STATE_MAP.md`
- `docs/state_registry.csv`

Required columns in `state_registry.csv`:

- `variable_name`
- `domain` (`agent`/`relation`/`global`)
- `type` (`stock`/`flow`/`event`/`policy`/`latent`/`derived`)
- `unit`
- `range_min`
- `range_max`
- `phase_owner` (`baseline`/`detect`/`propagate`/`reconcile`)
- `authorized_writers`
- `depends_on`
- `affects`
- `equation_id`
- `notes`

Definition of Done:

- every mutable field in `gim/core/core.py` and key relation/global fields mapped,
- no orphan mutable field without phase owner and writer set.

## P2. Simulation kernel refactor to 4 phases (core engineering)

Deliverables:

- refactored `gim/core/simulation.py` orchestration layer with explicit phase functions,
- phase-level telemetry payload in yearly logs,
- toggle flags for ablation per phase/channel.

Suggested implementation sequence:

1. Extract current order into phase wrappers without behavior change.
2. Move discrete event triggers into detection phase.
3. Move all crisis-induced macro/social deltas into propagation phase.
4. Keep reconciliation with explicit invariant checks and diagnostics.

Definition of Done:

- per-year output includes phase contributions for GDP/debt/conflict/risk,
- disabling propagation removes crisis deltas while keeping baseline path stable,
- reorder inside one phase does not produce large unintended drift.

## P3. Crisis validation harness (post-refactor proof layer)

Deliverables:

- `docs/CRISIS_VALIDATION_PROTOCOL.md`
- `tests/crisis_cases/` fixtures (canonical + near-miss)
- `gim/calibration_validator.py` extension or dedicated harness module

Validation dimensions per case:

- directional validity (sign),
- ordering validity (cascade order),
- magnitude validity (range/ratio tolerance),
- ablation sensitivity (channel necessity).

Definition of Done:

- each case yields a card: expected mechanism, observed path, mismatch notes, `pass/weak_pass/fail`,
- near-miss set shows low false-positive crisis activations.

## P4. Formal equation spec and parameter governance

Deliverables:

- `docs/MODEL_SPEC_V15.md` with equation-indexed transition definitions,
- parameter registry file (`data/parameters_v15.csv` or `yaml`) with source and uncertainty tags.

Minimum parameter columns:

- `parameter`
- `value`
- `unit`
- `module`
- `source`
- `uncertainty_level`
- `calibration_status`

Definition of Done:

- each equation in spec references parameter IDs from registry,
- no hidden magic constants in core transition path.

## 6) Proposed 3-track execution mode

- Quick draft (1-2 days): P1 + phase wrappers + minimal invariants.
- Reliable build (3-7 days): full P2 + protocol scaffold + first crisis pack.
- Research build (1-2 weeks): full P3/P4 + uncertainty/sensitivity workflow.

## 7) Immediate next execution steps inside GIM15

1. Build `state_registry.csv` from current dataclasses and active writers.
2. Introduce explicit phase function skeleton in `simulation.py` with no behavior change.
3. Add phase telemetry schema to yearly trace.
4. Write first crisis case cards (sanctions cascade, debt cascade, near-miss debt case).

