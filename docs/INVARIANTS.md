# GIM17 Accounting / Integrity Invariants

The invariant layer (`gim/core/invariants.py`) makes previously-silent
reconciliation behaviour explicit and auditable. It runs every simulated year and
emits one compact record per year, rolled up into `run_manifest.json` under
`invariants`.

## Modes

Set via `GIM17_INVARIANT_MODE` (or the `invariant_mode=` argument to `step_world`):

- `off` — skip enforcement (records still computed if an `invariant_log` is passed).
- `observe` — **default**: compute and log, never raise.
- `strict` — raise `InvariantViolation` on any *enforceable* breach. Use in CI.

## Enforceable invariants (strict mode raises)

1. **bounds** — no post-clamp critical field is out of range (`gdp, capital,
   public_debt ≥ 0`; `trust_gov, social_tension ∈ [0,1]`; non-negative global reserves).
2. **reconcile_clamp** — the final clamp in `transitions/reconcile.py` must not move a
   critical field by more than `RECONCILE_CLAMP_TOL` (1e-6). A breach means reconcile is
   silently masking an out-of-bounds propagated value.
3. **channel_telescope** — per-channel deltas must sum to the recorded net propagation
   delta within `CHANNEL_TELESCOPE_TOL` (1e-6). Guards snapshot-wiring integrity.
4. **trade_balance** — the world is a closed economy, so the sum of all actors'
   `net_exports` must be ~0: `|Σ net_exports| / world_gdp ≤ TRADE_BALANCE_TOL` (1e-6).
   (`apply_trade_deals` already redistributes any residual; this guards the closure.)

Under the default 2026 calibrated scenario all four are clean
(`enforceable.clean = true`), so `strict` is safe to enable in CI.

5. **debt_identity** (T1.1) — every public_debt write is recorded by source in a per-step
   ledger (`fiscal`, `restructuring`, `policy`, `institution`), so the stock-flow identity
   `Δpublic_debt == Σ recorded flows` must hold within `DEBT_IDENTITY_TOL` (1e-9 of GDP).

### Finding B-1 — RESOLVED (T1.1)

Previously the clean fiscal identity `Δdebt − [(gov_spending − taxes) + interest]` left a
residual reaching **~0.84·GDP/yr** for some actors (IRN/RUS/DEU), because the borrowing cap,
the zero-floor, and the discrete crisis "haircut" all moved debt outside that identity.

**Fix:** a debt-flow ledger (`gim/core/critical_pending.py`) records every debt write by its
economic source. The crisis haircut is now an explicit, labelled `restructuring` flow rather
than an unexplained shock. The identity `Δdebt = Σ(fiscal + restructuring + policy +
institution)` now closes to **~1e-16** and is an **enforceable** invariant (in the
`enforceable.clean` gate). Debt *values* are unchanged (backtest golden RMSEs identical) —
this is accounting instrumentation, not a dynamics change.

**Remaining (Phase 4 / financial sector):** the restructuring is now explicit but lacks a
*bilateral counterpart* (creditor write-down), since the model does not yet track bilateral
debt holdings. The within-actor identity is closed; the cross-actor counterpart is deferred.

## Diagnostic: resource accounting consistency (reported, NOT enforced)

Each year the layer reports, per resource (`energy, food, metals`): the `global_reserve`,
the summed country `own_reserve`, summed production and consumption, the global-to-own
ratio, and a flag for pools that are exhausted while production is still active
(`resource_consistency`), rolled up into `diagnostic_resource_consistency`.

### Finding C-1 — global reserves are dimensionally inconsistent with country accounting

The `global_reserves` pool is tracked separately from the sum of country `own_reserve`
and on an incompatible scale. Measured on the default scenario:

- **energy**: `global_reserve ≈ 32.5` vs summed country reserves ≈ `1.16e5`
  (ratio ≈ 3e-4); the global pool depletes slowly only because the energy
  allocation/cap machinery (`allocate_energy_reserves_and_caps`) governs it.
- **food, metals**: global pools are initialised to `100` but depleted by country-scale
  production sums, so they **floor at 0 within one year** and carry no real signal.

Only energy's global reserve is coherent. This is a stock-flow inconsistency inherited
from GIM16. Stage C **measures and reports** it (the trade balance, by contrast, is a
true closed invariant that holds). Reconciling `global_reserves` with the per-country
resource ledger is a modeling change scheduled for a later phase.

## Where it shows up

- `run_manifest.json → invariants` (run-level roll-up + per-year table).
- `phase_trace["invariant_summary"]` when a phase trace is requested.
- `tests/test_invariants.py` exercises both the enforceable guards and the diagnostic.
