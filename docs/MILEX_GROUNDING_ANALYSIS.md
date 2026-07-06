# Milex grounding — empirical basis for the v18.1.0 re-anchor ([F3+])

Self-contained record of the analysis behind `MILEX_CINC_COMPONENT` (SIPRI military-expenditure
component in the CINC capability index). The underlying research program (Richardson arms-race
econometrics, GPR↔milex causality, GDELT event studies, cyber hybridization) lives in a separate
local research workspace; everything the re-anchor decision rests on is reproduced here.

Data sources: SIPRI Military Expenditure Database (constant 2022 US$, 1949–2024); World Bank WDI
panel (`data/external/worldbank_wdi_1990_2024.csv` — milex_usd is SIPRI-derived, log-log r = 1.0000
against the SIPRI workbook); GPR index (Caldara–Iacoviello); UCDP/PRIO ACD v24.1.

## 1. Why the 3-proxy CINC needed the milex component

GIM grounded `technology.military_power` in a CINC-style share built from population, energy and
GDP (military spending was unpopulated in the state). Validation against observed milex shares
(49-country panel, 1990–2024):

| Test | Result |
|---|---|
| Cross-sectional fit, proxy share vs milex share (Pearson, by year) | mean **0.76** (0.68–0.85) |
| Correlation of share **changes** 2021→2024 (militarization dynamics) | **−0.115** |

The proxy ranks static capability adequately but is *anti-correlated* with post-2022 militarization
dynamics — e.g. Russia's milex share rose +2.7 pp while its proxy share fell −1.4 pp (GDP under
sanctions vs surging military spending). No component carries a military signal, so this is
structural, not a calibration issue.

A deterministic 2015→2024 run (2015 backtest fixture, default policies, no extreme events) showed
the model side of the same blind spot: `conflict_proneness` frozen at 0.4345 for all 10 years,
dyadic conflict a monotone drift with no 2022 inflection, while the observed GPR index jumped +46%
(2022–24 vs 2015–21 means).

## 2. Decomposition test — economy-only vs threat-structured militarization

Hypothesis tested: post-2022 milex shifts might be fully explained by economic drivers (no
autonomous arms-race dynamic needed). Panel: 48 countries × 1995–2024 (1402 obs), country fixed
effects, SEs clustered by country.

| Spec | Key result |
|---|---|
| (A) Δlog milex ~ Δlog gdp (+lag) | gdp coef **0.79** (p<0.001), R² 0.48 — peacetime milex is an economic phenomenon |
| (B) + lagged rival milex growth | rival term **p=0.74**, ΔR² +0.007 — classic Richardson rate-chasing **rejected** |
| (B) + frontier×post2022 | **+14.4 pp/yr**, p<0.0001 |

Economy-only residuals 2022–2024, by group (mean, pp/yr):

| Group | Excess milex growth |
|---|---|
| NATO frontier (POL, FIN, NOR, ROU) | **+13.0** |
| Russia / China | +9.6 |
| Other NATO | +5.5 |
| Rest of world | **+0.2 ≈ 0** |

Reading: in the normal regime milex tracks GDP; the post-2022 excess is *threat-gradient
structured* (not a global common shock, not an income effect) and takes the form of a discrete
regime shift, not continuous rate-chasing. Hence the decision matrix below.

## 3. Decisions

| Item | Verdict | Basis |
|---|---|---|
| Tier 1 — populate `economy.military_spending` from SIPRI, activate milex CINC component | **GO (shipped in v18.1.0)** | §1: proxy structurally blind to militarization |
| Tier 2 — Richardson rate-reaction mechanism (milex growth chases rival growth) | **NO-GO** | §2: empirically rejected (p=0.74) |
| Tier 2′ — regime-dependent milex/GDP = f(base share, dyadic threat state) | GO, future work, switchable off-by-default | §2: threat-gradient +13 pp/yr maps onto `RelationState`/tension |

## 4. Tier 1 implementation + verification (v18.1.0)

Mechanics: `scripts/build_milex_grounding.py` → `data/external/sipri_milex_2023.csv` (57 actors:
50 countries direct, AG_* aggregates summed over pipeline `model_region` members — 99.9% of the
SIPRI world total; carry-forward for SIPRI gaps: ARE←2014, VNM←2018; HKG=0, folded into CHN).
`capability.load_military_spending()` populates the state at world build (gated by
`MILEX_CINC_COMPONENT`), then the CINC picks up the 4th component:

C′ᵢ = ¾·Cᵢ + ¼·s(milex)ᵢ,  military_powerᵢ = C′ᵢ/⟨C′⟩

| Check | Requirement | Result |
|---|---|---|
| Golden backtest | bit-identical | **GDP 0.599 / CO₂ 0.939 / T 0.145** ✓ |
| UCDP conflict skill | no degradation | **AUC 0.739 / BSS +0.123** ✓ (scores the untouched state-CSV `conflict_proneness`) |
| Full unittest suite (incl. SCC bands) | green | OK ✓ |
| Calm 2015–2024 trajectories | no drift | bit-identical ✓ |

Capability ranking after: **USA 0.204 > CHN 0.185 > IND 0.080**; RUS 0.034 (+12.5%), ISR +88%,
SAU +50%, USA +40% vs proxy. The flip vs the published COW ordering (China > US) is an intentional,
documented departure from the steel-and-personnel-era COW component mix; the proxy configuration
keeps the published-CINC anchor and both configurations are pinned by `tests/test_capability.py`.

## 5. Honest caveats

- Grounding file is 2023 values applied at any world build (mild anachronism for the 2015 fixture —
  same class of approximation as the F3 proxy itself).
- SIPRI post-2022 Russia figures are estimates; milex shares are scale-invariant to price-base
  choice within a component.
- The decomposition test is a pilot (annual panel, bloc dummies); Tier 2′ calibration should
  re-estimate the threat gradient with dyadic geography before wiring anything into dynamics.
