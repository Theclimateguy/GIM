# Weak-signal detection (`gim/weak_signal.py`)

GIM's built-in crisis logic is **threshold-based**: a debt, regime, or currency crisis fires when its
conditions cross a line. **Weak-signal analysis** is the complement — spotting the subtle, multivariate
build-up that *precedes* a regime shift, before any threshold trips. This is the module the model was
missing for true early-warning / what-if work, and it is purely analyst-side: it reads trajectories
that the simulation already produced and has **zero effect on the simulation core or the golden
backtest**.

## What it does

It provides three detectors, run post-hoc over a single forward run or an ensemble:

1. **Mahalanobis anomaly** (`mahalanobis_scores`). Measures how far each time step's *joint* state
   (e.g. GDP growth, temperature change, debt, unrest together) sits from its recent baseline
   distribution, accounting for the correlations between those dimensions. A step is flagged when its
   squared Mahalanobis distance exceeds the χ²(df = number of dimensions) quantile (default 99%). This
   catches stress that no single variable would reveal — the system moving into an unusual *joint*
   region of state space.

2. **Structural break** (`structural_break`). A Gaussian mean-shift change-point on one series, scored
   by a BIC-penalised log-likelihood ratio (one mean vs. two segments) turned into a posterior-style
   break probability, with the most likely break location. Answers "did the dynamics of this variable
   regime-shift, and when?".

3. **Critical-slowing-down early warning** — reused from `gim/criticality.py` (rising lag-1
   autocorrelation + variance, the Scheffer indicators). The combined scan reports it per series.

`weak_signal_scan(series_by_name, ...)` runs all three and returns one report.

## Important: it detrends by default

GIM state series trend (GDP grows, temperature rises). Anomaly and break detection on raw *levels*
just re-detects the trend. So `weak_signal_scan` **first-differences each series to its stationary
increment** (`detrend=True`, reusing `criticality.to_stationary`) before scanning. Weak signals then
mean departures from the system's *normal dynamics* — which is what early warning is about. Pass
`detrend=False` to scan raw levels deliberately.

## Validation

`tests/test_weak_signal.py` checks the detectors against synthetic ground truth: the χ² quantile
matches known values; injected anomalies are flagged with the expected false-positive rate on the
baseline; a mean-shift is detected at the right location and scores above pure noise; detrending
suppresses trend-driven false anomalies; and an injected −15% GDP shock in a GIM-style trajectory is
caught at the right step. On a calm 30-year forward GIM run the joint-state scan stays near the χ²
false-positive rate; on the same run with a −15% shock injected at year 20 the GDP break probability
goes to 1.0 at exactly that step and the anomaly flags spike there.

## How to use it for what-if / weak-signal analysis

Run the baseline and the perturbed scenario (ideally as ensembles), collect the state series of
interest, and scan each:

```python
from gim.weak_signal import weak_signal_scan
rep = weak_signal_scan({"gdp": gdp_series, "temperature": temp_series, "debt": debt_series})
rep["mahalanobis"]["anomaly"]        # which years are multivariate-anomalous
rep["structural_breaks"]["gdp"]      # {break_prob, location, score}
rep["early_warning"]["temperature"]  # critical-slowing-down score
```

The intended workflow is **relative**: compare the weak-signal profile of a scenario against the
baseline (more/earlier anomalies, higher break probabilities, rising early-warning scores indicate the
scenario is moving the system toward a regime shift). As with the rest of GIM's forward use, this is
strongest for baseline-vs-scenario deltas on ensembles, not absolute point prediction.

## Dependencies

Analyst-tier: requires **numpy** (the GIM core is standard-library only; this is a diagnostic tool,
like `gim/sensitivity.py`). **No scipy** — the χ² quantile uses the Wilson-Hilferty approximation.
