# GIM_final.tex — what changed, and on what evidence

Prepared 2026-08-27 in response to two pre-submission reviews (Claude, ChatGPT) of
`gim_paper_v2_8K.pdf`. Everything below was checked against **release v20.1.0** of the model
by re-running the harness, not by reading the old PDF. Numbers I could not re-derive cheaply
are listed at the bottom as **carried over unverified**.

---

## A. Numerical errors that were real, and their corrected values

| # | Claim in the old paper | Correct value | How verified |
|---|---|---|---|
| 1 | 2053 median world product **241 T USD**, 5–95 **215–270**, T **1.94 °C** (§4 text) | **264 T**, **235–292**, **1.96 °C** | `results/ensemble-20260825-141639` p5/p50/p95 = 235 / 264.1 / 291.9; T 1.408/1.963/2.511. The **figure caption was right and the text was stale.** Deterministic baseline agrees (263.8 T). |
| 2 | Temperature 5–95 **1.39–2.49 °C** | **1.41–2.51 °C** | same run |
| 3 | 107 → 241 implies **≈2.7 %/yr** | **3.06 %/yr** (107 → 264) | arithmetic on the corrected median; base year re-run = 106.81 T |
| 4 | CO₂ out-of-sample **0.71** (§5) vs **0.72** (abstract, Table) | **0.72** | re-ran `scripts/run_holdout_validation.py`: 0.7183 |
| 5 | 2021–2023 CO₂ **0.10** | **0.12** | same run: 0.1159 |
| 6 | In-sample temperature RMSE **0.145 °C** in the text vs **0.99** (=0.099 °C ×10) in Fig. 4 | **both are real, in different configurations** — 0.0989 °C deterministic, 0.1447 °C with the interannual-variability term on. Paper now uses **0.099 °C** as headline (matching every other deterministic result and the figure) and states the other. | `run_historical_backtest(temperature_variability_sigma_override=0.0)` vs default |
| 7 | Best single conflict covariate **0.777**, paired Δ **−0.038**, CI **[−0.114, +0.032]** | **0.776**, **−0.037**, **[−0.114, +0.031]** | `e8_conflict_composite_vs_components.json`: 0.77646, −0.03750, [−0.11375, +0.03147]. Figure was right, text was rounded wrong. |
| 8 | Active crises rise to **14.4/yr** in the last decade | **14.1/yr** | `e1_crisis_clustering_null.json` baseline `last_decade_mean` = 14.1. **14.4 is the C1-ablation value**, quoted in place of the baseline. |
| 9 | Fano index model value **1.39** | **1.63** | same file, `fano_raw` = 1.627. (1.39 matches nothing; 1.31 is the all-cross-block ablation.) |
| 10 | **77 % of bot failures in 2040–2045** | **2040–2049** | `outcome_summary.json`: bins 2040–44 = 244 and 2045–49 = 346 of 767 losses → 31.8 % + 45.1 % = 76.9 %. Figure caption was right. |
| 11 | Game is **"thirty annual turns from 2023"** and "reaching 2050 wins" | **27 turns, 2023 → 2050** | 2023→2050 is 27 years; loss-year histogram terminates at 2050 |
| 12 | Carbon-tax emissions exponent **0.90** | **0.88** | log–log refit of `results/integration_benchmark/latest.json` sweep: 0.882, R² 0.9994 |
| 13 | Oil cascade tipping-order Spearman **−0.46 / −0.44** on debt and reserves | **−0.20 / −0.18**, and **−0.38 on GDP** | `e7_transfer_functions.json`: −0.46/−0.44 are the `forward_init=false` variant; the tipping counts quoted alongside them (3/4/12/19) are the `forward_init=true` **headline**. Two configurations were mixed in one sentence. Country size, not fiscal margin, is the stronger predictor — the claim is now weakened accordingly. |
| 14 | 2100 baseline **2.69 °C**, stock **3,270 → 4,380 GtCO₂**, net **1,110 GtCO₂** | **2.75 °C**, **3,270 → 4,470**, net **1,204** | 77-year deterministic run; preindustrial constant `CO2_PREINDUSTRIAL_GT = 2184.0` |
| 15 | **527-test suite** | **592 tests / 657 subtests** | `pytest --collect-only` = 592 |
| 16 | Stagflation response positive in **82 %** of draws | **76 %** | `e5_...json` `share_positive_shock_response` = 0.7583 |
| 17 | "The prior governing that response is `SOCIAL_STRESS_UNEMPLOYMENT_SENS`" | **false** — that prior scores r_s = +0.13, p = 0.16. Largest loading is a climate-damage parameter at −0.35. | `e5_...json` per-prior table |
| 18 | Passive archetype **18.7 %** quoted next to random 28.4 % / green 20.1 % / growth 21.9 % | 18.7 % is from the **75-run-per-policy difficulty-tuning batch**, not the 1,002-run reference batch (where the same policies score 37.3 / 24.0 / 32.0). Now flagged as non-comparable. | `difficulty_tuning.json` vs `outcome_summary.json` |
| 19 | Corrupted Table 1 cell: *"mass economic and climate mass 0.00"* | rewritten | — |
| 20 | Version **GIM20.1** (abstract) / **v18.1.3** (§7) / **v18.1.4** (Zenodo) | **v20.1.0** everywhere | `CITATION.cff`, `.zenodo.json`, `CHANGELOG.md` all say 20.1.0, released 2026-08-25 |
| 21 | Crop-shock gain "varies only modestly with dose" (spread 8.5 %) | protest/affordability gain spans **0.16–0.22** non-monotonically on the current run | recomputed from `integration_benchmark/latest.json` |

## B. New results computed for this revision (turning two criticisms into evidence)

1. **Jacobian ε-convergence.** Both reviewers asked whether the numerical Jacobian is
   trustworthy near thresholds. Recomputed the full 408×408 spectrum at
   ε ∈ {10⁻³, 10⁻⁴, 10⁻⁵}: **ρ = 1.03631 at all three, identical to five decimals**; the count
   above 1.001 is 32 at all three; only the raw count above 1.000 moves (36, 36, 37), because
   45 eigenvalues sit inside [0.999, 1.001]. This is now reported in §4.1 and it *strengthens*
   the result.

2. **Detrended crisis synchrony.** ChatGPT correctly noted that a lag-0 correlation between two
   trending series is confounded. Recomputed: raw **0.520**, linear-detrended **0.598**,
   Poisson-residual **0.555**; ablation raw **0.258**, detrended **0.297**, Poisson-residual
   **0.310**. **Detrending strengthens the association**, so the criticism is now answered with
   a number rather than conceded.

3. **Time-step accuracy of the explicit-Euler EBM.** Stability limit derived analytically
   (Δt < 2C_s/(λ+κ) = 7.1 yr headline, 3.2 yr at the tightest prior corner, 35 yr at ECS = 6);
   accuracy measured by re-integrating the baseline forcing path at Δt = 1/12 yr → **0.002 °C**
   at 2100 headline, **≤ 0.012 °C** at any prior-box corner.

4. **Base-year world product** re-derived: **106.81 T USD** (paper said "≈107").

## C. Claims reframed (both reviewers agreed; I verified the underlying facts)

| Old claim | New claim | Why |
|---|---|---|
| "the closed loop is **stable**", "convergence" | "**bounded over the tested horizon**, with contracting physical–economic perturbations and slowly amplifying socio-fiscal modes" | ρ(J) > 1 with 31–36 above-unity modes is not local asymptotic stability. |
| "the **climate subspace contracts entirely**" | "the climate coordinates carry **no above-unity eigenvector mass**; the τ = ∞ carbon pool is a perfect integrator and places \|λ\| = 1 there **by construction** — non-expanding, not contracting" | ∂C⁽¹⁾ₜ₊₁/∂C⁽¹⁾ₜ = 1 exactly (Eq. A6); 45 eigenvalues sit in [0.999, 1.001]. This was the single sharpest catch in either review. |
| "Jacobian of the **full annual map**" | "Jacobian of the **projected map** P∘F∘ι — a principal submatrix; the persistent-state registry carries 87 variable families, not 7+9" | `docs/state_registry.csv`; `run_stability_analysis.py` reads back only the 408 coordinates. |
| "**500-member history-matched** ensemble" | "**prior ensemble with a non-binding history-matching diagnostic**" | acceptance 100 %, NROY = prior box, tolerances loose by ~5×. Negative result kept and highlighted. |
| "**untouched** out-of-sample window" | "**procedurally held-out** scoring window" + three named leakage channels (decarb rate, energy elasticity, TFP sensitivity all set against 2015–2023; price subsystem repaired against the same series; functional forms chosen during development) | The holdout script *does* re-run HM on 2015–2019 and freeze — that part is clean. Model-development leakage is not. |
| "**carbon is conserved**" | "emissions are **mass-partitioned** across atmospheric response pools with removal to implicit land–ocean sinks" | sink stocks are not carried, so E = ΔC_atm + ΔC_ocean + ΔC_land cannot be checked. |
| the game is an "**importance sampler**" | "**adversarial stress testing** / targeted exploration of extreme regions" | no proposal density, no weights. |
| "**invariants** of nature and society" | "physical conservation laws, accounting identities and slow empirical regularities" | Okun/Phillips/Hofstede are regularities, not invariants. |
| "**all** uncertainty lives in ensembles" | "**parametric** uncertainty…" + explicit U_total = U_param + U_init + U_struct + U_scenario, with evidence that structural ≫ parametric | removing the SSP2 anchor moves 2100 warming 2.75 → ~2 °C, far outside the parametric fan. |
| "roughly **half the co-timing is the coupling**" | "removing the coupling **halves the lag-0 correlation**" | correlations don't decompose additively into attributable shares. |
| Fig. 7(c) "**climate → society**" | "**resources → society**" — the x-axis is exogenous yield loss, not ΔT | caption now states what a climate pathway would require. |
| "food supply response **supplies adaptation**" | "**price-induced acreage and output adjustment** — a market mechanism, not climate adaptation" | GIM has no crop switching, sowing dates, irrigation, cultivars or relocation. |
| "every loan creates a matching deposit; the money stock **is identically** deposits and loans" | qualified as "**in GIM's simplified banking balance sheet**" | model accounting identity, not a claim about real monetary aggregates. |
| "completer rate **is** an upper bound" | "**under the assumption that** runs going badly are abandoned more often" | the bound needs that premise. |
| Appendix B "**named sectoral model benchmark**" | "**characterisation of cross-sector transfer functions**"; only DICE is a named anchor and it is labelled as such | oil case cites "energy-system models", which is not a named anchor. |
| Brier skill quoted plainly | now flagged: the composite is a rank index, not a calibrated probability, so BSS is a relative statistic only | — |
| vintage-clean test "so ranking skill is **not** reverse-causation contamination" | "shows the ranking is not an artifact of **late input vintages**; it does **not** establish absence of reverse causation" | pre-2000 regime stability may itself reflect earlier conflict. |
| trust anchor: two similarly-named parameters, contradictory ON/OFF statements across §4, §7 and Limitations | **two distinct mechanisms, separately named and both ON**: trust mean-reversion pull χ = 0.10 yr⁻¹ (Eq. A9) and trust-gap effect on tension σ_tr = 0.060 (Eq. A10); Table 2 gives the full ON/OFF matrix | `TRUST_ANCHOR_PULL` and `SOCIAL_TRUST_ANCHOR_SENS` are different terms in different equations. The old §7 claim that the anchor "ships off in the headline configuration" was wrong. |
| the circularity of tuning χ on ρ was unstated | **named explicitly**, with the spectra at χ ∈ {0, 0.05, 0.10, 0.20} so the reader can price the choice | — |
| crisis statistics mixed episodes and active states | the two are now defined and distinguished in the text | — |
| "emergent dynamics" | split into coded nonlinearity / cross-domain propagation / endogenous ordering, with each claim assigned | — |

## D. New material added for GMD (both reviews demanded it)

- **§3.2 Numerical implementation** — Algorithm 1 (the full 21-step annual write order from
  `docs/SIMULATION_STEP_ORDER.md`), integration scheme and its stability/accuracy analysis,
  threshold handling, reproducibility and verification (592 tests, pinned goldens, seeds,
  checksums, manifests).
- **§3.3 + Table 2 Configuration matrix** — mechanism × ON/OFF × where it enters × provenance
  (empirical / structural / expert / numerical regularisation).
- **Appendix A rewritten** with real equations for the blocks that had none: Okun (A3),
  Phillips with energy+food cost-push and the quantity-theory term (A4), price mean reversion
  (A5), the renormalised damage function (A8) — which fixes the Ω(T_2023) ≠ 1 inconsistency the
  reviews caught — trust (A9), tension (A10), plus the crisis state machine with all thresholds
  and effects, public finance, banking, trade, resources, geopolitics, demography and migration.
- **Code and data availability** rewritten to GMD's policy: one frozen Zenodo DOI as the
  citable record, GitHub demoted to a mirror, Apache-2.0 named, and Table 6 listing every
  dataset with version, role and redistribution status — including **HadCRUT5.1.0.0 rebased to
  1850–1900** (the observational dataset the reviews correctly noted was never named), GCB 2024,
  NOAA GML, UCDP/PRIO ACD v24.1, World Bank Pink Sheet (CC BY 4.0), and **Hofstede flagged as
  not redistributable** (proprietary — archive carries only the derived vector plus the
  ingestion script).
- **USD units defined precisely**: levels anchored to 2015 current US$ at market exchange
  rates, carried forward by the World Bank real PPP (constant 2021 international $) growth
  index. Real, not nominal; MER-based levels, not PPP levels.
- **Copernicus back matter**: Code and data availability / Author contributions / Competing
  interests / Ethics / Financial support / Generative-AI disclosure / Acknowledgements.
- **AI disclosure rewritten** to the letter of the Copernicus policy: named tools, four
  enumerated uses, explicit statement that no passage was model-generated and adopted unedited
  and that no result or interpretation came from a model. "Drafting support" is gone — it falls
  under the policy's prohibited category.
- **Ethics paragraph rewritten**: it no longer asserts that the collection "was judged to fall
  outside the scope of human-subjects review" (no body judged it). It describes the
  data-minimisation design and states plainly that no review or exemption was sought. **This is
  a TODO — if an institutional confirmation exists, cite it.**
- **Title** now carries model name and version, as GMD requires.
- **Preprint disclaimer box removed** ("please cite the software record rather than this
  document" reads as disowning your own manuscript in a two-stage-review journal).
- **Three items of future work named explicitly** where the reviews found gaps: full-registry
  Jacobian; the scenario-difference-over-the-ensemble experiment that would turn the paper's
  central recommendation from a design argument into a result; and the reserve-identity
  sensitivity run.

## E. Format

`\documentclass[12pt]{article}` with `geometry`, `lineno`, `setspace`, `natbib(authoryear)`,
`plainnat`, `xltabular`. Deliberately **not** `copernicus.cls`: that class is not on CTAN and
not in Overleaf's TeX Live, so a `.tex` shipping it would not compile out of the box. What is
here already meets every GMD **review-file** requirement — single column, continuous page
numbers, line numbers, figures/tables near first mention, embedded fonts, author–year
citations, alphabetical references. The header block documents the two-line swap to
`copernicus.cls` + `copernicus.bst` at production.

Verified: `pdflatex → bibtex → pdflatex ×2` completes with **0 errors, 0 undefined
references, 0 undefined citations, 0 oversized floats**, 2 cosmetic overfull boxes under 8 pt.
50 pages.

## E-bis. Second pass (2026-08-27, after your review of the first package)

**Zenodo DOIs — resolved, and there were two of them.** Queried the Zenodo API. The link you
gave, `10.5281/zenodo.21575176`, is the **concept DOI** (`conceptrecid` 21575176): it always
resolves to whichever version is current. The **version DOI** of the frozen v20.1.0 deposit,
published 2026-08-25 and flagged `is_last: true`, is **`10.5281/zenodo.22102520`**. GMD's
code-and-data policy wants the DOI of the exact frozen version behind the results, not a moving
target, so the paper now cites **22102520** as the archival record and names 21575176 as the
all-versions link for referring to the model in general. Both appear in Code and data
availability; the `.bib` entry carries the version DOI. (Side note: `.zenodo.json` describes
21575176 as the thing v20.1.0 `isNewVersionOf`, which is what made the earlier draft treat it
as the v18.1.4 version DOI. It is not — it is the concept parent.)

**Telemetry.** Rewritten to state the fact rather than hedge it: the deployment records only
parameters of the run itself, no personal data of any kind is collected, stored or derived, and
therefore no individual-level data exist to report. The sentence claiming the collection "was
judged to fall outside the scope of human-subjects review" stays removed — no body judged it,
and the paragraph now says so plainly instead. TODO removed.

**Hofstede.** Paper corrected: the engine consumes **three** dimensions (PDI, IDV, UAI), not
six — IDV damps the inequality term in Eq. (A10). The data table now states that the source
table is not redistributed, and that the public archive carries the ingestion script, a
checksum of the expected input, and the three-dimension vector for the 57 modelled agents.
**Repo action still outstanding — see the note in the reply; I did not modify the repository.**

**Figure placement.** Root cause was LaTeX's default float fractions: at 12 pt with 1.5 spacing
in a single column, `\topfraction = 0.7` leaves too little of the page for a full-width figure,
so every figure was deferred and the queue flushed at the end — which is why Fig. B1 landed
among the references. Fixed by raising `topfraction`/`bottomfraction`, lowering `textfraction`,
raising the per-page float counters, switching every figure to `[!htbp]`, and adding
`\clearpage` before both `\appendix` and `\bibliography`. Figures now sit at pp. 6, 12, 14,
19, 22, 25 and 41 — each within a page of its first mention, none in the reference list.

**Length.** Main body + abstract measured at **10,031 words** in the first package. Cut to
**9,621** by compressing the game layer (both reviewers wanted it demoted from "third
scientific pillar" to a stress-testing method), the introduction, the cross-domain-dynamics
prose, Limitations, and the resource-price narrative. No result, number, caveat or negative
finding was removed — only restatement and hedging. Appendices (1,688 words), back matter and
tables are excluded from that count.

## E-ter. Third pass (2026-08-27)

**Layout is now a switch, not a decision.** `\newif\ifgmdreview` at the top of the file.
Default `\gmdreviewfalse` gives the reading layout you asked for: single spacing, no line
numbers, 42 pages. Setting `\gmdreviewtrue` restores 1.5 spacing and line numbers for the
Copernicus review upload, which is what `copernicus.cls` produces in `manuscript` mode and what
their submission page expects. Nothing else in the document changes between the two, so there
is no second file to keep in sync. Float fractions were re-tuned for the tighter page; figures
now land on pp. 5, 10, 12, 16, 19, 21 and 35, all within a page of first mention and none in
the reference list. Build is clean in both modes.

**Hofstede, option (1), implemented and verified.** Changes to
`scripts/build_public_release.py`:

- The three pipeline panels that carry the licensed multi-country scores are added to
  `EXCLUDE_GLOBS`: `data/agent_state_pipeline/generated/{actor_base_inputs,
  country_panel_raw, country_panel_imputed}.csv`. Nothing in `gim/` or `tests/` reads them ---
  they are written by `build_gim13_agent_states.py` and read only by
  `build_milex_grounding.py`, whose committed output (`data/external/sipri_milex_2023.csv`)
  ships as before. `results/` was already excluded wholesale, which covers the 68 rolling
  backtest origin-state files.
- A new **content-level** check, `FORBIDDEN_CSV_COLUMNS = ["hofstede_name",
  "hofstede_source", "mas"]`, reads the header row of every shipped CSV and fails the build if
  any appears. A path check cannot catch a licensed column reappearing inside a file we do
  ship, which is exactly what happened --- see below. PDI/IDV/UAI are deliberately *not* on
  that list: `agent_states_operational.csv` carries them for the 57 agents by design, and
  without them the public tree would not reproduce the paper's numbers.
- Module docstring extended to state what is withheld and why.

**The content check immediately found something a path check would have missed.**
`tests/fixtures/historical_backtest_state_2015.csv` --- a file the public tree must ship, since
it is the backtest's initial state --- carried a `mas` column. MAS is a licensed Hofstede
dimension that GIM does **not** use: `CulturalState` in `gim/core/core.py` keeps only
PDI/IDV/UAI/LTO and its comment records that MAS was dropped as empirically inert. So the
column was dead weight *and* a redistribution. Removed. Consequences checked, not assumed:
**592 tests / 657 subtests pass**, and the public build reports *"identical on every headline
metric, including all 20 country RMSEs"*. Original file backed up in the session scratchpad.

**Verified end state of the public tree:** the three panels are gone; no shipped CSV carries
`mas`, `hofstede_name` or `hofstede_source`; PDI/IDV/UAI ship for the 57 agents as intended;
`top50_source_audit.csv` retains provenance *labels* (`direct_hofstede`) but no values, which
documents where a number came from without redistributing it. Public tree: 493 files, 8.6 MB,
482 tests / 627 subtests passing in its own interpreter.

**One-line robustness fix, incidental.** `build_public_release.py` crashed at its closing
`print` when `--out` points outside the repository (`Path.relative_to` raises). Guarded.

## E-quater. Release v20.1.1 (2026-08-27)

**Zenodo is cited by the concept DOI.** `10.5281/zenodo.21575176` represents all versions and
always resolves to the latest. The paper cites it, and states that the results were produced by
the release tagged `v20.1.1`, which a reader can select from the version list on the record if
they need that exact state rather than the current one. Confirmed after the release: the
concept DOI now resolves to version **20.1.1**, published 2026-08-27, version DOI
`10.5281/zenodo.22127525`, `is_last: true`.

**One version string, not three.** `v20.1.1` in the title, the `\Version` macro, `CITATION.cff`
and `.zenodo.json`. The engine did not change --- v20.1.1 reproduces v20.1.0 to the bit on
every headline metric including all 20 country-level GDP RMSEs, and the suite is unchanged at
592 tests / 657 subtests --- so the paper says so once, in Code and data availability, rather
than leaving a reader to wonder why the archive version differs from the run version. The
version was bumped because the tag `v20.1.0` was already taken by the 2026-08-25 release, which
carries the superseded manuscript.

**`.zenodo.json` metadata bug fixed.** It recorded `isNewVersionOf: 10.5281/zenodo.21575176`.
That is the concept parent, not a previous version; corrected to `10.5281/zenodo.22102520`, the
actual v20.1.0 record. Naming the concept DOI there is precisely what led the first draft of
this paper to treat it as the v18.1.4 version DOI --- the version-confusion both reviewers
flagged as blocker #1 traces back to this one line.

**Wording aligned across metadata.** `CITATION.cff` and `.zenodo.json` said "history-matched
ensembles". Acceptance is 100 %, so the filter never bound; both now say "prior ensembles",
matching the correction the paper makes.

## F. Carried over from the previous version WITHOUT independent re-verification

Flagged so you can decide whether to re-run before submission. None was contested by either
reviewer.

- Social cost of carbon: \$90 Ramsey central, \$90–280 across (ρ, η), \$15 under DICE damages.
- Per-year holdout decompositions (0.56/0.78/0.80/0.90 output; 1.42 Gt in 2020) — these are
  *arithmetically consistent* with the aggregate RMSEs I did re-run, but I did not regenerate
  the per-year series itself.
- The 1990–2023 climate RMSE 0.096 °C.
- Implausibility statistics (max 1.69, median 0.665, output span 0.594–0.619, ρ = 0.90–0.95).
- Country-level RMSE median 0.10, IQR 0.05–0.13, and the five largest country errors.
- Stagflation IRF peak +0.0031 at lag 5, cumulative +0.33, within-R² 0.20.
- Spatial ablation percentages (6.5 %, 2.2 %, 21 %, 1.7 %, 4.3 %) — 6.5 % re-verified from e10;
  the rest not.
- Resource price-forcing effects (−5.5 %, −7.9 %, +0.8 %) and the +24 % 2053 food price.
- The "~2 °C without the SSP2 anchor" figure and the 7–9 % constant-returns sensitivity.
- Game score clusters (26; 70–81), winners' warming 1.6–1.9 °C, and the ≈75 % vs ≈5 %
  both-axes-restraint figure.
