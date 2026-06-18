# GIM17 Uncertainty Quantification (Phase 1)

GIM17 produces **probabilistic** projections: parameters are drawn from literature-grounded
priors, propagated through independent seeded worlds, and reported as percentile fan bands.

## Pipeline

1. **Priors** (`gim/core/priors.py`, `data/parameter_priors.csv`) — see `docs/PRIORS.md`.
2. **Parameter context** (`gim/core/params.py`) — each draw becomes an immutable
   `world.params` (option B2), with no global mutation.
3. **Ensemble** (`gim/ensemble.py`) — N independent members, member `i` seeded from
   `(master_seed, i)`; aggregated into percentile bands per simulated year.

## Running an ensemble

```bash
ENS_MEMBERS=500 ENS_YEARS=10 ENS_MAX_AGENTS=100 ENS_PRIORS=key ENS_JOBS=0 \
  python3 scripts/run_ensemble.py
```

Writes `results/ensemble-<ts>/ensemble.json` (per-year `p5/p25/p50/p75/p95/mean` for each
headline metric) and a `run_manifest.json`. `ENS_JOBS=0` uses all cores; `ENS_PRIORS=all`
adds the tag-derived long tail.

Library use:

```python
from gim.ensemble import EnsembleConfig, run_ensemble
res = run_ensemble(EnsembleConfig(state_csv=..., n_members=500, years=10))
res.bands["temperature"]["p95"]   # upper fan band over years
```

## Headline metrics

`world_gdp`, `world_population`, `temperature`, `co2`, `n_debt_crises`, `n_regime_crises`,
`n_wars`, `mean_social_tension`.

## Determinism

The ensemble is reproducible and **order-independent**: serial and parallel runs are
bit-for-bit identical (each member's seed derives only from `(master_seed, index)`). This
rests on the Phase-0 world-scoped RNG and the Phase-1-A parameter isolation.

## Performance

Cost scales with members × years × actors² (bilateral relations). Use `ENS_JOBS=0` for
parallelism; reduce `ENS_MAX_AGENTS` for faster exploratory runs. A 500-member, 10-year,
100-actor run is a multi-minute job best run across cores.

## Global sensitivity analysis (`gim/sensitivity.py`)

Which parameters actually drive each output? Two standard methods, implemented natively on
numpy and **validated against the analytical Ishigami benchmark** (closed-form Sobol indices):

- **Morris elementary effects** (Morris 1991; Campolongo 2007) — cheap screening over many
  factors. `mu_star` ≈ overall influence, `sigma` ≈ non-linearity/interaction. Cost
  `r*(D+1)` model runs.
- **Sobol indices** (Sobol 2001; Saltelli 2010 estimators) — variance decomposition on the
  reduced set. `S1` first-order, `ST` total (incl. interactions). Cost `N*(D+2)` runs.

The model is wrapped as a deterministic scalar function of a parameter vector (world RNG held
at a fixed seed), and factor ranges are the prior `[low, high]` bounds.

```bash
SENS_METRIC=temperature SENS_METHOD=morris SENS_PRIORS=all SENS_R=10 \
  python3 scripts/run_sensitivity.py        # screen all priors, then:
SENS_METRIC=temperature SENS_METHOD=sobol SENS_NAMES=ECS_DEFAULT,HEAT_CAP_SURFACE,... \
  SENS_NBASE=128 python3 scripts/run_sensitivity.py
```

Writes `results/sensitivity-<ts>/sensitivity.json` (ranked indices). Example finding: for
short-horizon temperature, `HEAT_CAP_SURFACE` and `ECS_DEFAULT` dominate (transient +
equilibrium climate response), as expected physically.

## Probabilistic outputs (`gim/fan_charts.py`)

`scripts/run_ensemble.py` writes a self-contained `fan_charts.html` alongside `ensemble.json`:
one SVG panel per headline metric with the 5–95% and 25–75% bands and the median line (pure
SVG, no plotting dependency). The run manifest carries final-year p5/p50/p95 for the key
metrics. This is the probabilistic projection surface — point forecasts are gone.

Phase 1 (uncertainty quantification) is complete: priors → ensemble → sensitivity →
probabilistic outputs, all reproducible and CI-gated.
