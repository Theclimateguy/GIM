# Changelog

All notable changes to the Global Integrated Model. This project follows semantic versioning.

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
