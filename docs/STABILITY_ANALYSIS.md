# Stability analysis of the one-year world map

Quantitative backing for the convergence claim in the paper (v2, "What keeps it
together: stability, measured"). Harness: `scripts/run_stability_analysis.py`;
output: `results/calibration/stability_analysis.json` (gitignored, deterministic
— reruns reproduce it bit-for-bit); figure: `Paper/figures/make_stability_figure.py`
(fig12) and `Paper/figures/make_ensemble30_figure.py` (fig11).

Configuration: deterministic core, simple background policy, extreme events off,
`forward_init=True` (post-18.1.2 forward market corrections), base year 2023.

## 1. Spectral radius of the numerically linearized annual map

State vector (408 coordinates): per-agent `gdp, capital, public_debt,
unemployment, inflation, trust_gov, social_tension` (57 agents) + global
`temperature_global, temperature_ocean`, 4 carbon pools, 3 resource prices.
Central finite differences around the baseline trajectory; the Jacobian is
scale-normalized (`D^{-1} J D`, D = mean coordinate magnitudes along the
trajectory) so eigenvalues are unit-comparable.

| linearization year | rho(J) | eigenvalues >1 | >0.9 |
|---|---|---|---|
| 2026 | 1.0750 | 74 | 194 of 408 |
| 2036 | 1.0758 | 66 | ~same |
| 2046 | 1.0777 | 68 | ~same |

Interpretation, verified against eigenvectors:
- The ~70 modes clustered tightly at |lambda| ≈ 1.07–1.08 are the **common
  growth modes** of the 57 economies (capital–output compounding at the
  calibrated growth rate) — level growth, not error amplification.
- Removing the deliberate growth trend, the rest of the spectrum lies inside
  the unit circle; roughly half the modes sit above 0.9 — slow memory.
- The dominant slow mode loads on the socio-political block (top coordinates:
  `trust_gov`, `unemployment`, `inflation`, `social_tension` of an aggregate
  agent) — consistent with the multi-year lagged economy→tension channel found
  independently by the social-channel analysis.

Caveat: the annual map contains threshold events (crisis triggers); the
linearization is local to the smooth part of the dynamics at the baseline
state. Radius values are stable across the three linearization points.

## 2. Twin runs (trajectory-level perturbation response)

Epsilon-perturbations of the 2023 initial state, 30-year runs, gap in world
aggregates vs the unperturbed baseline:

| perturbation | world-product gap y1 | y10 | y30 | behaviour |
|---|---|---|---|---|
| USA GDP +0.1% | 2.6e-4 | 2.3e-4 | 1.2e-4 | contracts (×2) |
| temperature +0.01 °C | 4.0e-5 | 2.3e-5 | 7.0e-6 | contracts (×6) |
| social tension +0.01 (all agents) | 6.7e-11 | 1.6e-4 | 3.1e-2 | **persists & grows** |

Physical and economic perturbations wash out; a broad socio-political
perturbation is the one persistent direction (transmitted through savings and
crisis channels to a 3% world-product gap by year 30). Reported in the paper
as a property, not a defect — social initial-state uncertainty does not decay.

## 3. Ensemble fan growth (500 × 30 years)

`ENS_YEARS=30 python3 scripts/run_ensemble.py` — 500 members over the 33
history-matched key priors, no member diverges or saturates. Relative 5–95th
half-width of world product: ±1.7% (y5) → ±4.0% (y10) → ±8.4% (y20) → ±11.5%
(y30) — near-linear in horizon, far from exponential divergence. Temperature
fan widens 0.72 → 1.10 °C (the ECS prior expresses itself early). 2053 median:
241 T$ [215, 270], +1.94 °C [1.39, 2.49].

## 4. Crisis clustering on the deterministic baseline

Active crises per year rise from 1–2 (2020s) to ~10 (2040s, peak 15); Fano
index (variance/mean) = 2.0 — crises cluster in time as slow accumulators
(debt, temperature, tension) mature together.

## Reproduce

```
python3 scripts/run_stability_analysis.py          # ~4 min on an M4 Pro
ENS_YEARS=30 python3 scripts/run_ensemble.py       # ~1 min
python3 Paper/figures/make_stability_figure.py
python3 Paper/figures/make_ensemble30_figure.py
```
