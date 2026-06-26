# Geographic-coupling prior anchors — literature search (S6 follow-up)

Goal: lift the three **expert-prior** weights in the geographic-coupling layer (conflict / tension /
climate) onto the same literature-anchored footing the **trade** channel already enjoys
(`TRADE_GRAVITY_DIST_ELASTICITY = 0.9` ← Head & Mayer 2014). This is the S6 carry-over flagged in
[`SOCIAL_VALIDATION_PROGRAM.md`](SOCIAL_VALIDATION_PROGRAM.md): *"conflict/tension/climate are
directionally-right but modest, expert-prior weights."*

**Headline finding:** the literature is **rich, not thin** — all three channels have published,
quantified spatial-spillover estimates. We do **not** need to fall back to building anchors from
scratch; the data-route the brief proposed (EM-DAT events → neighbour economic trajectories at
18–24 months) has, in substance, **already been done** in peer-reviewed work (Costa & Hooley 2025;
Feng, Li & Wang 2025) and would be **confirmatory**, not novel discovery. See §5.

---

## 0. The four weights (what we are anchoring)

| Channel | Param | Value | Functional form (per step) | Status |
| --- | --- | --- | --- | --- |
| **Trade** | `TRADE_GRAVITY_DIST_ELASTICITY` | 0.9 | gravity init `GDP·GDP / dist^δ` | **anchored** (Head & Mayer 2014) |
| **Conflict** | `GEO_CONTAGION_W` | 0.03 | `conflict_push += W·(1 + n̄_i + n̄_j)` between neighbours | expert prior → **§2** |
| **Tension** | `GEO_TENSION_SPILLOVER_W` | 0.05 | `ΔT_i += W·(mean_{j∈N(i)} T_j − T_i)` | expert prior → **§3** |
| **Climate** | `GEO_CLIMATE_SPILLOVER_W` | 0.10 | `risk_i ← risk_i + W·(mean_{j∈N(i)} risk_j − risk_i)` | expert prior → **§4** |

(`n̄_i` = mean conflict level over `i`'s geographic neighbours. Code: `political_dynamics.py:362`,
`social.py:271`, `climate.py:380`.)

---

## 1. The mapping problem — read this before using the numbers

All three weights are **per-step pull rates toward the neighbourhood mean**. They are **not** directly
comparable to a published spatial-autoregressive coefficient ρ, for two reasons:

1. **Step semantics are inconsistent across run modes.** The headline projection advances in **yearly**
   steps (`console_app.py`), but the crisis-outcome suite runs **6 steps over a 12-month horizon**
   (`calibrate_crisis_persistence.py: SIM_STEPS=6`, cases' `horizon_months: 12`) — i.e. ≈ bi-monthly.
   The same `W=0.05` therefore produces very different cumulative smoothing in the two modes, so there
   is no single "annual ρ" the per-step W could equal.

2. **The literature measures an equilibrium property, not a per-step rate.** A SAR ρ, a Moran's I, or
   an odds ratio describes the **stationary cross-sectional spatial dependence** of the variable. GIM's
   W is the *mechanism* that produces such dependence as an **emergent** output.

**Consequence — and the upgrade.** The honest anchor is **not** "set W = ρ". It is:

> Calibrate/validate W so that GIM's **emergent** cross-country spatial autocorrelation — Moran's I, or
> a SAR ρ estimated on the *simulated* panel — lands inside the published band.

Because the emergent autocorrelation is a **system output, not the sampler input**, this is
**engine-reproduction-eligible** (the good Tier-A.2 / Tier-B move), unlike S1's war-size exponent where
input = output and only anchoring was available. That flips these three weights from **Tier C**
(expert prior, sensitivity-only) to **Tier B** (benchmark the emergent spatial dependence against a
reproducible literature target). This is the concrete deliverable the brief was after.

---

## 2. Conflict — `GEO_CONTAGION_W` (0.03)

**Quantity to reproduce:** the elevation of conflict risk in a country whose **neighbour** is at war
(equivalently, the spatial-lag ρ of conflict onset/incidence on a contiguity graph).

| Source | Estimate | Notes |
| --- | --- | --- |
| **Salehyan & Gleditsch 2006**, *Int. Org.* 60(2) | neighbour conflict → **≈ +52%** odds of intrastate conflict | spatial-lag + refugee channel; **already cited by GIM** |
| **Buhaug & Gleditsch 2008**, *ISQ* 52(2) | **≈ +44%** odds | "Contagion or Confusion?"; **already cited by GIM** |
| **Bosker & de Ree 2014**, *J. Dev. Econ.* 108 | neighbour civil war → **+~3 pp** onset (country-FE); **+4–6 pp** if ethnic | baseline onset ≈ **1.7%**; only *ethnic* wars spill |
| **Carmignani & Kler 2016/2018** (EAP 49; Econ. Systems 40; World Econ. 41) | positive, significant **spatial-AR** spillover; SSA neighbour-at-war **≥ +1 pp** (base 1.1%) | RoW effect ≈ 0; **stronger for interstate** war |
| **Black 2013**, *JPR* 50(6) | *causally-linked* contagion **rarer** than proximity implies | downward-calibrating caution against over-weighting |

**Anchor.** Neighbour-at-war raises own conflict risk by a **modest but robust** factor: ≈ +44–52% in
odds (Gleditsch lineage) or ≈ +3 pp on a ~1.7% base. Spillover is **heterogeneous** (strong in
SSA / ethnic / interstate; near-zero elsewhere) — so a *global* uniform weight should sit at the
**low end**. The current `geo_prop = 0.03·(1 + n̄_i + n̄_j)` puts the baseline contiguity premium
(0.03) on par with GIM's other conflict-push drivers (`0.04·trade_short`, `0.05·avg_tension`,
`0.06·mil_gap`) — order-consistent. **Defensible band: 0.02–0.05.** Reproduction target: simulated
neighbour-vs-non-neighbour conflict-onset odds ratio in the **1.4–1.5×** range (and the S5 locality
metric, already 2.7× → 9.6×).

---

## 3. Tension / unrest — `GEO_TENSION_SPILLOVER_W` (0.05)

**Quantity to reproduce:** cross-border diffusion of protest / unrest to geographic neighbours.

| Source | Estimate | Notes |
| --- | --- | --- |
| **Arezki, Dama, Djankov & Nguyen 2024**, *Empirical Economics* 66(6) (WB PRWP 9321) | **pure geographic/distance spillover is statistically _insignificant_** (Table 1 cols 1–2: 0.012 [se .015]; 0.022 [se .022]); significant **only** when weighted by *common social-media penetration* (cols 3–5; the "+37% of own SD" applies to >30%-penetration pairs) | autoregressive spatial model (LeSage–Pace ZIP), 200 countries 2000–2020. ⚠ does **not** support a pure-adjacency anchor (verified from the WB PDF) |
| **Braha 2012**, *PLoS ONE* 7(10) e48596 (arXiv:1207.0739) | spatial-epidemic contagion; **region-specific infectiousness rate**, near-critical | **already cited by GIM**; anchors the *form* (epidemic, neighbour + long-range, criticality), 170 countries 1919–2008 |
| **Magee 2022**, *Int. Interactions* | protest strength driven by neighbours' protests over **prior 1–2 weeks**; trade-weighted | short diffusion timescale |
| **Garcia & Wimpy 2016**, *PSRM* 4(1) | significant **spatial dependence** in anti-government violence (Africa) | conditioned by communication-tech access |

**Anchor (revised after first-source check).** The cleanest cross-national study (Arezki et al.) finds
**pure geographic adjacency/distance protest spillover statistically insignificant**; the contagion that
*is* significant runs through **common social-media penetration** — a network weight, not a border weight.
So the *geographic* tension channel is the **least literature-anchored** of the three: directionally
supported by the general clustering of unrest (Braha 2012, epidemic short + long-range links) but **without
a clean adjacency magnitude**. **Recommendation: keep `W=0.05` modest; do _not_ push to 0.10** (the earlier
suggestion is withdrawn — Arezki's null undercuts a strong pure-adjacency spillover). This squares with the
S6 diagnostic ("near 2.2× far (weak)") and the model's own finding that tension clustering is mostly
inherited from clustered initial conditions (§6.5). Reproduction target: a *positive* Moran's I on the
simulated tension cross-section (a stylized fact), not a specific adjacency ρ.

**Caveat (honest):** Braha's exact per-region infectiousness β sits in an SI table that did not extract
cleanly, and Arezki's significant spillover is **social-media-mediated, not geographic** — so the tension
channel has **no clean numeric adjacency anchor**: its *form* (epidemic, short + long-range) is
literature-grounded but its *weight* is an expert prior. (The deferred SOC-sandpile branch in
[`CRITICALITY_RISK.md`](../CRITICALITY_RISK.md) is the natural *emergent* generator here.)

---

## 4. Climate-risk — `GEO_CLIMATE_SPILLOVER_W` (0.10)

This is the **best-anchored** of the three, with two independent anchor types.

**(a) Physical spatial coherence** (why neighbours' climate risk co-moves at all):

| Hazard variable | Spatial correlation / decorrelation length |
| --- | --- |
| **Temperature anomalies** | monthly decorrelation **~1300 km** (land) / **~1550 km** (marine); strongly correlated out to ~1000 km — gridded-temperature climatology (classic Hansen–Lebedeff 1200 km; ESSD 17:7079, 2025) |
| **Daily precipitation** | global-mean correlation length **~289 km** (land 262, ocean 300) |
| **Extreme precipitation** | **< 100 km** (annual-max rainfall decorrelates < 15 km) |

→ Temperature/heat/drought-driven risk is correlated **far beyond** typical neighbour distances ⇒
**strong** neighbour co-movement; flood/extreme-precip risk is correlated **weakly**. This *physically
justifies* climate carrying the **largest** of the three weights (0.10), and suggests the spillover is
hazard-dependent (large for heat/drought, small for floods).

**(b) Economic spatial spillover** (the brief's EM-DAT-→-neighbour-GDP idea, already in the literature):

| Source | Estimate |
| --- | --- |
| **Costa & Hooley 2025**, OECD Econ. Dept WP 1837 | severe weather event **−2.2%** regional GDP; **spillover within 100 km → further −0.5%** (≈ 23% of the direct effect); **spillovers ≈ half of total impact**; 1,600 regions, 31 countries |
| **"Spatial Effects of Climate Change on Growth" 2023**, *Sustainability* 15(10):8197 | dynamic **SAR**, positive **Moran's I** (contiguity & inverse-distance W); indirect (spillover) long-run effects **−0.173 / −0.240** (low–mid-income) |
| **Feng, Li & Wang 2025**, *Economic Journal* 135(669) | cross-border climate-disaster spillovers via **trade / supply chains** — complements GIM's *trade*-gravity channel, not the adjacency one |
| **NBER w32450 (2024)** | constructs an **external (neighbour) temperature shock**, distance/trade-weighted |

**Anchor.** Spatial spillovers are roughly **as large as the direct local effect** (Costa & Hooley:
spillovers ≈ half of *total* ⇒ comparable to direct). `W=0.10` (the largest weight) is **defensible and
physically well-grounded**. **Band: 0.08–0.15**, with a credible refinement to make it hazard-specific
(higher for temperature/drought risk, lower for precipitation/flood risk). Reproduction target: positive,
significant Moran's I on the simulated climate-risk cross-section, matching the sign/order of the
*Sustainability* 2023 estimates.

---

## 5. Verdict on the data-based fallback (EM-DAT / OWID neighbour trajectories)

The brief proposed: *if literature is thin, geolocate EM-DAT climate events to a country and compare
neighbours' economic trajectories at 18–24 months.* Two points:

1. **Literature is not thin** — so this is **not required** to anchor the priors.
2. **That exact study already exists.** Costa & Hooley (2025) regress regional GDP on local + spatially
   weighted disaster shocks with multi-year horizons; Feng et al. (2025) trace disaster shocks to trade
   partners; the *Sustainability* (2023) SAR uses EM-DAT-style climate measures with contiguity weights.
   The brief's 18–24-month horizon coincides with the disaster-growth literature's persistence window
   (Costa & Hooley find ~1.7% loss **persisting at 5 years**).

**Recommendation.** Treat an in-house EM-DAT + WDI replication as an **optional confirmation step**, not
a discovery step — valuable mainly to obtain a **GIM-specific Moran's I / SAR-ρ target** on the same
country aggregation GIM uses. Minimal design if we do it:

- EM-DAT events (or OWID/EM-DAT mirror) → ISO3 → align to GIM's 57 agents (reuse `gim/geography.py`
  adjacency, already built);
- World Bank WDI GDP (already vendored: `data/external/worldbank_wdi_1990_2024.csv`) at horizons
  h = 12/18/24 months;
- spatial-lag panel (event in `i` → growth in adjacent `j`), report ρ and Moran's I;
- use the estimate purely as the **reproduction target** for §2–§4, not as a new structural equation.

Honest caveats for any such replication: confounding (common shocks, trade), EM-DAT reporting bias
(richer/larger countries over-reported), and the aggregate-vs-network distinction already learned in
`diagnose_trade_gravity.py` (network structure can change while aggregates do not).

---

## 6. Summary: recommended bands & tiering

| Weight | Current | Literature anchor | Defensible band | New tier | Reproduction check |
| --- | --- | --- | --- | --- | --- |
| `GEO_CONTAGION_W` | 0.03 | neighbour-at-war +44–52% odds / +3 pp (Salehyan-Gleditsch; Buhaug-Gleditsch; Bosker-de Ree; Carmignani-Kler) | **0.02–0.05** | **B ✓** | **1.47× dyadic premium** (lit +44–52%) |
| `GEO_TENSION_SPILLOVER_W` | 0.05 | ⚠ pure-adjacency spillover **insignificant** (Arezki); significant only social-media-mediated. Form from Braha (epidemic) — no clean adjacency magnitude | **keep ~0.05** (weakest channel) | **C→B** | Moran's I 0.84, p=.001 (clustering present; mostly inherited) |
| `GEO_CLIMATE_SPILLOVER_W` | 0.10 | corr-length: T ~1000+ km, precip ~290 km; spillover ≈ half of total (Costa-Hooley; *Sustainability* SAR) | **0.08–0.15** (hazard-specific) | **B ✓** | **Moran's I 0.87, p=.001** |

**Net:** conflict and climate move from "expert prior, sensitivity-only" to **literature-anchored bands
with an emergent-spatial-autocorrelation reproduction target**, and both sit **inside** their bands — the
priors are **vindicated, not overturned**. **Tension is the exception:** its pure-adjacency magnitude has
**no clean literature anchor** (Arezki's geographic spillover is null; significant contagion is
social-media-mediated), so it stays an honest expert prior at a deliberately **modest** `W=0.05` (the
earlier "push to 0.10" is withdrawn). Candidate refinement: make climate hazard-specific (large for
heat/drought, small for floods).

---

## 6.5 Reproduction benchmark — DELIVERED (`scripts/run_s6_geo_autocorrelation.py`)

The Tier-B plan of §1 is now **run, not just specified.** We advance the world 10 yearly steps with the
geographic channels ON (headline default) vs OFF and measure, on the 48-country shared-border graph
(49 contiguity edges), the **emergent** spatial dependence of each variable. Deterministic (extreme
events off, seeded permutations); 5 tests in `tests/test_s6_geo_autocorrelation.py`; full suite **460 passed**.

| Variable | Statistic | OFF | ON | p(on) | Literature target | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| **Conflict** | dyadic neighbour-premium (adj / non-adj conflict) | 1.03× | **1.47×** | — | +44–52% neighbour effect (Salehyan-Gleditsch; Buhaug-Gleditsch) | **reproduced** — +47% ≈ lit band |
| **Tension** | node Moran's I (perm test) | 0.79 | **0.84** | 0.001 | positive clustering of unrest (Braha; stylized fact — Arezki's *adjacency* spillover is null) | clusters (sig.), but ΔI small / mostly inherited |
| **Climate** | node Moran's I (perm test) | 0.86 | **0.87** | 0.001 | positive, significant (Costa-Hooley; *Sustainability*) | **reproduced** (sig.) |

**Two honest readings.**
- **Conflict is edge-level**, so a node Moran's I dilutes it (came back n.s., I ≈ −0.01). The correct
  projection is the **dyadic neighbour-premium**, which rises 1.03× → **1.47×** with the coupling — the
  coupling manufactures a **+47%** neighbour-conflict premium that lands squarely on the literature's
  **+44–52%** (and is consistent with S5's 2.7× → 9.6× escalation locality). This is the cleanest causal
  signature of the three channels.
- **Tension / climate node autocorrelation is high AND significant, but mostly *inherited*** from
  spatially-clustered initial conditions (neighbours share water-stress / inequality); the coupling's
  *marginal* contribution (ΔI ≈ +0.05 / +0.01) is small. So the **level** matches the literature, but the
  channel is a modest add-on to pre-existing clustering — consistent with "payoff concentrated in trade".

Ledger: `results/calibration/geo_autocorrelation.json`.

---

## 7. Honest caveats (carry into the paper)

- **First-source verification (done 2026-06-26).** Load-bearing numbers were checked against primaries:
  **Costa & Hooley** (−2.2% direct / −0.5% within 100 km ≈ ¼ of direct / ~½ of impact via spillovers) —
  verified verbatim; **temperature decorrelation ~1300 km (land) / ~1550 km (marine)** — verified
  (gridded-temperature climatology); **Head–Mayer δ = 0.9** — confirmed as the Disdier–Head (2008) /
  Head–Mayer (2014) meta-central distance elasticity (literature spans ~0.7–1.5). **Conflict +44% / +52%**
  are stable secondary syntheses of the primaries' logit coefficients (primaries confirm a significant
  positive neighbour effect, ethnic/separatist-mediated; Bosker–de Ree **+3 pp** read from the primary).
  **Arezki — CORRECTED:** the WB PDF Table 1 shows pure geographic/distance protest spillover is
  *statistically insignificant* (cols 1–2); it is significant only via common social-media penetration —
  so the tension channel has **no clean adjacency anchor** (§3 revised, §6 row downgraded C→B with the
  caveat). **Still open:** the Carmignani–Kler ρ and *Sustainability* 2023 ρ/Moran's I are read from
  abstracts/highlights, not yet the regression tables.
- **Anchoring ≠ engine reproduction — now delivered (§6.5).** The reproduction is run: GIM produces the
  literature's positive spatial dependence (tension/climate Moran's I sig.; conflict +47% dyadic premium).
  But it is a **sign/order** reproduction, not a same-test-set coefficient bake-off, and for tension/climate
  the coupling's *marginal* effect is small (the high autocorrelation is largely inherited from initial
  conditions). State that explicitly; do not over-sell ΔI.
- **Heterogeneity is real.** Conflict spillover is near-zero outside SSA/ethnic/interstate cases; a
  uniform global weight is a deliberate simplification toward the low end.
- **Payoff still concentrated in trade.** Even fully anchored, the geographic gain remains strongest in
  the trade channel (clean δ + cascade shape); these three add realism, not a headline result.

## Sources

- Salehyan & Gleditsch 2006, *International Organization* 60(2), "Refugees and the Spread of Civil War".
- Buhaug & Gleditsch 2008, *International Studies Quarterly* 52(2), "Contagion or Confusion?".
- Bosker & de Ree 2014, *Journal of Development Economics* 108, "Ethnicity and the spread of civil war".
- Carmignani & Kler 2016, *Economic Analysis and Policy* 49; 2016 *Economic Systems* 40(1); 2018 *The World Economy* 41(1).
- Black 2013, *Journal of Peace Research* 50(6), "When have violent civil conflicts spread?".
- Arezki, Dama, Djankov & Nguyen 2024, *Empirical Economics* 66(6) / World Bank PRWP 9321 (2020), "Contagious Protests".
- Braha 2012, *PLoS ONE* 7(10) e48596 / arXiv:1207.0739, "Global Civil Unrest" / "A Universal Model of Global Civil Unrest".
- Magee 2022, *International Interactions*, "Diffusion of protests in the Arab Spring".
- Garcia & Wimpy 2016, *Political Science Research and Methods* 4(1).
- "Correlation Models for Temperature Fields", *Journal of Climate* 24(22), 2011; gridded near-surface temperature record, *Earth Syst. Sci. Data* 17:7079, 2025 (monthly decorrelation ~1300 km land / ~1550 km marine).
- Head & Mayer 2014, "Gravity Equations: Workhorse, Toolkit, and Cookbook", *Handbook of Int. Economics* 4; Disdier & Head 2008, *Rev. Econ. Stat.* 90(1) (distance-elasticity meta-mean ≈ 0.9).
- Costa & Hooley 2025, OECD Economics Department WP 1837, "The macroeconomic implications of extreme weather events".
- "Unveiling the Spatial Effects of Climate Change on Economic Growth", *Sustainability* 15(10):8197, 2023.
- Feng, Li & Wang 2025, *The Economic Journal* 135(669), "We Are All in the Same Boat".
- NBER Working Paper 32450 (2024), extreme-climatic-events damages with economic spillovers.
