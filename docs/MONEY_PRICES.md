# Money → prices transmission (E4.1)

Status: **headline-active at the data-calibrated λ = 0.027** (switchable; 0.0 reproduces the
pre-E4.1 golden bit-identically). Golden re-anchored on activation (4th-decimal move; 0.590/1.146/0.135
unchanged at reported precision). THE-60.

## Why

Before E4.1 the model already carried **endogenous broad money** (E3.3 / THE-44): in the closed
banking system every loan creates a matching deposit, so `economy._money_supply = deposits = loans`
(`gim/core/private_finance.py`). But that money was purely an *accounting* stock — it had **no
behavioural link to prices**. Inflation (`gim/core/labor_market.py`) was driven only by the
unemployment gap (Phillips), an energy cost-push term, and an adaptive expectation anchor. So the
classic monetary transmission "money growth → inflation" was simply absent.

E4.1 closes that gap with the minimal, defensible quantity-theory channel.

## Mechanism

The expectations-augmented Phillips curve gains one optional term:

```
money_term = MONEY_INFLATION_PASS · (broad-money growth − reference growth)
pi_t       = pi_expected + PHILLIPS_SLOPE·(NAIRU − u_t) + cost_push + money_term
```

- **Broad-money growth** = year-over-year growth of `economy._money_supply` (the SFC deposit stock,
  updated earlier in the step order, so it is current when inflation is advanced).
- **Reference growth** = `POTENTIAL_OUTPUT_GROWTH + INFLATION_TARGET` (= 0.025 + 0.02 = 0.045). This
  is the stable-velocity benchmark from MV = PY: with broadly constant velocity, nominal money should
  grow at trend real output plus target inflation. Only money growth *in excess* of this reference is
  inflationary — so at the calibration steady state the term is ≈ 0 by construction.
- **`MONEY_INFLATION_PASS`** (λ) — the pass-through weight, in `calibration_params.py`.

## Golden safety

`MONEY_INFLATION_PASS = 0.0` by default. The entire money block (including the per-agent
`_macro_money_prev` tracking attribute) lives inside `if money_pass != 0.0:`, so the default run
computes **no extra term and writes no extra agent state** — it is byte-for-byte the validated
golden (2015–2023 RMSE 0.590 / 1.146 / 0.134). Verified by `tests/test_money_prices.py`
(`test_default_golden_preserved`). The channel also degrades gracefully when the SFC money block is
off (no `_money_supply` → no term).

## The "deliberately weak modern pass-through" stance

The headline λ should be **modest and bounded**, consistent with the flat modern Phillips curve
(`PHILLIPS_SLOPE = 0.25`). Post-1990, the empirical short-run money-growth/inflation correlation in
advanced economies is weak (velocity is unstable, money is endogenous, central banks target the rate
not the aggregate); the strong quantity-theory link is a long-run / high-inflation regularity. So
E4.1 models a **long-run, weak** pass-through rather than a mechanical one-for-one MV = PY — and that
choice is defended explicitly rather than tuned to hit a target, matching the model's honesty bar.

## Calibration (done)

λ is the marginal response of inflation to excess broad-money growth, estimated across the model's
49-country panel (World Bank `FP.CPI.TOTL.ZG`, `FM.LBL.BMNY.ZG`, `NY.GDP.MKTP.KD.ZG`), 2000–2023,
restricted to the modern low-inflation regime (|inflation| ≤ 20%, money growth ∈ [−10%, 40%] —
hyperinflation episodes excluded, since the near-1:1 quantity-theory link is carried by high-inflation
observations: De Grauwe & Polan 2005; McCandless & Weber 1995). Script:
`calibration/calibrate_money_inflation_pass.py`; output: `money_inflation_pass_calibration.json`.

Six specifications, to expose how λ moves as confounders and dynamics are stripped out (SE
cluster-robust by country for the panel specs):

| Spec | λ | SE | notes |
|---|---|---|---|
| A. pooled bivariate | 0.235 | 0.016 | R²=0.20 |
| B. pooled + output control | 0.230 | 0.017 | output coef ~0.04 |
| C. country-FE bivariate | 0.050 | 0.021 | within |
| D. country-FE + output control | 0.046 | 0.020 | static long-run-ish; 95% CI [0.006, 0.085] |
| **E. dynamic LSDV (lagged inflation) — used** | **0.027 (short-run)** | 0.015 | ρ=0.51, long-run = 0.055 |
| F. Anderson–Hsiao IV (consistent, robustness) | 0.003 | 0.023 | ρ=0.44; CI [−0.04, 0.05], imprecise |

Reading the ladder:

1. **The raw cross-country slope (0.235) is mostly between-country regime heterogeneity** — countries
   with chronically high money growth also run chronically high inflation. Country fixed effects
   collapse the *within-country* pass-through ~5× (C/D ≈ 0.05); the output control leaves it there.
2. **Adding lagged inflation (dynamics) matters, because the model already carries persistence.** The
   estimated persistence **ρ ≈ 0.51 (LSDV) / 0.44 (AH) brackets the model's
   `INFLATION_EXPECTATION_ANCHOR = 0.5`** — a clean independent validation of the model's inflation
   anchor. The *short-run* (per-period) money pass-through conditional on that persistence is **λ ≈
   0.027**; the Anderson–Hsiao IV (consistent but weak-instrument-imprecise) agrees the effect is weak
   (point ~0, CI spans both 0 and 0.027).

**Used: λ = 0.027** — the dynamic short-run coefficient. It is the right object for the model because
the model supplies persistence at ρ_model = 0.5, so the per-period term λ·(money−ref) reproduces the
empirical **long-run** within-country pass-through (~0.05) through the model's long-run multiplier
1/(1−0.5) = 2 (2 × 0.027 ≈ 0.05, consistent with static FE 0.046 and dynamic-LSDV long-run 0.055).
R²_within ≈ 0.01–0.02: within a country over time, money growth is a *very weak* inflation driver —
the genuinely "deliberately weak modern pass-through", now identified through FE + output control +
dynamics + cluster-robust SE rather than asserted.

**Caveat:** the model's "broad money" is the SFC deposit stock (a stylized counterpart to empirical
M2/broad money), anchored by the g*+π* reference. λ transfers the empirical *sensitivity*; it does
not require the model's money aggregate to equal observed M2.

### Golden impact (2015–2023 backtest)

Activating λ = 0.027 is indistinguishable from golden (only CO₂ moves in the 4th decimal):

| | GDP RMSE | CO₂ RMSE | Temp RMSE |
|---|---|---|---|
| golden (λ=0) | 0.5903 | 1.1483 | 0.1349 |
| λ = 0.027 | 0.5903 | 1.1482 | 0.1349 |

So the channel is golden-safe **even when active**. Headline activation (set `MONEY_INFLATION_PASS =
0.027`) would stay inside the validated band, but it remains a deliberate re-anchor decision (refresh
the golden fixture + flip the `test_money_prices` default-off assertion). Until taken, the mechanism
ships off-by-default.

## Activating

```python
run_historical_backtest(params_override={"MONEY_INFLATION_PASS": <λ>})
```

`tests/test_money_prices.py::test_money_pass_changes_trajectory` confirms the channel propagates end
to end: money growth → inflation → Taylor rule → cost of capital → investment → GDP.

## Files

- `gim/core/labor_market.py` — the optional money term in `update_inflation_unemployment`.
- `gim/core/calibration_params.py` — `MONEY_INFLATION_PASS`.
- `gim/core/private_finance.py` — source of `economy._money_supply` (E3.3).
- `tests/test_money_prices.py` — golden-safety + activation tests.
