# GIM paper revision — consolidated findings

Evidence base: ten experiments, `Paper/revision/scripts/e1..e10`, results as JSON under
`Paper/revision/results/`. Chronology and method notes in `LOG.md`. Every headline number
in the current manuscript that these experiments touch was **reproduced first**, then
tested against a null the paper does not currently run.

Reproductions confirmed: Fano 2.0 (E1: 1.99), conflict AUC 0.739 (E8: 0.7394), social
channel correlations +0.59/-0.52 (E5: +0.490/-0.598), oil cascade "two importers at 3%
burden, four by 15%" (E7, exact), the 2015-2023 in-sample RMSEs (E4). The engine does what
the paper says it does. What follows is about what those numbers mean.

---

## 1. One defect explains most of the paper's headline results

`gim/core/calibration_params.py:580-592` carries a diagnosis dated **2026-07-12** that was
never acted on: `trust_gov` has no equilibrium term of its own, so it drifts down at a
near-constant rate until clamped, after which the `SOCIAL_TRUST_ANCHOR_SENS` /
`TRUST_TENSION_SENS` coupling turns the drift into a self-reinforcing collapse.
`TRUST_GINI_SENS * gini` alone contributes about -0.0165/yr and is never offset. The fix
(`TRUST_ANCHOR_PULL`) is implemented and ships defaulted to 0.0. Resource prices got the
equivalent fix — `PRICE_ANCHOR_PULL = 0.15` — and E6 shows it works.

Measured (E2): mean trust falls **0.585 -> 0.242** over 2023-2053, at -0.0121/yr, with
**57 of 57 agents drifting down in every configuration tested**, including a strong 20%/yr
mean reversion. Across the 120-member ensemble of E5, mean final trust is **0.195** —
below the 0.20 regime-collapse threshold.

Three headline results are downstream of this:

| paper claim | what the null says |
|---|---|
| §6 "late clustering of failures" — the paper's *cleanest* case | Dead (E1, E2). See §2. |
| §4 above-unity modes confined to the slow socio-fiscal subspace | Largely this defect (E3). See §3. |
| §6 lagged, mediated economy->society channel, "mediation structure not coded" | The localization half is dead; the impulse-response half survives (E5). See §4. |

**This is the first thing to fix, and it is a code fix, not a text fix.** Every number in
Sections 4, 6 and 7 moves when `trust_gov` gets a restoring force.

## 2. Section 6, claim 4 (late clustering) — withdraw

Three independent failures (E1):

- **Fano 2.0 measures the trend, not clustering.** Against an inhomogeneous-Poisson
  surrogate with the same fitted intensity, the null mean is **2.19 [1.58, 2.86]** and the
  model's 1.99 sits *below* it. Detrended dispersion is **0.75** — the counts are more
  regular than Poisson. The homogeneous-Poisson reference (Fano = 1) was the wrong null.
- **The ramp survives severing every cross-block channel** (2.10 -> 8.90 vs baseline
  3.30 -> 9.00). It is not accumulators maturing *together*.
- **The crisis mix is degenerate.** fx crises fire **zero times in 30 years in every
  configuration**. Debt onsets stop in 2032 (3 total, centroid 2027). Regime crises carry
  138 of 141 onsets, centroid 2043.5. Economic and social onsets correlate at **-0.34**,
  16 years apart. They do not mature together; they are anti-correlated.

The fx trigger never firing is a model finding in its own right and needs its own
investigation before the block can be claimed as functional.

## 3. Section 4 (stability) — reduce the claim

Sweeping `TRUST_ANCHOR_PULL` (E3), Jacobian by central differences at 2026/2036/2046:

| pull | rho 2026 | n eigs > 1 | above-unity mass social / econ / climate | dominant eigenvector top coord |
|---|---|---|---|---|
| 0.0 (headline) | 1.0750 | 76 | 0.61 / 0.39 / 0.00 | `trust_gov` |
| 0.05 | 1.0517 | 50 | 0.56 / 0.44 / 0.00 | `trust_gov` |
| 0.10 | 1.0363 | 38 | 0.43 / 0.57 / 0.00 | `trust_gov` |
| 0.20 | 1.0201 | 32 | 0.30 / 0.70 / 0.01 | `social_tension` |

Give trust a restoring force and rho falls monotonically, two thirds of the above-unity
modes disappear, and the above-unity mass moves from the social block to the economic one.

**Survives, and should become the claim:** rho stays above unity (1.020-1.025) even with a
strong anchor, 25-32 modes remain above one — but on `unemployment` and `public_debt`, not
on social coordinates. And **climate mass in the above-unity subspace is 0.00 in every
configuration**, so "climate perturbations contract" holds throughout.

**Does not survive:** "confined to the slow socio-fiscal subspace ... social perturbations
fail to contract", presented as a structural property of coupled world models. It is, to a
large extent, one missing term.

## 4. Section 6, claim 1 (social channel) — keep the IRF, drop the localization

E5, 120 members, same draws scored three ways: L = final tension level (the paper's
statistic), D = baseline drift slope, R = paired shock-minus-baseline IRF integral.

| prior | rho vs level | rho vs drift | rho vs shock response |
|---|---|---|---|
| `SOCIAL_TRUST_ANCHOR_SENS` | -0.598 | -0.545 | **+0.029** |
| `INEQUALITY_EFFECT_SENS` | +0.490 | +0.169 | **-0.096** |
| `SOCIAL_STRESS_UNEMPLOYMENT_SENS` | +0.312 | +0.129 | **+0.210** |

Aggregate: level vs drift **+0.578**; level vs causal response **-0.123**.

The two priors the paper cites as evidence of an uncoded mediation structure are the
coefficients on the drift terms of a non-stationary accumulator, and have no relationship
to the causal response. The one prior that governs the response is the coded
economy -> society coefficient.

**The impulse response itself is methodologically sound** — `social_channel_analysis.py`
differences shock against a paired baseline, so the drift cancels. Build the claim on the
IRF; delete the localization argument.

## 5. Section 6, claim 5 (spatial) — survives and strengthens

E10. Fit cost of the spatial channel is **0.001-0.004%**, two orders of magnitude below
the stated "under a quarter of a percent". And the channel is not merely free: switching
tension diffusion off raises cross-country tension dispersion by **+13.5%**, quadrupling
the weight lowers it by **-13.3%**, monotone in the weight. That is a measured effect size
and a far better claim than "spatially realistic propagation at no cost in anchor".

Separately, the **climate** spatial channel has no measurable downstream effect (-0.000%
on tension dispersion, 0.00% on regime crises), because there is no climate -> society path
at all (see §8).

## 6. Section 5 (validation) — rename the hold-out, requantify the calibration

**The 3-sigma cut does not bind, and not marginally** (E4, 600 draws): **0/600 ruled out**,
maximum implausibility anywhere in the prior box **1.689** against a cut at 3.0, median
0.665 — 4.5x of headroom. Tolerances are loose by a consistent factor of ~5:

| output | current tol | tol that would bind at 3 sigma | median I | max I |
|---|---|---|---|---|
| world_gdp | 6.0 T$ | 1.19 | 0.594 | 0.619 |
| global_co2 | 2.0 Gt | 0.384 | 0.576 | 1.446 |
| temperature | 0.15 C | 0.028 | 0.556 | 1.689 |

`world_gdp` implausibility spans 0.594-0.619 across the **entire** prior box — the
2015-2023 window does not identify the economic parameters at all.

**The constructive half.** Implausibility still *ranks* draws by out-of-sample error:

| out-of-sample error | rho vs max-I | rho vs own-output I | best/worst decile lift |
|---|---|---|---|
| CO2 2020-2023 | +0.516 | **+0.950** | 2.05x |
| temperature 2020-2023 | +0.522 | **+0.899** | 1.75x |
| country GDP 2020-2023 | +0.059 | **+0.920** | 1.00x |

Per-output implausibility predicts its own out-of-sample error at rho 0.90-0.95, but the
`max_o I_o` aggregation **destroys that for GDP** (+0.06, lift 1.00) because the max is
taken by temperature or CO2. That is a reportable methodological result: max-aggregation is
wrong for a multi-domain simulator, and per-output implausibility should be kept separate.

**Naming.** Drop "constraint hold-out". The exercise is a **free-running temporal
out-of-sample test** — legitimate, because 2020-2023 enters nowhere — plus a separate and
better statement about what history matching does here: it ranks, it does not filter.

## 7. Section 5 (conflict) — the composite fails its own benchmark

E8, 57 agents, 21 positives, 20,000 paired bootstrap resamples:

| score | AUC | 95% CI | composite - this | P(composite better) |
|---|---|---|---|---|
| composite `conflict_proneness` | 0.7394 | [0.600, 0.861] | — | — |
| **`1 - regime_stability`** | **0.7765** | [0.644, 0.890] | -0.0375 [-0.114, +0.032] | **0.146** |
| `social_tension` | 0.7487 | [0.609, 0.872] | -0.0092 | 0.388 |
| `military_power` | **0.4722** | [0.300, 0.643] | +0.2684 | 0.989 |

A single WGI-derived governance indicator outranks the blend. The composite adds nothing
detectable and is point-estimate worse; `military_power` is below chance while carrying a
0.20 construction weight.

Either benchmark the composite explicitly against `1 - regime_stability` and say it does
not improve on it, or use regime stability directly. The current sentence — "no coefficient
estimated from conflict data ... AUC 0.739" — is true and will not survive review as
written.

## 8. Appendix B — transfer functions, not a "dividend"

E7. The "integration dividend" framing is unsalvageable: a sectoral model's slope on the
society axis is zero by construction, not by measurement. The shapes, however, are real and
measurable:

| channel | response | exponent | R2 linear -> quadratic |
|---|---|---|---|
| carbon tax | emissions cut | +0.891 | 0.9957 -> 1.0000 |
| carbon tax | tension | +1.078 (**linear**) | 0.9896 -> 0.9984 |
| oil burden | importers in crisis | stepped, 5 levels | 0.714 -> 0.909, 8-country jump |
| crop loss | food affordability | +1.676 | 0.8870 -> 0.9989 |
| crop loss | protest pressure | +1.676 | 0.8876 -> 0.9989 |

Three corrections:

1. **The crop chain does not compound across blocks.** protest/food gain is **0.15051,
   range [0.15030, 0.15075] over a sevenfold dose range — 0.29% spread.** The
   resources -> society leg is a constant-gain linear map; both legs carry the identical
   exponent because all curvature is generated inside the food block. Replace "compounding
   across blocks" with: a power law of exponent 1.68 generated in the resource block and
   transmitted to protest pressure with constant gain 0.15.
2. **The cascade ordering is mostly a ranking on the trigger's own variable.** Spearman
   between tipping dose and pre-shock debt/GDP is **-0.685**; against reserves only +0.15.
   The debt trigger reads debt/GDP directly. The reportable part is the residual: rho is
   not -1.0, and EGY and ESP share a debt/GDP of ~1.03-1.07 yet tip four doses apart.
3. **The oil scenario does not demonstrate a resources -> finance channel.** The supply cut
   is converted to an import bill *outside* the model by two hard-coded constants
   (elasticity 0.30, import intensity 0.05, `gim_benchmark.py:201-207`) and injected
   straight into `public_debt` and `fx_reserves`. What it demonstrates is
   finance -> sovereign-crisis thresholding.

Also: there is **no direct climate -> society channel** anywhere in the core (`climate_risk`
does not appear in `social.py`). Climate reaches trust and tension only through the
economy. Section 6's "convex escalation of food-driven instability" is composition through
the economy and should say so.

## 9. Configuration issues that affect published numbers

- **The validation configuration pins resource prices** (E6). `run_historical_backtest`
  calls `make_world_from_csv(...)` with no `forward_init`
  (`gim/historical_backtest.py:264`). Over the actual 2015-2023 backtest the **energy price
  is exactly 1.0 for all eight steps** and metals reaches its 0.30 floor in 2022. The
  validation window carries no information about the price subsystem — which independently
  explains why `GAMMA_ENERGY` is unidentified in E4.
- **The benchmark's honesty note N1 is stale.** With `forward_init=True` no resource price
  touches a bound in 30 years; `PRICE_ANCHOR_PULL = 0.15` does its job. The benchmark's
  self-imposed ban on price-mediated transmission is no longer needed.
- **Appendix B runs in the pinning configuration** (`gim_benchmark.py:371` calls
  `load_world()` with the default). Under `forward_init=True` the headline "two additional
  importers cross at ~3% of GDP" **doubles to ~6%**. Rerun the benchmark forward, or report
  the threshold as configuration-dependent.

## 10. Section 5 (country-level skill) — change the metric space

E9. In levels the model wins 50% vs persistence and 40% vs linear, with pooled skill
(-0.42, -3.58) set by China and the United States. In **annual log-growth**, the space
`celasun2021` scores in:

| metric | vs zero-growth | vs mean-growth 2015-2019 |
|---|---|---|
| win rate | **60.0%** | **50.0%** |
| pooled skill | **+0.074** | -0.033 |

Country-level growth skill is at parity with a naive mean-growth rule — the same bar
professional forecasts meet in Celasun et al. Report growth, state the win rate rather than
pooled skill, and keep levels as a secondary panel.

---

# What to do, in order

**Code, before any text.**
1. Give `trust_gov` an equilibrium term. `TRUST_ANCHOR_PULL` is not enough on its own — at
   0.20 all 57 agents still drift down. The drift source is `TRUST_GINI_SENS * gini` at
   ~-0.0165/yr against a `TRUST_GDP_PC_SENS` term of ~+0.0005/yr.
2. Investigate why the fx trigger never fires in 30 years.
3. Decide whether the backtest should run with `forward_init=True`. If yes, every number in
   Section 5 is recomputed. If no, state in Limitations that the validation window contains
   an inert price subsystem.
4. Retune the history-matching tolerances by ~5x, or state plainly that the cut is
   non-binding and the stage is a ranking.
5. Rerun the integration benchmark under `forward_init=True`.

**Then the text.**
6. Withdraw §6 claim 4. Rebuild §6 around the two claims that survive: the paired impulse
   response (claim 1, IRF half) and the spatial diffusion effect size (claim 5).
7. Reduce §4 to what E3 leaves standing.
8. Rename the hold-out; add the per-output implausibility result as a positive contribution.
9. Benchmark the conflict composite against `1 - regime_stability` explicitly.
10. Rewrite Appendix B as three measured transfer functions; drop "dividend".
11. Switch country-level skill to growth space.
12. Merge `references_additions.bib` and index the diagnostics against the Jakeman /
    Bennett / Augusiak hierarchy so E1's surrogate test and E4's per-output implausibility
    read as additions to it rather than inventions.
13. Full equations to SI — only after a GMD topical-editor reply.

**Note on scope.** Items 1-5 change published numbers. Until they are done, the manuscript
cannot be finalised, and a pre-submission enquiry to GMD is premature.

---

# Fixes — status after 2026-08-24

Full detail in `LOG.md`. Test suite **589 passed / 657 subtests** after every change.

| # | fix | state | pending decision |
|---|---|---|---|
| 1 | trust/tension deviation form | **implemented, switches default OFF** | flip V6 on? |
| 2 | fx crisis trigger | **diagnosed; guard added, not repaired** | build a real current account? |
| 3 | resource prices vs history | **validated; data added** | fix energy inertness and the metals sign |
| 4 | history-matching cut | **implemented, `TIGHTENED_TOLERANCES` offered** | switch tolerances? |
| 5 | benchmark forward | **done, applied** | — |

## The three decisions still open

**1. Turn on V6?** The switches ship off, so the model still behaves exactly as published.
Turning them on (`TRUST_GINI_DEVIATION_FORM`, `TRUST_UNEMP_DEVIATION_FORM`,
`TRUST_INFLATION_DEVIATION_FORM`, `TRUST_GDPPC_DEVIATION_FORM`,
`TENSION_GINI_DEVIATION_FORM`, `TENSION_STRESS_DEVIATION_FORM`, `TENSION_REF_PER_AGENT`)
cuts the trust drift 62%, ends its universality, nearly doubles cross-country dispersion,
improves the shock response and the fit, and reduces the regime-crisis ramp from
1.20 -> 7.00 to 0.10 -> 2.50 per year. It also changes every number in Sections 4, 6 and 7,
which is the point. Not flipped unilaterally.

**2. Give the model a current account?** The fx channel is dead because `net_exports` is
written only by bilateral trade deals and no scripted policy proposes any. Repairing it is
a modelling addition: resource balances are in units incommensurate with GDP (raw
balance/GDP spans -142 to +569, world sum +1838 rather than 0), so it needs a calibrated
scale, residual redistribution to preserve closure, and validation against observed
current-account data not in the repository — and because two of the three trigger
conditions already coincide in 63.68% of agent-years, switching it on without recalibrating
thresholds would produce a flood of currency crises. The alternative is to say plainly in
the paper that the channel is inert under deterministic policy and drop fx from the claims.

**3. Switch the tolerances?** `TIGHTENED_TOLERANCES` exists but `DEFAULT_TOLERANCES` is
unchanged. Switching makes the calibration stage do something (NROY 15.3%, `EMISSIONS_SCALE`
constrained to 20.5% of its prior range, out-of-sample gains of 1-31%) and moves every
number that depends on the NROY region. Note that per-output ranking beats the tightened
filter on all three outputs anyway, so "rank, do not filter" is available as the primary
recommendation with tightened filtering as a secondary.

## What fix 5 already changed in the manuscript

Appendix B's numbers are now different, and one claim is largely gone: the crop
dose-response exponent falls from 1.676 to **1.176**, with R2 = 0.990 against a straight
line. The convexity Appendix B reports was largely a price-clamp artefact. The oil channel
remains genuinely stepped, the cascade-ordering result is unchanged, and the headline oil
threshold moves from a 3% to a 6% burden.
