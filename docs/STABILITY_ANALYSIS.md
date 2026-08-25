# Stability analysis of the one-year world map

Quantitative backing for the convergence claim in the paper (v2, "What keeps it
together: stability, measured"). Harness: `scripts/run_stability_analysis.py`;
output: `results/calibration/stability_analysis.json` (gitignored, deterministic
— reruns reproduce it bit-for-bit). Figure generators are maintained with the
publication materials, outside this repository.

Configuration: deterministic core, simple background policy, extreme events off,
`forward_init=True` (post-18.1.2 forward market corrections), base year 2023.

## 1. Spectral radius of the numerically linearized annual map

State vector (408 coordinates): per-agent `gdp, capital, public_debt,
unemployment, inflation, trust_gov, social_tension` (57 agents) + global
`temperature_global, temperature_ocean`, 4 carbon pools, 3 resource prices.
Central finite differences around the baseline trajectory; the Jacobian is
scale-normalized (`D^{-1} J D`, D = mean coordinate magnitudes along the
trajectory) so eigenvalues are unit-comparable.

| linearization year | rho(J) | eigenvalues >1 | above-unity mass: social / econ / climate |
|---|---|---|---|
| 2026 | 1.0363 | 36 | 0.43 / 0.57 / 0.00 |
| 2036 | 1.0998 | 35 | 0.35 / 0.65 / 0.00 |
| 2046 | 1.0410 | 31 | 0.22 / 0.78 / 0.00 |

Updated 2026-08-24. The previous table read rho = 1.075/1.076/1.078 over 66–74
above-unity modes, with `trust_gov` carrying most of the eigenvector loading.
That spectrum was substantially an artefact of the trust equation, not a
property of the coupling:

- Three of the five trust drivers entered as **levels** rather than deviations
  from a reference, so an agent at a constant and entirely normal gini,
  unemployment and inflation lost trust every year forever. A state variable
  with no restoring force has a unit eigenvalue by construction.
- Repairing the functional form (`TRUST_*_DEVIATION_FORM`) removes the drift
  but not the unit root — a walk without drift still sits at |lambda| = 1 — so
  trust also received the weak mean reversion resource prices already had
  (`TRUST_ANCHOR_PULL = 0.10`, chosen as the weakest anchor that lowers rho at
  all three linearization points).
- Together these roughly halve the above-unity count and move the mass from the
  social block to **economic** coordinates: public debt compounding near the
  effective interest rate, unemployment, inflation.

Interpretation, verified against eigenvectors:
- The spectrum still has modes above unity — the loop does not contract
  everywhere — but they are now mainly the growth/compounding modes of the 57
  economies rather than a decaying institutional variable.
- **Climate coordinates carry 0.00 of the above-unity mass in every
  configuration tested**, before and after both repairs. That the
  economic–climate subspace contracts is the robust part of the claim.
- The asymmetry between physical and social directions is real and smaller than
  previously reported, and is not a general property of coupled world models.

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

Active crises per year rise from 5.9 (first decade) to 14.4 (last), Fano index
(variance/mean) = 1.39.

**The Fano index does not show clustering and should not be read that way.**
Computed on a trending deterministic series it measures the trend. Against an
*inhomogeneous* Poisson surrogate carrying the same fitted intensity the null
mean is 2.07, i.e. the model is *below* its own trend-matched null, and the
dispersion of residuals about a fitted trend is 0.51 — the counts are more
regular than Poisson, not clustered.

What the baseline does show is **cross-block synchrony**: economic (debt, fx)
and social (regime) crisis onsets correlate at +0.52 at lag zero, with centroids
four years apart. Severing every cross-block channel halves that to +0.26 while
leaving the rise intact — so about half the co-timing is the coupling and half
is each block's own clock. See `Paper/revision/results/e1_crisis_clustering_null.json`.

## Reproduce

```
python3 scripts/run_stability_analysis.py          # ~4 min on an M4 Pro
ENS_YEARS=30 python3 scripts/run_ensemble.py       # ~1 min
```
