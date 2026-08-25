# GIM18 Parameter Priors (Phase 1-B)

Uncertainty quantification draws parameter vectors from priors and runs them through the
per-run `ParameterSet` context. Priors come in two tiers.

## Tier 1 — Key priors (literature-grounded, validated)

`data/parameter_priors.csv` — ~18 climate-economy parameters whose distributions are taken
from the literature and **cross-validated against authoritative consensus values**. Each row
carries an explicit `source` and `rationale`.

| Parameter | Dist | Central | Validated range / source |
| --- | --- | --- | --- |
| `ECS_DEFAULT` | lognormal | 3.0 °C | best 3.0, likely 2.5–4.0, very likely 2.0–5.0 — **IPCC AR6 WG1 SPM A.4.4 / Ch.7.5** |
| `DAMAGE_QUAD_COEFF` | lognormal | 0.006 | DICE-2016R2 0.00236 (2.1%/3 °C); Howard-Sterner 6.7–8.3%/3 °C (~0.0074–0.0092); RFF 7–10% |
| `DAMAGE_BENEFIT_MAX/PEAK`, `DAMAGE_RISK_ADJ` | triangular | small | mild-warming co-benefit & resilience adj — weak support, wide priors toward 0 |
| `ALPHA_CAPITAL` | triangular | 0.30 | capital share ~0.20–0.35 — **PWT 10 / Gollin (2002)** (labor share 0.65–0.80) |
| `BETA_LABOR` | triangular | 0.60 | labor elasticity — PWT/Gollin |
| `GAMMA_ENERGY` | triangular | 0.042 | energy output elasticity — GIM backtest + energy-economy literature |
| `CAPITAL_DEPRECIATION` | triangular | 0.05 | ~4.0–4.2% — **PWT 8/9 (Inklaar & Timmer); Karabarbounis & Neiman 2014** |
| `HEAT_CAP_SURFACE/DEEP`, `OCEAN_EXCHANGE` | triangular | 8 / 100 / 1.0 | two-layer EBM — **Geoffroy et al. 2013 / DICE**, backtest-calibrated |
| `DECARB_RATE_STRUCTURAL` | triangular | 0.052 | artifact/backtest; constrained (<0.031 fails CO₂ envelope); raw intensity decline ~1.5%/yr (GCP/WDI) |
| `EMISSIONS_SCALE` | normal | 0.9755 | data-derived — **GCP 2023** (Global Carbon Project) |
| `BASE_BIRTH_RATE/DEATH_RATE` | triangular | 0.025 / 0.012 | baseline pre-modifier — **World Bank WDI 2023** (global ~17 / ~8 per 1000) |
| `BASE_INTEREST_RATE` | triangular | 0.02 | neutral rate r* ~0.5–2.5% — IMF WEO 2025 |
| `TFP_RD_SHARE_SENS` | triangular | 0.30 | R&D→TFP elasticity — GIM backtest + endogenous-growth literature |

Distributions are **truncated** to the bounds in the CSV (resample-then-clamp). The lognormal
choice for ECS and the damage coefficient reflects their right-skew (long upper tail). Tests in
`tests/test_priors.py` assert the samples reproduce the published central estimates and ranges
(e.g. ECS median 3.0 with the 2.5–4.0 likely range inside the 5–95% interval; the damage
coefficient spanning DICE in its lower tail and Howard-Sterner above its median).

## Tier 2 — Long-tail priors (tag-derived)

For every other scalar parameter, `all_priors()` derives a bounded uniform band from the
registry `uncertainty_level` tag (low ±5%, medium ±15%, high/unspecified ±25–35%) around the
calibrated value. Vector parameters (the IPCC-AR6 carbon-pool fractions/timescales) and
structural limits (`*_MAX/_MIN/_CAP/_FLOOR`) are **not** perturbed. These are a first pass; the
sensitivity stage (P1-D) identifies which actually matter.

## Usage

```python
from gim.core.priors import key_priors, all_priors, sample_parameter_set
from gim.core.params import default_params
import random

priors = key_priors()                 # literature-grounded core (default for the ensemble)
ps = sample_parameter_set(default_params(), priors, random.Random(seed))
world.params = ps                      # attach to an ensemble member
```

`key_priors()` is the defensible ensemble core; `all_priors()` adds the long tail for
sensitivity screening.
