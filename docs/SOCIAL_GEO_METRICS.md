# GIM18 Social / Geopolitical / Military — External Metric Map (F3)

GIM's unique social-geopolitical-military layers are built on expert priors. To ground and
validate them (the F3 challenge) each internal variable must be mapped to an **established
external index/dataset** — the social-science equivalent of using AR6/PWT for climate/economics.
This is the researched mapping; all datasets verified June 2026.

## Governance / stability

| GIM variable | Best external metric | Source / coverage | Use |
|---|---|---|---|
| `risk.regime_stability` | **WGI Political Stability & Absence of Violence (PV)** | World Bank, 0–100 abs scale, 1996–2024, 200+ economies | direct anchor (regime_stability ≈ WGI-PV/100) |
| `risk.conflict_proneness` | inverse WGI-PV; **Fragile States Index**; **State Fragility Index** | World Bank / Fund for Peace / George Mason | calibrate base rates |
| `society.trust_gov` | **WGI Voice & Accountability**; **EIU Democracy Index**; **Edelman / WVS** trust surveys | World Bank / EIU / WVS | level + trend validation |
| `culture.regime_type` | **V-Dem**, **Polity5**, **Boix-Miller-Rosato** | V-Dem Inst. / CSP | the one load-bearing cultural var; ground the Democracy/Autocracy split |
| `political.legitimacy` | **WGI Government Effectiveness / Rule of Law**; **BTI** | World Bank / Bertelsmann | mapping |
| political risk (composite) | **ICRG (PRS Group)** political-risk rating | 140 countries, 1984+, annual/monthly | cross-check the risk block |

## Conflict (bilateral)

| GIM variable | Best external metric | Source / coverage | Use |
|---|---|---|---|
| `relation.at_war`, `relation.conflict_level` | **UCDP/PRIO Armed Conflict Dataset** (v26.1, 1946–2025) + **UCDP Dyadic** | Uppsala / PRIO | the global standard — backtest conflict onset/escalation; skill vs base rate |
| sub-war events / protests / riots | **ACLED** (event-level, 1997–, near-real-time) | ACLED | high-resolution unrest/violence |
| interstate disputes | **Militarized Interstate Disputes (MID)** / Correlates of War | CoW | dyadic dispute calibration |

## Military capability

| GIM variable | Best external metric | Source / coverage | Use |
|---|---|---|---|
| `technology.military_power` (scalar, ungrounded) | **CINC — Composite Index of National Capability** | Correlates of War, National Material Capabilities v7.0, 1816–2016 | **replace the ungrounded scalar with CINC** (0–1 share of global capability), computed from mil-expenditure, mil-personnel, energy, iron/steel, urban+total population |
| `economy.military_spending` | **SIPRI Military Expenditure Database** | SIPRI, 1949–, ~170 countries | direct $ anchor (a CINC component) |
| `technology.security_index` | **Global Peace Index**; IISS Military Balance | IEP / IISS | external-security state |

## Social / unrest / inequality

| GIM variable | Best external metric | Source / coverage | Use |
|---|---|---|---|
| `society.inequality_gini` | **SWIID** (Standardized World Income Inequality DB); **WID**; World Bank Gini | Solt / WID / WB | direct anchor |
| `society.social_tension`, `political.protest_pressure` | **Mass Mobilization Project**; **CNTS Domestic Conflict**; ACLED protests/riots | Clark-Regan / Banks / ACLED | unrest validation; skill vs base rate |
| `economy.unemployment`, `inflation` | ILO / IMF WEO / WDI | ILO/IMF/WB | already data-anchored (P4-A) |

## Sanctions / external policy

| GIM variable | Best external metric | Source / coverage | Use |
|---|---|---|---|
| `political.sanction_propensity`, sanctions dynamics | **Global Sanctions Database (GSDB)** (1950–2022, 1100+ cases); **TIES** | Felbermayr et al. / Morgan et al. | calibrate sanction onset & effect |

## Environmental risk

| GIM variable | Best external metric | Source / coverage | Use |
|---|---|---|---|
| `risk.water_stress` | **WRI Aqueduct Water Risk Atlas**; **FAO AQUASTAT** | WRI / FAO | direct anchor |

## Priority recommendations (concrete, high-value)

1. **`military_power` → CINC.** The single clearest upgrade: replace the ungrounded scalar
   (default 1.0) with the Composite Index of National Capability — observable, standard, and a
   real 0–1 share. Most GIM countries' CINC are computable from data the model already loosely
   tracks (population, energy, military spending).
2. **`regime_stability` → WGI Political Stability** and **`inequality_gini` → SWIID** as direct
   numeric anchors at the initial state, with skill-vs-base-rate scoring over a historical window.
3. **`at_war`/`conflict_level` → UCDP/PRIO** as the validation target: backtest GIM's conflict
   onset against UCDP 1990–2023 and report skill vs the empirical base rate (the geopolitics
   analogue of the climate backtest).
4. **`sanction_propensity` → GSDB**; **`social_tension` → Mass Mobilization / ACLED.**

## Implemented: `military_power` → CINC (F3, step)

`gim/capability.py` computes a **CINC-style capability share** (Correlates of War methodology) from
the components GIM tracks — total population, energy consumption, GDP (industrial proxy), and
**SIPRI military expenditure** (populated at world build from `data/external/sipri_milex_2023.csv`
since v18.1.0, `MILEX_CINC_COMPONENT=True`, [F3+]). Both configurations validated
(`tests/test_capability.py`):

| | 3-proxy (flag off) | 4-component headline (v18.1.0) | Published CINC ~2016 |
|---|---|---|---|
| United States | 0.147 | **0.204** | ~0.14 |
| China | 0.205 | 0.185 | ~0.22 |
| India | 0.096 | 0.080 | ~0.08 |
| Russia | 0.030 | 0.034 | ~0.04 |
| Japan | 0.027 | 0.025 | ~0.03 |

The 3-proxy configuration reproduces the published COW ranking (China > US > India). The headline
4-component index intentionally departs from it — the milex share (US ≈ 37% of world) outweighs the
steel-and-personnel-era COW mix; rationale: the proxy fits milex levels (r≈0.76 cross-section) but
is anti-correlated with 2021–24 militarization dynamics (share-change corr −0.115; see
`docs/MILEX_GROUNDING_ANALYSIS.md`). `ground_military_power(world)` sets
`technology.military_power` to the capability share (rescaled to mean ~1) and is **auto-wired at
world build** since the E2.4 re-anchor (`GROUND_MILITARY_POWER=True`); golden backtest unaffected
(military_power is conflict-gated), conflict backtest AUC 0.739 / BSS +0.123.

## Honest caveat

These layers will **never** reach AR6/PWT-grade identifiability — conflict and unrest are
intrinsically lower-signal than physical climate. The realistic bar is **skill vs base-rate /
naive** (does GIM beat "predict the historical average conflict rate"?), not point precision —
consistent with the F1 objectivity layer. Grounding the *inputs* (CINC, WGI, SWIID, UCDP) is
achievable now; *predictive* validation is a longer, honestly-bounded effort.
