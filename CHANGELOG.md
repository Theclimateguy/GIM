# Changelog

All notable changes to the Global Integrated Model. This project follows semantic versioning.

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
  development-structured equations added to `docs/GIM17_UNIFIED_MODEL_SPEC.md`.

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

- The accompanying paper (`paper/gim_paper.tex`) is translated into academic English, reframed
  around strategic planning and scenario analysis; the Russian version is retained as
  `paper/gim_paper_ru.tex`. The appendix and the bibliography each begin on a new page.
- Figures regenerated with English labels: `fig1` (architecture, TikZ) and `fig2`--`fig5` via the
  committed, reproducible generator `paper/figures/make_figures.py`.

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
- **Committed, reproducible figure generator** (`paper/figures/make_figures.py`) for Fig. 2–5,
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
