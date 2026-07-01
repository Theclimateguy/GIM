# GIM18 reviewer-response program — model deepening & global sensitivity

Closes GitHub issues #11–#19 (reviewer-proposed deepening of the climate, economy and social modules,
plus a global sensitivity analysis). All work done locally in a worktree; golden discipline preserved
(every change is either bit-identical by default or a documented, backtest-in-band re-anchor).

**Headline backtest after all changes (2015–2023):** GDP RMSE **0.598** (was 0.621 — *improved*),
CO₂ RMSE **0.939**, temperature RMSE **0.145**; climate backtest (1990–2023) temp RMSE **0.096**,
best-fit ECS **3.0** (both unchanged). Full suite green.

---

## Per-issue outcomes

| # | Area | Change | Default | Tests |
|---|---|---|---|---|
| 19 | Production | Documented DRS as a near-neutral design choice; bounded DRS-vs-CRS test | headline | `test_returns_to_scale` |
| 12 | Climate | Internal-variability σ/ρ re-derived from observed residuals | headline | `test_temperature_variability_calibration` |
| 11 | Climate | Forward non-CO₂ ERF from SSP2-4.5 table (vs unbounded linear) | headline | `test_nonco2_forward_forcing` |
| 17 | Damage | Howard-Sterner-central coeff + 2023-normalised; Burke growth channel | headline + switch | `test_damage_function_calibration` |
| 15 | Social | Logistic demographic transition (Lutz/Preston) | switchable (off) | `test_demographic_transition` |
| 16 | Social | Trust sensitivities anchored (misery-index 2:1) + interaction | headline + switch | `test_trust_sensitivity_calibration` |
| 13 | Economy | β-convergence slope validated, SE added | headline | `test_tfp_convergence_validation` |
| 14 | Economy | Sovereign-spread coeffs anchored (Hilscher-Nosbusch/Arora-Cerisola) | headline | `test_sovereign_spread_calibration` |
| 18 | GSA | Sobol/Saltelli over top-20 priors | tooling | (script) |

---

## Conclusion-relevant findings (for the paper)

These materially affect, strengthen, or honestly qualify prior GIM conclusions:

1. **(#11) Prior forward warming was biased HIGH.** The non-CO₂ forcing used an unbounded linear
   trend (0.012 W/m²/yr → **1.42 W/m² at 2100**, physically implausible). Replacing the post-2024 path
   with the SSP2-4.5 marker (plateau **0.73 W/m²**) lowers projected **2100 GMST from 3.12 °C to
   2.75 °C (−0.37 °C)**. The historical calibration (ECS 3.0, 1990–2023) is untouched. **Forward/SCC
   warming numbers in the paper shift down ~0.37 °C.**

2. **(#17) Damage was double-counting the base year; corrected & re-anchored.** GIM anchors GDP to
   2023-observed values (which already embed today's climate damage), yet the damage multiplier was
   measured from pre-industrial — double-counting at the base. Normalising to 2023 **removed a spurious
   base damage and *improved* the backtest GDP RMSE (0.621 → 0.598).** The coefficient was re-anchored
   to the Howard-Sterner (2017) preferred central (~7% at +3 °C). *Honesty:* the issue's premise that
   the old value implied "0.6% at 3 °C" was a miscalculation (0.006·9 = 5.4%); Kotz et al. (2024),
   cited by the issue, is **retracted** and is deliberately excluded as an anchor.

3. **(#19) DRS is not a hidden 43% bias.** The exponent sum (0.942) was flagged as a possible 43%
   long-run output penalty. In GIM it is not: per-country `_scale_factor` re-anchoring pins the output
   level at the base year, so renormalising to CRS moves 2100 GDP by only ~7–9% (and the sign depends
   on which factor absorbs it). **A reviewer concern is resolved as immaterial, with a test to prove it.**

4. **(#12) The temperature ensemble was under-dispersed.** σ re-derived from the observed 1990–2023
   forced residuals (AR(1) fit 0.097, 95% CI [0.074, 0.120]); the spread-matched operating value 0.088
   makes the predicted ensemble spread equal the observed (0.104 ≈ 0.103). The assumed ENSO-like
   persistence ρ=0.65 is **not supported** — the forced residuals are near-white (ρ≈0.13).

5. **(#13) β-convergence is externally validated.** Fresh OLS on the WB real-PPP cross-section gives
   0.0144 (SE 0.0039, 95% CI [0.0068, 0.022], R² 0.44); the in-model 0.0093 is inside the CI and the
   literature band — **a reviewer-requested external validation passes.**

6. **(#18) Variance is concentrated in a few parameters** (see GSA section): calibration effort and the
   paper's uncertainty discussion should focus on those, and many priors are provably immaterial.

---

## #18 Global Sensitivity Analysis (Sobol/Saltelli)

Sobol variance decomposition (Saltelli 2010 S1 + Jansen 1999 ST), low-discrepancy Sobol sampling,
**N=128, 2816 model evaluations**, each a deterministic 2015→2050 forward run. Four outputs; the
carbon-cycle feedback switch was enabled so `CARBON_FEEDBACK_CO2_GTCO2_PER_C` is a live parameter.
Full indices in `calibration/gsa_results.json`.

**Total-order driver of each output (ST):**

| Output (2050) | Dominant driver | ST | 2nd | ST |
|---|---|---|---|---|
| Global temperature | `ECS_DEFAULT` | 0.95 | `CARBON_FEEDBACK_CO2…` | 0.04 |
| Global GDP | `TFP_CONVERGENCE_SENS` | 0.88 | `DEBT_SPREAD_QUADRATIC` | 0.08 |
| Atmospheric CO₂ | `CARBON_FEEDBACK_CO2…` | 0.81 | `TFP_CONVERGENCE_SENS` | 0.16 |
| Global Gini | `DEBT_SPREAD_QUADRATIC` | 0.86 | `DEBT_SPREAD_LINEAR` | 0.17 |

**Findings:**
- **Variance is concentrated and physically attributable**, not a tangle of compensating priors: each
  output is dominated by a single, mechanistically-correct parameter (climate sensitivity → temperature;
  catch-up convergence → GDP; carbon feedback → CO₂; sovereign-spread curvature → inequality).
- **The high-leverage parameters are now empirically anchored.** Of the ST>0.05 priorities
  (`ECS_DEFAULT`, `TFP_CONVERGENCE_SENS`, `DEBT_SPREAD_QUADRATIC`, `DEBT_SPREAD_LINEAR`,
  `CARBON_FEEDBACK…`, `SAVINGS_BASE`, `TRUST_UNEMPLOYMENT_SENS`), three were anchored *in this very
  cycle* — `TFP_CONVERGENCE_SENS` (#13, validated + SE), `DEBT_SPREAD_LINEAR/QUADRATIC` (#14) — and
  `ECS_DEFAULT` is the IPCC AR6 best estimate. The GSA thus retroactively confirms #13/#14 targeted the
  right parameters.
- **Ten priors are freezable** (max ST < 0.01 across all four 2050 outputs): `DECARB_RATE_STRUCTURAL`,
  `CRISK_TEMP_SENSITIVITY`, `PHILLIPS_SLOPE`, `GINI_GROWTH_SENS`, `EVENT_BASE_PROB`, `CES_SIGMA_KE`,
  `SFC_ACCEL_SENS`, `TAYLOR_PHI_PI`, `STRUCTURAL_TRANSITION_POLICY_SENS`, `RESILIENCE_TECH_W`. Their prior
  uncertainty does not propagate to the 2050 headline outputs — they can be frozen, simplifying the
  uncertainty story in the paper.
- `DAMAGE_QUAD_COEFF` has low ST (0.02) **at 2050** because warming is still modest then; its influence
  grows toward 2100 (a horizon-dependent caveat worth stating, not a contradiction of #17).


---

## Honesty / completeness ledger

- Where raw microdata could not be downloaded in-environment (PWT10, HadCRUT5 full, RCMIP, BIS, WVS,
  Burke panels), parameters are anchored to **published point estimates + CIs with real citations**, and
  every such case is tagged as literature-anchored (not a re-run of the source microdata). Where data
  *is* bundled (WB WDI/WGI real-PPP panel, the 1990–2023 climate fixture), the regression is run and the
  SE/R²/CI reported.
- Kotz et al. (2024) is retracted and excluded despite being cited by issue #17.
- Switchable-but-calibrated channels (#15 demographic logistic, #17 Burke growth effect, #16 Gini×unemp
  interaction) are kept **off by default** to preserve the golden and avoid contestable headline claims,
  exactly as the codebase already treats `RD_STOCK_GROWTH`, `EXPECTATIONS_HORIZON`, etc. Their calibrated
  on-values and effects are documented so they can be activated deliberately in a future re-anchor.

## Reproduce

```
PYTHONPATH=<repo root> python3 calibration/calibrate_variability_ar1.py      # #12
PYTHONPATH=<repo root> python3 calibration/calibrate_demographics.py         # #15
PYTHONPATH=<repo root> python3 calibration/calibrate_tfp_convergence.py      # #13
PYTHONPATH=<repo root> python3 calibration/calibrate_sovereign_spreads.py    # #14
PYTHONPATH=<repo root> python3 calibration/global_sensitivity.py 128         # #18
python3 -m unittest discover -s tests
```
