# Changelog

All notable changes to the Global Integrated Model. This project follows semantic versioning.

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
