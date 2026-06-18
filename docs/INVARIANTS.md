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

## Diagnostic: debt fiscal residual (reported, NOT enforced)

For each actor the layer reports the deviation of the realised debt change from the
clean fiscal identity:

```
residual = Δpublic_debt − [(gov_spending − taxes) + interest_payments]
```

reported as a share of GDP (`debt_fiscal_residual`), plus a run-level worst-offender
roll-up (`diagnostic_debt_fiscal_residual`).

### Finding B-1 — the fiscal identity does not currently hold

Measured on the default scenario, `|residual| / GDP` reaches **~0.84 per year** for some
actors (e.g. IRN, RUS, DEU). Three implementation mechanisms break the identity:

1. **Borrowing cap** — `update_public_finances` caps new debt at `MAX_NEW_DEBT_GDP`
   (0.05·GDP/yr), so large deficits are not fully financed.
2. **Zero-flooring** — debt is floored at 0 inside `economy.py` (`max(0.0, …)`), so fiscal
   surpluses larger than the debt stock cannot reduce debt further (e.g. DEU).
3. **Crisis debt shocks** — debt/FX/regime crisis channels move debt outside the fiscal
   identity (e.g. IRN debt falls despite a deficit).

This is a genuine stock-flow-consistency gap inherited from GIM16. Stage B deliberately
**measures and reports** it rather than silencing it; closing it is a modeling change
(debt dynamics + recalibration) scheduled for a later phase, at which point the residual
can be promoted to an enforceable invariant.

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
