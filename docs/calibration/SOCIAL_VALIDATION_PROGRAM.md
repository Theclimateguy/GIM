# Social / political validation program (S1–S4)

Goal: lift the **society / politics / geopolitics / culture** blocks from the honest-but-weak bar
("beats a naive benchmark", "channel identification") onto **numeric, reproducible, literature-anchored
priors** — the same standard the climate/economy core already meets (e.g. `ECS_DEFAULT` ← IPCC AR6,
`DAMAGE_QUAD_COEFF` ← DICE/Howard–Sterner, and the **D6** keystone check in
[`scripts/run_d6_dice_scc.py`](../../scripts/run_d6_dice_scc.py)).

## Why this is not one method but two

D6 did **two** things at once, and they transfer unequally to the social domain:

1. **Anchoring a prior to a published number** (damage `a₂` ← DICE/Howard–Sterner). Transferable
   broadly: war sizes, migration, trust, inequality all have published exponents / elasticities / base
   rates with citations.
2. **Engine reproduction** (feed DICE's inputs → recover DICE's SCC with GIM's *own* engine, isolating
   movement of the movie from the input). Transferable **only** where GIM computes an *emergent*
   quantity that a reference also computes — conflict skill, the trust→growth impulse, migration
   elasticities. Where the parameter **is** the measured quantity (an exponent that is both the sampler
   input and the fitted output), only the anchoring half is available; full engine-reproduction would
   require an *emergent* generator (the deferred SOC-sandpile, see
   [`docs/CRITICALITY_RISK.md`](../CRITICALITY_RISK.md)).

Climate-economics is the lucky case: it has a **consensus scalar from a shared process model** (DICE's
SCC). Most of social science instead offers (i) empirical regularities / elasticities and (ii)
forecast-skill leaderboards. So the program runs on **three tiers**:

- **Tier A — anchor the prior to a published number** (and verify the engine reproduces it where the
  quantity is emergent). → S1, S2, S3.
- **Tier B — benchmark forecast skill against a reproducible reference model** (Brier / AUC /
  calibration vs ViEWS/PITF). → S4.
- **Tier C — bounded expert priors, disciplined only by sensitivity analysis** (structural thresholds,
  culture-coupling coefficients with no canonical number and weak identification). Stated plainly, not
  dressed up as D6. → out of scope for direct validation; tracked as residual.

**Honesty rule for this program:** never present *anchoring* (Tier A.1) as *engine reproduction*
(Tier A.2). Each epic states which half it delivers.

## Current baseline (what we are improving on)

- `data/parameter_priors.csv`: 26 rows, **all climate/economy**, **zero** social/political.
- Conflict block: ranking 57 countries by conflict-proneness vs the UCDP/PRIO registry →
  **AUC 0.736 [0.59; 0.86], BSS +0.143, p≈0.001** (a discrimination metric, not a reproduced number).
- Society/politics/geopolitics otherwise: "improvement over naive benchmark" + channel identification
  (paper §5).

## The epics

| ID | Quantity (GIM) | Published target | Source | Tier | Delivers |
| --- | --- | --- | --- | --- | --- |
| **S1** | crisis/war severity tail exponent `CRISIS_SEVERITY_ALPHA` | **α ≈ 1.5** (1.5–1.8 band) | Richardson 1948; Clauset 2018 (Sci. Adv.); Cederman 2003 | A | anchor prior + verify sampler (round-trip MLE + KS). **Not** emergent reproduction. |
| **S2** | migration income/distance elasticities | income ≈ **+1**, distance ≈ **−1** | Beine, Bertoli & Fernández-Huertas Moraga 2016; Ramos 2017 | A | anchor `MIGRATION_*` + engine reproduction (regress simulated flows). |
| **S3** | trust→growth impulse | **+0.5…0.8 pp** growth per **+10 pp** trust | Knack & Keefer 1997 (QJE); Algan & Cahuc 2010 (AER) | A | anchor trust-economy channel + engine reproduction (IRF). |
| **S4** | conflict-onset forecast skill | published AUC/Brier of a standard model | ViEWS (Hegre et al. 2019/2022); PITF (Goldstone et al. 2010); onset coeffs Fearon & Laitin 2003, Collier & Hoeffler 2004 | B | Brier + calibration + head-to-head vs reproducible benchmark; anchor onset weights. |

### S1 — war-size power-law exponent

- **Anchor:** war severity follows `Pr(x) ∝ x^−α` with α ≈ 1.5–1.6 — "among the most accurate and robust
  findings in world politics" (Richardson 1948; reconfirmed Clauset 2018 with modern MLE+KS; Cederman
  2003 SOC model). GIM already sets `CRISIS_SEVERITY_ALPHA = 1.5` ([`gim/core/calibration_params.py`])
  and ships a `powerlaw_severity` sampler ([`gim/criticality.py`]).
- **Reproduction procedure (reusable on real war data later):** truncated-Pareto MLE
  `fit_truncated_pareto_alpha(samples, a, b)` + KS goodness-of-fit. Applied to the engine's own draws it
  must recover α̂ ≈ 1.5 and not be rejected by KS — verifying the sampler is a correct truncated Pareto.
- **Honest scope:** this is Tier-A anchoring + sampler validation. The exponent is an *imposed input*,
  so recovering it is a consistency check, not endogenous emergence. Emergent reproduction (the exponent
  arising from a self-organized-criticality conflict dynamic) is the deferred research branch noted in
  `CRITICALITY_RISK.md` — out of scope for S1.
- **Artifacts:** prior row in `data/parameter_priors.csv`; `scripts/run_s1_war_severity.py`;
  `tests/test_s1_war_severity.py`.

### S2 — migration gravity elasticities — DONE

The shipped engine (`update_migration_flows`) was exercised on a controlled world (one poor origin + 35
richer destinations that do not back-migrate, so bilateral flows are read off population deltas — the
real engine, not a re-implementation). Recovered elasticities: **mass = 1.000** (canonical gravity mass
term), **income-gap = 1.000** and **trade-linkage = 1.000** (the engine is unit-elastic in the income
gap and the linkage), **income-LEVEL = 1.18** (positive, order-1, inside the gravity band ~0.5–1.5;
Beine et al. 2016).

**Honest scope / form:** GIM has **no bilateral distance field** — trade linkage plays the gravity
proximity/contiguity role (a positive linkage elasticity, **not** a −1 distance elasticity). The engine
is **gap-linear, not log-linear**, so the income-level elasticity is operating-point dependent
(reported, not hidden). Anchored `MIGRATION_BASE_RATE`/`MAX_SHARE` to observed migration rates (UN DESA)
and `MIGRATION_INCOME_PUSH_W`/`CONFLICT_PUSH_W` to the income-dominant-pull structure (Beine et al.;
UNHCR). Artifacts: `gim/migration_validation.py`, `scripts/run_s2_migration_gravity.py`,
`tests/test_s2_migration_gravity.py`, 4 prior rows in `data/parameter_priors.csv`.

### S3 — trust→growth channel — DONE (with a structural finding)

Tracing the code shows `trust_gov` enters the economy in exactly one place — the **diagnostic** credit
rating — which does **not** feed the effective interest rate. **Finding:** GIM has **no marginal
trust→growth channel** (the effective rate, hence cost of capital and investment, is provably invariant
to trust: rate span = 0.0 over trust ∈ [0.05,0.95]). So a clean Knack–Keefer marginal-elasticity
reproduction is **not applicable** — a trust→TFP channel is a **candidate model extension**, flagged not
papered over.

The channel that **does** exist — the only trust→growth pathway — is the **nonlinear regime-collapse
threshold**: trust < 0.20 ∧ tension > 0.80 → a one-off **20% GDP drop** (capital 30%). That magnitude is
anchored to the **macroeconomic-disaster literature** (Barro & Ursúa 2008 peak-to-trough losses ~10–30%,
typical ~20%; Aisen & Veiga 2013 political-instability→growth; cost-of-civil-war). Anchored
`REGIME_COLLAPSE_GDP_MULT` (0.7–0.9 band = 10–30% loss) and `REGIME_COLLAPSE_CAPITAL_MULT`; the collapse
**thresholds** stay **Tier-C** expert priors. Artifacts: `gim/trust_growth_validation.py`,
`scripts/run_s3_trust_growth.py`, `tests/test_s3_trust_growth.py`, 2 prior rows.

### S4 — conflict forecast-skill benchmark — DONE (framework; live bake-off deferred)

Upgraded the conflict block from "skill vs base rate" to a reproducible benchmark: on the live UCDP/PRIO
scoring set (57 countries, 1990–2023) it now reports **AUC 0.736, BSS +0.143**, plus the **Murphy
calibration decomposition** (reliability **0.0122**, resolution 0.0470, cal.err 0.091) and a **reliability
diagram** — calibration, not just discrimination. GIM's number is placed against the **published**
out-of-sample skill of the standard models (PITF — Goldstone et al. 2010; ViEWS — Hegre et al. 2019/2022).

**Honest scope:** Tier-B forecast-skill benchmark, not D6 engine-reproduction. The references score
**different targets/units** (PITF: 2-yr instability onset, country-year; ViEWS: country-month/grid-month
incidence — AUC inflated by easy negatives), so this is a sign/order placement, **not** a same-test-set
bake-off; GIM lands at the lower end of the published EWS band, achieved by an **unfitted** mechanistic
input. **Deferred:** a true common-set bake-off needs ViEWS replication data; anchoring the
`conflict_proneness` construction to Fearon–Laitin / Collier–Hoeffler onset coefficients is a follow-up.
Artifacts: `gim/conflict_benchmark.py`, `scripts/run_s4_conflict_benchmark.py`,
`tests/test_s4_conflict_benchmark.py`.

### S5 — geography in the conflict block — DONE (diagnostic → leverage → switchable wiring)

A follow-on from S2/S4: GIM's escalation/`border_incident` target is `argmax(conflict_level + 0.5·(1−trust))`
with **no adjacency term** — geography-shaped but geography-free. Three steps, each cheap and golden-safe:

1. **Geography asset** (`gim/geography.py`, from `data/world_countries.geojson` via shapely): centroid
   great-circle distance + shared-border adjacency for the agents (48/57 matched; 7 aggregates + 2
   city-states unmatched, ≈6.5% of GDP). **Not imported by the core** — pure diagnostic.
2. **Diagnostic** (`scripts/diagnose_border_geography.py`): real interstate conflict is strongly local
   (UCDP 1990–2023, full world: **92%** of dyads between neighbours, **45.6× chance**, median **863 km**)
   while GIM's escalation targets are not (**12%**, **2.7×**, median 6906 km).
3. **Leverage test** (`gim/conflict_geography.py`, `scripts/run_s5_conflict_geography.py`): augmenting
   `conflict_proneness` with a spatial lag of neighbour conflict-risk (spatial contagion; Gleditsch 2007;
   Buhaug & Gleditsch 2008) lifts the conflict ranking **AUC 0.772 → 0.805** (neighbour-exposure alone
   0.690). Gain is **modest** and on a small geo-matched set; the blended best is grid-search-optimistic.

Given a real (if modest) gain, wired a **switchable, off-by-default** adjacency contagion term into
`update_relations_endogenous` (`GEOGRAPHY_CONFLICT_LINKS=False`, `GEO_CONTAGION_W=0.03`; adjacency built
lazily so the core stays shapely-free and **golden-identical** when off). Enabling it raises GIM's
escalation locality **2.7× → 9.6× chance** (median 6906 → 3364 km), closing part of the gap to reality.
Artifacts add: `gim/geography.py`, `gim/conflict_geography.py`, two scripts, three tests, a result ledger.

## Status

- **S1** — DONE (war-size exponent anchored; sampler validated, α̂=1.51, KS=0.003).
- **S2** — DONE (migration gravity elasticities reproduced; mass=1, income≈1.18; MIGRATION_* anchored).
- **S3** — DONE (no marginal trust→growth channel found; regime-collapse 20% GDP hit anchored to disasters).
- **S4** — DONE (conflict skill + calibration + published-reference placement; live ViEWS bake-off deferred).
- **S5** — DONE (geography diagnostic → leverage AUC 0.772→0.805 → switchable adjacency contagion,
  locality 2.7×→9.6×; off by default, golden-safe).

**Net:** 7 new literature-anchored prior rows in `data/parameter_priors.csv` (was 0 social/political);
6 reproduction/diagnostic scripts + 6 test modules; 5 validation modules; one switchable, off-by-default
core enhancement (geography contagion). Honest carry-overs: (i) all cited numeric values need first-source
verification before paper inclusion; (ii) Tier-C residual (collapse thresholds, culture-coupling
coefficients) stays sensitivity-disciplined, not D6-validated; (iii) the geography AUC gain is modest and
the wiring ships off by default.
