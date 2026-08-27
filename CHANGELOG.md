# Changelog

All notable changes to the Global Integrated Model. This project follows semantic versioning.

## [20.1.1] — 2026-08-27 — the manuscript, corrected, and only it

No engine change: this release reproduces v20.1.0 to the bit on every headline metric,
including all 20 country-level GDP RMSEs, and the suite is unchanged at 592 tests / 657
subtests. What changed is what ships.

### Changed
- **`Paper/GIM_final.tex` replaces `gim_paper_v2_8K`** as the manuscript, and every superseded
  draft is untracked. Shipping a retired draft beside the current one means shipping numbers
  the current one has corrected. Each number in the new manuscript was re-derived from this
  release rather than carried over; the corrections that changed a stated result are listed in
  `Paper/REVISION_NOTES.md`, with 2053 world product (241 → 264 T USD), the in-sample
  temperature RMSE (0.145 → 0.099 °C, the deterministic configuration every other result uses),
  the bot failure window (2040–2045 → 2040–2049) and the oil-cascade Spearman correlations
  (−0.46/−0.44 → −0.20/−0.18, the earlier pair having come from a different initialisation than
  the tipping counts printed beside them) the largest of them.
- Claims are stated at the strength the diagnostics support: bounded over the tested horizon
  rather than stable; the climate coordinates carry no above-unity eigenvector mass, with the
  τ=∞ carbon pool contributing |λ|=1 by construction; a prior ensemble with a non-binding
  history-matching diagnostic, since acceptance is 100 %; a procedurally held-out validation
  window with its leakage channels named. `CITATION.cff` and `.zenodo.json` follow the same
  wording — "history-matched ensembles" was the mislabel the paper corrected.
- Zenodo is cited by the **concept DOI** `10.5281/zenodo.21575176`, which represents all
  versions and always resolves to the latest. `.zenodo.json` now records `isNewVersionOf`
  `10.5281/zenodo.22102520` — the actual v20.1.0 record. It previously named the concept DOI
  there, which is what made an earlier draft mistake the concept parent for a version.

### Removed
- **The licensed Hofstede multi-country panels leave the distribution.**
  `data/agent_state_pipeline/generated/{actor_base_inputs, country_panel_raw,
  country_panel_imputed}.csv` are excluded from the public build: they are written by
  `build_gim13_agent_states.py` and read only by `build_milex_grounding.py`, whose committed
  output ships as before, so nothing in `gim/` or `tests/` loses an input. PDI, IDV and UAI
  remain in `agent_states_operational.csv` for the 57 agents — without them the public tree
  would not reproduce the paper.
- **A `mas` column in `tests/fixtures/historical_backtest_state_2015.csv`.** GIM does not use
  MAS: `CulturalState` keeps PDI/IDV/UAI/LTO and records MAS as empirically inert. It was dead
  weight and a redistribution of a licensed score at once.

### Added
- `FORBIDDEN_CSV_COLUMNS` in `scripts/build_public_release.py`: the build now reads the header
  row of every shipped CSV and fails on `hofstede_name`, `hofstede_source` or `mas`. A path
  check cannot catch a licensed column reappearing inside a file the release must ship, which
  is exactly how the `mas` column above was found.
- `Paper/REVISION_NOTES.md` and `Paper/BIBLIOGRAPHY_AUDIT.md`: what changed in the manuscript
  and why, including the numbers carried over without independent re-verification.

### Fixed
- `build_public_release.py` no longer crashes at its closing `print` when `--out` points
  outside the repository.

## [20.1] — 2026-08-25 — validation repairs: five defects found by making the model check itself

The public release line for the paper. Resource prices became a validation target for the first
time, and doing that exposed four defects that no existing check could see; a fifth was found by
running null models against the paper's own claims. The historical fit moves by **less than
0.1%** across all of it, while three price targets, a live currency channel and a
climate-to-crop channel were added. Suite: 592 tests, 657 subtests.

### Added
- **Resource prices in the historical backtest.** `resource_price_index_by_year` (World Bank
  commodity indices, renormalised to the base year) in the observed fixture; per-resource RMSE
  on `HistoricalBacktestResult`; `PRICE_TOLERANCES` set to the error a no-skill flat price
  makes, so implausibility below 1 beats a flat line. Scores: energy 0.99, food 0.80, metals 0.96.
- **Climate → crop yield** (`FOOD_YIELD_TEMP_SENS = 0.049`). The model had no climate channel
  into food at all. Prior: Zhao et al. 2017 PNAS, four independent method families.
- **Food supply price response** (`FOOD_SUPPLY_PRICE_ELAST = 0.143`, Haile et al. 2016 AJAE).
  Composes with the yield prior without double counting — Zhao excludes adaptation, this is it.
  The pair gives a +24% food price by 2053, inside the IPCC assessed range it was not fitted to.
- **Food cost-push into inflation** (`INFLATION_COSTPUSH_FOOD_COEFF = 0.04`). Energy had a
  pass-through; food did not, while being the larger CPI component nearly everywhere.
- **Structural current account** (`STRUCTURAL_TRADE_BALANCE`), demeaned pro rata to GDP so the
  world closes to 4e-18 of world product.
- `scripts/regenerate_backtest_baseline.py` — the golden baseline had no generator. Refuses to
  write when a guarded metric regresses more than 1% without `--force --reason`.
- `scripts/build_public_release.py` — builds the public tree and fails unless it reproduces the
  working repository's numbers exactly and passes its own suite.
- `tests/test_global_golden_run.py` — the public golden: ten years of the 57-agent world, plus a
  guard that every crisis channel fires at least once.
- `TENSION_CLIMATE_SENS` — a continuous climate→tension term, **shipped off** and tagged: the
  prior (Hsiang et al. 2013) is contested (Buhaug et al. 2014) and the magnitude is not identified.

### Fixed
- **The currency channel was structurally dead.** `net_exports` was written only by bilateral
  trade deals, which no scripted policy proposes, so the current account was identically zero
  and the fx trigger could never fire — zero crises in 30 years, at any calibration. Four causes:
  the resource trade bill was ~300x too large to be read as a share of GDP (world sum 3190% of
  world GDP, hence 1.6 days of "import cover"); cover was measured against the resource bill
  rather than total imports; there was no current account; and `FX_CRISIS_MAX_YEARS` capped the
  counter without ending the episode. Now 3.5% of eligible agent-years against 3–5% observed,
  mean duration 1.9 years against 1–3.
- **Monetary-union false positives.** The repaired trigger flagged Italy and Spain in the 2016
  backtest. The model has no monetary-union or reserve-currency concept, and the agents holding
  the thinnest reserves are exactly those that need none. `FX_CRISIS_MONETARY_EXEMPT_AGENTS`.
- **Trust was a countdown, not a state.** Three of five trust drivers entered as levels rather
  than deviations from a reference, so an agent at constant, normal conditions lost trust every
  year forever; all 57 agents drifted down monotonically. `TRUST_*_DEVIATION_FORM` and
  `TENSION_*_DEVIATION_FORM` fix the form; `TRUST_ANCHOR_PULL = 0.10` fixes the separate unit
  root the form change leaves behind.
- **Metals recycling double-count.** Recycled supply was added on top of a base-year figure that
  already represented total supply — a permanent ~45% glut. Price implausibility 2.26 → 0.96.
- **The price-damping buffer read the geological reserve.** For energy that is fifty years of
  production in the ground, which froze the price at its initial value for the whole window.
  `PRICE_BUFFER_YEARS_*`, anchored on IEA/FAO/exchange inventory.
- **Energy demand had no income or population elasticity**, so demand/supply was exactly 1.0000
  every year. `ENERGY_DEMAND_INCOME_ELASTICITY = 0.5`, anchored on IEA intensity arithmetic.
- **Food production was frozen** at 1339.3 in every forward year while demand grew 33%, driving
  the price to 4.68 by 2053 against a real record of roughly flat real food prices.

### Changed
- The "constraint hold-out" is renamed a **free-running temporal out-of-sample test**. At the
  published tolerances the 2015–2019 window rules out no draw, so the frozen region equals the
  prior box; what makes 2020–2023 out-of-sample is that it is never used. Quantified: 0 of 600
  draws ruled out, maximum implausibility 1.69 against a cut at 3.0. History matching here is a
  ranking, not a filter — and per-output implausibility predicts its own out-of-sample error at
  rho 0.90–0.95, which the usual max-aggregation destroys for output.
- **Section 6's "late clustering" claim is withdrawn.** Fano on a trending series measures the
  trend; against a trend-matched Poisson surrogate the model shows no excess dispersion. The
  replacement claim is cross-block synchrony, which has a null behind it.
- **The "integration dividend" framing is dropped.** A model with no society block has a slope of
  zero there by construction. The benchmark now reports transfer-function shapes.
- The conflict composite is reported against its own best single covariate: `1 - regime_stability`
  alone scores AUC 0.777 against the composite's 0.739.

## [lib 19.2.0] — 2026-08-05 — full-model library: the 57-actor world core joins the package

One installable library now carries the whole GIM19 model: the `gim` annual world core
(57 actors, validated GIM18 engine line) plus the `gim19` sub-national block layer, with
every runtime data file packaged (~2.2 MB). Zero runtime dependencies. **No behavioural
change** — the full research-repo suite (589 tests + 657 subtests) is green before and after.

### Added

- `lib/sync_core.sh` — syncs `gim/` and the engine's runtime data (operational state,
  parameter priors/registry + lock, world geojson, RCMIP forcing, SIPRI anchor) into the
  build tree; `lib/gim` is generated and gitignored, the repo package stays canonical.
- `docs/core/` in the bundle: UNIFIED_MODEL_SPEC (canonical core equations),
  MODEL_METHODOLOGY, MODEL_LAYERS, SIMULATION_STEP_ORDER, MODEL_STATE_MAP, external-data
  sources; `docs/SPEC_SUBNATIONAL.md` (the §-numbering source); `docs/OVERVIEW.md` — the
  architecture map and reading guide.
- `examples/04_world_run.py` — the full model: world core with the RUS block layer ON vs
  OFF from one wheel install.

### Changed

- **Engine data paths resolve packaged copies**: `gim.paths.DATA_ROOT` now resolves
  `$GIM_DATA` → repo checkout → package data (marker-file check keeps repo runs
  bit-identical); `core/priors.py` and `geography.py` routed through `paths.DATA_ROOT`
  instead of ad-hoc repo-relative paths.
- Internal roadmap codenames (A1–A6, B1–B8, THE-1xx) replaced with descriptive names
  throughout the bundle docs; a translation table stays in MATHEMATICS.md's appendix for
  tracing repo commits and tests.
- `gim.__version__` 18.1.4 → 19.2.0 (lineage note added; the core is the GIM19 model's
  annual engine now, flag-off behaviour unchanged).

## [lib 19.1.1] — 2026-08-05 — gim19 handoff release (docs + examples, no engine change)

The `lib/gim19` package becomes a self-contained transferable asset. **No change to any
equation, parameter or data file** — the wheel's runtime contents are identical to 19.1.0.

### Added

- `lib/docs/MATHEMATICS.md` — the full mathematics of the block layer in one document:
  the five behavioural equations, the macro bridge, the interaction channel with the B1
  restoring forces, the quarterly fold, the A1–A3 constrained-hybrid estimation, the A4
  conjugate-ridge priors/posterior (full prior table), aggregation operators, political
  mass, the validator tolerances and the known model properties (bistability, hysteresis).
- `lib/docs/DATA.md` — every packaged data file with provenance, plus the hard-won source
  caveats (EMISS filtered GET, Levada press-release series, Treasury OKTMO defect, NE and
  CIE artifacts).
- `lib/docs/INTEGRATION.md` — the host-model contract (flag-off = bit-identical, authorized
  writers, the two insertion points, the war-intensity scenario hook) with a reference shim.
- `lib/examples/` — three runnable stdlib-only scripts: endogenous 10-year run, A4 ensemble
  fan, mini-host integration + quarterly fold; all verified from a clean-venv wheel install.
- `lib/HANDOFF.md` + `lib/dist/gim19-handoff-19.1.1.zip` (wheel, sdist, docs, examples) —
  the bundle to hand to colleagues; sdist now carries docs and examples via MANIFEST.in.

## [18.1.4] — 2026-07-26 — archival release (repo hygiene, no engine change)

Documentation and repository-hygiene release cut for the Zenodo archive. **No change to the
simulation engine, calibration, or results** — the golden backtest and full test suite are
bit-identical to 18.1.3.

### Changed

- **README streamlined** to the essentials (what the model is, validation highlights, screenshots,
  native app, links); per-version status/lineage detail now lives solely in this changelog.
- **GODMODE game section rewritten** for the production browser game
  ([godmode-rwhp.onrender.com](https://godmode-rwhp.onrender.com/),
  [source](https://github.com/Theclimateguy/GODMODE)) — CEO of the largest multinational holding,
  ~1-in-6 survival, decision cards, War Room advisors, cabinet politics, interactive world map,
  optional LLM advisors — replacing the earlier "play as a country" sketch.
- **Default branch** moved to `GIM18`.

### Added

- **`scripts/run_stability_analysis.py`** committed — the deterministic stability-analysis harness
  (Jacobian spectral radius, twin runs, crisis clustering) referenced by
  [`docs/STABILITY_ANALYSIS.md`](docs/STABILITY_ANALYSIS.md).

### Removed

- **`Paper/` LaTeX/figure materials removed from the public repository** (working manuscript, kept
  locally). References to `paper/…` paths scrubbed from the documentation and citation metadata;
  there is no published paper to cite.



Behaviour fix to the political/social layer, same shape as the 18.1.2 resource-price fix; **opt-in**
(default off), so the 2015–2023 golden backtest and the full test suite (527 tests, same pass/skip
split) are bit-identical with the flag at its default.

### Found
- **`trust_gov` has no equilibrium term, and the model's own comment claiming otherwise is wrong.**
  `gim/core/social.py:update_social_state` computes `trust_gov`'s per-year change as a straight sum
  of sensitivities (GDP-per-capita level, unemployment, inflation, inequality, a tension penalty)
  with a governing comment stating the flow is "balanced by the positive GDP-per-capita drift." Under
  calibrated values that balance does not hold: the GDP-per-capita term is ~0.0004–0.0005/yr for a
  typical tracked country, while the inequality (`gini`) term alone is ~−0.0165/yr and stays close to
  constant since gini barely moves under normal play — ~40× larger, unopposed. Net effect: trust decays
  at a near-constant rate regardless of policy, and once it crosses the tension threshold a self-
  reinforcing trust↔tension coupling (via `SOCIAL_TRUST_ANCHOR_SENS`) takes over independent of any
  further input, settling into a repeating regime-collapse/partial-recovery cycle rather than a stable
  floor. Confirmed empirically with a downstream consumer's scripted-policy batch (an extreme
  pro-stability policy and its exact opposite produced statistically indistinguishable trajectories,
  12 seeds to a 27-year horizon: −34.2 vs −34.6). Not caught by the existing social-validation program
  (`docs/calibration/SOCIAL_VALIDATION_PROGRAM.md` S1–S6) — S3 explicitly found no marginal
  trust→growth channel exists at all, so `trust_gov`'s own time-series behaviour was never itself
  checked for realism, and `docs/SOCIAL_GEO_METRICS.md` still lists trust_gov "level + trend
  validation" as an open item, not a finished one.

### Fixed (opt-in — see the partial-result note below for why this isn't the new default yet)
- **Equilibrium anchor** — `TRUST_ANCHOR_PULL` (default `0.0`) adds a weak linear mean-reversion,
  after the normal walk step in `update_social_state`, pulling `trust_gov` back toward each agent's own
  base-year (2023) value (`_trust_anchors`, capture-once, same pattern as
  `resources._resource_price_anchors`). Linear rather than log-space since `trust_gov` is an additive
  `[0,1]` quantity, unlike a multiplicative price.
- **Per-agent tension reference** — the tension equation's own `trust_anchor` term previously measured
  every agent against one global constant (`SOCIAL_TRUST_ANCHOR_REF = 0.50`), so an agent whose own
  baseline trust sits above 0.50 (most of a typical tracked set) had an ordinary crisis dip flip this
  term from damping tension to amplifying it, at a threshold unrelated to that agent's own social
  reality. Now references the same per-agent anchor as above when `TRUST_ANCHOR_PULL > 0`.
- **Verified but partial:** at `TRUST_ANCHOR_PULL = 0.15` (the same value already validated for
  `PRICE_ANCHOR_PULL`), the repeating collapse cycle is gone and the settling floor is measurably
  higher (~13 vs ~7–9 with the flag off, same 12-seed batch). It does **not** by itself restore
  policy-sensitivity — the scripted pro-/anti-stability policies remain statistically indistinguishable
  at every pull strength tested (0.08/0.15/0.25), because the domestic-policy levers that could move
  `gini`/`unemployment`/`inflation` don't do so strongly or often enough on their own. Left opt-in
  (default `0.0`) rather than activated in the headline pending that follow-on work, unlike
  `PRICE_ANCHOR_PULL` which was validated sufficient on its own and activated by default.

## [18.1.2] — 2026-07-06 — resource-price degeneracy fix (equilibrium anchor + demand growth)

Behaviour fix to the forward/scenario path; the 2015–2023 golden backtest is **bit-identical** and
the full test suite (527 tests) is green — every change below is a no-op at the base year, so no
golden snapshot moved.

### Fixed
- **Resource prices pinned to their clamp bounds on a forward run** (`gim/core/resources.py`,
  `gim/core/calibration_params.py`, `gim/core/world_factory.py`, `gim/runtime.py`). The
  reserve-buffered clearing rule (v18.1.1) damped the *speed* of a price move but not its
  *destination*: a persistent one-directional supply/demand imbalance still walked a price to a
  `[0.3, 5.0]` clamp and pinned there (energy → ceiling as reserves depleted; food/metals → floor
  under structural over-supply), identically across seeds. Four coordinated changes close it:
  - **Equilibrium anchor** — `PRICE_ANCHOR_PULL` (default 0.15) adds a weak log-space mean-reversion
    toward a per-resource anchor (the base-year reference price) after the walk step in
    `update_global_resource_prices`, so no persistent imbalance can pin a price. Zero pull, or a
    price already at its anchor, is a no-op.
  - **Resource demand growth** — food/metals consumption grows each year with realized population and
    per-capita income (`FOOD_/METALS_DEMAND_POP/INCOME_ELASTICITY`) instead of a frozen constant.
    Energy retains its cost-min demand path (elasticities 0). Clamped per-year growth band.
  - **Metals recycling compounding bug** — primary production is now carried forward as the desired
    base (`_primary_production`); recycled secondary supply is a within-year market term only, so it
    no longer inflated next year's production base (metals supply had run away ~20× over the horizon).
  - **Forward base-year balancing** — `normalize_resource_scales_forward` now also balances the
    base-year food market (consumption scaled up to production, mirroring the metals balance), and is
    reached via a new opt-in `forward_init` flag on `make_world_from_csv` / `load_world`. Default off
    keeps the raw loader, historical backtest and calibration paths byte-identical; forward-run entry
    points opt in.
- **gim2 forward paths use `forward_init=True`** (`gim2/policy_game.py`, `gim2/scenario.py`) so
  scenario and policy-game projections get balanced base-year markets. (`gim2/levers.py` ensemble
  members already normalized; cascade/ontology use a read-only world and are unaffected.)

## [18.1.1] — 2026-07-06 — reserve-buffered resource-price clearing (forward-stability fix)

Behaviour fix to the forward/scenario path; the 2015–2023 golden backtest is **bit-identical**
(GDP 0.599 / CO₂ 0.939 / T 0.145), so all validated headline numbers are unchanged.

### Fixed
- **Instant market-clearing overshoot on stock goods** (`gim/core/resources.py`). The headline
  clearing rule `p* = p_cur·(demand/supply)^(1/ε)` treated every resource as a pure flow good that
  must clear within the year — fine for energy (reserve/flow ≈ 7×) but wrong for metals (≈ 2.3×,
  mostly above-ground/recycled stock) whose 2023 baseline flow imbalance (demand/supply ≈ 4.7×, a
  data fact in the canon, not a runtime artifact) drove food and metals prices into their
  `[0.3, 5.0]` clamp bounds within 2–4 years on a plain `step_world` forward run. The rule now damps
  the demand/supply ratio toward 1 by a **reserve buffer** already tracked in
  `global_state.global_reserves` (`buffer_ratio = reserve / (reserve + |imbalance|)`): large standing
  stocks (metals, energy) absorb most of a flow imbalance, while thin-buffer food keeps clearing near
  the original pure-flow rule and correctly stays the most volatile. Prices are now smooth and
  monotonic for 10–15 years. No calibration data changed; `MARKET_CLEARING`, `PRICE_ADJUST_ALPHA`,
  `MARKET_DEMAND_ELASTICITY` untouched. (Surfaced while driving the engine year-by-year through the
  plain programmatic API during a game-prototype integration.)
- **State-artifact manifest test regression** (`tests/test_state_artifact_manifest.py`). The v18.1.1
  line inherited a test that redirected the canon via `_repo_root`; since v18.1.0 resolved the canon
  through `paths.OPERATIONAL_STATE_CSV` (gim-lib data relocation), the redirect no longer took effect
  and the missing-manifest fallback was never exercised. The test now patches `_primary_state_csv`,
  the actual resolution seam — **full suite 527/527 green**.

### Changed
- Version 18.1.0 → **18.1.1** (patch: forward-behaviour fix, no API or golden change).

## [18.1.0] — 2026-07-05 — SIPRI milex grounding (4-component CINC, F3+)

Data-grounding re-anchor of the capability index, based on the empirical analysis in
`docs/MILEX_GROUNDING_ANALYSIS.md`: the pop/energy/GDP proxy fits military-
expenditure *levels* (r≈0.76 cross-section) but is **anti-correlated with 2021–24 militarization
dynamics** (share-change corr −0.115), and the deterministic core had no military-expenditure
observable at all.

### Changed (headline)
- **`economy.military_spending` populated at world build** from the committed SIPRI 2023 grounding
  file (`data/external/sipri_milex_2023.csv`; 50 country actors direct, AG_* aggregates summed over
  pipeline `model_region` members — 99.9% of the SIPRI world total; documented carry-forward for
  SIPRI gaps: ARE←2014, VNM←2018; HKG=0, folded into CHN). Built by
  `scripts/build_milex_grounding.py`; gated by `MILEX_CINC_COMPONENT=True` ([F3+]).
- **CINC becomes 4-component** (pop, energy, GDP, milex): C′ = 0.75·C + 0.25·s_milex. Capability
  ranking shifts to **USA 0.204 > CHN 0.185 > IND 0.080** (RUS 0.034, +12.5%; ISR +88%, SAU +50%,
  USA +40% vs proxy) — an intentional, documented departure from the steel-and-personnel-era COW
  component mix. The 3-proxy configuration keeps the published-CINC anchor (China > US > India)
  and stays covered by tests under flag-off.

### Verified
- Full suite OK; golden backtest bit-identical: **GDP 0.599 / CO₂ 0.939 / T 0.145**; SCC bands
  (`test_benchmark_alignment`) in band.
- Conflict backtest re-scored locally against UCDP/PRIO ACD v24.1: **AUC 0.739 / BSS +0.123**
  (scores the untouched state-CSV `conflict_proneness`; re-fetch instructions in
  `data/external/SOURCES.md`).
- Calm 2015–2024 trajectories bit-identical (military_power is conflict-gated).

## [18.0.0] — 2026-07-01 — GIM18 reviewer-response (deepening + global sensitivity)

Closes reviewer issues #11–#19: deepened the climate, economy and social modules and added a Sobol
global sensitivity analysis. Golden discipline preserved — every change is bit-identical by default or a
documented, backtest-in-band re-anchor. Post-change backtest (2015–2023): GDP RMSE **0.598** (improved
from 0.621), CO₂ **0.939**, temperature **0.145**; climate backtest temp RMSE **0.096** / ECS **3.0**
unchanged. See `docs/GIM18_REVIEWER_RESPONSE.md`.

### Changed (headline)
- **#11 Forward non-CO₂ forcing.** Post-2024 non-CO₂ ERF follows the SSP2-4.5 marker table (plateau
  ~0.73 W/m² by 2100) instead of the unbounded linear extrapolation (1.42 W/m²). Historical window
  byte-unchanged. **Projected 2100 GMST 3.12 → 2.75 °C (−0.37 °C).**
- **#12 Internal-variability σ/ρ** re-derived from observed 1990–2023 forced residuals: σ 0.08 → 0.088
  (spread-matched, AR(1) CI [0.074, 0.120]); ρ 0.65 → 0.13 (residuals near-white). Cures ensemble
  under-dispersion.
- **#17 Damage function** re-anchored to Howard-Sterner preferred central (0.006 → 0.0078, ~7% at +3 °C)
  and **normalised to the 2023 baseline** (removes a base-year double-count → backtest GDP RMSE improved).
  Warming "benefit" removed. Burke growth channel calibrated (switchable, off).
- **#13 β-convergence** validated on the WB real-PPP panel (0.0093 ∈ 95% CI [0.0068, 0.022]); SE added.
- **#14 Sovereign spreads** anchored: LINEAR 0.03 → 0.06 (Hilscher-Nosbusch ~2.1 bp/pp), QUADRATIC 0.10
  (Arora-Cerisola), THRESHOLD 0.60 (Maastricht + Reinhart-Rogoff).
- **#16 Trust sensitivities** anchored to the misery-index 2:1 weighting (unemployment −0.030, inflation
  −0.015); Gini retagged; switchable Gini×unemployment interaction added (off).
- **#19 Returns to scale** documented: DRS (sum 0.942) is near-neutral (≤~9% at 2100, not 43%) because
  per-country `_scale_factor` re-anchoring pins the output level; bounded test added.

### Added (switchable / tooling)
- **#15 Logistic demographic transition** (Lutz/Preston), calibrated to UN WPP; switchable (off by default).
- **#18 Sobol/Saltelli global sensitivity** over the top-20 priors (`calibration/global_sensitivity.py`,
  numpy/scipy, no SALib dependency) → `calibration/gsa_results.json`.
- New calibration scripts + `data/forcing/rcmip_nonco2_ssp245.csv`; new tests for each issue.

### Honesty
- Kotz et al. (2024), cited by #17, is **retracted** and excluded as an anchor. The #17 premise
  ("0.6% at 3 °C") and #19 premise ("43% bias") were both shown to be miscalculations.

## [17.3.0] — 2026-06-30

**Development-structured recalibration: a realistic no-policy forward baseline.** The app's
no-policy forward projection had CO₂ *falling* and temperature reaching only ~1.49 °C by 2033 —
contradicting observation. Root-causing it exposed a chain of compounding defects, two of which
silently cancelled in the historical backtest, so the headline fit looked fine while the forward
path was wrong. Fixing them required re-grounding two structural mechanisms in data, which moved the
golden backtest and the SCC. The objective economic core, the geo-on default, the conflict
validation, and the uncertainty machinery are all unchanged; this is a *calibration* release, not an
architecture change.

### Fixed

- **Carbon-cycle initialization.** The 2023 forward carbon pools were seeded with the *flow*
  partition fractions, which over-loaded the fast (4.3-yr) pool and created a phantom ~50 GtCO₂/yr
  sink — the source of the falling-CO₂ baseline. They are now seeded with the aged 1750→2023 spin-up
  partition (`CARBON_POOL_INIT_FRACTIONS_2023`), so atmospheric CO₂ rises realistically (+2.5 ppm/yr)
  on the no-policy path.
- **2015 backtest state capital.** The historical-backtest 2015 state carried capital at ~0.23×
  GDP (vs a realistic ~3.0×). The legacy decarbonisation rate of 0.052 had been silently
  compensating this broken capital init — the two errors cancelled in-sample. The 2015 capital is
  corrected to ~3.0× GDP and the observed GDP series is re-based from nominal (`NY.GDP.MKTP.CD`) to
  real-PPP growth (`NY.GDP.MKTP.PP.KD`).

### Added

- **TFP conditional convergence** (EQ-ECO-003). Catch-up TFP growth proportional to the log
  GDP-per-capita gap to the frontier (`TFP_CONVERGENCE_SENS = 0.0093`, cap 4), fit to the 2015–2023
  real-PPP cross-section (R² = 0.38). Lifts China/India toward their observed growth instead of the
  old uniform drift.
- **Development-dependent decarbonisation** (EQ-CLI-001). Per-country CO₂/GDP intensity decline now
  scales with income (renewables + post-industrial shift) — the mirror image of the convergence
  term, fit to the same panel (R² = 0.46). Improves the backtest CO₂ RMSE from 1.26 to 0.93.
- **`calibration/growth_decarb_calibration.py`** + committed World Bank inputs
  (`data/worldbank_growth_decarb_2015_2023.csv`) fitting both new development terms, and the four
  development-structured equations added to `docs/UNIFIED_MODEL_SPEC.md`.

### Changed

- **Golden 2015–2023 backtest re-derived** on the corrected state and the two new mechanisms:
  **GDP RMSE 0.59 → 0.62, CO₂ RMSE 1.15 → 0.93, temperature 0.135** (unchanged). Note the
  capital-init fix lifts *both* production functions, so plain Cobb-Douglas now also reaches GDP 0.62 —
  the nested-CES advantage now shows in emissions (CO₂ 0.93 vs CD ~1.87) rather than in GDP.
- **Climate anchor** made self-consistent with the spin-up: `TGLOBAL_2023_C` 1.2 → 1.333 and
  `TOCEAN_2023_C` = 0.404 (the old 0.4 °C ocean gap under-stated heat uptake). **ECS stays 3.0**
  (backtest-optimal).
- **Manifest decarb rate re-stamped 0.052 → 0.016**, the data-derived observed prior; the `DECARB`
  parameter prior is re-centred accordingly.
- **Social cost of carbon refreshed** for the faster, empirically-calibrated growth path: modern
  Ramsey (near-zero ρ) ≈ **$95/tCO₂** (was ~$140; range ≈ $95–280), Nordhaus-style ≈ $42. Under
  DICE-2016R2's own lower damages the marginal-pulse engine now returns ≈ **$20** (was ~$31) — i.e.
  the development-convergence growth discounts future damages more, so DICE *underestimates* damages
  relative to GIM's empirically-calibrated function.
- **Paper (RU + EN)** updated: validation table, SCC narrative, and the two new
  development-structured mechanisms; figures `fig2`–`fig5` regenerated on the recalibrated model.

Tests: **546 passed + 627 subtests**; golden/provenance assertions updated to the recalibrated
values. Conflict-risk validation (AUC 0.736 [0.59; 0.86], BSS +0.143, p ≈ 0.001) and the geo
calibration are unchanged.

[17.3.0]: https://github.com/Theclimateguy/GIM/releases/tag/v17.3.0

## [17.2.2] — 2026-06-30

**Validated 2023-canon data unification + paper refresh.** Establishes a single validated source of
truth for the compiled actor state and refreshes the paper to it.

- **Canon:** all runs start from `data/agent_states_operational.csv` (2023 base year, 57 actors —
  the 50 largest economies + residual regional aggregates + Taiwan, covering essentially all world
  output: world GDP ≈ $107T, population ≈ 8.06B, CO₂ ≈ 38 Gt), reconciled against World Bank / UN /
  Global Carbon Project to within ~1%. Resolved everywhere via `runtime.default_state_csv()` /
  `paths.CANONICAL_STATE_CSV`; the retired forward-2026 projection is archived in `data/archive/`.
- **Engine:** adopts the per-agent forward energy-reserve normalization (supersedes 17.2.1's global
  factor — fixes a mid-horizon importer depletion that spuriously spiked the energy price and cooled
  the forward temperature fan). Forward-path only; **golden backtest RMSE byte-identical** (GDP
  0.5917 / CO₂ 1.1467 / T 0.1349). `base_year` defaults corrected to 2023 across ensemble/SCC/
  sensitivity/metrics.
- **Paper (RU+EN):** forward ensemble refreshed to the canon (base 2023 ≈ $107T; 10-yr median ≈
  $127T, IQR 125–130, 5–95% 121–133; temperature 1.0–2.0 °C); fixed the "57 = subset" framing
  (it covers essentially all output); regenerated fig3 (Morris) and fig4 (ensemble); Morris
  robustness re-verified on canon (r=8→32 Spearman ρ ≈ 0.99 for the three physical quantities,
  0.986–0.995; social tension ρ ≈ 0.93 at the noise floor). SCC headline holds (low-discount Ramsey
  ≈ $147 @100y; DICE reproduction $30.1 @300y, target $31). Conflict/backtest validation unchanged.

## [17.2.1] — 2026-06-29

**Resource-block units & data reconciliation (patch).** A forward-projection patch correcting three
localized units/data defects in the resource block that depressed the *baseline forward* GDP path
(~5% spurious drag, with a near-term dip in the first years) without ever touching the validated
historical surfaces. The "golden" 2015–2023 backtest is **byte-identical** (GDP RMSE 0.5917 trn,
CO₂ 1.1467 Gt, T 0.1349 °C), as are the geo-calibration golden and the state-CSV loader contract;
the forward baseline now grows smoothly from year one. This is a correction of model *plumbing*
(units and a state-data imbalance), not of any calibrated parameter — the 17.x calibration and its
validation stand unchanged. Full suite: 460 passed.

### Fixed

- **Energy-block unit mismatch.** The physical ZJ annual-supply cap was `min()`-compared directly
  against the model's energy *index* production (~10⁴), collapsing effective supply to ~0.65 and
  slamming the energy price into its ceiling on step 1 — a units bug, not a calibration choice. The
  cap is now anchored to base-year world production (× `ENERGY_ANNUAL_CAP_HEADROOM`) so it constrains
  only *growth*, never current output; under-scaled forward energy reserves (~7 yr of cover) are
  lifted to the physical proven-reserves horizon (~50 yr). Forward path only.
- **Metals market never cleared.** Forward-state metals production is understated ~4.7× vs
  consumption, and the substitution term used a *fixed* price reference `(p/p_ref)^(−e)`, compounding
  a constant off-reference price into an exponential demand ratchet (~30× over a decade — the exact
  runaway the energy demand-response comment warns against). Metals production/reserve are balanced to
  the consumption scale on the forward path, and the substitution is made non-compounding
  (year-over-year, like energy).
- **Food stress over-triggered.** `_resource_stress` used a 3-yr "years of reserve" threshold for
  food, but food is a perishable flow good (real stocks-to-use ≈ 0.3 yr), so every realistic world
  read as ~90% food-stressed and bled GDP through the security channel. The threshold is lowered to a
  realistic perishable horizon.

### Changed

- **Live conflict-risk ensemble metric.** The ensemble now also reports `conflict_risk` (structural
  `conflict_proneness` — the AUC-0.736 onset ranking — modulated by current social tension) alongside
  the legacy discrete `n_wars`, which is dormant in the deterministic baseline. Additive; no validated
  surface changes.

The three forward-path corrections are confined to a single member-runner init step
(`normalize_resource_scales_forward`, called only on the forward projection path and only ever scaling
*up*), so the historical backtest, geo calibration, and game modes remain byte-identical.

[17.2.1]: https://github.com/Theclimateguy/GIM/releases/tag/v17.2.1

## [17.2.0] — 2026-06-26

**The final release of the 17.x family.** It completes the model's distinctive cross-domain story: the
geographic-coupling layer is activated in the headline and grounded in the literature with a delivered
reproduction benchmark; the social/political layers are put on a reproducible numeric footing; the
economic core is deepened; and the integration claim is made computational. Every headline number is
calibrated, literature-anchored, and shown to be statistically reliable, with the objective 17.0.0 core
and the "golden" backtest preserved (now under the geo-on default).

### Added

- **Geographic coupling — activated and anchored.** A real spatial graph (shapely, now a runtime
  dependency) drives four switchable channels: trade gravity (δ = 0.9; Disdier–Head 2008 / Head–Mayer
  2014) plus conflict / tension / climate spatial contagion. Literature anchors and a *delivered*
  reproduction benchmark (`scripts/run_s6_geo_autocorrelation.py`): emergent Moran's I and a dyadic
  neighbour-conflict premium of 1.0×→1.5× (matching the +44–52% empirical record). First-source
  verification keeps each anchor honest — the tension channel is documented as a modest expert prior
  (the cleanest cross-national study finds pure-adjacency protest spillover insignificant). The S5
  conflict-geography leverage test and a switchable adjacency-contagion term. Docs:
  `docs/calibration/GEO_PRIOR_ANCHORS.md`, `GEO_ON_REVALIDATION.md`.
- **Social / political validation program (S1–S6).** War-size power-law exponent (Richardson; Clauset),
  migration gravity elasticities (Beine et al.), trust→growth / regime-collapse disaster magnitude
  (Barro–Ursúa), conflict-onset forecast skill placed against PITF/ViEWS, and the geographic coupling
  above — each with a literature anchor and, where the quantity is emergent, an engine-reproduction
  check. `docs/calibration/SOCIAL_VALIDATION_PROGRAM.md`.
- **Integration benchmark (paper Appendix B).** A literature-anchored, computational contrast of the
  cross-sector claim against sectoral models — carbon tax / DICE, oil shock / MESSAGEix, crop shock /
  AgMIP — showing GIM reproduces each sectoral first-order effect and surfaces a cross-sector
  consequence the sectoral model structurally cannot. `scripts/integration_benchmark/`,
  `docs/INTEGRATION_BENCHMARK.md`.
- **Economic-core deepening (E4.1–E4.3).** Money→prices transmission (quantity-theory Phillips term,
  calibrated λ ≈ 0.027); growth foundations (R&D-stock / Jones TFP channel + SSP1–5 drift presets);
  near-rational (model-consistent) expectations scaffold — the last two off by default.
- **D6 DICE/SCC engine reproduction** in the validation table: GIM recovers DICE-2016R2's social cost of
  carbon (~$32–33) under DICE inputs with its own engine.
- **Decision-maker interface + LLM persona scenarios** (`python3 -m gim ui`): a bilingual, exploration-
  first UI ("play as a country", "what if", "compare", expert mode) with persona-biased doctrines.

### Changed

- The headline model now runs with **geographic coupling ON by default**; the 2015–2023 "golden"
  backtest is re-pinned to the geo-on configuration (GDP 0.5917 / CO₂ 1.1467 / T 0.1349) and stays in
  band.
- **Re-validated under geo-on:** backtest RMSE, conflict AUC 0.736 [0.59; 0.86] (BSS +0.143), and the
  Morris sensitivity (drivers + robustness ρ ≥ 0.99) all hold. Paper Morris parameter counts corrected
  to 33 key / 305 total; `fig3_sensitivity` regenerated from the 33-factor screen.
- Repository reorganized for academic presentation (climate/calibration doc subfolders, meaningful
  top-level directories); committed, reproducible figure generator.

[17.2.0]: https://github.com/Theclimateguy/GIM/releases/tag/v17.2.0

## [17.1.1] — 2026-06-24

Preprint snapshot for the Zenodo archive. No changes to the simulation engine, calibration, or
results relative to 17.1.0; this release finalizes the accompanying paper and makes the figure
pipeline fully reproducible.

### Changed

- The accompanying paper is translated into academic English, reframed around strategic planning
  and scenario analysis; a Russian version is retained. The appendix and the bibliography each
  begin on a new page.
- Figures regenerated with English labels: `fig1` (architecture, TikZ) and `fig2`--`fig5` via a
  committed, reproducible figure generator.

[17.1.1]: https://github.com/Theclimateguy/GIM/releases/tag/v17.1.1

## [17.1.0] — 2026-06-23

Statistical-rigor, robustness, and analysis layer on top of the unchanged 17.0.0 core. The
simulation engine and the "golden" backtest are not modified; this release strengthens the evidence
behind the reported results, identifies the (lagged) economy→society channel, and makes the figures
reproducible. The accompanying paper is reframed around strategic planning and scenario analysis.

### Added

- **Reproducible conflict-AUC inference** (`scripts/conflict_auc_inference.py`): bootstrap 95% CI
  **[0.59, 0.86]** (20k resamples) and a label-permutation significance test for AUC = 0.736.
- **Morris-screening robustness** (`scripts/run_sensitivity_robustness.py`): trajectory-count
  convergence (Spearman **ρ ≥ 0.99** from r = 8 to r = 32) and seed stability across the four metrics.
- **Ensemble Monte-Carlo convergence** (`scripts/run_ensemble_convergence.py`): N = 80 → 500
  convergence with bootstrap standard errors on every reported percentile.
- **Economy→social-tension channel analysis** (`scripts/social_channel_analysis.py`): localization,
  accumulation, an impulse response to a stagflation shock, and a distributed-lag regression. The
  channel is **statistically significant but lagged**; its direct drivers are the social-block priors,
  which were absent from the screened physico-economic set — hence the screen's apparent null.
- **Committed, reproducible figure generator** for Fig. 2–5,
  including a new **Fig. 5** (economy→society channel). Method citations (Morris 1991,
  Campolongo 2007, Efron & Tibshirani 1993) added to the paper.

### Changed

- All sensitivity/ensemble runs now use the **full 57 modeled countries** (was 25 for speed). The
  reported "world GDP" is explicitly the 57-country aggregate (~116 trln at the 10-year horizon,
  ~109 trln in the 2026 base), clarified in the paper as distinct from all-world output.
- **Corrected** the conflict-AUC permutation p-value 0.0005 → **≈0.001** (the old value was a
  2000-permutation artifact; stable at 50k permutations). Bootstrap CI [0.59, 0.86] confirmed.
- Ensemble temperature 5–95% lower bound refined ≈0.9 → **≈1.0 °C** after the N-convergence check.
- Paper reframed around **strategic planning and scenario analysis** (risk management secondary);
  prose tidied for academic style.

[17.1.0]: https://github.com/Theclimateguy/GIM/releases/tag/v17.1.0

## [17.0.0] — 2026-06-22

First released version of GIM17. Evolves the frozen GIM16 baseline into an objective,
validated scenario-and-uncertainty platform with an integrated economy–climate–society–
geopolitics core.

### Headline validation (2015–2023 "golden" backtest)

- GDP RMSE **0.59** trillion USD (20 countries), global CO₂ RMSE **1.15** GtCO₂,
  temperature RMSE **0.135 °C**. Improved from the prior Cobb-Douglas core (1.03 / 1.61 / 0.134)
  by the objective economic core, and held stable since.
- Conflict-risk skill vs the standard armed-conflict record (UCDP GED, 57 countries):
  **AUC 0.736, Brier skill +0.143** over the base rate.

### Added

- **Objective, fully-closed economic core (now the base model):** calibrated base-normalized
  nested-CES (capital–energy substitution) production; cost-minimising, price-responsive energy
  demand; energy/resource and capital markets that clear by price; a closed stock-flow-consistent
  bank balance sheet (money = deposits = loans) with a financial accelerator.
- **SSP2-anchored forward growth** with GDP skill-vs-naive reporting.
- **Carbon-cycle channels (switchable):** land-use CO₂ source (headline); smooth permafrost/peat
  feedback and abrupt carbon-release tipping (ensemble-only, off in the headline).
- **Carbon-price → energy-substitution → emissions channel**, validated against empirical pricing.
- **CINC-grounded military capability** (national-power data, not arbitrary numbers).
- **Weak-signal detection module** (`gim/weak_signal.py`): multivariate Mahalanobis anomaly,
  Gaussian mean-shift structural break, and reused critical-slowing-down early warning — for
  what-if / early-warning analysis. numpy-only, no scipy; zero core/golden impact.
- External-data ingestion and validation scripts (World Bank WDI/WGI, UCDP, SWIID anchoring).

### Changed

- Headline non-CO₂ forcing retains the calibrated net (the AR6 central over-warms the validated
  record); AR6 components exposed as scenario levers. See `docs/climate/CLIMATE_BENCHMARKS.md`.
- Social cost of carbon reported at ~$140/tCO₂ (modern 2% discounting) within the broad modern
  range, with the growth/discounting sensitivity (~$140–380) documented rather than tuned to target.
- Culture layer trimmed to the load-bearing dimensions; inert dimensions removed.

### Fixed

- Energy-demand price response compounded a constant price into runaway energy decay on forward
  projections; corrected to a year-over-year price change. Added a forward-stability regression test.

### Engineering

- Python 3.10+, standard-library-only runtime core (numpy/scipy are optional analysis-tier extras).
- Enforceable accounting/integrity invariants; deterministic, reproducible runs.
- Uncertainty machinery: evidence-based priors, Monte-Carlo ensembles, sensitivity analysis,
  history matching (NROY), skill scoring against persistence/trend baselines.
- Manifest-bound state artifacts: data-derived climate coefficients locked to a content hash and
  guarded by tests (cannot be hand-tuned).

[17.0.0]: https://github.com/  (set to the release tag URL on push)
