# GIM17 Economics — Honest Benchmark vs Industry Models

A pre-Phase-5 review of GIM's **economic engine** against current industry-standard
integrated-assessment and macro models. The aim is an honest placement, not a flattering
one: where GIM is genuinely competitive, where it is behind, and which directions to push.

## 1. What GIM's economics actually is

| Component | GIM implementation |
|---|---|
| Production | Cobb-Douglas + energy factor: `Y = TFP·tech·K^0.30·L^0.60·E^0.042` (α+β+γ = 0.942, mildly decreasing returns; a per-country `scale_factor` anchors the level to data) |
| Capital | Endogenous: `K' = (1−δ)K + s·Y`, δ=0.05, savings rate s≈0.24 modulated by stability/tension |
| Labour | `L = population` (no labour-supply elasticity); unemployment now endogenous (Okun) |
| TFP / growth | Endogenous: 1%/yr drift + R&D share + trade spillover + frontier diffusion, clamped ±5%/yr. **No large exogenous growth term** — long-run growth is mostly emergent |
| Damages | Level-effect quadratic `1 − 0.006·T²` (5.4%/3 °C; cross-validated, T1.4) |
| Money / finance | Sovereign debt, deficit, interest, **Taylor-rule** policy rate, **endogenous inflation** (Phillips + energy cost-push), debt-crisis dynamics with stock-flow identity (T1.1) |
| Trade | Reduced-form `net_exports` + bilateral trade deals; closed world (Σ net_exports ≈ 0) |
| Markets | **No general-equilibrium clearing**; resource prices are reduced-form adjustment rules |
| Expectations | Adaptive (anchored), not model-consistent / perfect-foresight |
| Solution | Recursive-dynamic **simulation** (step-by-step), not intertemporal optimization |
| Resolution | 57 country-agents, bilateral relations, geopolitics + culture layers |
| Uncertainty | N=500 ensembles, Morris/Sobol, history-matching/NROY, skill scoring, 2015–23 backtest |

**One-line DNA:** a recursive-dynamic, **non-equilibrium simulation** IAM with a
**macro-financial + geopolitical** layer and a neoclassical (Cobb-Douglas) supply core —
closest in solution method to **E3ME** (macro-econometric, demand-aware, no market clearing),
but with explicit sovereign finance and geopolitics that E3ME and the GE-class IAMs lack.

## 2. Industry model taxonomy (validated)

| Class | Examples | Solution | Markets | Expectations | Production |
|---|---|---|---|---|---|
| Welfare optimization | DICE, RICE, FUND, MERGE | Intertemporal optimization | implicit | perfect foresight | Cobb-Douglas, exog. TFP |
| General equilibrium | REMIND, WITCH, MESSAGE-MACRO, GEM-E3, GTAP/CGE | Optimization / recursive GE | **clear** | foresight / recursive | **nested CES** (KLE) |
| Partial equilibrium | GCAM, IMAGE, POLES | recursive simulation | energy/land only | myopic | technology-explicit |
| Macro-econometric | **E3ME**-FTT | recursive simulation | **no clearing** | adaptive/econometric | demand-led, evolutionary |
| Stock-flow / ABM | SFC (Godley-Lavoie), Eurace, Mark-0 | simulation | no clearing | behavioural | heterogeneous agents |
| **GIM17** | — | **recursive simulation** | **no clearing** | **adaptive** | **Cobb-Douglas + E** |

## 3. Benchmarks (quantitative, validated to sources)

**Forecast-accuracy bar (the realistic ceiling).** IMF WEO evaluation (Celasun et al. 2021;
Timmermann 2006): current/next-year real-GDP-growth forecasts are roughly unbiased with MAE
comparable to Consensus; **2-to-5-year-ahead forecasts are upward-biased and, in up to half of
countries, *less accurate than a naïve "recent-average-growth" forecast.*** Implication: no
credible model reliably beats naïve baselines at multi-year horizons — "industry-grade" means
**calibrated honesty about uncertainty**, not point precision. GIM already has the right tool
(P2-A skill scoring vs persistence/trend baselines); it should *report* GDP skill there.

**Structural parameters vs data.**

| Parameter | GIM | Industry / data | Verdict |
|---|---|---|---|
| Capital share α | 0.30 | PWT/Gollin 0.30–0.40 | ✅ in range |
| Labour share β | 0.60 | Gollin 0.65–0.80 | ⚠️ low (energy factor + non-CRS) |
| Depreciation δ | 0.05 | PWT 0.04–0.05 | ✅ |
| Savings rate | 0.24 | WDI world gross ~0.25 | ✅ |
| TFP growth (baseline) | ~1%/yr + endog. | DICE ~1.5%↓, SSP2 ~1.8%/yr | ⚠️ low/uncertain |
| Returns to scale | 0.942 | textbook/CES = 1.0 (CRS) | ⚠️ non-standard (scale_factor absorbs) |
| Damage @3 °C | 5.4% | DICE 2.1%, Howard-Sterner 7–8% | ✅ mid-envelope (T1.4) |
| Backtest GDP RMSE | 1.03 tn / 20 countries 2015–23 | (report as skill vs naïve) | report needed |

## 4. Honest scorecard

**Ahead of standard IAMs (genuine strengths):**
- Explicit **sovereign finance + monetary policy + endogenous inflation/unemployment** — DICE/RICE
  and most IAMs have *none* of this. Closer to E3ME/DSGE on the macro-financial side.
- **Geopolitics + culture + 57-country bilateral** resolution — essentially unique among IAMs.
- **Uncertainty quantification + validation** (ensembles, Sobol, history-matching, backtest, skill
  scoring) — competitive with the best (RFF-SP class), ahead of DICE.
- **Stock-flow-consistent accounting** (debt identity, resource ledger, trade closure, enforceable).

**Behind the GE-class IAMs (the real gaps — the "several directions"):**
1. **No general-equilibrium market clearing.** Prices are reduced-form; no factor-market or
   goods-market equilibrium. REMIND/WITCH/GEM-E3/GTAP clear all markets. (Caveat: E3ME deliberately
   doesn't either — this is a *paradigm choice*, but it must be made and defended explicitly.)
2. **Unit-elasticity production (Cobb-Douglas).** Cannot represent **energy-capital substitution**
   under carbon prices — the central climate-economy mechanism. Industry standard is **nested CES**
   with calibrated substitution elasticities.
3. **Shallow private finance.** Sovereign side is good; no banks, money stock, credit creation, or
   financial accelerator. SFC and DSGE-macro-finance go further.
4. **Adaptive (not forward-looking) expectations / no intertemporal optimization.** DICE/REMIND
   optimize with foresight; GIM is myopic-recursive (defensible as ABM-like, but a real difference).
5. **Reduced-form, weakly-identified endogenous growth.** TFP drift/R&D/spillover/diffusion are not
   separately identified over the 8-yr panel (confirmed by P1-D sensitivity).
6. **Reduced-form trade.** `net_exports` closure, no bilateral Armington elasticities (vs GTAP).

## 5. Recommended directions (parallel tracks for Phase 5+)

- **D1 — Production: nested CES (KLEM). [scaffold delivered — F2.1/THE-36]** Switchable nested KLE
  core in `gim/core/economy.py` (`NESTED_CES`, `CES_SIGMA_KE`): inner CES on (capital, energy) with
  σ_KE≈0.4, outer Cobb-Douglas vs labour; reduces **exactly** to Cobb-Douglas at σ_KE=1 (verified:
  golden bit-identical at σ=1). Default off (Cobb-Douglas) → golden preserved; σ=0.4 shifts the path
  materially (energy-capital complements) and is activated at the economics re-anchor. Prior
  `CES_SIGMA_KE` ~ triangular 0.4 [0.2,0.6] (van der Werf 2008; Koetse 2008). Highest-leverage for
  climate-policy realism; makes carbon-price responses meaningful.
  **Phase-2a finding (THE-36, why it stays OFF):** the F2.1 scaffold swaps only the *output
  aggregator*; it does not yet derive cost-minimizing **energy demand** from the CES, so emissions
  (∝ output) are disrupted at meaningful σ without delivering the carbon-price→energy-substitution
  channel. Re-fit grid: σ≈0.9 reproduces the golden (GDP 0.89 / CO₂ 1.64) but gives weak
  substitution; σ≈0.4 holds GDP-ish but breaks CO₂ (~6.9), and `EMISSIONS_SCALE` does not fix it
  (lowering it worsens CO₂). The real D1 = couple CES factor demands (energy) to the emissions/
  resource system, then recalibrate — a focused rework, not a parameter re-fit. Nested-CES stays off.
- **D2 — Partial market clearing. [energy/resource delivered — F2.2/THE-37]** Switchable
  `MARKET_CLEARING` in `gim/core/resources.py`: within-period clearing price for the resource
  (energy/food/metals) markets via a constant-elasticity demand (`p* = p·(demand/supply)^(1/ε)`,
  `MARKET_DEMAND_ELASTICITY≈0.4`), replacing the default sluggish tâtonnement (default off →
  golden bit-identical). Capital-market clearing (investment=savings via the rate) is the remaining
  piece. Bridges toward the GE class for energy without a full CGE; the non-equilibrium default is
  the deliberate, defended (E3ME) stance.
- **D3 — Stock-flow-consistent private finance. [SFC-lite delivered — F2.3/THE-38]**
  `gim/core/private_finance.py` (`SFC_FINANCE`, default off): a private-credit stock with an SFC
  flow (ΔDebt = new credit − repayment) and a Bernanke-Gertler **financial accelerator** —
  over-leverage damps credit appetite and adds a borrowing-rate premium read by
  `compute_effective_interest_rate`. Runtime-attribute state (no CSV/hash change); golden
  bit-identical at default. Remaining: explicit bank balance sheets + money stock (deposits as the
  mirror liability) for full SFC closure.
- **D4 — Growth foundations + SSP anchoring. [calibrated — E4.2/THE-61]** Now data-calibrated: the
  R&D→growth channel is a Jones semi-endogenous **R&D-stock** form (SENS level-matched to the validated
  flow form, elasticity φ=0.5 from the World Bank 47-country panel), and the SSP1–5 forward TFP-drift
  presets are grounded on the published SSP marker GDP-per-capita pathways (reproducing the 1.0–2.8%
  growth envelope). Both switchable, off by default (golden-safe). See `docs/GROWTH_FOUNDATIONS.md`.
  (Earlier scaffold: F2.4/THE-39 — SSP TFP-drift anchors + `scripts/report_gdp_skill.py`, GDP
  skill-vs-naive **+0.09**.)
- **D5 — Expectations. [near-rational operator — E4.3/THE-62]** Beyond the `EXPECTATIONS_FORESIGHT`
  backward proxy (F2.5/THE-40), a near-rational (model-consistent, **level-1**) operator now exists
  (`gim/core/expectations.py`): agents forecast by running an H-step event-frozen projection of the
  model itself (reusing `step_world` under a recursion guard); both the investment and Phillips
  inflation-anchor sites read it. Switchable, off by default. The recursive/adaptive default remains
  the **defended** stance (no unified theory of second best — Pollitt-Mercure 2021; demand-led
  non-equilibrium models argue full foresight is unrealistic), and the operator is a *contained,
  additive* change, not an equilibrium rewrite. See `docs/EXPECTATIONS.md`.
- **D6 — DICE reproduction (THE-16, the keystone check). [DONE — reproduced.]** GIM's independent
  marginal-pulse SCC engine recovers Nordhaus's DICE-2016R ~\$31/tCO₂ when fed DICE's damage
  coefficient (a₂=0.00236) and discounting (η=1.45, ρ=1.5%, already GIM defaults) at a DICE-comparable
  multi-century horizon: **\$29 (100 y) → \$32–33 (200–300 y)**. So the valuation core is sound, and
  GIM's higher *headline* SCC is attributable to its higher (literature-based, ~2.5× DICE) damage
  function, not the engine. Reproducible via `scripts/run_d6_dice_scc.py`; see
  `docs/climate/WELFARE_SCC.md`.

## 6. Self-critique of this benchmark

- This is a **structural/parametric** comparison, not a head-to-head output run. The decisive
  numeric test, D6 (reproduce DICE's SCC), is **now done** — GIM's SCC engine recovers DICE-2016R's
  ~\$31/tCO₂ under DICE's inputs (see D6 above), so "competitive economics" is no longer only a
  structural claim on the SCC axis. A full head-to-head on output paths (welfare-optimal mitigation)
  remains future work.
- "Behind the GE class" assumes the GE paradigm is the target. There is **no unified theory of
  second best** (Pollitt-Mercure; IOP 2021 review), and demand-led non-equilibrium models (E3ME)
  argue market clearing is *unrealistic*. So D1/D2 should be pursued as *options to evaluate*, not
  foregone conclusions — GIM's non-equilibrium stance is a legitimate research position if defended.
- Several parameter "⚠️" flags (β low, RTS 0.942) are partly absorbed by the `scale_factor` and may
  not bias dynamics; they need a dedicated identification check before being treated as errors.
