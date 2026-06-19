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
