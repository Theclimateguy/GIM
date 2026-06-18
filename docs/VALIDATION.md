# GIM17 Validation & Calibration (Phase 2)

Phase 2 replaces "does it look right" with proper, baseline-grounded scoring and a
data-driven calibration of the parameters that matter.

## Skill scoring (`gim/scoring.py`)

Proper scoring rules and reference baselines, so the model is judged against "do nothing"
forecasts, not in the abstract:

- **RMSE / MAE** — point error; **CRPS** — proper score for the ensemble forecast (reduces to
  MAE for a single member); **interval coverage** — does the X% band contain the truth ~X%?
- **Baselines** — persistence (carry the anchor value forward) and naive linear trend.
- **Skill score** `1 - err_model/err_baseline` (>0 beats the baseline).

```bash
python3 scripts/run_scoring.py    # scores the 2015-2023 backtest vs observed + baselines
```

**Honest finding (2015–2023, anchored at 2015):** the model **beats persistence on
temperature** (skill ≈ +0.14) and marginally on GDP, but **loses to a naive linear trend** for
GDP and CO₂ over this short, smooth window. This is the value of baselines: they show where the
structural model adds skill (climate dynamics) and where a trivial extrapolation is hard to
beat (short-horizon smooth aggregates). It also sets the bar Phase-2 calibration must clear.

## History-matching calibration (`gim/calibration_hm.py`)

Rather than point-fitting, history matching rules *out* implausible parameter regions, leaving
a "Not Ruled Out Yet" (NROY) posterior — the standard method for expensive simulators
(Craig 1997; Williamson et al. 2013, climate-model tuning).

For a draw θ, implausibility `I_o(θ) = RMSE(model_o(θ), obs_o) / tol_o`; combined
`max_o I_o`; NROY if ≤ `threshold` (3, Pukelsheim's rule). Draws run through the
parameter-isolated backtest (`params_override`), so calibration is parallel-safe.

```bash
CAL_SAMPLES=200 python3 scripts/run_calibration.py
```

**Finding (short backtest window):** the production-side parameters are constrained most
(`GAMMA_ENERGY`, `ALPHA_CAPITAL` via the GDP fit; `EMISSIONS_SCALE` via CO₂), while the
climate-response parameters (`ECS`, `HEAT_CAP_SURFACE`, `DECARB_RATE_STRUCTURAL`) are only
weakly identified over 8 years — consistent with the P1-D sensitivity result that they act on
longer horizons. More samples and a longer panel tighten the NROY region.

## Next

- **P2-C** — re-run the ensemble restricted to the NROY region; show tightened, better-scored
  probabilistic forecasts vs the prior ensemble.
- Longer observation panel (pre-2015) for stronger out-of-sample identification.
