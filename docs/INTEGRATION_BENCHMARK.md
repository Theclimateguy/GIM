# GIM18 Integration Benchmark — making the "integrated beats sectoral" claim computational

**Question.** The paper claims an *integrated* world model adds value over *sectoral* models
(climate-economy IAMs, energy-system models, crop models). Without a demonstration that is
a declaration, not a result. This benchmark turns it into a controlled computation.

**Design (literature-anchored, NOT internal ablation).** For each of three shocks we take a
**published conclusion from a named sectoral model**, feed GIM the *same exogenous shock*, and
show GIM (a) reproduces the sectoral first-order effect where they overlap, and (b) surfaces a
**cross-sector consequence the sectoral model cannot represent by construction**. The unit of
comparison is the *decision-relevant conclusion*, not a headline number — GIM is not claimed to
compute emissions/welfare "better" than DICE; it is claimed to see a consequence DICE is blind to.

Reproduce:

```bash
python3 -m scripts.integration_benchmark.gim_benchmark          # -> results/integration_benchmark/<ts>/benchmark.json
python3 -m scripts.integration_benchmark.make_benchmark_figures # -> paper/figures/fig6..fig9 (.pdf/.png)
```

Runs are deterministic (`enable_extreme_events=False`, `simple_rule_based_policy`, full 57-agent
world, horizon 10) so the *only* difference between the baseline and shock arms is the injected
shock. Each scenario also reports a **dose-response sweep**: the sectoral model's slope on the
cross-sector axis is *structurally zero*; GIM's is measured and non-zero.

---

## Three honesty notes (load-bearing — stated in every figure)

These came out of the engine audit and are part of the result, not footnotes to hide.

**N1 — Resource *prices* saturate in forward simulation.** GIM's global resource-price subsystem
rails to its caps within one simulated year (energy → 5.0 ceiling, food → 0.3 floor; supply/demand
clearing on the 2023 initial state). Price-mediated transmission is therefore *not usable* in
forward sim. Each shock is injected at its **first cross-sector transmission variable** — exactly
the channel the sectoral model lacks — rather than at the market price:
  * carbon tax → a CPI wedge (the tax's pass-through to consumer energy prices);
  * oil shock → the importers' fiscal/reserve burden (the higher import bill);
  * crop shock → the food-supply gap (cover-days) of vulnerable importers.

**N2 — `conflict_escalation_pressure` is geopolitical, not the domestic food chain.** In GIM that
metric aggregates inter-state hawkishness / force posture / mistrust. A domestic food shock does
**not** move it (verified: Δ ≈ +0.0002). Scenario C's honest endpoint is *domestic*
(`food_affordability_stress`, `protest_pressure`, `regime_fragility`).

**N3 — Effect sizes differ, and we report them honestly.** The sovereign-debt cascade (B) is
strong but threshold-shaped; the food→protest channel (C) is convex/accelerating but starts small;
the economy-wide carbon→tension link (A) is weak-but-robust. GIM's value is in *quantifying* these
spillovers and their shape — not in claiming each is large.

---

## Scenario A — Carbon tax \$50/tCO2  (`fig6_integration_carbon`)

| | |
|---|---|
| **Sectoral anchor** | Nordhaus, **DICE-2016R**, *Revisiting the social cost of carbon*, PNAS 114(7):1518–1523 (2017). Optimal carbon price ≈ \$31/tCO2 (2015) rising ~3%/yr (≈\$47 by 2020); welfare-optimal, emissions decline. **No** unemployment, inflation, or political economy. Our \$50/t sits inside DICE's own optimal range — no strawman. |
| **Real-world reversals** | France 2018 (carbon/fuel-tax rise scrapped after the *gilets jaunes*; frozen at the 2018 level since); Australia 2014 (carbon price repealed after ~2 years). |
| **GIM injection** | emission lever (`CARBON_PRICE_USD_PER_TCO2=50`, `ENERGY_PRICE_SUBSTITUTION=True`) + CPI wedge = `CARBON_PRICE_PASSTHROUGH·$50 · energy-CPI-share` ≈ 0.15·0.08 ≈ **1.2 pp/yr** during phase-in (the model's *own* pass-through number). |
| **Result (10y)** | emissions **−6.3%** (GIM *agrees* with DICE's direction) **and** social tension **+6.5×10⁻³**, trust **−7.9×10⁻³** (the cost DICE omits). Dose-response: tension rises monotonically with the carbon price; DICE's slope on that axis is 0. |
| **Reading** | DICE's "optimal tax" conclusion is *conditional on the tax surviving*. GIM models the economy→society→policy path that decides whether it does. |

## Scenario B — Oil price shock  (`fig7_integration_oil`)

| | |
|---|---|
| **Sectoral anchor** | Energy-system / oil-market models (e.g. **MESSAGEix**): supply gap → price up → demand adjustment, bounded within the energy sector. Cross-sector evidence: **IMF GFSR Oct-2025 ch.3** "Global Shocks, Local Markets: EM Sovereign Debt"; **BU GDP Center 2026** "Rising oil prices and developing-country debt". |
| **Real-world case** | Sri Lanka 2022: import-bill + reserve drain (\$1.9B reserves vs \$6B external debt service) → sovereign default. |
| **GIM injection** | a per-year oil-import burden (% of GDP), financed by drawing reserves + new debt over a 4-year window, applied to all net importers — GIM's *own* debt/rate thresholds decide which fiscally-fragile ones tip (no cherry-picking; the derived risk ratios are recomputed each step, see N1). Two reference points: **realistic** −20% supply (elasticity ~0.3 ⇒ ~+60% price ⇒ ~3.3% of GDP/yr) and **severe** ~15% of GDP/yr (a severe multi-year oil crisis on the most import-dependent economies — cf. the worst historical oil episodes / EM import-bill blowouts). |
| **Result (10y)** | **Severe headline:** importer mean debt-crisis-years **×2.7 (+0.50)**, **+4 importers** tipped into sovereign crisis (baseline has 2 of 38). **Realistic point:** marginal (+1 importer, +0.026). Dose-response is **threshold-stepped** (flat to ~3% GDP, +1 from ~6%, +3 at 15%, +5 at 20%). The energy model produces zero sovereign crises at *every* magnitude. |
| **Reading** | The realistic shock is marginal on average but already tips the most fragile importer; a severe shock produces a clear cascade. The contrast is both qualitative (GIM has a slope; the energy model is flat) and, at severe magnitude, quantitatively large. |

## Scenario C — Severe crop yield shock (warming-driven, −50% regional)  (`fig8_integration_crop`)

| | |
|---|---|
| **Sectoral anchor** | **AgMIP / IPCC AR6** crop-yield assessment: yield decline → food-security / hunger index (the endpoint). No political-instability channel. |
| **Cross-sector evidence** | Lagi, Bertrand & Bar-Yam, *The Food Crises and Political Instability in North Africa and the Middle East*, NECSI, **arXiv:1108.2455** (2011): *"food riots occur above a threshold of the FAO price index of 210 (p < 10⁻⁷)"*; timing coincides with the Arab Spring 2011. |
| **GIM injection** | cut food production + carried reserves of the most income-vulnerable countries (a global yield hit leaves global surplus — the effect is **distributional**); the resulting cover-days gap is computed endogenously. Severe headline: a **50% regional yield loss** (AR6/AgMIP worst-case for vulnerable tropical staples under sustained warming). |
| **Result (10y, vulnerable subset)** | at the severe −50% yield loss: food-affordability stress **+0.090**, protest pressure **+0.014**, regime fragility **+0.002** (attenuating along the chain). Dose-response is **convex/accelerating** (food-stress Δ 0.004→0.21 as the cut goes 10%→70%) — the nonlinear "crossing into high impact" Lagi describes. AgMIP's protest slope is 0. |
| **Reading** | AgMIP stops at hunger; GIM carries the same yield loss into domestic affordability and protest pressure in the vulnerable importers, with realistic convex escalation (not interstate conflict — see N2). |

---

## The thesis figure (`fig9_integration_summary`)

Three cross-sector channels on one panel, each normalized to its own peak. GIM has a positive,
quantified slope (smooth for A, threshold for B, convex for C); every sectoral model is a flat line
at zero on its cross-sector axis. That gap — not any single number — is the integration dividend.

## Limitations (honest)

* The injection magnitudes (CPI wedge, fiscal burden, yield cut) are literature-calibrated *inputs*,
  not endogenous to GIM; GIM supplies the **downstream dynamics**, which is the claim under test.
* Because of N1, this benchmark does **not** demonstrate an endogenous *market-price* cascade
  (oil price → everything); it demonstrates the cross-sector *transmission* once the shock reaches
  the channel a sectoral model lacks. A future engine fix to the resource-price saturation would let
  the price channel carry the shock end-to-end.
* Effect sizes are aggregate/subset means over a 57-agent world; country-level tails are larger.
* No endogenous policy-reversal mechanism: Scenario A reports reversal *risk* (tension/trust
  trajectory), not an automatic repeal.
