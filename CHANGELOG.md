# Changelog

All notable changes to the Global Integrated Model. This project follows semantic versioning.

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
  record); AR6 components exposed as scenario levers. See `docs/CLIMATE_BENCHMARKS.md`.
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
