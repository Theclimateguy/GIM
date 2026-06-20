# GIM17 Work Log

Lean engineering log for the GIM16 → GIM17 modernization. One entry per stage:
decision, rationale, what changed, how it was verified. Read this first when resuming.

## Goal

Industry-grade **predictive** model that quantifies the weight of **natural capital**
(climate variables in particular) in economy, politics, and conflict. GIM16 is frozen as
the reference baseline; GIM17 is the evolving next version.

## Roadmap (phases)

- **Phase 0 — Foundation** (current): reproducibility, integrity invariants, balance
  closure, determinism, CI.
- **Phase 1 — Uncertainty**: ensemble/Monte-Carlo runtime, global sensitivity (Sobol/Morris),
  probabilistic outputs.
- **Phase 2 — Calibration & validation**: Bayesian/history-matching calibration on an
  extended panel; skill scoring vs. baselines (RMSE/CRPS, interval coverage).
- **Phase 3 — Welfare/SCC**: utility, discounting, calibrated damage function, optimization
  mode → endogenous social cost of carbon.
- **Phase 4 — Structural depth**: FAIR/MAGICC climate benchmarking, SSP/RCP alignment,
  optional regional/trade/financial detail.
- **Phase 5 — Benchmarking & paper**: reproduce DICE/RICE/E4A reference runs; document.

## Conventions

- Target runtime: **Python ≥ 3.10** (compatibility is a hard requirement).
- GIM16 is never modified. All work lands in `GIM17/`.
- Each stage is independently auditable and ends with a verification step.

## Git workflow (important)

The sandbox's FUSE mount cannot unlink files inside `.git/`, so it can make **only one
commit per session** before a stale `.git/index.lock` blocks further commits. Practically:
the agent commits Stage A; later stages are left **complete but uncommitted** in the working
tree, and you commit them natively on your Mac. Per stage, run in `GIM17/`:

```
rm -f .git/*.lock .git/objects/maintenance.lock && find .git/objects -name 'tmp_obj_*' -delete && git gc --prune=now
git add -A && git commit -m "<stage message>"
git push -u origin GIM17   # first push only; later: git push
```

Current state: **Stage A committed (`8b59f08`); Stage B complete but uncommitted** — commit
it with the message recorded in the Stage B entry below.

---

## Stage A — Bootstrap GIM17 + Python 3.10+ compatibility

**Status:** complete.

**Changes**
- Created `GIM17/` from GIM16 (code, data, docs, golden backtest artifacts).
  Excluded from the copy: `.git/`, `__pycache__/`, `*.pyc`, `results/` run folders
  (302 MB of regenerable artifacts), and the large regenerable raw archives under
  `data/agent_state_pipeline/cache/*.zip` (~98 MB). Result: 429 MB → 6 MB.
  `results/backtest/` (1.6 MB golden/OOS artifacts) was kept.
- `pyproject.toml`: name `gim17`, version `17.0.0.dev0`, `requires-python = ">=3.10"`.
- `gim/__init__.py`: `__version__ = "17.0.0.dev0"`.
- `gim/dashboard.py`: removed a `Δ` escape inside an f-string expression (illegal
  before Python 3.12) by using the literal `Δ`. This was the **only** hard syntax blocker
  preventing the package from importing on 3.10/3.11.
- `.gitignore`: keep `results/backtest/`, ignore other `results/` run folders.
- **Naming migration**: renamed `parameters_gim16.csv/.lock.json`, `GIM16_UNIFIED_MODEL_SPEC.md`,
  `gim16_dashboard_prototype.html`, `run_validation_package_gim16.sh` → `gim17` equivalents,
  and replaced `GIM16/gim16` → `GIM17/gim17` across all current source/docs/tests (41 files).
  Excluded from the replace: `docs/legacy/`, `misc/old_docs/`, golden `results/`, and this
  work log (which legitimately refers to GIM16 as the baseline).
- **Git**: `GIM17/` initialized as a git repo on branch `GIM17`, remote `origin` =
  `Theclimateguy/GIM`, clean-history initial commit (419 files). Object integrity verified
  (`git fsck --connectivity-only` clean).

**Verification (Python 3.10.12)**
- AST parse of every `gim/**/*.py`: 0 syntax errors (was 1: `dashboard.py`).
- `import gim` → `17.0.0.dev0`; world builds (57 actors); `python -m gim.core` 3-year run
  writes a valid `run_manifest.json`.
- Test suite: ~172 tests pass. The only 2 errors (`test_ui_server` manifest tests) occur
  **only in `TemporaryDirectory` teardown** because the sandbox's FUSE mount rejects
  fd-relative `os.unlink(..., dir_fd=...)` with EPERM. Reproduced: fd-relative unlink fails
  on the mount, succeeds on `/tmp`. This is an environment limitation, not a code defect,
  and does not occur on a native filesystem.

**Open items**
- The sandbox's FUSE mount cannot unlink files inside `.git/`, so the commit left empty
  lock files and `tmp_obj_*` clutter that don't affect integrity but block further git
  writes. **On the native macOS filesystem, run once before pushing:**
  `rm -f .git/*.lock .git/objects/maintenance.lock && find .git/objects -name 'tmp_obj_*' -delete && git gc --prune=now`
  then `git push -u origin GIM17`.

---

## Stage B — Invariant / accounting harness

**Status:** complete.

**What existed already**
- `simulation._invariant_report` already computed post-clamp bounds breaches and the
  EQ-INV-001 debt residual; `reconcile_critical_fields` already recorded a per-field
  `reconcile_adjustment` (final − raw). Both were only surfaced via `phase_trace`.

**Changes**
- New module `gim/core/invariants.py`: builds one compact, auditable record per year and
  separates **enforceable** invariants (bounds, reconcile-clamp tolerance,
  channel-telescope consistency) from the **diagnostic** debt fiscal residual. Adds a
  `strict` mode (`GIM17_INVARIANT_MODE` / `invariant_mode=`) that raises
  `InvariantViolation`, and an `aggregate_run` roll-up for the manifest.
- `simulation.py`: `_invariant_report` now also returns debt-residual aggregates
  (max/mean abs share, count); `step_world` gained `invariant_log` / `invariant_mode`
  params, builds the per-year summary, enforces strict mode, and logs it.
- `cli.py`: collects `invariant_log` and writes the roll-up into `run_manifest.json`
  under `invariants`.
- Docs: `docs/INVARIANTS.md` (modes, the three enforceable invariants, and **Finding B-1**).
- Tests: `tests/test_invariants.py` (13 tests) — clean enforceable invariants under the
  default scenario, strict-mode raises on injected bounds/clamp/telescope breaches,
  diagnostic residual reported-not-enforced, mode resolution, summary shape.

**Verification (Python 3.10)**
- 13 new tests pass; transition/contract/critical-write/smoke/results/equilibrium
  regressions green.
- Default-scenario manifest shows `invariants.enforceable.clean = true`
  (0 bounds breaches, reconcile clamp 0.0, channel telescope ≈1e-17).

**Finding B-1 (carried forward).** The clean fiscal debt identity does not hold:
`|Δdebt − (deficit + interest)| / GDP` reaches ~0.84/yr for some actors, driven by the
borrowing cap, debt zero-flooring in `economy.py`, and crisis debt shocks. Reported as a
diagnostic now; closing it is a debt-dynamics modeling change (+ recalibration) for a
later phase, after which it can be promoted to an enforceable invariant.

---

## Stage C — Global balance closure

**Status:** complete (uncommitted; commit natively per the Git workflow above).

**Changes**
- `simulation._invariant_report`: in the existing agent loop, accumulate world
  `net_exports`, GDP, and per-resource own_reserve / production / consumption; return two
  new sections — `trade_balance` (closed-economy check) and `resource_consistency`
  (per-resource diagnostic).
- `gim/core/invariants.py`: `trade_balance` is a new **enforceable** invariant
  (`|Σ net_exports| / world_gdp ≤ TRADE_BALANCE_TOL = 1e-6`); `resource_consistency` is a
  **diagnostic** rolled up as `diagnostic_resource_consistency` (Finding C-1). Both flow
  into `summarize_step`, `evaluate_violations`, `aggregate_run`, and the per-year table.
- Docs: `docs/INVARIANTS.md` extended (trade invariant + resource diagnostic + Finding C-1).
- Tests: `tests/test_invariants.py` now 18 tests (added trade-closure clean, strict-raises
  on injected trade imbalance, resource diagnostic present/flagged, not-enforced).

**Verification (Python 3.10)**
- 18 invariants tests pass. Manifest on the default scenario:
  `enforceable.clean = true`, `max_trade_balance_abs_share = 0.0`;
  `diagnostic_resource_consistency.pools_exhausted_with_active_production = ["food","metals"]`.

**Finding C-1 (carried forward).** `global_reserves` is dimensionally inconsistent with the
summed country `own_reserve`: energy global ≈ 32.5 vs ≈ 1.16e5 summed (ratio ~3e-4), and
food/metals global pools floor at 0 within one year. Only energy's global reserve is
coherent. Reconciling the global resource ledger with per-country reserves is a later-phase
modeling change. The trade balance, by contrast, is a true closed invariant and holds exactly.

---

## Stage D — Determinism

**Status:** complete (uncommitted; commit natively per the Git workflow above).

**Problem found.** Two core channels drew from the process-global `random` module rather
than a world-scoped RNG: climate extreme events (`climate.py`) and the geopolitical
security-action roll (`geopolitics.py`). So a bare `step_world` was non-reproducible and
parallel ensemble members would interfere via shared global RNG state. Only temperature
variability was properly seeded.

**Changes**
- New `gim/core/rng.py`: `seed_world(world, seed)` / `get_rng(world)` — a single seeded
  `random.Random` on the world (default master seed 0; syncs the temperature seed).
- `geopolitics.py`, `climate.py`: stochastic draws now use `get_rng(world)`.
- `world_factory.py`: initialise `_sim_seed = 0`.
- `cli.py`: `SIM_SEED` now routes through `seed_world`; **policy default changed
  `auto` → `simple`** so scientific/CI runs are deterministic unless `POLICY_MODE=llm` is
  set explicitly. Removed the now-unused global `random` import.
- Docs: `docs/DETERMINISM.md`.
- Tests: `tests/test_determinism.py` (6 tests) — same seed → identical trajectory;
  independence from global RNG state; default-seed reproducibility; RNG unit checks.

**Verification (Python 3.10)**
- 6 determinism tests pass. **Backtest golden RMSEs unchanged** (GDP 1.025, CO2 1.605,
  Temp 0.138) — the refactor does not perturb the calibration. Broad regression green
  (core/contracts/invariants/crisis/calibration/climate-energy/hybrid).

**Known residual.** `hybrid_simulator.py`, `state_projection.py`, and `game_theory/` still
seed the global `random` module (reproducible in isolation, not yet world-isolated);
migrate if they enter scientific/ensemble pipelines.

---

## Stage E — CI + lockfile + strict-invariants gate

**Status:** complete (uncommitted; commit natively per the Git workflow above). Closes Phase 0.

**Changes**
- `pyproject.toml`: core `dependencies = []` (the runtime is **standard-library only**);
  optional extras `llm` (requests), `analysis` (numpy, pandas), `viz` (matplotlib), and
  `dev` (all of the above).
- `requirements-lock.txt`: reference pins of the optional/dev deps (real PyPI releases;
  the sandbox's installed versions are synthetic/future-dated and intentionally not used).
- `scripts/check_invariants.py`: fast strict-mode gate — runs 10y × full actor set with
  `invariant_mode="strict"` and exits non-zero on any enforceable breach.
- `.github/workflows/ci.yml`:
  - `test` job — matrix Python **3.10 / 3.13**, `pip install ".[dev]"`, full `unittest`.
  - `invariants` job — strict gate (`scripts/check_invariants.py`) + invariant/determinism
    unit tests, separate from the LLM-capable suite.

**Verification (Python 3.10)**
- `pyproject.toml` parses; extras present; `ci.yml` is valid YAML.
- Strict gate exits 0 (`enforceable.clean = true`, 10y × 57 actors).
- CI gate unit tests (`test_invariants` + `test_determinism`) pass (24 tests).
- Editable/wheel build could not be exercised in-sandbox (its setuptools predates PEP 621,
  so it reports `UNKNOWN-0.0.0`, and the mount blocks `build/` writes). CI uses build
  isolation with `setuptools>=68`, which reads `[project]` correctly; config validated
  structurally.

**CI fix (post-push).** First CI run failed: `test_geo_calibration` →
`FileNotFoundError: tests/fixtures/baseline_evaluation.json`. Root cause: the `.gitignore`
artifact pattern `*_evaluation.json` also matched that committed test fixture, so it was
never pushed (it existed locally, so every local run passed — the failure only surfaced on
a clean CI checkout). Fix: added `!tests/fixtures/**` to `.gitignore` and committed the
fixture (commit `6aa86f6`). All 196 tests otherwise passed (2 `scipy` skips are expected).

## Phase 0 — done

GIM17 now has: Python 3.10+ portability, a clean lean repo, an enforceable
accounting/integrity invariant layer (bounds, reconcile-clamp, channel-telescope, trade
balance) with diagnostics surfacing Findings B-1 (debt) and C-1 (resources), deterministic
reproducible runs, and CI gating it all. Foundations are in place for Phase 1 (uncertainty
quantification).

---

# Phase 1 — Uncertainty quantification

## P1-A — Per-run ParameterSet refactor (option B2)

**Status:** complete (uncommitted).

**Goal.** Move model parameters off the process-global `calibration_params` module onto an
immutable per-run context so Monte-Carlo ensemble members can vary parameters in parallel
without global mutation. Chosen realization: **B2** — an immutable `ParameterSet` carried on
the already-threaded `WorldState`.

**Changes**
- New `gim/core/params.py`: `ParameterSet` (immutable, attribute access, `with_overrides()`
  with unknown-key validation, `__deepcopy__` returns self); `build_params()` (fresh snapshot
  of current `calibration_params`, uncached) and `default_params()` (cached fallback);
  `resolve_params(world)`.
- `world.params` is attached at runtime by `world_factory` via `build_params()` — **not** a
  dataclass field, so it is excluded from `dataclasses.asdict()` (snapshots stay JSON-safe).
- All **337** `cal.X` reads across 8 core modules now resolve per-run: world-scoped functions
  rebind `cal = resolve_params(world)`; 10 world-less helpers take an explicit `params` arg
  threaded from their callers. AST audit confirms zero remaining global-`cal` reads on the
  hot path.
- `world_factory` uses the *fresh* `build_params()` so calibration harnesses that mutate
  `calibration_params` (e.g. the decarb-rate backtest's `_temporary_decarb_rate`) are still
  reflected in freshly-built worlds.
- Tests adapted: `test_climate_forcing` now overrides `world.params` instead of mutating the
  module. New `tests/test_params.py` (10 tests) proves immutability, override validation,
  serialization exclusion, and — decisively — that overriding `world.params` changes outputs
  (CO2 via `EMISSIONS_SCALE`, GDP via `ALPHA_CAPITAL`) while a same-value override is an exact
  identity.

**Verification (Python 3.10).** Backtest golden RMSEs unchanged (1.025 / 1.605 / 0.138);
decarb-sensitivity candidates still differentiate; full suite green; strict invariants clean;
determinism intact. Behaviour-preserving with the parameter context fully wired.

## P1-B — Literature-grounded parameter priors

**Status:** complete (uncommitted).

**Changes**
- `data/parameter_priors.csv`: ~18 key climate-economy priors, each with an explicit source and
  rationale, **validated against authoritative consensus** via the research connectors:
  ECS (IPCC AR6 WG1 — 3.0 best, 2.0–5.0 very likely); damage coefficient (DICE-2016R2 0.00236
  → Howard-Sterner 6.7–8.3%/3 °C → RFF 7–10%); production elasticities & depreciation
  (PWT/Gollin); two-layer EBM heat capacities (Geoffroy et al. 2013 / DICE); emissions scale
  (GCP 2023); demographics (WDI 2023). ECS and the damage coefficient use lognormals for their
  right-skew.
- `gim/core/priors.py`: `Prior` (truncated normal/lognormal/triangular/uniform/fixed),
  `key_priors()` (literature core), `all_priors()` (adds tag-derived bounded bands for the long
  tail; skips carbon-pool vectors and `*_MAX/_MIN/_CAP/_FLOOR`), and
  `sample_parameter_set(base, priors, rng)` producing an immutable per-run `ParameterSet`.
- Docs: `docs/PRIORS.md`. Tests: `tests/test_priors.py` (10) assert well-formedness + sourcing,
  bound-respecting samples, and that the samples reproduce the published central estimates and
  ranges (ECS median 3.0 with 2.5–4.0 inside 5–95%; damage spanning DICE→Howard-Sterner).

**Verification.** Priors tests green; statistical sanity (ECS 5–95% ≈ [1.9, 4.7]; damage 5–95% ≈
[0.0029, 0.0125]); core suite + backtest unchanged. Ready to feed the P1-C ensemble.

## P1-C — Monte-Carlo ensemble runtime

**Status:** complete (uncommitted).

**Changes**
- `gim/ensemble.py`: `run_ensemble(EnsembleConfig)` samples priors into a per-run
  `world.params`, runs N independent members (member `i` seeded from `(master_seed, i)`),
  collects 8 headline metrics per year, and aggregates into percentile fan bands
  (`p5/p25/p50/p75/p95/mean`). Serial or `ProcessPoolExecutor` parallel; results are
  order-independent. `default` N=500.
- `scripts/run_ensemble.py`: env-driven CLI writing `results/ensemble-<ts>/ensemble.json` +
  manifest. Docs: `docs/UNCERTAINTY.md`. Tests: `tests/test_ensemble.py` (7).

**Verification.** Fan bands form with real spread (temperature ±~0.4 °C from ECS/heat-capacity
priors). **Serial and parallel runs are bit-for-bit identical**; same seed reproducible, different
seed differs. Pure-Python percentiles (no numpy dependency in core). Backtest/core unchanged.

## P1-D — Global sensitivity analysis

**Status:** complete (uncommitted).

**Changes**
- `gim/sensitivity.py`: native-numpy **Morris** elementary effects (mu*/sigma screening) and
  **Sobol** indices (S1/ST via Saltelli-2010/Jansen estimators) — no SALib dependency. Model
  wrapped as a deterministic scalar function of a parameter vector (fixed world seed); factor
  ranges = prior bounds. `make_output_fn`, `rank`, `bounds_for` helpers.
- `scripts/run_sensitivity.py` (env-driven CLI, saves ranked `sensitivity.json`); docs section
  in `docs/UNCERTAINTY.md`. Tests: `tests/test_sensitivity.py` (6).

**Verification.** **Sobol validated against the analytical Ishigami benchmark**: S1 ≈
[0.325, 0.454, −0.005] vs [0.314, 0.442, 0]; ST ≈ [0.577, 0.443, 0.252] vs [0.557, 0.442, 0.244];
x3 pure-interaction captured. Morris ranks x1 most influential and flags x3 interaction via
sigma. Real model: `HEAT_CAP_SURFACE` + `ECS_DEFAULT` dominate short-horizon temperature
sensitivity (physically correct). Only new dependency is numpy (already in the analysis/dev
extras); core stays stdlib-only.

## P1-E / P1-F — Probabilistic outputs, tests & CI

**Status:** complete (uncommitted). Closes Phase 1.

**Changes**
- `gim/fan_charts.py`: `render_fan_charts(result)` → self-contained HTML with one SVG panel per
  headline metric (5–95% and 25–75% bands + median line), pure SVG, no plotting dependency.
- `scripts/run_ensemble.py` now writes `fan_charts.html` next to `ensemble.json`; manifest carries
  final-year p5/p50/p95.
- CI (`.github/workflows/ci.yml`): the fast core-only gate now also runs `test_params`,
  `test_priors`, `test_ensemble`; the full matrix job (with dev extras / numpy) covers
  `test_sensitivity` and `test_fan_charts` via discovery.
- Tests: `tests/test_fan_charts.py` (4). Docs: `docs/UNCERTAINTY.md` updated.

**Verification.** Fan charts render (8-panel HTML; e.g. 40-member/8-year temperature fan
1.02/1.32/1.64). All Phase-1 tests green; backtest golden RMSEs unchanged.

## Phase 1 — done

GIM17 is now a **probabilistic** simulator: literature-grounded priors (validated vs IPCC AR6 /
DICE / Howard-Sterner / PWT / GCP) → immutable per-run parameter context → reproducible
Monte-Carlo ensemble (serial==parallel) → Morris/Sobol sensitivity (Ishigami-validated) →
fan-chart outputs. Point forecasts are replaced by distributions, and every step is
deterministic and CI-gated. Foundations are in place for Phase 2 (formal calibration &
validation), which can now target the parameters sensitivity flags as the real drivers.

---

# Phase 2 — Calibration & validation

## P2-A — Skill scoring + baselines

**Status:** complete (uncommitted).

- `gim/scoring.py`: RMSE/MAE, **CRPS** (ensemble proper score), interval coverage, persistence
  + naive-trend baselines, skill scores. `scripts/run_scoring.py`; `tests/test_scoring.py` (9).
- **Finding:** on the 2015–2023 backtest (anchored 2015), the model beats persistence on
  temperature (skill ≈ +0.14) and marginally on GDP, but loses to a naive linear trend for GDP
  and CO₂ over the short window — the honest, baseline-grounded picture.

## P2-B — History-matching calibration

**Status:** complete (uncommitted).

- `gim/calibration_hm.py`: implausibility scoring of prior draws vs observations → NROY
  posterior; per-parameter constraints. Threaded a parallel-safe `params_override` through
  `run_historical_backtest`. `scripts/run_calibration.py`; `tests/test_calibration_hm.py` (6).
- **Finding:** production params (`GAMMA_ENERGY`, `ALPHA_CAPITAL`, `EMISSIONS_SCALE`) are
  constrained most by the backtest; climate-response params (`ECS`, `HEAT_CAP_SURFACE`,
  `DECARB_RATE_STRUCTURAL`) are weakly identified over 8 years — consistent with P1-D sensitivity.

## P2-C/D — Docs & CI

- `docs/VALIDATION.md`; fast CI gate now also runs `test_scoring`; backtest golden RMSEs
  unchanged after the `params_override` addition.
- `calibration_hm.constrained_priors()` closes the loop: an NROY posterior becomes priors
  (calibrated params restricted to their NROY range) that feed `gim.ensemble` directly for a
  tightened, calibrated projection. The full forward calibrated ensemble is a production run
  (`run_calibration.py` → constrained priors → `run_ensemble.py`).

## Phase 2 — status

P2-A (scoring + baselines) and P2-B (history-matching calibration) complete and pushed; the
calibration→ensemble loop is wired via `constrained_priors`. Remaining for a full Phase 2:
a longer observation panel (pre-2015) for stronger out-of-sample identification, and a
large-sample production calibration run.

---

# Phase 3 — Welfare & Social Cost of Carbon

**Status:** P3-A/B/C complete (uncommitted). The DICE/RICE valuation layer.

**Changes**
- New params `ELASTICITY_MARGINAL_UTILITY` (η=1.45) and `PURE_TIME_PREFERENCE` (ρ=0.015),
  DICE-2016R2 defaults, with literature priors spanning the Nordhaus↔Stern debate.
- `gim/welfare.py` (P3-A): consumption from GDP/savings, CRRA utility, Ramsey-discounted social
  welfare. `gim/scc.py` (P3-B): marginal CO₂-pulse SCC (FAIR-style pool injection, common random
  numbers); (P3-C) `scc_distribution` propagates the climate-economy + discounting priors → an
  SCC distribution. `scripts/run_scc.py`; `docs/WELFARE_SCC.md`.
- Tests: `tests/test_welfare.py` (4), `tests/test_scc.py` (5). CI fast gate runs `test_welfare`.

**Results.** Central **SCC ≈ $22/tCO₂** (30-year horizon); probabilistic SCC right-skewed
(median ≈ $13, p95 ≈ $32) — the characteristic IAM shape. SCC is **linear in pulse size**
(marginality confirmed) and deterministic. Level is horizon-sensitive (30y truncates long-run
damages; sits at the lower end of the DICE→EPA range, which a multi-century horizon would raise).
Backtest golden RMSEs unchanged.

**Remaining for full Phase 3:** multi-century horizon for a DICE-comparable SCC level; optional
welfare-optimization mode (optimal mitigation maximizing W).

---

# Tier 1 — Structural integrity (peer-review-driven, blocks Phase 4)

A June-2026 academic peer review re-prioritized the roadmap: Tier-1 macro-accounting fixes
must precede Phase 4. (It also mis-stated GIM's damage as "1/4 of DICE" — actually ~2.5×;
the low $22 SCC is purely the 30-year horizon, confirmed: 30y→$17, 100y→$54, 200y→$63.)

## T1.1 — Debt stock-flow identity (resolves Finding B-1)

**Status:** complete (uncommitted).

**Problem.** `Δdebt − [(gov_spending−taxes)+interest]` left a residual reaching ~0.84·GDP/yr
(IRN/RUS/DEU): the borrowing cap, the zero-floor, and the discrete crisis "haircut" all moved
debt outside the fiscal identity — a Godley-Lavoie stock-flow inconsistency.

**Fix (accounting only — debt values unchanged).** A per-step **debt-flow ledger**
(`critical_pending.py`: `record_debt_flow`/`get_debt_flows`/`reset_debt_flows`) records every
`public_debt` write by source: `fiscal` (economy), `restructuring` (the now-explicit crisis
haircut, social), `policy` (actions), `institution` (bailout grants). The four module debt
writers were instrumented; `simulation._invariant_report` computes the residual as
`Δdebt − Σ(flows)`.

**Result.** Residual **0.84 → 1.6e-16**. Promoted to an **enforceable** invariant
(`debt_identity`, tol 1e-9) in the `enforceable.clean` gate. Backtest golden RMSEs unchanged;
strict gate clean; 3 new tests. Docs: `docs/INVARIANTS.md` (B-1 marked RESOLVED).
**Remaining:** the restructuring lacks a bilateral creditor counterpart (Phase-4 financial sector).

## T1.4 — SCC multi-horizon reporting

**Status:** complete (horizon part; damage cross-validation remains).

`gim/scc.scc_multi_horizon()` reports the central SCC at several integration horizons; the run
script and `docs/WELFARE_SCC.md` now report **30y ≈ $17, 100y ≈ $54, 200y ≈ $63**. This proves
the low headline SCC is purely the 30-year horizon (not low damages — GIM's 0.006 → 5.4%/3 °C
is ~2.5× DICE). Test asserts SCC rises with horizon. **Remaining T1.4:** cross-validate the
damage coefficients against Burke 2015 / Hsiang 2017 / Howard-Sterner 2017.

## T1.2 — Coherent global resource ledger (resolves Finding C-1)

**Status:** complete (uncommitted).

**Problem.** `global_reserves` was tracked on a separate, divergent path from the country
`own_reserve` ledgers; the food/metals global pools (init 100) floored at 0 within one year,
and the energy pool sat at ~3e-4 of the summed country reserves.

**De-risking finding.** `global_reserves` only feeds the `reserve_zj` field of
`allocate_energy_reserves_and_caps`, which is **never read** — energy production uses
`prod_cap_zj_per_year` (from `WORLD_ANNUAL_SUPPLY_CAP_ZJ` × country shares) and country
`own_reserve`. So `global_reserves` drives no dynamics → the fix is behaviour-preserving.

**Fix.** `global_reserves[r]` is now the coherent aggregate `Σ_i own_reserve[r]`, set at world
build (`world_factory`) and re-synced each year (`resources.sync_global_reserves_from_agents`,
replacing the old divergent global update). Ratio is now exactly 1.0; no pool floors at 0.
Promoted to an **enforceable** `resource_ledger` invariant (tol 1e-9) in `enforceable.clean`.
Backtest golden RMSEs unchanged; strict gate clean; `docs/INVARIANTS.md` C-1 RESOLVED; the
old Stage-C "flags C-1" test updated to assert coherence.

## T1.3 — Long-window climate calibration (1990-2023)

**Decision.** Add an observational window long enough to identify the climate-response
parameters (the peer review flagged ECS as unconstrained over the 8-year economic
window). Built a climate-only backtest that reuses the exact production carbon cycle +
two-box EBM, spun up free-running from the 1750 pre-industrial state under observed
emissions; only 1990-2023 is scored.

**Data (primary sources, validated).** GCB fossil+cement CO2 1750-2024 (OWID OWID_WRL,
`data/global_co2_emissions_owid.csv`; cumulative 1750-2023 = 494 GtC, matches GCB);
NOAA GML CO2 ppm; HadCRUT.5.1.0.0 temperature rebased to 1850-1900 with a fixed offset
that reproduces the legacy 2015-2023 fixture bit-for-bit. Built by
`scripts/build_climate_observations.py`.

**Findings.** (1) Emission-driven CO2 runs ~10 ppm low — the missing land-use-change
source (model is fossil-only). (2) Concentration-driven, the 34-year window has a clear
interior temperature-RMSE minimum at **ECS = 3.0** (AR6 central) once surface heat
capacity is at its physical ~8. (3) The production `HEAT_CAP_SURFACE = 18` is a
short-window artifact: it fits 2015-2023 marginally better (noise) but over-damps the
multi-decadal transient and, left free, pushes ECS to the 4C ceiling.

**Changed.** New `gim/climate_backtest.py` (emission + concentration modes, ECS sweep,
best_ecs); added inert `prescribed_co2_gt` hook to `update_global_climate` for
concentration-driven forcing (golden backtest RMSEs unchanged: 1.025/1.605/0.138);
`tests/test_climate_backtest.py` (7 tests); enriched ECS/HEAT_CAP_SURFACE prior
rationales with the observational evidence (prior numerics unchanged — no ensemble
disturbance); `docs/CLIMATE_BACKTEST.md`.

**Deferred (documented, not applied).** Joint multi-window recalibration of
{ECS, heat capacities, ocean exchange} against trend (1990-2023) + levels (2015-2023),
moving HEAT_CAP_SURFACE to its physical value — a deliberate calibration decision, since
lowering it in isolation worsens the short-window golden RMSE.

## T1.3b — Joint multi-window climate recalibration

**Decision.** T1.3 showed the long window wants a physical surface heat capacity (~8)
while the short window had been fit with 18. Rather than leave the tension documented,
ran a constrained joint search over {ECS, HEAT_CAP_SURFACE, OCEAN_EXCHANGE} minimising
the 1990-2023 concentration-driven temperature RMSE subject to the 2015-2023 economic
gates (temp RMSE < 0.15, |bias| < 0.02).

**Result.** A feasible optimum improves BOTH windows at physical values:
`HEAT_CAP_SURFACE 18->8`, `OCEAN_EXCHANGE 0.7->1.0` (ECS unchanged at 3.0). Stronger ocean
heat uptake damps the short-window overshoot the faster surface response would cause.
Long-window temp RMSE 0.237->0.161; economic temp RMSE 0.138->0.134 (bias +0.012);
GDP/CO2 RMSE essentially unchanged (1.026/1.606). SCC 200-yr ~$56->~$48 (heat drawn deeper).

**Changed.** `calibration_params.py` (the two values); `data/parameter_priors.csv` (priors
recentred on the physical values); regenerated `tests/fixtures/historical_backtest_baseline.json`
and the `GOLDEN` constants in `tests/test_historical_backtest.py`; pinned the long-window ECS
identification test to its original (cap=8, oex=0.7) configuration so it is independent of the
new production defaults; updated `docs/CLIMATE_BACKTEST.md` and `docs/WELFARE_SCC.md`.
Verified: historical/climate/forcing/scc/welfare/invariants/params/priors + calibration,
decarb, equilibrium, projection, contract suites all green (~150 tests).

## P4-A — Endogenous inflation & unemployment (Phillips + Okun)

**Decision.** `economy.inflation` and `economy.unemployment` drive social tension, trust
and political stability but were static (only discrete crisis hits). Gave them a law of
motion so they respond to the output gap and to climate/resource price shocks - closing
the loop climate damage -> energy price -> inflation/unemployment -> social tension ->
instability (the model's core thesis).

**Changed.** New `gim/core/labor_market.py` (`update_inflation_unemployment`): Okun's law
for unemployment (partial adjustment to a growth-gap target) + expectations-augmented
Phillips curve for inflation (anchored adaptive expectations, flat unemployment-gap slope,
energy cost-push). Wired into `simulation.py` after the economy/finance updates, before
the social block. Added calibration block (POTENTIAL_OUTPUT_GROWTH, NAIRU, OKUN_COEFF,
PHILLIPS_SLOPE, INFLATION_COSTPUSH_COEFF, bounds, ...). `tests/test_labor_market.py`
(7 tests); `docs/LABOR_MARKET.md`.

**Verified.** 2015-2023 economic backtest golden values unchanged (1.026/1.606/0.134);
invariants/determinism/contracts/crisis/hybrid/equilibrium/projection suites all green
(~120 tests).

## P4-B — Multi-GHG non-CO2 forcing decomposition

**Decision.** The non-CO2 forcing was a single lumped linear term. Decompose it into
AR6/IGCC-anchored components (CH4, N2O, halocarbons, O3, aerosols, minor) exposed as
per-gas scenario/policy levers, WITHOUT changing the default net (so the T1.3b climate
calibration and backtest golden values stay put).

**Changed.** New `gim/core/forcing.py`: `NONCO2_ERF_REFERENCE` (AR6 ~2019 component ERF,
net +0.57), `nonco2_forcing` (default == lumped path; `component_scales` perturb a gas's
AR6 contribution), `nonco2_forcing_components` (sign-correct attribution summing to net),
`set_nonco2_component_scales` (world lever). Rewired `climate._resolve_nonco2_forcing` to
delegate and read world levers. `tests/test_forcing.py` (11 tests, incl. an end-to-end
methane-cut-runs-cooler integration); `docs/MULTI_GHG_FORCING.md`.

**Verified.** Default net bit-identical to the old formula at 1990/2015/2019/2023/2050;
golden backtest unchanged (1.026/1.606/0.134); forcing/climate/backtest/invariants/
determinism suites green (55 tests).

**Deferred (P4-B2).** Adopt the full AR6 net (~+0.11 W/m2 higher) with annual per-component
series - shifts the trajectory, so it must ride with a climate recalibration.

## T1.4 — Damage-function cross-validation (closes THE-19 remaining)

**Decision.** The damage coefficient is the dominant driver of the SCC spread across IAMs.
Pin GIM's choice to the world empirical literature explicitly and guard it with a test,
rather than leave it an unexamined number. Represent the deep uncertainty honestly instead
of point-picking.

**Evidence (validated from primary sources).** Level-effect quadratic loss = a*T^2 at 3C:
DICE-2016R2 0.00236 (2.1%); DICE-2013R 0.00267 (2.4%); GIM 0.006 (5.4%); Howard-Sterner
2017 preferred 0.0078-0.0089 (7-8%), +catastrophic 0.010-0.011 (9-10%); prior meta-analysis
span 0.0021-0.0192 (1.9-17.3%). Growth-effect studies (Burke 2015 ~23%/2100; Kotz 2024
RETRACTED) imply a fatter upper tail not captured by a level multiplier.

**Finding.** GIM (0.006) sits inside the empirical envelope at +2/+3/+4C, above DICE
(answering the "IAMs lowball damages" critique) and below the Howard-Sterner preferred
central. Defensible as-is; coefficient unchanged. Because GIM is a level-effect multiplier,
its damages are likely a lower bound on the growth-effect estimates - documented, and
reflected in the right-skewed lognormal prior.

**Changed.** New `gim/damage_validation.py` (evidence table, GIM-vs-literature comparison,
empirical envelope + `gim_within_envelope` guard); `tests/test_damage_validation.py`
(7 tests, incl. retraction flag + envelope bracketing); enriched `DAMAGE_QUAD_COEFF` prior
rationale; `docs/DAMAGE_FUNCTION.md`. SCC / golden backtest unchanged (coefficient unchanged).

## Phase 4 remainder (autonomous)

### T2.4 — AR(1) red-noise temperature variability
Replaced iid Gaussian internal variability with an AR(1) process
w_t = rho*w_{t-1} + sqrt(1-rho^2)*sigma*sqrt(dt)*eps_t (rho=TEMP_NATURAL_VARIABILITY_AR1_RHO=0.65;
rho=0 reproduces iid). sqrt(1-rho^2) keeps the stationary std = sigma, so per-year marginal
variance (what the backtest scores) is preserved while year-to-year correlation becomes
physical (ENSO-like). Unsigned state carried on global_state; antithetic `sign` applied at
output so mirror ensemble members stay exact negatives. Verified: lag-1 autocorr ~0.70,
std ~0.088, antithetic mirror exact, deterministic; golden backtest unchanged
(1.026/1.606/0.134). `tests/test_temperature_variability.py` (5 tests).

### P4-C — Taylor-rule monetary policy
compute_effective_interest_rate's neutral base rate now follows a Taylor rule:
base = BASE_INTEREST_RATE + PHI_PI*(inflation - target) + PHI_Y*(NAIRU - unemployment),
capped at +-TAYLOR_DEVIATION_CAP and floored at 0. Zero deviation at inflation==target and
u==NAIRU, so the calibration steady state (and the golden backtest) are preserved; closes the
central-bank loop on P4-A (inflation up / economy hot -> CB hikes -> higher debt service).
Disable-able via the `monetary_policy_feedback` channel. tests/test_monetary_policy.py
(5 tests); golden backtest unchanged.

### T2.6 — World-isolate remaining global RNG
Replaced the last global-`random` users with world-scoped RNG: state_projection and
hybrid_simulator now call `seed_world(world, seed)` instead of `random.seed(...)`;
game_theory/equilibrium_runner `_hedge_select` draws from `get_rng(world)` instead of the
global `random` module. Dropped the now-dead `import random`. Determinism preserved
(same seed -> identical trajectory); equilibrium/state_projection/determinism suites green.

### T2.1 + benchmark — SSP/RCP alignment & FAIR/MAGICC emulator check
New gim/scenario_alignment.py. (1) Emulator benchmark: GIM ECS=3.0 (AR6 best) and TCR=1.79
(AR6 1.8, likely 1.4-2.2) - measured by the idealised 1%/yr-to-doubling ramp, forced response
only. Matching both ECS and TCR is the FAIR/MAGICC bar; GIM passes. (2) AR6 SSP 2100 warming
envelopes (SPM.1) + classify_warming/closest_ssp. Finding: GIM's strongly-decarbonising
"simple" baseline (~2.0C at 2100, CO2 28->2 GtCO2) is closest to SSP1-2.6; producing a
no-policy SSP2-4.5/3-7.0 reference needs a scenario-driver preset (Phase-5).
Caught during build: an apparent EBM non-monotonicity in the TCR ramp was internal AR(1)
variability noise, not instability - the forced response is monotonic (variability disabled
for TCR). tests/test_scenario_alignment.py (6 tests); docs/SCENARIO_ALIGNMENT.md.
