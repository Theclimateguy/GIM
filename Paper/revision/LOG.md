# GIM paper revision — work log

Target: GMD (Geoscientific Model Development), model description paper.
Mode: facts first, manuscript rewrite last.

Work order (fixed 2026-08-24):
1. Null models for Section 6 "emergent dynamics"   [WEEK, changes claims]
2. Hold-out rename + history-matching tolerance audit
3. Model-evaluation literature gap
4. Integration "dividend" -> transfer functions
5. Country-level / trigger-level naive benchmarks
6. Full equations in SI (only after GMD topical-editor reply)

Numbering: T<n> task, E<n> experiment. Every experiment writes a JSON under
Paper/revision/results/ and a log entry here.

---
## T1 — Null models for Section 6

### Prep: cross-block coupling map
`Paper/revision/CROSS_BLOCK_MAP.md`. Channels C1..C6 read off the transition code, each
resolved to the calibration parameters that carry it. Nulls are applied with
`ParameterSet.with_overrides`, so every null is a reportable parameter diff. The existing
`_ablation_disabled_channels` machinery covers only three intra-economy channels and was
not usable for cross-block severance.

Recorded while mapping: **there is no direct climate -> society channel.** `climate_risk`
does not appear in `social.py`. Climate reaches trust/tension only through
climate -> economy -> society. Section 6's "convex escalation of food-driven instability"
is therefore composition through the economy, and the paper should say so.

### E1 — crisis clustering vs trend-matched null and coupling severance
`scripts/e1_crisis_clustering_null.py` -> `results/e1_crisis_clustering_null.json`
30-year deterministic baseline, extreme events off, simple policy, forward_init — same
configuration as `scripts/run_stability_analysis.py`.

Baseline reproduces the paper: 3.30 -> 9.00 crises/yr, **Fano 1.99** (paper: 2.0). Then:

| config | mean/yr | 1st dec -> last dec | Fano | trend-matched null | detrended disp. |
|---|---|---|---|---|---|
| baseline                    | 6.97 | 3.30 -> 9.00 | 1.99 | 2.19 [1.58, 2.86] | 0.75 |
| C1 severed (econ->soc)      | 6.90 | 3.20 -> 9.60 | 2.22 | 2.26 [1.66, 2.96] | 0.92 |
| C2 severed (soc->econ)      | 6.17 | 2.20 -> 9.20 | 2.28 | 2.59 [1.91, 3.43] | 0.61 |
| C1+C2 severed               | 6.03 | 2.00 -> 9.10 | 2.57 | 2.60 [1.92, 3.38] | 0.88 |
| C3 severed (clim->econ)     | 6.97 | 3.30 -> 9.00 | 1.99 | 2.20 [1.57, 2.92] | 0.75 |
| C6 severed (cross-country)  | 7.07 | 3.40 -> 9.30 | 2.00 | 2.16 [1.56, 2.86] | 0.80 |
| **all cross-block severed** | 6.10 | 2.10 -> 8.90 | 2.15 | 2.46 [1.82, 3.21] | 0.62 |

Three findings, all negative for the claim as written.

1. **Fano 2.0 is trend, not clustering.** Against an inhomogeneous-Poisson surrogate with
   the same fitted intensity, the baseline Fano of 1.99 sits *below* the null mean (2.19)
   and deep inside the null band. Detrended dispersion is 0.75 — the counts are *more*
   regular than Poisson, not clustered. Fano on a trending deterministic series measures
   the trend; the homogeneous-Poisson reference (Fano = 1) was the wrong null.
2. **The ramp survives severing every cross-block channel** (2.10 -> 8.90). "Slow
   accumulators across blocks mature together" is not what produces it.
3. **The crisis mix is degenerate.** Per-type counts, baseline:
   - fx: **0 in all 30 years, in every configuration** — the trigger never fires.
   - debt: 3 onsets total, all before 2032, then flat at 2-3 active. Centroid 2027.
   - regime: 138 onsets, centroid 2043.5, carries 100% of the ramp.
   Economic and social onsets are *negatively* correlated (lag-0 r = -0.34; -0.30 at
   lag 1, -0.40 at lag 2). They do not mature together — they are 16 years apart.

C3 severance changes nothing at all (identical series), which is its own finding: climate
damage has no measurable effect on crisis incidence over 30 years at the headline
calibration.

### E2 — the ramp is a missing equilibrium term in `trust_gov`
`scripts/e2_trust_drift_artifact.py` -> `results/e2_trust_drift_artifact.json`

E1 put the ramp inside the social block. `gim/core/calibration_params.py:580-592` already
carries the diagnosis, dated 2026-07-12 and never acted on: `trust_gov` has no equilibrium
term of its own, drifts down at a near-constant rate until clamped, after which the
`SOCIAL_TRUST_ANCHOR_SENS`/`TRUST_TENSION_SENS` coupling turns the drift into a
self-reinforcing collapse. `TRUST_GINI_SENS * gini` alone contributes about -0.0165/yr and
is never offset. The mean-reversion fix `TRUST_ANCHOR_PULL` is implemented and defaults 0.0.

| TRUST_ANCHOR_PULL | mean trust 2023 -> 2053 | median drift/yr | agents drifting down | regime/yr 1st -> last decade | Fano |
|---|---|---|---|---|---|
| 0.0 (headline) | 0.585 -> 0.242 | -0.0121 | **57/57** | 1.20 -> 7.00 | 2.75 |
| 0.01 | 0.585 -> 0.190 | -0.0131 | 57/57 | 0.40 -> 9.30 | 3.67 |
| 0.02 | 0.585 -> 0.222 | -0.0121 | 57/57 | 0.30 -> 8.90 | 3.76 |
| 0.05 | 0.585 -> 0.256 | -0.0109 | 57/57 | 0.30 -> 7.70 | 2.79 |
| 0.10 | 0.585 -> 0.310 | -0.0091 | 57/57 | 0.10 -> 6.70 | 2.39 |
| 0.20 | 0.585 -> 0.410 | -0.0055 | 57/57 | 0.00 -> 3.20 | 1.60 |

Every country in the world loses institutional trust, every year, monotonically, in every
configuration. Mean trust falls 59% by 2053 at the headline setting. The regime-crisis rate
is a monotone function of the drift rate: damp the drift, the ramp shrinks proportionally.

**The "late clustering of failures" is the trust walk crossing a fixed 0.20 threshold.** It
is not emergent, not cross-block, and not clustered. Section 6's "cleanest case" has to be
withdrawn.

Note the drift is far larger than any defensible mean reversion: even a 20%/yr pull toward
each agent's own 2023 trust leaves all 57 agents falling. The fix is not a bigger anchor;
`trust_gov` needs a real equilibrium term.

**Consequence flagged for E3:** Section 4's headline — above-unity modes confined to the
slow socio-fiscal subspace, social perturbations failing to contract — is the signature a
state variable with no restoring force produces by construction. Testing whether that
result is the same artifact.

## T2 — Hold-out and the history-matching tolerance

### E4 — constraint power of the 3-sigma cut
`scripts/e4_constraint_power.py` -> `results/e4_constraint_power.json`
600 draws from `key_priors()` over the six `DEFAULT_CALIBRATION_PARAMS`, implausibility
computed on 2015-2019 exactly as `scripts/run_holdout_validation.py` does it.

**The cut does not bind, by a wide margin.** 0/600 draws ruled out. The maximum
implausibility anywhere in the prior box is **1.689** against a cut at 3.0; the median is
0.665, i.e. 4.5x of headroom. The paper's aside ("rules out none of the sampled draws")
is not a quirk of a 60-draw sample — nothing in this prior box can be ruled out at 3 sigma.

Tolerances (`gim/calibration_hm.py:29`) are loose by a consistent factor of about five:

| output | current tol | tol that would bind at 3 sigma | ratio | median I | max I |
|---|---|---|---|---|---|
| world_gdp   | 6.0 T$   | 1.19  | 5.0x | 0.594 | 0.619 |
| global_co2  | 2.0 Gt   | 0.384 | 5.2x | 0.576 | 1.446 |
| temperature | 0.15 C   | 0.028 | 5.4x | 0.556 | 1.689 |

Note `world_gdp` spans I = 0.594 to 0.619 across the entire prior box. World output over
2015-2023 is effectively **not identified** by these six parameters — the window carries
no information about `ALPHA_CAPITAL` or `GAMMA_ENERGY` at the world-aggregate level.

**But the ranking is informative, and that is the salvage.** Even though the filter never
fires, implausibility orders draws by out-of-sample error:

| out-of-sample error | Spearman vs max-I | Spearman vs own-output I | best/worst decile lift |
|---|---|---|---|
| CO2 RMSE 2020-2023         | +0.516 | +0.950 | 2.05x |
| temperature RMSE 2020-2023 | +0.522 | +0.899 | 1.75x |
| country GDP RMSE 2020-2023 | +0.059 | +0.920 | 1.00x |

Per-output implausibility predicts its own out-of-sample error at rho = 0.90-0.95. The
aggregate `max_o I_o` retains that for CO2 and temperature but **destroys it entirely for
GDP** (rho +0.06, decile lift 1.00) because the max is almost always taken by temperature
or CO2, whose skill is unrelated to GDP skill.

Two things follow, and both are reportable rather than embarrassing:
1. `max_o I_o` is the wrong aggregation for a multi-domain simulator. Per-output
   implausibility, kept separate, is a strong out-of-sample predictor; collapsing it to a
   max throws that away for whichever outputs do not dominate the max.
2. The correct statement about the calibration stage is that it is **non-binding at the
   published tolerances** and functions as a ranking, not a filter. Retuning the
   tolerances by ~5x would make it a filter.

Action for the manuscript: drop "constraint hold-out" as a name. The exercise is a
**free-running temporal out-of-sample test** — legitimate, because 2020-2023 enters
nowhere — plus a separate, and better, statement about what history matching does and does
not do here.

### E3 — the Section 4 spectral result is largely the same missing term
`scripts/e3_spectral_trust_mode.py` -> `results/e3_spectral_trust_mode.json`
Jacobian of the one-year map by central differences, scale-normalised D^-1 J D, at 2026 /
2036 / 2046 — the method and linearisation points of `scripts/run_stability_analysis.py`.
State vector 408 coordinates (57 agents x 7 fields + climate + prices).

| TRUST_ANCHOR_PULL | rho 2026 | rho 2036 | rho 2046 | n eigs > 1 (2026 -> 2046) | above-unity mass social / econ / climate (2026) | dominant eigenvector top coordinate |
|---|---|---|---|---|---|---|
| 0.0 (headline) | 1.0750 | 1.0758 | 1.0777 | 76 -> 72 | 0.61 / 0.39 / 0.00 | `trust_gov` |
| 0.05 | 1.0517 | 1.0529 | 1.0550 | 50 -> 55 | 0.56 / 0.44 / 0.00 | `trust_gov` |
| 0.10 | 1.0363 | 1.0373 | 1.0407 | 38 -> 35 | 0.43 / 0.57 / 0.00 | `trust_gov` |
| 0.20 | 1.0201 | 1.0241 | 1.0246 | 32 -> 25 | 0.30 / 0.70 / 0.01 | `social_tension` |

Giving `trust_gov` a restoring force moves the spectral radius monotonically toward unity
(1.075 -> 1.020), removes two thirds of the above-unity modes (76 -> 32), and moves the
above-unity mass from the social block to the economic one (0.61 -> 0.30 social). At the
headline setting the dominant eigenvector's largest coordinate is `trust_gov` at every
linearisation point.

**Section 4's headline is therefore not safe as written.** "Above-unity modes confined to
the slow socio-fiscal subspace; social perturbations fail to contract" is, to a large
extent, the signature of one state variable with no equilibrium term — the same defect E2
found. It cannot be presented as a structural property of coupled world models of this
class.

What does survive, and should be the reduced claim: rho stays above unity (1.020-1.025)
even with a strong anchor, and 25-32 modes remain above one — but they then load on
economic coordinates (`unemployment`, `public_debt`), not social ones. And climate mass in
the above-unity subspace is 0.00 in every configuration, so "climate perturbations
contract" holds throughout.

Caveat to carry into the manuscript: the scale normalisation is computed per configuration
from that configuration's own trajectory, so the four rows are not normalised identically.
The effect is small (same model, one parameter changed) but the comparison is between
configurations, not a single fixed metric.

## T3 — Model-evaluation literature

**Correction to my own initial assessment.** I said the bibliography had zero
model-evaluation methodology. That was wrong. `Paper/references_v2.bib` already carries
`oreskes1994` (verification/validation/confirmation in the earth sciences), `sterman2000`
(system-dynamics validation), `keppo2021` (IAM capability and gap stocktake),
`williamson2013` (history matching) and `celasun2021` (forecast evaluation). The real gap
is narrower and more specific: there is no IAM- or environmental-model-specific
**evaluation hierarchy** into which the paper's own diagnostics are placed, so Sections
4-6 read as invented from scratch.

`Paper/revision/references_additions.bib` — nine entries, each verified against the
publisher or repository record on 2026-08-24, none written from memory:

| key | why it is needed |
|---|---|
| `schwanitz2013` | EM&S 50:120-131. The IAM evaluation hierarchy. Non-optional. |
| `jakeman2006` | EM&S 21(5):602-614. Ten iterative steps — the frame for "what stage is each diagnostic". |
| `bennett2013` | EM&S 40:1-20. Standard vocabulary for quantitative performance characterisation. |
| `augusiak2014` | Ecol. Modelling 280:117-128. "Evaludation" — separates model validity from output validity, which is exactly the distinction the paper needs for its socio-political blocks. |
| `grimm2014trace` | Ecol. Modelling 280:129-139. TRACE documentation standard. |
| `wilson2021` | Climatic Change 166:3. Current IAM evaluation practice. |
| `grimm2020odd` | JASSS 23(2):7. ODD. A GMD reviewer will ask why a 57-agent simulator is not described against it. |
| `craig1997` | Case Studies in Bayesian Statistics III, LNS 121:37-93. History-matching origin — cited in `gim/calibration_hm.py` but absent from the bibliography. |
| `saltelli2020` | Nature 582:482-484. For the "what this class of model may and may not claim" framing. |

Positioning to write into the manuscript: the spectral radius / twin runs belong to
Jakeman's structural-verification step, the retrospective RMSE and naive benchmarks to
performance characterisation in Bennett's terms, and the socio-political blocks to
Augusiak's distinction between validating the model and validating its output. The
inhomogeneous-Poisson surrogate of E1 and the per-output implausibility ranking of E4 are
then genuine additions to that hierarchy rather than free-standing inventions — which is
the form GMD's "new methods for model evaluation" scope asks for.

### E5 — the social-channel "localization" result is a drift statistic
`scripts/e5_social_channel_level_vs_response.py` -> `results/e5_social_channel_level_vs_response.json`
120 members, 50 years, key priors plus the four direct social priors — the configuration
of `scripts/social_channel_analysis.py`. Per member: L = final-year mean tension (the
paper's statistic), D = OLS slope of baseline mean tension, R = integral of
tension(shock) - tension(base) over a 25-year IRF after a 3-year stagflation pulse.

Replication first: the paper's r_s ~ +0.59 (inequality sensitivity) and ~ -0.52 (trust
anchor) come out as +0.490 and -0.598. Same signs, same magnitudes.

| prior | rho vs level | rho vs drift | rho vs shock response | partial (level given drift) |
|---|---|---|---|---|
| `SOCIAL_TRUST_ANCHOR_SENS` | **-0.598** | -0.545 | **+0.029** | -0.413 |
| `INEQUALITY_EFFECT_SENS` | **+0.490** | +0.169 | **-0.096** | +0.487 |
| `SOCIAL_STRESS_UNEMPLOYMENT_SENS` | +0.312 | +0.129 | **+0.210** | +0.294 |
| next best (`LAND_USE_CO2_GTCO2_YR`) | +0.207 | +0.167 | -0.187 | +0.137 |

Aggregate: level vs drift rho = **+0.578**; level vs causal shock response rho = **-0.123**.

The two priors the paper names as evidence of an uncoded mediation structure are the two
that govern the LEVEL and the DRIFT and have **no relationship to the causal response**
(+0.03 and -0.10). They are the coefficients on the drift terms of a non-stationary
accumulator. Correlating them with a final level recovers the drift rate, which is a coded
consequence of a coded term.

The one prior that does govern the shock response, `SOCIAL_STRESS_UNEMPLOYMENT_SENS`
(rho +0.21), is precisely the coded economy -> society coefficient.

What survives, and should become the claim: the **impulse response** is sound. The existing
`social_channel_analysis.py` differences shock against a paired baseline, so the drift
cancels; the lagged, mediated economy -> society channel is real as a causal response. It is
the *localization* statistic that cannot support the "not coded" reading and has to go.

Also: mean final trust across the 120 members is **0.195**, below the regime-collapse
threshold of 0.20. In the average ensemble member the average country ends in regime crisis.

## T4 — Integration benchmark

### E6 — resource-price pinning: the docstring note is stale, but the backtest is affected
`scripts/e6_resource_price_pinning.py` -> `results/e6_resource_price_pinning.json`

`scripts/integration_benchmark/gim_benchmark.py` honesty note N1 states that the resource
price subsystem "saturates at its caps within one forward year (energy -> 5.0 ceiling,
food -> 0.3 floor)", and the benchmark injects every shock downstream of prices for that
reason. Measured over 30 years from the 2023 state, clamps `[0.3, 5.0]`
(`gim/core/resources.py:329-334`, hard-coded default arguments, not calibration parameters):

| config | energy | food | metals |
|---|---|---|---|
| `forward_init=True` (headline forward) | 1.00 -> 1.00, **never bounded** | 1.00 -> 3.91, never bounded | 1.00 -> 0.75, never bounded |
| `forward_init=False` (backtest / calibration) | -> 5.00 ceiling from 2037, 17 yrs pinned | -> 0.30 floor from 2026, **27 yrs pinned** | -> 5.00 ceiling from 2040, 14 yrs pinned |

**Note N1 is out of date.** With `forward_init=True` — the headline forward configuration —
no price touches a bound in 30 years. `PRICE_ANCHOR_PULL = 0.15` (the log-space mean
reversion that `trust_gov` conspicuously lacks) does its job. The benchmark's self-imposed
restriction against price-mediated transmission is no longer necessary, and the shocks
could be injected at prices, which is the natural transmission point.

**But the validation configuration is a different matter.** `run_historical_backtest`
calls `make_world_from_csv(...)` with no `forward_init`
(`gim/historical_backtest.py:264`), so Section 5's whole retrospective evaluation and all
of the history matching run in the pinning configuration. Instrumenting the actual
2015-2023 backtest:

| year | energy | food | metals |
|---|---|---|---|
| 2016 | 1.0000 | 1.0000 | 0.8035 |
| 2019 | 1.0000 | 1.0155 | 0.4010 |
| 2022 | 1.0000 | 1.1343 | **0.3000** (floor) |
| 2023 | 1.0000 | 1.2105 | **0.3000** (floor) |

Energy price is **exactly constant at 1.0 for all eight steps** — the channel is inert
across the entire validation window. Metals reaches its floor in 2022 and stays. Only food
moves, and only mildly.

Consequence: the 2015-2023 fit and the history matching carry **no information about the
resource-price subsystem**, which independently explains E4's finding that `world_gdp`
implausibility spans only 0.594-0.619 over the whole prior box. `GAMMA_ENERGY` cannot be
identified by a window in which the energy price never moves.

### E7 — transfer-function shapes, and where the nonlinearity is generated
`scripts/e7_transfer_functions.py` -> `results/e7_transfer_functions.json`

Replication first: with the benchmark's own convention (persistent `memory` dict, shock
hook applied AFTER the step, `gim_benchmark.py:62-66`) the appendix reproduces exactly —
two additional importers (ESP, ISR) cross at a 3% burden, four by 15%.

**Shapes, stated as numbers rather than adjectives:**

| channel | response | log-log exponent | R2 linear -> quadratic | reading |
|---|---|---|---|---|
| A carbon tax | emissions cut | +0.891 (R2 0.9995) | 0.9957 -> 1.0000 | near-linear, mildly saturating |
| A carbon tax | tension | +1.078 (R2 0.9818) | 0.9896 -> 0.9984 | **linear**, not "smooth" |
| B oil burden | extra importers in crisis | n/a (step) | 0.714 -> 0.909 | genuinely stepped: 5 levels, largest jump 8 countries between 15% and 20% |
| C crop loss | food affordability | +1.676 (R2 0.9724) | 0.8870 -> 0.9989 | power law, exponent 1.68 |
| C crop loss | protest pressure | +1.676 (R2 0.9725) | 0.8876 -> 0.9989 | power law, same exponent |

**The crop chain does not compound across blocks.** Appendix B says the convex response
"arises from the chain supply gap -> price -> affordability -> protest compounding across
blocks". Measured, the protest/food gain is **0.15051, ranging [0.15030, 0.15075] over a
seven-fold dose range — a relative spread of 0.29%**. The resources -> society leg is a
constant-gain linear map. Both legs carry the identical exponent 1.676 because the whole
curvature is generated upstream, inside the food block, before society sees it.

The defensible claim is better and more precise than the one in the paper: a power-law
dose-response with exponent 1.68, generated in the resource block and transmitted to
protest pressure with constant gain 0.15.

**The cascade ordering is largely a ranking on the trigger's own variable.** Spearman
between tipping dose and pre-shock debt/GDP is **-0.685** (benchmark config) / -0.650
(forward config); against reserves/GDP only +0.15 / +0.45, against GDP +0.10. The debt
trigger reads debt/GDP directly, so "an ordering selected by each country's fiscal state,
not by hand" is true but close to tautological. What is not tautological is the residual:
rho is -0.69, not -1.0, so reserves and the endogenous interest rate do reorder some
countries (EGY and ESP share a debt/GDP of ~1.03-1.07 yet tip four doses apart). That
residual is the reportable part.

**The oil scenario does not demonstrate a resources -> finance channel.** The supply cut is
converted into an import bill OUTSIDE the model by two hard-coded constants — elasticity
0.30 and import intensity 0.05 (`gim_benchmark.py:201-207`) — and injected straight into
`public_debt` and `fx_reserves`. What the scenario demonstrates is
finance -> sovereign-crisis thresholding. Appendix B's sentence "an oil-supply shock
propagates through import bills, reserves, and debt issuance" overstates what is inside
the loop.

**Configuration dependence.** The benchmark calls `load_world()` with the default
(`gim_benchmark.py:371`), i.e. `forward_init=False` — the pinning configuration of E6.
In the headline forward configuration nothing tips at a 3% burden; the first three
countries tip at 6%. The paper's headline "at a realistic burden (~3% of GDP), two
additional importers cross" **doubles to ~6% under `forward_init=True`**. The threshold
has to be reported as configuration-dependent, or the benchmark rerun under the forward
configuration.

## T5 — Naive benchmarks where the model claims to be useful

### E8 — the conflict composite does not beat its best single component
`scripts/e8_conflict_composite_vs_components.py` -> `results/e8_conflict_composite_vs_components.json`
57 agents, 21 positives (base rate 0.368), UCDP/PRIO 1990-2023, 20,000 paired bootstrap
resamples (the same resample indices for composite and component, so the difference is
paired).

Replication: composite AUC **0.7394**, CI [0.600, 0.861] — the paper's 0.739 [0.60, 0.86].

| score | AUC | 95% CI | composite - this | P(composite better) |
|---|---|---|---|---|
| **composite `conflict_proneness`** | **0.7394** | [0.600, 0.861] | — | — |
| `1 - regime_stability` | **0.7765** | [0.644, 0.890] | **-0.0375** [-0.114, +0.032] | 0.146 |
| `social_tension` | 0.7487 | [0.609, 0.872] | -0.0092 | 0.388 |
| `1 - trust_gov` | 0.7288 | [0.587, 0.852] | +0.0103 | 0.603 |
| `inequality_gini` | 0.6329 | [0.474, 0.782] | +0.1074 | 0.861 |
| `climate_risk` | 0.6151 | [0.458, 0.768] | +0.1238 | 0.958 |
| `water_stress` | 0.6052 | [0.438, 0.762] | +0.1355 | 0.949 |
| `military_power` | **0.4722** | [0.300, 0.643] | +0.2684 | 0.989 |

**A single input outranks the blend.** `1 - regime_stability` alone reaches AUC 0.7765
against the composite's 0.7394; the paired difference is -0.0375 with a CI straddling zero
and P(composite better) = 0.146. The composite adds nothing detectable over its dominant
input, and is point-estimate worse.

`military_power` scores **below chance** (0.472) while carrying a 0.20 construction weight.

Reduced form of the two construction steps (`build_gim13_agent_states.py:1172, 1372`):
0.3875*(1-regime_stability) + 0.2250*climate_risk + 0.2000*military +
0.0875*(1-trust_gov) + 0.0625*gini + 0.0375*water_stress. The score is dominated by
regime stability, and E8 says that domination is the whole of its skill.

Caveats to carry: the `military_power` column in the state CSV is not literally the
`minmax(military_gdp_ratio)` term used in construction, so that row bounds rather than
measures the construction input; and `social_tension` is itself a composite, not a
primitive. Neither affects the headline, which rests on `1 - regime_stability`.

Consequence for the manuscript. The current sentence — "a fixed-weight composite of
observed inputs with no coefficient estimated from conflict data ranks the 57 agents at
AUC 0.739" — is true but incomplete in a way a reviewer will catch immediately. The honest
version is that a single published governance indicator ranks them at 0.78 and the model's
blend does not improve on it. Either report the composite against that benchmark and say
so, or drop the composite and use regime stability directly.

This also revises my own earlier advice to the user. I said the n=57 objection could be
argued back on the grounds that 57 is the modelled population rather than a sample. That
point stands, but it is not the binding problem: the binding problem is that the
evaluation has no covariate benchmark, and once one is added the composite does not
survive it.

### E9 — country-level naive benchmarks, and the right metric space
`scripts/e9_country_level_benchmarks.py` -> `results/e9_country_level_benchmarks.json`
20 anchored economies, 2020-2023, benchmarks built from observed data through 2019 only.

**In levels** (the paper's metric):

| metric | vs persistence | vs linear |
|---|---|---|
| win rate across countries | 50.0% (10/20) | 40.0% (8/20) |
| median per-country skill | -0.045 | -0.254 |
| pooled skill | -0.423 | -3.577 |

The pooled numbers are an artefact of scale. RMSE in trillion USD over a panel spanning
three orders of magnitude is set by China (model 3.11 vs linear 0.32) and the United
States (1.40 vs 0.44); the model wins outright on Japan, Canada, Spain, Indonesia, the
Netherlands and Saudi Arabia. A metric where a 1% error on China outweighs a 30% error on
the Netherlands does not measure what the paper wants to claim.

**In annual log-growth** — the space the forecast-evaluation literature scores in, and the
space `celasun2021` (already cited) uses:

| metric | vs zero-growth | vs mean-growth 2015-2019 |
|---|---|---|
| win rate across countries | **60.0%** | **50.0%** |
| median per-country skill | +0.047 | +0.001 |
| pooled skill | **+0.074** | -0.033 |

In growth space the model is at parity with a mean-growth rule (pooled skill -0.033, win
rate 50%) and modestly ahead of zero-growth (+0.074). That is precisely the standard
Celasun et al. report for IMF WEO forecasts, which the paper already cites for the claim
that professional forecasts lose to naive benchmarks in about half of countries.

Recommendation: report country-level skill in growth space, keep the levels table as a
secondary panel, and state the win rate rather than the pooled skill. The defensible
sentence is "country-level growth skill indistinguishable from a naive mean-growth rule,
the same bar professional forecasts meet" — not "output loses to a ruler".

### E10 — the spatial channel: the one Section 6 claim that survives, and strengthens
`scripts/e10_spatial_channel_effect.py` -> `results/e10_spatial_channel_effect.json`

| config | pooled country GDP RMSE | change | forward sd(tension) | change | regime agent-years | change |
|---|---|---|---|---|---|---|
| headline (spatial on) | 0.599293 | — | 0.230559 | — | 140 | — |
| tension diffusion off | 0.599297 | +0.001% | 0.261684 | **+13.50%** | 142 | +1.43% |
| climate diffusion off | 0.599268 | -0.004% | 0.230558 | **-0.000%** | 140 | +0.00% |
| all spatial off | 0.599268 | -0.004% | 0.266913 | +15.77% | 141 | +0.71% |
| tension diffusion x4 (0.20) | 0.599282 | -0.002% | 0.199973 | **-13.27%** | 136 | -2.86% |

The fit claim holds with room to spare: the cost is 0.001-0.004%, not "under a quarter of
a percent" — two orders of magnitude smaller than stated.

And the channel is **not inert**, which is the part the paper leaves unmeasured. Switching
tension diffusion off raises cross-country tension dispersion by 13.5%; quadrupling the
weight lowers it by 13.3%. The effect is monotone in the weight and in the direction a
diffusion should act. That is a measured effect size, and a much better claim than
"spatially realistic propagation at no cost in anchor".

Separately: the **climate spatial channel has no measurable downstream effect at all**
(-0.000% on tension dispersion, 0.00% on regime crises). This is the same asymmetry the
cross-block map found — there is no climate -> society path, so a climate-risk diffusion
cannot reach the social block. It should be described as acting within the climate block
or dropped from the list of things the loop produces.

---

# Fixes

## Fix 1 — the trust/tension level-vs-deviation defect

**Diagnosis, one level above the 2026-07-12 note.** That note says `trust_gov` has no
equilibrium term. The cause is the functional form: three of the five trust drivers, and
two of the three tension drivers, enter as **levels** rather than deviations from a
reference. A country at a constant and entirely normal gini, unemployment and inflation
therefore loses trust every year forever, and gains tension every year forever. No anchor
strength cancels a constant — it only moves where the constant settles, which is why E2
found all 57 agents still drifting down at `TRUST_ANCHOR_PULL = 0.20`. The tension driver
of trust already uses the correct deviation form (`TRUST_TENSION_THRESHOLD`), so the
pattern was already in the file; four terms simply did not follow it.

**Implementation.** Seven switches, all defaulting to `False` => level form, verified
bit-identical (E1 baseline series reproduced exactly; full suite 589 passed / 657
subtests):

- `gim/core/social.py` — `TRUST_GINI_DEVIATION_FORM`, `TRUST_UNEMP_DEVIATION_FORM`,
  `TRUST_INFLATION_DEVIATION_FORM`, `TRUST_GDPPC_DEVIATION_FORM`,
  `TENSION_GINI_DEVIATION_FORM`, `TENSION_STRESS_DEVIATION_FORM`, `TENSION_REF_PER_AGENT`
- references: unemployment against `NAIRU` (0.045), inflation against `INFLATION_TARGET`
  (0.02), gini and income against each agent's own base-year value (new `_gini_anchors`,
  `_gdppc_anchors`, mirroring `_trust_anchors`)
- `TENSION_REF_PER_AGENT` additionally frees the per-agent tension reference from its
  accidental gating on `TRUST_ANCHOR_PULL`

### E11 — variant selection against four acceptance criteria
`scripts/e11_trust_form_variants.py` -> `results/e11_trust_form_variants.json`

| variant | trust 2053 | drift/yr | agents down | sd kept | tension shock response | fit change | regime 1st -> last decade |
|---|---|---|---|---|---|---|---|
| V0 current (level form) | 0.242 | -0.0121 | **57/57** | 1.17 | +0.02580 | — | 1.20 -> 7.00 |
| V1 trust gini only | 0.404 | -0.0074 | 40/57 | 2.10 | +0.01471 | -0.072% | 0.90 -> 6.70 |
| V2 trust gini+unemp+infl | 0.441 | -0.0050 | 39/57 | 2.13 | +0.01383 | -0.080% | 0.90 -> 5.60 |
| V3 trust all four | 0.439 | -0.0049 | 39/57 | 2.11 | +0.01385 | -0.079% | 0.90 -> 5.80 |
| V4 anchor only, 0.20 | 0.410 | -0.0055 | **57/57** | 1.25 | **+0.00842** | +0.146% | 0.00 -> 3.20 |
| V5 tension only | **0.164** | **-0.0148** | 57/57 | 1.15 | +0.01513 | -0.116% | 0.10 -> 4.90 |
| **V6 trust + tension** | **0.442** | **-0.0046** | **39/57** | **2.12** | **+0.02760** | **-0.195%** | **0.10 -> 2.50** |
| V7 V6 + weak anchor 0.05 | 0.473 | -0.0032 | 37/57 | 1.82 | +0.01485 | -0.195% | 0.00 -> 1.80 |

**V6 is the fix.** Against V0 it cuts the drift by 62%, ends the universality (57/57 -> 39/57,
so 18 countries now gain trust), nearly doubles the cross-country spread (the model starts
differentiating countries instead of parking them all near the floor), **improves the shock
response** (+0.0276 vs +0.0258), improves the fit by 0.195%, and reduces the regime-crisis
ramp from 1.20 -> 7.00 to 0.10 -> 2.50.

Three secondary results worth carrying into the manuscript:

- **The anchor is the wrong tool** (V4): it leaves all 57 agents drifting and buys its lower
  crisis count by crushing the shock response 67%. It suppresses dynamics rather than
  balancing the equation.
- **The two fixes only work as a pair** (V5): the tension fix alone is *worse than doing
  nothing* — trust ends at 0.164 against V0's 0.242 — because `TENSION_REF_PER_AGENT` raises
  the reference for high-trust countries while trust is still in free fall, widening the gap
  the term acts on.
- **Do not add the anchor on top** (V7): it lowers the drift a little further but costs 46%
  of the shock response and a sixth of the dispersion.

**Residual.** V6 still drifts at -0.0046/yr with 39/57 agents falling, ending at 0.442 from
0.585. That is no longer a universal countdown, and a mild secular decline in institutional
trust is not obviously wrong — but it is now a claim about the world, so it needs checking
against observed trust series (WGI, V-Dem, WVS) rather than assertion. Same family of task
as the resource-price validation in fix 3.

## Fix 2 — the fx crisis trigger

### E12 — diagnosis
`scripts/e12_fx_trigger_diagnosis.py` -> `results/e12_fx_trigger_diagnosis.json`
1710 agent-years (57 agents x 30 forward years), all three trigger inputs recorded.

| input | threshold | min | median | max | sd | share meeting condition |
|---|---|---|---|---|---|---|
| `external_debt_ratio` | > 0.50 | 0.000 | 0.669 | 1.405 | 0.284 | **74.21%** |
| `current_account_ratio` | < -0.04 | **0.000** | **0.000** | **0.000** | **0.0000** | **0.00%** |
| `fx_cover_months` | < 3.0 | 0.001 | 0.053 | 677145.7 | 91866 | **86.96%** |

Two of the three conditions coincide in **63.68%** of agent-years, and 46 of 57 agents reach
two of three at some point. All three: **zero, ever**.

**Root cause: `current_account_ratio` is structurally pinned at zero.** It derives from
`agent.economy.net_exports`, which is reset to 0.0 at the top of `apply_trade_deals`
(`gim/core/actions.py:343-344`) and written only by executed bilateral trade deals
(`actions.py:404-449`). Those come from `proposed_trade_deals`, which is populated only from
LLM or player action data (`policy.py:507`). Both scripted policies were checked directly:
**`simple` and `growth` produce zero non-zero net_exports for all 57 agents over 10 years.**

So the currency-crisis channel is alive only when an LLM or a human player proposes trade.
In every deterministic run — which is every run reported in the paper — it is identically
zero and cannot fire at any calibration. This is not a threshold problem.

Secondary finding: `fx_cover_months` has a median of **0.053 months** — 1.6 days of import
cover — and a maximum of 677,146. Both tails are implausible; the reserves-to-import-bill
scaling needs its own look before the trigger is recalibrated.

**Why the existing invariant did not catch it.** `TRADE_BALANCE_TOL` checks
`|sum(net_exports)| / world_gdp < 1e-6` — a *closure* check, which passes trivially when
every net export is zero. Added `net_exports_gross`, `gross_share` and `n_agents_with_trade`
to the trade-balance summary (`gim/core/simulation.py`) so an identically-inert trade block
is visible rather than silent. Suite still 589 passed / 657 subtests.

**Not fixed, deliberately.** Giving the model a real current account is a modelling
addition, not a repair: resource balances are in physical units incommensurate with GDP
(measured raw balance/GDP spans -142 to +569, and the world sum is +1838 rather than 0), so
it needs a calibrated scale and a residual redistribution to preserve closure, then
validation against observed current-account data that is not in the repository. And because
two of three conditions already coincide 64% of the time, switching it on without
recalibrating thresholds would produce a flood of currency crises. That decision is scoped
and handed over, not taken here.

## Fix 3 — validate resource prices against history

The observed-data fixture carries GDP, CO2 and temperature only, so no check in the
repository has ever looked at the price subsystem. Added the missing target:
`data/external/worldbank_commodity_price_indices_annual.csv` — World Bank CMO Pink Sheet
annual nominal indices (2010 = 100), energy / food / metals & minerals, 1990-2024,
retrieved 2026-08-24, CC BY 4.0, provenance in `data/external/README_commodity_prices.md`.

Scope caveat, stated in the script and in its JSON output: the Pink Sheet series are
**market** price indices for traded baskets; GIM prices are **clearing** indices for three
aggregate resources with a reserve buffer and no storage, futures or financialisation. The
fair test is direction and multi-year magnitude, not year-by-year timing.

### E13 — price validation, both configurations
`scripts/e13_price_history_validation.py` -> `results/e13_price_history_validation.json`
2015-2023, both sides renormalised to 1.0 at 2015. "Flat null" is a price held at 1.0.

| config | resource | model move | observed | direction | correlation | skill vs flat null |
|---|---|---|---|---|---|---|
| backtest (Section 5's own) | energy | **+0.0%** | +61.8% | **no** | undefined (constant) | **+0.000** |
| backtest | food | +21.0% | +41.8% | yes | **+0.878** | **+0.296** |
| backtest | metals | **-70.0%** | +55.4% | **no** | **-0.773** | **-1.263** |
| forward_init | energy | -0.1% | +61.8% | no | -0.644 | -0.001 |
| forward_init | food | +6.3% | +41.8% | yes | +0.860 | +0.088 |
| forward_init | metals | -16.5% | +55.4% | no | -0.856 | -0.241 |

Three separate findings, and they are not the same finding:

1. **Food works, and nobody knew.** Correlation +0.88 in both configurations, right
   direction, positive skill (+0.296 in the reported configuration). This is a genuine
   validation success for a block the paper never claimed anything about. It should be
   reported.
2. **Energy is inert over this window in BOTH configurations.** Skill is exactly 0.000 in
   the backtest configuration — the model price is identical to the flat null by
   construction — and -0.001 forward. E6's 30-year path shows energy only starts moving
   later, so the eight-year window is not where the forward configuration rescues it.
3. **Metals has the wrong sign in both configurations.** The observed index rose 55%; the
   model falls 70% (backtest, into the 0.30 floor) or 17% (forward). Correlation -0.77 and
   -0.86. In the reported configuration the model is **2.3x worse than a flat line**.

**Correction to my own earlier framing.** I wrote in the E6 entry that "the validation
window carries no information about the price subsystem". That holds for energy, but it is
wrong as a general statement: food is informative and the model does well, metals is
informative and the model does badly.

**Recommendation, and it is deliberately not the obvious one.** Do not simply switch the
backtest to `forward_init=True`. E13 shows that trade is real and goes both ways: forward
init makes metals much less wrong (-0.241 vs -1.263) but makes food distinctly worse
(+0.088 vs +0.296) and does nothing for energy. There is no configuration that wins on all
three. The right response is to treat the energy inertness and the metals sign error as
**model defects to be fixed**, not as a configuration choice to be made, and meanwhile to
report the price validation as a new Section 5 result with all three numbers, including the
one that fails.

## Fix 4 — the history-matching cut

`gim/calibration_hm.py`: added `TIGHTENED_TOLERANCES` (the values at which the same 3-sigma
cut rules out roughly half the prior box), documented the non-binding finding at the
tolerance definition, and documented at `implausibility()` why the per-output entries must
not be collapsed to the max. Offered, not imposed: `DEFAULT_TOLERANCES` is unchanged, so
nothing downstream moves until someone chooses to switch.

### E14 — what the stage does once the cut binds
`scripts/e14_tightened_tolerances.py` -> `results/e14_tightened_tolerances.json`
Same 600 draws, scored under both tolerance sets.

| | published | tightened |
|---|---|---|
| NROY retained | **600/600 (100%)** | 92/600 (15.3%) |
| median implausibility | 0.665 | 3.507 |
| mean prior range retained | **100.0%** | 68.8% |
| out-of-sample gain, country GDP | **+0.00%** | +1.41% |
| out-of-sample gain, CO2 | **+0.00%** | +30.68% |
| out-of-sample gain, temperature | **+0.00%** | +15.84% |

At the published tolerances the calibration stage does **exactly nothing** — every parameter
keeps 100.0% of its prior range and the out-of-sample gain is an exact zero on all three
outputs. This is stronger than E4's "non-binding": it is quantified as a null effect.

Tightened, it constrains where it should — `EMISSIONS_SCALE` down to 20.5% of its prior
range, `ECS_DEFAULT` to 48.8%, the rest 77-92% — and buys real out-of-sample skill.

**And per-output ranking beats max-aggregated filtering on every output:**

| out-of-sample error | gain from tightened filter | gain from best decile on the matching output |
|---|---|---|
| country GDP 2020-2023 | +1.41% | **+4.02%** |
| CO2 2020-2023 | +30.68% | **+37.13%** |
| temperature 2020-2023 | +15.84% | **+25.08%** |

This is the strongest positive result in the revision and the one to build the GMD
methods claim on: for a multi-domain simulator, rank draws on the output you care about
rather than filter them on `max_o I_o`. The max is a scalar summary that throws away
per-output information and, for whichever outputs do not dominate it, throws away all of it.

## Fix 5 — rerun the integration benchmark forward

`scripts/integration_benchmark/gim_benchmark.py:371` now calls
`load_world(max_agents=MAX_AGENTS, forward_init=True)`. The benchmark is a forward
experiment; without the flag it ran in the configuration where prices saturate at their
clamps, which is the whole reason honesty note N1 forbids price-mediated transmission. E6
showed that note no longer applies with `forward_init=True`.

Rerunning it changes the appendix's numbers, and one of them substantially. E7 re-scored on
the new run:

| quantity | pinning config (as published) | forward config (corrected) |
|---|---|---|
| crop -> food affordability, exponent | 1.676 | **1.176** (R2 linear 0.990) |
| crop -> protest, exponent | 1.676 | **1.216** |
| protest/food gain, spread | 0.15051, 0.29% | 0.19267, 8.46% |
| carbon -> tension, exponent | 1.078 | 1.232 |
| oil, largest step in importers tipped | 8 countries | 5 countries |
| oil, R2 linear -> quadratic | 0.714 -> 0.909 | 0.819 -> 0.878 |
| oil, first importers tip at burden | 3% of GDP | **6% of GDP** |
| crop headline: food / protest delta at -50% | 0.1066 / 0.0161 | 0.1758 / 0.0345 |

**The convexity claim mostly does not survive the correction.** Appendix B's "convex
dose-response of protest pressure to yield loss" had exponent 1.68 in the pinning
configuration; corrected it is 1.18 with R2 = 0.990 against a straight line — essentially
linear. The curvature the paper reports is largely an artefact of prices sitting on their
clamps. What survives is a small residual: the second leg now carries a slightly higher
exponent than the first (1.216 vs 1.176, gain spread 8.46% rather than 0.29%), so under the
corrected configuration the resources -> society leg does contribute a little curvature of its
own — the opposite of the pinning-configuration result, and a much smaller effect than the
paper claims.

The oil channel remains genuinely stepped and the ordering result is unchanged
(Spearman tip-dose vs pre-shock debt/GDP -0.65 forward, -0.685 pinning).

---

# Round 2 — model repairs (authorised 2026-08-24: fix the defects, nothing published yet)

## Backtest rebuilt with prices as a validation target

`tests/fixtures/historical_backtest_observed.json` gains `resource_price_index_by_year`
(World Bank Pink Sheet, renormalised to 2015 = 1.0, provenance and construct caveat in
`source_notes`). `HistoricalBacktestResult` gains `resource_price_rmse`,
`predicted_resource_prices`, `actual_resource_prices`, all defaulted so the stored baseline
fixture still loads. `calibration_hm.backtest_rmses` now reports `price_<resource>`, and
`PRICE_TOLERANCES` sets each tolerance to the RMSE a no-skill flat price makes against the
observed index — so implausibility reads directly: below 1 beats a flat line, 1 ties it,
above 1 means a constant would have been better.

Baseline at the time of writing: energy **1.000**, food 0.704, metals **2.263**.

## Three price defects, traced by following supply and demand through the backtest

| resource | annual flow (2015) | `global_reserves` | reserve / flow |
|---|---|---|---|
| energy | 0.650 | 32.5 | **50.0 years** |
| food | 4000.0 | 200.0 | 0.05 years (~18 days) |
| metals | 392.5 | 591.6 | 1.51 years |

**Defect A — metals recycling double-count.** `update_resource_stocks` treated the base-year
`production` loaded from the state CSV as PRIMARY output and then added recycled secondary
supply on top of it. At the base year that figure is TOTAL supply (it equals consumption), so
the first step injects a permanent glut of `recycle_rate x consumption`: metals supply jumps
388.9 -> 565.5 in one year — exactly `388.9 + 0.45 x 392.5` — demand/supply settles near 0.69
and the price walks to its 0.30 floor while the observed index rose 55%.
Fix: `METALS_BASE_PRIMARY_NET_OF_RECYCLING` nets recycling out of the base primary.
Effect: metals implausibility **2.263 -> 0.964**, GDP/CO2/temperature untouched.

**Defect B — the price-damping buffer reads the geological reserve.**
`update_global_resource_prices` damps the clearing price by how much standing stock can
absorb a flow imbalance, via `buffer_ratio = reserve / (reserve + imbalance)`. But
`global_reserves` is not the same quantity for each resource. For food it is ~18 days of
genuine carry-over stock — **which is precisely why food is the one resource whose price
validates against observation**. For energy it is 50 years of proven resources *in the
ground*, which cannot clear a market within the year; `buffer_ratio -> 1`, `damped_ratio -> 1`,
and the price is frozen.
Fix: `PRICE_BUFFER_YEARS_{ENERGY,FOOD,METALS}` cap the buffer in years of consumption.
Anchors: IEA 90-day net-import stockholding obligation (0.25 yr); FAO cereal stocks-to-use
~30% (0.30 yr, above what the fixture already implies, so food is untouched); exchange and
producer inventories for base metals, weeks to months (0.25 yr).

**Defect C — energy demand had no income or population elasticity.**
`ENERGY_DEMAND_POP_ELASTICITY` and `ENERGY_DEMAND_INCOME_ELASTICITY` were both 0.0, the
second carrying the note "energy demand handled by ENERGY_DEMAND_PRICE_RESPONSE". But a
price response is a one-time shift for a constant price, so energy demand grew with neither
population nor income; with static supply, demand/supply was exactly 1.0000 every year.
Fix: `ENERGY_DEMAND_INCOME_ELASTICITY = 0.5`, anchored on the IEA intensity arithmetic
(intensity improving ~2%/yr over 2010-2019 and ~1.2%/yr over 2019-2023 against ~3%/yr world
GDP growth implies ~0.33-0.6).

### E15 — calibration sweep, and what was deliberately NOT taken
`scripts/e15_demand_elasticity_calibration.py` -> `results/e15_demand_elasticity_calibration.json`
36 configurations over the price anchor pull, energy and metals income elasticities.

| config | I energy | I food | I metals |
|---|---|---|---|
| current (no fixes) | 1.000 | 0.704 | 2.263 |
| **defaults now shipped** | **0.986** | **0.704** | **0.964** |
| best on summed price implausibility | 0.959 | 0.596 | 0.819 |

The best-scoring configuration needs `METALS_DEMAND_INCOME_ELASTICITY = 2.0` and
`PRICE_ANCHOR_PULL = 0.0`. Neither was taken. A metals income elasticity of 2.0 says material
intensity rises *supra*-proportionally with income, contradicting both the literature and the
parameter's own comment; and removing the price mean-reversion entirely to gain fit on nine
observations is overfitting. Shipped: the two structural bug fixes plus one literature-anchored
elasticity. All 589 tests / 657 subtests pass.

**Honest reading of the energy result.** The energy price now moves in the right direction but
reaches 1.025 by 2023 against an observed 1.618 — about 11% of the magnitude. The observed
2015-2023 energy series is dominated by the 2020 demand collapse and the 2022 supply shock,
neither of which the model represents. Near-flat is therefore the *correct* model behaviour.
What was wrong before was that it was flat **by construction** rather than by result: same
number, entirely different epistemic status, and only the second is defensible in a paper.

### E16 — how far do prices actually reach?
`scripts/e16_price_downstream_reach.py` -> `results/e16_price_downstream_reach.json`
Every E15 configuration returned identical GDP, CO2 and temperature to four decimals, which
raised the question. Forcing each price by a fixed multiplier over a 10-year run:

| forced price | world GDP | inflation | CO2 | tension |
|---|---|---|---|---|
| energy x5 | **-6.32%** | +3.29% | **-5.28%** | +0.71% |
| food x5 | **+0.0000%** | **+0.0000%** | **+0.0000%** | **+0.0000%** |
| metals x5 | +0.0026% | +0.04% | +0.01% | -0.21% |

**Only energy has a working price -> economy channel.** Food is exact zero to five decimal
places at every multiplier up to 5x — the food price is an output-only variable that feeds
nothing. Metals moves world GDP by hundredths of a percent, non-monotonically, which is
numerical noise rather than a channel.

Two consequences.

1. The irony is worth stating plainly in the paper: food is the one resource whose price
   validates well against observation (I = 0.704) and the one whose price influences nothing.
2. **Appendix B's crop chain is wrong as written.** It describes "supply gap -> price ->
   affordability -> protest". The price leg is inert; the crop shock reaches society through
   the supply gap directly. This independently confirms E7's finding that the resource ->
   society leg transmits with constant gain — there is no price mechanism in it to add
   curvature.

## The currency channel

### E17 — repairing a structurally dead trigger
`scripts/e17_fx_channel_validation.py` -> `results/e17_fx_channel_validation.json`

E1 found the fx trigger fires zero times in 30 years, in every configuration. The cause is
that `economy.net_exports` is written ONLY by executed bilateral trade deals
(`actions.py:404-449`), which come from `proposed_trade_deals` — populated only by LLM or
player action data. No scripted policy proposes any, so in every deterministic run the
current account is identically zero for all 57 agents and the three-way conjunction can
never complete, at any calibration.

Four defects, each fixed behind a switch:

**1. The resource trade value was ~300x too large.** Resource quantities are physical and
prices are indices, so their product is not commensurate with GDP in trillions — yet
`_estimate_annual_import_bill` was divided by GDP and read as a ratio. Measured, the world
sum of net import bills was **3190% of world GDP** (median agent 2975%), which is why
`fx_cover_months` came out at a median of **0.053 months — 1.6 days of import cover**.
`fx_reserves` were already in GDP units (median 13.9%, realistic), so only the trade side
needed converting. `RESOURCE_TRADE_GDP_SHARE = 0.04` sets the scale so the world sum of net
import bills is 4% of world GDP. Anchor: WTO 2022 world exports of fuels and mining products
US$5.16tn (21% of world merchandise exports) plus agricultural products ~US$2.2tn, together
~7.4% of world GDP gross; the model carries net positions, whose sum is a fraction of gross.
Result: import bill/GDP median **29.76 -> 0.033**.

**2. Months of import cover was measured against the resource bill alone**, but the metric is
defined against total imports. `IMPORT_COVER_TOTAL_MULTIPLIER = 3.3`, anchored on resource
goods being ~30% of world merchandise trade.

**3. There was no current account.** `apply_structural_trade_balance` writes production minus
consumption valued at world prices, converted to GDP units, demeaned pro rata to GDP so the
world closes exactly — measured residual **3.97e-18** of world GDP against a
`TRADE_BALANCE_TOL` of 1e-6. Added to whatever the deal layer wrote, so bilateral deals still
move the balance on top of the structural position.

**4. `FX_CRISIS_MAX_YEARS` capped the counter but never ended the episode.** An agent whose
reserve cover did not recover stayed in crisis indefinitely with the counter parked at 4.
Nothing in the model rebuilds reserves — there is no nominal exchange rate, hence no
depreciation-driven import compression — so the crisis was an absorbing state: mean duration
**8.35 years** against a real-world 1-3. `FX_CRISIS_MAX_YEARS_TERMINATES` makes the parameter
do what its name says.

### The repair produced a testable prediction, and history rejected the first version

With the first three fixes in place the historical backtest flagged **Italy and Spain** with
currency crises in 2016, breaking the country-RMSE envelope test (Italy 0.0924 -> 0.1855).
Both are false positives against the record, and diagnosably so: **the model has no concept
of a monetary union or a reserve currency.** The fx trigger reads reserve cover, and the
agents holding the thinnest reserves are precisely those that need none — the United States
carries the lowest reserve ratio in the entire set (0.86% of GDP) because it issues the
reserve currency, and euro-area members hold little because the ECB holds it.

`FX_CRISIS_MONETARY_EXEMPT_AGENTS` is the minimal stand-in: euro-area members plus
reserve-currency issuers and the HKD hard peg, matched on both id and name because the
operational state uses ISO codes while the backtest fixture uses C01..C20 with full names.
This should become a state column if the FX block is ever given a nominal exchange rate.

### Result

| metric | before | after | reference |
|---|---|---|---|
| onsets in 30 forward years | **0** | 43 | — |
| onset rate per eligible agent-year | 0.0000 | **0.0350** | 0.03-0.05 (Laeven & Valencia) |
| mean duration | n/a | **1.88 yr** | 1-3 yr |
| distinct agents affected | 0 | 13 of 41 eligible | — |
| active agent-years | 0.0% | 4.7% | — |
| backtest false positives | — | **none** | — |

**Both targets are met at the published thresholds, with no threshold tuning.** The original
values — external debt > 50% of GDP, current account < -4%, reserve cover < 3 months — are
the standard early-warning thresholds and turn out to be right once the inputs are correct.
The affected agents are BGD, KOR, EGY, AG_SOUTH_AS, IND, VNM, PAK, TUR, CHN, PHL, MEX, THA,
POL — emerging markets with external deficits and thin reserves, which is the right
population. KOR and CHN are the least convincing entries and are worth a second look.

**Deliberately left OFF: `FX_RESERVE_ACCUMULATION_SHARE`.** A trade surplus should accumulate
reserves and a deficit drain them; nothing in the model does this. But switching it on makes
matters worse, not better — the median agent runs a deficit, so accumulation drains reserves
with no offsetting adjustment, and the onset rate goes to 8% of agent-years. The missing
piece is the exchange rate. Implemented and documented, left off until the FX block carries a
nominal rate. Same for `FX_CRISIS_DEFICIT_COMPRESSION`, which had no measurable effect
because it moves the accounting balance without moving the import bill the cover metric reads.

Suite: 589 passed / 657 subtests.

## The unit root is a second, separate defect

E3 was rerun with V6 shipped, expecting the spectral result to move. **It did not.**

| TRUST_ANCHOR_PULL (with V6 on) | rho 2026 | rho 2036 | rho 2046 | consistent fall? | sd retained | shock response | drift/yr |
|---|---|---|---|---|---|---|---|
| 0.0 (V6 alone) | 1.0750 | 1.0998 | 1.0765 | — | 2.08 | +0.01827 | -0.0056 |
| 0.05 | 1.0517 | 1.0998 | **1.0996** | **NO** | 1.89 | **+0.02323** | -0.0051 |
| **0.10** | **1.0363** | **1.0368** | **1.0386** | **yes** | 1.72 | +0.01970 | -0.0024 |
| 0.20 | 1.0201 | 1.0259 | 1.0270 | yes | 1.45 | +0.01160 | -0.0013 |
| *(pre-V6 reference)* | *1.0750* | *1.0758* | *1.0777* | — | *1.21* | *+0.00829* | *-0.0124* |

V6 left rho at ~1.075-1.10 with the dominant eigenvector still loading on `trust_gov`. The
reason is precise and worth stating in the paper: **drift and unit root are different
defects.** The deviation form removed the systematic downward push — that is what E2
measures — but a walk *without* drift still has an eigenvalue of exactly 1. Mean reversion
is a separate mechanism from the functional form, and prices already carry it
(`PRICE_ANCHOR_PULL = 0.15`; the 2026-07-12 note says trust should mirror it).

**Anchor strength chosen on evidence, not fit.** 0.05 gives the strongest shock response but
rho *rises* at 2046 (1.0765 -> 1.0996) — rejected as inconsistent. 0.10 is the weakest anchor
that lowers rho at all three linearisation points, halves the residual drift again, keeps
cross-country dispersion at 1.72x its starting value (pre-V6: 1.21) and keeps the shock
response at 2.4x the pre-V6 value. 0.20 buys a lower rho at the cost of dispersion (1.45) and
response (+0.0116). The 2015-2023 fit moves by 0.001% and the resource-price implausibilities
do not move at all across the whole grid, so nothing here is fit-driven.

**Shipped: `TRUST_ANCHOR_PULL = 0.10`.**

Consequence for Section 4. The claim now has three separable parts, and only the third
survives as originally written:
1. the above-unity modes at the published calibration were a **missing equilibrium term**,
   not a property of coupled world models — removed by the anchor;
2. what remains above unity at anchor 0.10 loads on **economic** coordinates
   (`public_debt`, `unemployment`), not social ones;
3. **climate mass in the above-unity subspace is 0.00 in every configuration tested**, at
   every anchor strength and both before and after V6 — "climate perturbations contract" is
   the one part of the original claim that was never in doubt.

Golden trajectory updated a second time: the anchor lifts RUS trust by 0.02-0.04 over
2025-2027 and leaves gdp, inflation, key_rate and milex_share untouched. The collapse still
fires in 2028. Suite 589 passed / 657 subtests.

### Caveat on E11's variant labels
With V6 shipped as the default, the V0-V6 rows of `e11_trust_form_variants.json` are all
no-op overrides and therefore identical. Only the anchor rows are informative in that rerun;
the pre-V6 numbers are preserved in the git history of the same file.

---

# Round 3 — round-1 findings recomputed on the repaired model

Every round-1 conclusion that depended on model dynamics was rerun. Two of them change
materially, and both change in the paper's favour.

## E1 — the synchrony claim now has evidence, the clustering claim still does not

| | round 1 | repaired |
|---|---|---|
| fx onsets in 30 years | **0** | 64 |
| debt onsets | 4 (all before 2032) | 4 |
| regime onsets | 138 | 85 |
| economic onset centroid | 2027.0 | **2039.5** |
| social onset centroid | 2043.5 | 2043.7 |
| lag-0 correlation | **-0.34** | **+0.52** |
| same, all cross-block channels severed | — | **+0.26** |
| Fano | 1.99 | 1.63 |
| trend-matched Poisson null | 2.19 [1.58, 2.86] | 2.07 [1.43, 2.78] |
| detrended dispersion | 0.75 | 0.51 |

With the currency channel alive, economic and social crises now co-time: the centroids close
from 16 years apart to 4, and the lag-0 correlation flips from -0.34 to +0.52. Severing every
cross-block channel halves that correlation to +0.26, so roughly **half the synchrony is the
coupling** and half is each block's own clock. That is a measured claim with a null behind
it, which is what Section 6 needed and did not have.

The dispersion claim still fails, and more clearly than before: Fano 1.63 against a
trend-matched null of 2.07, detrended dispersion 0.51. The counts remain *more regular* than
a Poisson process with the same trend. **Section 6 should claim synchrony, not clustering** —
Fano was always the wrong statistic for it.

## E7 — the cascade ordering is no longer close to tautological

| Spearman of tipping dose against | round 1 | repaired |
|---|---|---|
| pre-shock debt/GDP | **-0.685** | **-0.459** |
| pre-shock reserves/GDP | +0.154 | **-0.438** |

In round 1 the ordering was dominated by debt/GDP, the variable the debt trigger reads
directly, which made "an ordering selected by each country's fiscal state, not by hand" true
but nearly circular. With reserves now moving, the ordering is set **jointly** by debt and
reserves, and the tipping ladder is graded (0.02, 0.03, 0.04, 0.06, 0.08, 0.12) rather than
clumped. The claim survives in a much stronger form.

Transfer-function shapes also moved:

| channel | round 1 exponent | repaired |
|---|---|---|
| carbon tax -> tension | +1.078 (linear) | +1.232 |
| crop loss -> food affordability | +1.676 | +1.176 |
| crop loss -> protest | +1.676 | +1.216 |
| protest/food gain | 0.15051, spread **0.29%** | 0.19267, spread **8.46%** |

The crop chain is no longer a perfectly constant-gain map: the two legs now carry different
exponents (1.176 vs 1.216) and the gain varies by 8.5% across the dose range instead of 0.3%.
So the resource -> society leg does contribute a little curvature of its own. But the effect is
small, and the honest description is unchanged in kind: most of the curvature is generated
inside the food block. The overall response is also much less convex than before
(1.68 -> ~1.2), a direct consequence of the price repairs.

## E10 — the spatial channel matters more downstream, and the climate half is still inert

| config | fit cost | forward sd(tension) | regime agent-years |
|---|---|---|---|
| tension diffusion off | +0.000% | +6.53% | +1.61% |
| climate diffusion off | -0.004% | **-0.000%** | **+0.00%** |
| all spatial off | -0.005% | +8.07% | **+20.97%** |
| tension diffusion x4 | +0.001% | -2.24% | -9.68% |

The dispersion effect halved (13.5% -> 6.5%) but the effect on crisis outcomes grew from
0.71% to **21%**: with trust now differentiated across countries, spatial diffusion changes
who fails, not just how similar tension levels are. The fit cost remains negligible.

The climate spatial channel is still **exactly inert** — 0.000% on tension dispersion and
0.00% on regime crises — because there is still no climate -> society path. Unchanged by any
repair, and it belongs in Limitations rather than in a list of what the loop produces.

## Unchanged by the repairs
E4 (the history-matching cut) and E8 (the conflict composite) read the state CSV and the
calibration priors directly and do not depend on the repaired dynamics. E8's finding stands:
`1 - regime_stability` alone scores AUC 0.7765 against the composite's 0.7394.

## E5 — the social-channel claim reverses

Rerun on the repaired model. Round 1 reproduced the paper's headline correlations and showed
they were drift statistics. After the repairs the whole result inverts.

| prior | round 1: level / drift / response | repaired: level / drift / response |
|---|---|---|
| `SOCIAL_TRUST_ANCHOR_SENS` | **-0.598** / -0.545 / +0.029 | +0.185 / +0.127 / +0.023 |
| `INEQUALITY_EFFECT_SENS` | **+0.490** / +0.169 / -0.096 | -0.198 / -0.142 / +0.094 |
| `SOCIAL_STRESS_UNEMPLOYMENT_SENS` | +0.312 / +0.129 / **+0.210** | -0.111 / -0.115 / +0.129 |
| `SOCIAL_STRESS_INFLATION_SENS` | — | +0.162 / +0.064 / -0.004 |

The two social priors the paper cites as evidence of an uncoded mediation structure drop from
|rho| ~0.5-0.6 to ~0.2. What governs final tension now is **physico-economic**:

| prior | rho vs final tension level |
|---|---|
| `BASE_INTEREST_RATE` | **+0.399** |
| `ECS_DEFAULT` | **+0.315** |
| `DAMAGE_BENEFIT_PEAK` | +0.220 |
| `INEQUALITY_EFFECT_SENS` (social) | -0.198 |
| `SOCIAL_TRUST_ANCHOR_SENS` (social) | +0.185 |
| `EMISSIONS_SCALE` | +0.184 |
| `DAMAGE_RISK_ADJ` | +0.172 |

And the causal shock response is led by climate-damage parameters, not social ones:
`DAMAGE_RISK_ADJ` **-0.349**, `OCEAN_EXCHANGE` +0.179, `REGIME_COLLAPSE_CAPITAL_MULT` +0.167,
`HEAT_CAP_DEEP` -0.143, `DAMAGE_BENEFIT_PEAK` -0.138.

Aggregates: level vs drift **+0.864** (was +0.578), level vs shock response **-0.325** (was
-0.123), mean tension drift now **+0.0037/yr** (was negative), share of members with a
positive shock response **75.8%**.

**This reverses the paper's Section 6 claim, and in the direction that helps it.** The paper
says tension is "insensitive to physico-economic priors ... while final tension is governed by
[the social priors]". The opposite is now true: the trust drift was *masking* a real
physico-economic channel, and with the drift removed the interest rate, climate sensitivity
and damage parameters come through. The correct claim is that economy and climate reach
society — which is the integration claim the paper wants to make — and it should be stated on
the response, not on the level, since level vs response still correlates at only -0.325.

## E9 — unchanged
Country-level growth skill is identical to round 1 (win rate 60% vs zero-growth, 50% vs
mean-growth, pooled skill +0.074 / -0.033). The social and fx repairs do not touch GDP
dynamics at this horizon, so the recommendation stands: report growth space, state the win
rate, keep levels as a secondary panel.

---

# Round 4 — the food and spatial channels

## Correction: the food price is no longer inert

E16 was rerun on the current model. Its round-3 result — food price forced to 5x moving every
downstream output by exactly zero — **no longer holds**, and the reason is that E16 predates
the fx repair.

`apply_structural_trade_balance` values each agent's production minus consumption **at world
prices**, so the food price now enters every trade balance, hence reserves, the current
account and the fx trigger. The channel opened as a side effect of repairing the currency
channel, not through the CPI.

| forced price x5 | world GDP | inflation | CO2 | tension |
|---|---|---|---|---|
| energy | -5.51% | +11.22% | -4.76% | -0.69% |
| food | **-7.95%** | -4.56% | -4.79% | **+5.55%** |
| metals | +0.76% | +2.32% | +0.28% | +0.07% |

Food now has the **largest** effect on social tension of the three — which is the channel
Appendix B wanted, arriving by a different route than the one it describes.

## The climate spatial channel is not broken, it is switched off

E18 (`scripts/e18_climate_spatial_with_events.py`).

My round-1 reading — "there is no climate -> society path" — was wrong.
`gim/core/climate.py:400-412` (`apply_climate_extreme_events`) reads `climate_risk` and writes
`society.social_tension` and `society.trust_gov`. The path exists. Every experiment here, and
the paper's headline runs, set `enable_extreme_events=False`, which closes it.

| config | sd(climate_risk) | sd(tension) | regime crises |
|---|---|---|---|
| events OFF, diffusion x3 | **-7.29%** | **+0.000%** | **+0.000%** |
| events ON (12 seeds), diffusion x3 | -7.21% | **-1.71%** | **-4.26%** |
| events ON, diffusion off | +3.89% | -0.77% | +0.00% |

Diffusion does its job on the risk field in both cases. What differs is what is downstream.
With events off, `climate_risk`'s only consumers are **linear** — the damage multiplier
`1 + DAMAGE_RISK_ADJ*(1-risk)` and adaptation spending `BASE + SENS*risk` — and a
mean-preserving redistribution of a linear function changes nothing in aggregate. Hence
exactly 0.000%. The one nonlinear consumer in a deterministic run, the climate-org threshold
at `institutions.py:393`, only fires for members of a climate organisation.

**No code fix is warranted.** What is warranted is a scope statement in the paper: the climate
spatial channel acts through extreme events, and the deterministic headline configuration
switches those off. Whether climate should ALSO reach society continuously is a modelling
decision, not a defect — see the open question below.

## Food: three defects, of which the third is the largest

**Defect 1 (fixed earlier)**: the price-damping buffer. Food was untouched by that fix because
its reserve was already realistic.

**Defect 2: food has no CPI channel.** Energy has had a cost-push pass-through into the
Phillips curve since [E4]; food never did, despite being the larger CPI component nearly
everywhere — food and non-alcoholic beverages carry 8% of the basket in the US, 12% in the
UK, 15.5% in the euro area, 19.5% in Japan, 31% in China and 45% in India, against household
energy weights of 3-9.5%. `INFLATION_COSTPUSH_FOOD_COEFF` added, default 0.0.
Derivation for a candidate value: GDP-weighted global CPI food weight ~0.16 times a
commodity-to-retail pass-through of ~0.25 gives **~0.04**, close to the energy coefficient,
which carries the same two-stage structure.

**Defect 3: food production is frozen.** Measured over 30 forward years:

| year | food supply | food demand | D/S | price |
|---|---|---|---|---|
| 2023 | 1339.3 | 1339.3 | 1.0000 | 1.000 |
| 2035 | **1339.3** | 1493.4 | 1.1151 | 1.249 |
| 2047 | **1339.3** | 1662.3 | 1.2411 | 2.957 |
| 2053 | **1339.3** | 1787.8 | 1.3349 | **4.681** |

Supply is identical to one decimal place in every year while demand grows 33%. Against a real
record of ~2%/yr production growth (FAO) and roughly **flat real food prices** over decades,
the model manufactures a 4.7x food price by 2053. Food is also the one resource whose reserve
genuinely grows (regen 0.02) while its production does not — internally inconsistent.

`FOOD_YIELD_GROWTH` and `FOOD_SUPPLY_PRICE_ELAST` added, both default 0.0. Sweep:

| yield trend | price elasticity | price 2053 | supply 2053 | D/S | hist. fit GDP | I_food |
|---|---|---|---|---|---|---|
| 0.000 | 0.00 (current) | **4.681** | 1339.3 | 1.335 | 0.5981 | **0.702** |
| 0.020 | 0.00 | **0.300** (floor) | 2426.0 | 0.763 | 0.5970 | 1.631 |
| 0.015 | 0.00 | 0.623 | 2093.5 | 0.889 | 0.5970 | 1.329 |
| 0.000 | **0.20** | **1.035** | 1748.0 | 1.034 | 0.5980 | 0.828 |
| 0.000 | 0.40 | 1.027 | 1763.1 | 1.033 | 0.5979 | 0.894 |
| 0.010 | 0.20 | 1.006 | 1816.7 | 1.016 | 0.5970 | 1.027 |
| 0.015 | 0.20 | 0.974 | 1868.8 | 0.972 | 0.5970 | 1.095 |

An exogenous yield trend alone overshoots hard — 2%/yr drives the price to its 0.30 floor.
A **price elasticity alone** reproduces the observed long-run regularity: price essentially
flat at 1.03 over 30 years, supply growing endogenously to meet demand (+30.5%, 0.89%/yr,
internally consistent with the model's own 0.96%/yr demand growth). The result is insensitive
to the exact elasticity between 0.2 and 0.4, which is a good sign.

All new switches default off; suite 589 passed / 657 subtests with no change.

## E19 — the food supply response derived from two priors, not chosen

`scripts/e19_food_climate_supply.py` -> `results/e19_food_climate_supply.json`

A fourth food defect, and structurally the largest: **the model had no climate channel into
crops at all.** Warming did not touch food production anywhere, which is why Appendix B's crop
scenario has to inject a yield cut by hand. `FOOD_YIELD_TEMP_SENS` added.

Two published priors, composed:

| prior | source | value |
|---|---|---|
| yield loss per degree C | Zhao et al. 2017, PNAS 114(35):9326-9331 | wheat 6.0%, rice 3.2%, maize 7.4%, soybean 3.1%; unweighted mean **4.925%** |
| supply price elasticity | Haile et al. 2016 AJAE; Iqbal et al. 2018 Agric. Econ. | aggregate long-run growing-area **0.143** (short run 0.024; crop range 0.045-0.793) |

They compose without double counting: Zhao's estimate explicitly excludes CO2 fertilisation,
adaptation and genetic improvement, and the price elasticity **is** the model's adaptation
mechanism.

| temp sens | elasticity | price 2053 | supply 2053 | D/S | supply growth/yr | I_food |
|---|---|---|---|---|---|---|
| 0.000 | 0.000 (before) | **4.681** | 1339.3 | 1.335 | **0.00%** | 0.702 |
| 0.049 | 0.000 | **5.000** (ceiling) | 840-885 | **2.02** | **-1.42%** | 0.702 |
| 0.000 | 0.143 | 1.070 | 1742.1 | 1.060 | 0.91% | 0.800 |
| **0.049** | **0.143** | **1.244** | 1699.6 | 1.069 | 0.82% | 0.800 |
| 0.055 | 0.200 | 1.172 | 1721.0 | 1.036 | 0.87% | 0.828 |
| 0.055 | 0.300 | 1.097 | 1742.4 | 1.038 | 0.91% | 0.866 |

The climate channel **alone** is a catastrophe — price at the 5.0 ceiling, supply falling
1.4%/yr, demand/supply above 2. That is precisely Zhao's no-adaptation counterfactual, and it
demonstrates why the two priors have to be taken together rather than separately.

**Independent validation the pair was not fitted to.** IPCC SRCCL assesses a **1-29% cereal
price increase by 2050** from climate change across SSP1-3 under RCP6.0. The shipped pair
gives a 2053 food price of 1.244, i.e. **+24.4%** — inside the assessed range. The historical
food price implausibility depends only on the elasticity (0.702 -> 0.800), not on the climate
channel, because 2015-2023 warming is small.

**Why 0.143 rather than 0.20-0.30.** 0.143 is the directly estimated published aggregate;
0.2-0.3 is my inference adding a yield-intensity margin on top of area. Preferring the
estimated number over the inference costs almost nothing in outcome (2053 price 1.244 vs
1.172 vs 1.097, all inside the IPCC range) and is citable exactly.

**Cost, stated plainly.** `I_food` degrades 0.702 -> 0.800 on the 2015-2023 window. The
observed food index rose 42% over those nine years on COVID and Ukraine; a model with an
elastic supply response tracks less of that. This is the same trade-off refused for the metals
elasticity, resolved the other way — because here the structurally correct mechanism is also
the one the long-run record and the IPCC range support, and the window that disagrees is
nine shock-dominated years.

Shipped: `FOOD_YIELD_TEMP_SENS = 0.049`, `FOOD_SUPPLY_PRICE_ELAST = 0.143`,
`INFLATION_COSTPUSH_FOOD_COEFF = 0.04` (the last only after the first two, since feeding the
pre-repair 4.68 price into the CPI would have injected an artifact).

Food supply is no longer frozen: 1339.3 -> 1699.7 over 30 years, D/S peaking at 1.10 and
settling at 1.07, price 1.244. Suite 589 passed / 657 subtests.

## Climate -> conflict: prior found, NOT taken

Hsiang, Burke & Miguel 2013 (Science 341) is the canonical prior for a continuous
climate -> social-stress channel: per 1 SD warming, interpersonal violence +4% and intergroup
conflict +14%, from a meta-analysis of 60 studies. It is also **genuinely contested**. Buhaug
et al. 2014 (Climatic Change 127:391-397) argue the meta-analysis has sample-selection and
analytical-coherence problems and that the literature is "mixed and inconclusive"; Hsiang et
al. reply identifying five errors in that reanalysis. The dispute is not settled.

Recommendation: do not ship it as a default. The direction is defensible, the magnitude is
not, and a contested elasticity wired into the headline configuration is exactly what a
reviewer would use to dismiss the socio-political block. If it is wanted at all, it belongs
where the model already puts contested mechanisms — switchable, tagged as a prior, and
confined to tail scenarios, the way the carbon feedbacks are handled.

Contrast with the yield prior, which was taken: Zhao rests on four independent method families
that converge, and is not seriously disputed.

---

# Round 5 — release split, new golden, contested prior parked

## Climate -> conflict: implemented, tagged, shipped OFF

`TENSION_CLIMATE_SENS`, a continuous climate -> social-tension term. Prior: Hsiang, Burke &
Miguel 2013 (Science 341, 1235367) — per 1 SD of warming, interpersonal violence +4%,
intergroup conflict +14%, from 60 studies. Contested by Buhaug et al. 2014 (Climatic Change
127:391-397) on sample selection and analytical coherence; Hsiang et al. reply identifying
five errors in that reanalysis. Unsettled.

Direction defensible, magnitude not identified, so it ships off, tagged as a prior, for tail
and sensitivity scenarios only — the treatment `CARBON_TIPPING_*` already gets. Exploratory
band 0.002-0.010 documented in the parameter, the lower end mapping to HBM's interpersonal
figure and the upper to the intergroup one. Measured effect at 2053 mean tension: 0.448 (off),
0.473, 0.500, 0.545. Any run that enables it has to say so.

## New golden baseline, and a correction to my own claim

I said the stored backtest baseline was stale because its temperature RMSE was 0.1447 against
an actual 0.0989. **That was wrong** — a configuration mismatch on my side. The baseline and
the envelope test both call `run_historical_backtest()` with its defaults, i.e. the
temperature ENSEMBLE with internal variability on; 0.0989 is the deterministic single-member
figure that `temperature_variability_sigma_override=0.0` produces, which most diagnostic
scripts here use. Run in the right configuration the stored number was exact.

The baseline was genuinely out of date in one respect: it predated prices becoming a
validation target and carried no price fields, so the price subsystem sat outside the guard.

`scripts/regenerate_backtest_baseline.py` added — the baseline had no generator at all, so
moving it was a manual edit with no record of what produced it. The script prints the delta
against the stored values and **refuses to write** when a guarded metric regresses by more
than 1%, unless given `--force --reason`, so regenerating cannot silently launder a
regression into the reference. Regenerated at `230b308`:

| metric | stored | new | change |
|---|---|---|---|
| GDP RMSE | 0.5990 | 0.5984 | -0.09% |
| CO2 RMSE | 0.9386 | 0.9391 | +0.05% |
| temperature RMSE | 0.1447 | 0.1447 | -0.00% |
| resource price RMSE | *(absent)* | energy 0.521, food 0.2095, metals 0.396 | new |

Every repair of rounds 2-4 together moved the historical fit by less than a tenth of a
percent, while adding three price targets, a live currency channel and a climate-yield
channel. That is worth stating in the paper.

## `tests/test_global_golden_run.py` — the reference to expand

The only golden forward run was `test_integrated_golden_run.py`, which pins the RUS
block-layer trajectory and therefore cannot ship publicly. The new global golden pins ten
years of the 57-agent world — world GDP, temperature, CO2, mean trust, mean tension, the three
resource prices and the three crisis counts — deterministic, block layer off.

It also carries `test_every_crisis_channel_fires_at_least_once`, which exists precisely
because the fx channel produced zero crises in every configuration until round 2 and nothing
in the suite noticed.

## Public release split

The paper never mentions the block layer — only the authors' affiliations reference Russia.
The repository, however, carries a sub-national decomposition of Russia: 303 tracked data
files at 2.3 GB, six RUS scripts, a nine-module block engine, a second packaged copy of the
whole thing under `lib/`, the desktop app that ships the block by design, the specification
document, and thirteen tests.

`scripts/build_public_release.py` builds the public tree. Two things made this a build rather
than a branch:

1. **The engine already runs Russia consolidated by default.** `BLOCK_LAYER_AGENTS` is empty
   and `block_substep.py` returns immediately on an empty list, importing `gim.blocks` only
   lazily inside the guard. Removing the block layer changes no default behaviour — and the
   build **verifies** that rather than asserting it.
2. **A public branch would still ship the 2.3 GB.** Git history is shared, so the data would
   live in the object store of any branch pushed from this repository. The public tree needs
   its own history, which `--git-init` gives it.

Result: **408 files, 5.8 MB**, from 1119 files and 2389 MB — 711 files and 2383.7 MB withheld.

The build fails rather than shipping if any of three checks fail:
- no excluded material survives into the output (this caught the second copy of the RUS data
  inside `lib/gim19/`, which the directory list had missed);
- the public tree reproduces the local headline numbers **exactly** — GDP, CO2, temperature
  and resource-price RMSEs and all 20 country-level GDP RMSEs, run in a clean interpreter;
- the public tree passes its own suite: **479 passed, 627 subtests**.

That third-party-checkable identity is the point. The public release is not a reduced model:
it is the same model, and the build proves it on every headline metric.

Local suite after the split: 592 passed / 657 subtests.
