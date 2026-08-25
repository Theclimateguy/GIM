# Re-validation of paper headline numbers under the geo-on headline (2026-06-26)

> **17.3.0 note.** This is a point-in-time record of the geo-on activation, run on the *pre-17.3.0*
> golden (GDP 0.5917 / CO₂ 1.1467 / T 0.1349). The 17.3.0 development-structured recalibration later
> moved the golden to **0.621 / 0.933 / 0.135** on a corrected 2015 state (see `CHANGELOG.md`); the
> conflict, integration-benchmark, and Morris-structure findings below are unchanged. The numbers in
> this note are retained as-run for provenance.

The geographic-coupling channels were activated by default in S6 (`TRADE_GRAVITY_INIT`,
`GEOGRAPHY_CONFLICT_LINKS`, `GEOGRAPHY_TENSION_LINKS`, `GEOGRAPHY_CLIMATE_LINKS` all `True`). This note
records a re-run of the paper's headline quantities under that configuration, to confirm none drifted.
**Verdict: every quoted number holds.** Two pre-existing bookkeeping drifts (from the social-validation
program, *not* from geo) were surfaced and are listed as action items.

## Confirmed — matches the paper

| Quantity | Paper | Re-run (geo-on, live) | Source |
| --- | --- | --- | --- |
| GDP RMSE 2015–2023 | 0.59 trln $ | **0.5917** | `run_historical_backtest()` |
| CO₂ RMSE 2015–2023 | 1.15 Gt | **1.1467** | same |
| T RMSE 2015–2023 | 0.135 °C | **0.1349** | same |
| Conflict AUC | 0.736 [0.59; 0.86] | **0.7361 [0.591; 0.864]** | `conflict_auc_inference.py` |
| Conflict BSS / p | +0.143 / ≈0.001 | **+0.143 / 0.00118** | `conflict_backtest.py` |
| Integration benchmark (App B) | 6% / ×2.7 / +4 / 0.09 / 0.015 | **6.42% / ×2.73 / +4 / 0.0895 / 0.0139** | `integration_benchmark/gim_benchmark.py` |
| Morris — temperature top-3 | ECS, ocean exchange, surface heat cap | **ECS 0.64, OCEAN 0.29, HEATCAP_SURF 0.14** | `run_sensitivity.py` |
| Morris — CO₂ top-2 | emission scale, decarb rate | **EMISSIONS_SCALE 30.9, DECARB 23.3** | same |
| Morris — GDP top-3 | depreciation, damage, energy intensity | **DAMAGE 11.0, CAPITAL_DEP 9.5, GAMMA_ENERGY 7.4** | same |
| Morris — tension | ~3 orders below physical, noise floor | **μ\* ≈ 0.005 vs 0.6–31; jumbled** | same |
| Morris robustness (GDP) | Spearman ρ ≥ 0.99; top-4 stable, 5th swaps | **ρ(8 vs 32) = 0.9956; stable-4 + 5th swaps** | `run_sensitivity_robustness.py` |

The geo activation did not move any headline number beyond its quoted precision and did not disturb the
sensitivity structure (the drivers remain physico-economic, as the paper states).

## Two drifts — RESOLVED 2026-06-26 (from S1–S3, not geo)

1. **Parameter counts are stale: 26 → 33 key, 294 → 305 all.** The social-validation program added 7 key
   priors (`CRISIS_SEVERITY_ALPHA`, `MIGRATION_BASE_RATE/MAX_SHARE/INCOME_PUSH_W/CONFLICT_PUSH_W`,
   `REGIME_COLLAPSE_GDP_MULT/CAPITAL_MULT`). The paper still says **26 key / 294 all** in 6 places
   (Morris text, figure caption, and Appendix A, in both the RU and EN versions).
   Note **26 = 33 − the 7 social priors**, and the paper's own text says the screen "varies only
   physico-economic priors." So the faithful fix is a **design choice**:
   - **(a)** restrict the Morris screen to the 26 physico-economic priors (exclude the 7 social) and keep
     "26" — preserves the published figure and the "top-4 stable, 5th swaps between two *economic*
     params" wording; or
   - **(b)** update text+figure to 33 key / 305 all — but then `REGIME_COLLAPSE_GDP_MULT` (social) enters
     GDP's stable top-4 and the 5th swaps economic↔climate, so the surrounding sentence needs editing.
   Recommendation: **(a)** — least disruptive and matches the paper's stated intent. Implement by passing
   `SENS_NAMES` (the 26 physico-economic names) to `run_sensitivity.py`, or by splitting `key_priors()`
   into physico-economic vs social subsets.
   **Resolved — chose (b):** updated all 6 spots to **33 key / 305 all**; revised the GDP robustness
   sentence (RU+EN) so the stable top-4 now names the regime-collapse GDP multiplier and the 5th
   alternates between K–E substitution and climate sensitivity; regenerated `fig3_sensitivity.pdf/png`
   from the 33-factor Morris artifacts (suptitle "33 priors", new `regime collapse (GDP)` label).

2. **Golden backtest fixture is pinned to geo-off.** `tests/fixtures/historical_backtest_baseline.json`
   holds GDP 0.5903 / CO₂ 1.1482 (the geo-*off* values per the S6 program note), while the live geo-on
   headline is 0.5917 / 1.1467. The gap is < 0.3% (within the paper's rounding), and the suite still
   passes on tolerance, but the golden is technically off-config relative to the headline. Fix:
   `python3 calibration/refresh_historical_backtest_baseline.py` to re-pin it to the geo-on headline (a
   calibration decision — confirm the suite tolerance and golden intent first).
   **Resolved:** refreshed; fixture now 0.5917 / 1.1467 / 0.1349 (geo-on); full suite **460 passed**.

## Artifacts (ledgers written this pass)

- `results/calibration/conflict_auc_inference.json` (AUC CI + permutation)
- `results/integration_benchmark/latest.json` (App B re-run)
- `results/sensitivity-*/sensitivity.json` (Morris, 4 metrics)
- `results/sensitivity_robustness/robustness_world_gdp.json` (r-convergence + seed stability)
