# GIM15 Remediation Plan from Validator Reports (Physics + LLM)

Date: 2026-03-17  
Sources:
- `/Users/theclimateguy/Downloads/gim14_validation_report.docx`
- `/Users/theclimateguy/Downloads/gim14_llm_validation_report.docx`

This plan maps GIM14 validator findings onto current GIM15 code, separating:
- already addressed in GIM15,
- partially addressed,
- still open and required before release hardening.

## 1) Release Hygiene Decisions (agreed)

- Web UI visualization is excluded from release scope.
- `ui/` is now ignored in git via `.gitignore`.
- Core CLI/model artifacts remain under `results/<run_id>/...` through `build_run_artifacts()` and `resolve_run_output_path()`.

## 2) Finding Status Matrix (GIM14 report -> GIM15 state)

1. Q9 Actor inference coverage (aliases/group entities): **PARTIAL / OPEN**
- Current aliases are still narrow in `gim/scenario_compiler.py` (`US/China/Japan/...` only).
- Missing group/entity mapping requested by validators (BRICS, OPEC, G7, G20, ASEAN, EU, NATO, MENA, Sub-Saharan Africa, Gulf states).
- No explicit confidence flag showing explicit match vs GDP fallback.

2. T2 Parameter sensitivity dead zones: **PARTIAL**
- GIM15 already has rolling backtest + stage calibration harness.
- But no explicit re-run protocol for “simple vs growth/llm” sensitivity decomposition tied to this finding.
- Need a formal “active/inert by mode” parameter registry and report.

3. T3 Crisis pathway replication (Argentina overshoot, Turkey FX channel): **OPEN**
- `DEBT_CRISIS_GDP_MULT=0.90`, `DEBT_CRISIS_DEBT_MULT=0.60` unchanged in `gim/core/calibration_params.py`.
- Debt crisis still activated by debt/interest thresholds in `gim/core/social.py`.
- Dedicated FX-crisis trigger path remains absent in transition logic (metrics exist, trigger path does not).

4. T5 Outcome taxonomy mislabeling near-miss (economic crises mapped to military labels): **OPEN**
- Risk classes in `gim/types.py` remain the 8 legacy classes.
- No `sovereign_financial_crisis` / `social_unrest_without_military` class yet.
- Geo calibration and payoff matrices still tuned around legacy taxonomy.

5. T4 Bilateral trust asymmetry drift: **OPEN**
- Directed relation updates remain in `gim/core/political_dynamics.py` without explicit symmetric dampening term.

6. LLM T9 Strategic divergence too weak: **OPEN (high priority)**
- `gim/core/policy.py` still uses:
  - narrow numeric bounds (`social [-0.015,+0.02]`, `mil [-0.01,+0.015]`),
  - prompt instruction “Use small, incremental changes”,
  - temperature `0.2`.
- `apply_political_constraints()` still applies strong damping `scale = 0.4 + 0.6*policy_space`.

7. LLM T8 Coherence edge case (debt stress vs military exceptions): **PARTIAL**
- Constraint logic exists, but no explicit codified exception rule tied to security margin/conflict context in validator terms.

8. Numerical core stability / 4-phase causality / write-audit concerns: **ADDRESSED in GIM15**
- Four-phase transition architecture and critical-write guard migration are in place.

### Progress update (2026-03-17, local branch)

- WP1 LLM strategic activation: **DONE**
- WP2 actor inference confidence metadata: **DONE**
- WP3 outcome taxonomy expansion (`sovereign_financial_crisis`, `social_unrest_without_military`): **DONE**
- WP4 debt/FX crisis pathways: **DONE**
- WP5 bilateral asymmetry stabilizer (trust/conflict damping + stronger mean reversion): **DONE**
- WP6 re-validation package:
  - non-LLM snapshot (`simple`, `growth`) for `operational_v2`: **DONE**, results in `results/validation/non_llm/wp3_wp5_2026-03-17/`
  - reproducible runner script: `scripts/run_validation_package_v15.sh`
  - latest rerun package: `results/validation/non_llm/wp3_wp5_package_2026-03-17/`
  - explicit LLM-mode revalidation with live-provider uncertainty: **DEFERRED** by operator decision.

## 3) New Work Packages (execution order)

## WP0. Guardrails for release integrity (small, immediate)

Goal: keep release clean and deterministic.

Tasks:
- Keep `ui/` ignored (done).
- Add/update CLI smoke tests to assert artifacts always written under `results/<run_id>/...` for `question/game/world` when custom path not absolute.
- Ensure manifest output paths remain absolute-resolved entries in `run_manifest.json`.

Acceptance:
- `tests/test_results_artifacts.py` (or equivalent) passes with explicit checks for `results/<run_id>/`.

## WP1. LLM strategic activation recalibration (critical)

Goal: make LLM materially different from simple policy without physics breaks.

Tasks:
- In `gim/core/policy.py`:
  - widen bounds:
    - `social_spending_change` to `[-0.03, +0.04]`,
    - `military_spending_change` to `[-0.02, +0.03]`.
  - remove/replace “small, incremental” instruction with severity-proportional rule.
  - relax coercion activation threshold (conflict/trust gate) to increase meaningful foreign-policy actions.
  - raise LLM temperature to `0.4` baseline (configurable env override).
- In `gim/core/political_dynamics.py`:
  - soften damping: `scale = 0.6 + 0.4*policy_space`.
  - recheck sanctions filtering thresholds against observed zero-sanction pathology.

Acceptance:
- Re-run LLM validation subset (T9/T8 equivalents):
  - GDP divergence vs simple materially above prior 0.13%.
  - non-zero sanctions/security actions in stressed scenarios.
  - sanity bounds still pass.

## WP2. Scenario compiler inference quality + confidence exposure

Goal: avoid silent wrong actor resolution.

Tasks:
- Extend alias/group dictionary in `gim/scenario_compiler.py`.
- Add explicit inference metadata in scenario payload:
  - match type (`explicit`, `alias`, `group_expansion`, `gdp_fallback`),
  - confidence score/band.
- Surface this metadata in dashboard/brief narrative.

Acceptance:
- New unit tests for known prompts:
  - Sub-Saharan Africa drought,
  - BRICS dollar abandonment,
  - MENA/Gulf energy shock.

## WP3. Outcome taxonomy expansion for economic crises

Goal: separate financial/social crises from military escalation buckets.

Tasks:
- Add new risk classes in `gim/types.py`:
  - `sovereign_financial_crisis`,
  - `social_unrest_without_military`.
- Update:
  - `geo_calibration.py` (intercepts/drivers/links),
  - `game_runner.py` scoring and explanation paths,
  - `dashboard.py`, `briefing.py`, `decision_language.py`.
- Migrate calibration fixtures and validator expectations.

Acceptance:
- Near-miss suite accuracy uplift vs GIM14 baseline.
- Stable-control non-status-quo mass reduced to acceptable range.

## WP4. Crisis replication channels (Argentina/Turkey)

Goal: calibrate debt haircut severity and add FX-triggered crisis mode.

Tasks:
- Tune debt onset multipliers:
  - `DEBT_CRISIS_GDP_MULT` from 0.90 toward calibration band 0.92–0.95,
  - `DEBT_CRISIS_DEBT_MULT` from 0.60 toward 0.70–0.75 (if needed).
- Add FX crisis trigger branch in `gim/core/social.py` or transition layer:
  - inflation high + reserve coverage low + import pressure -> FX crisis state.
- Keep debt and FX pathways distinguishable but interoperable.

Acceptance:
- Crisis replication tests:
  - Argentina GDP-loss band no overshoot.
  - Turkey-like FX event triggers non-debt pathway with realistic duration/dynamics.

## WP5. Bilateral asymmetry stabilizer

Goal: prevent pathological trust/conflict divergence under long horizons.

Tasks:
- Add weak symmetrization term for relation pairs in political dynamics update.
- Increase conflict mean-reversion when far from baseline.

Acceptance:
- Bilateral audit: asymmetry max/mean below thresholds without flattening directed behavior.

## WP6. Re-validation package and publication artifacts

Goal: produce v15-ready evidence with old-vs-new comparability.

Tasks:
- Run non-LLM + LLM suites on GIM15 post-fixes.
- Store outputs in:
  - `results/validation/non_llm/...`
  - `results/validation/llm/...`
- Publish summary table:
  - GIM14 baseline vs GIM15 current vs GIM15 remediated.

Acceptance:
- No regression on physical bounds/stability tests.
- Material uplift on open fails (Q9/T3/T5/T9).

## 4) Practical sequencing (recommended)

1. WP1 (LLM strategic activation)  
2. WP2 (scenario inference confidence)  
3. WP4 (crisis pathways)  
4. WP3 (taxonomy expansion)  
5. WP5 (relation symmetry)  
6. WP6 full validation rerun  

Rationale: this order delivers early signal on strategic behavior and crisis realism before broad taxonomy migration.
