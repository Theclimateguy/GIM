# Growth foundations (E4.2)

Status: **mechanism calibrated, switchable, OFF by default** — the golden 2015–2023 backtest is
bit-identical to the pre-E4.2 baseline. Two channels: a Jones semi-endogenous R&D-**stock** TFP-growth
form (`RD_STOCK_GROWTH`, default off) and SSP1–5 forward-drift presets (`SSP_SCENARIO`, default `SSP2`
= the validated forward drift). THE-61. This closes ROADMAP item 6 ("stronger growth foundations") at
the **calibrated-mechanism** level; headline activation of the R&D-stock core remains a deliberate
future re-anchor decision (it is dormant in the historical window, so it does not touch the golden).

## Why

The endogenous TFP block (`gim/core/metrics.py::update_tfp_endogenous`) drove R&D→growth off the raw
**flow** R&D share (`TFP_RD_SHARE_SENS · rd_spending/GDP`) and used a single forward TFP drift. Two
gaps versus the growth literature:

1. **Flow, not stock.** Growth theory links productivity to the accumulated **knowledge stock**, not
   the current-year R&D flow, and with **diminishing returns** to that stock (the semi-endogenous /
   Jones 1995 form; Bloom et al. 2020 document that ideas are "getting harder to find").
2. **One forward scenario.** Long-horizon projections rode a single SSP2 drift, with no way to select
   the other SSP marker pathways.

E4.2 closes both with switchable, calibrated, golden-safe channels.

## Channel 1 — R&D knowledge stock (Jones semi-endogenous)

### Mechanism

When `RD_STOCK_GROWTH` is on, the R&D term in TFP growth becomes

```
S_t            = (1 − δ_R)·S_{t-1} + rd_spending_t           (perpetual inventory of R&D)
tfp_growth_RD  = TFP_RD_STOCK_SENS · (S_t / GDP_t)^φ · spillover            (φ < 1)
```

instead of the flow form `TFP_RD_SHARE_SENS · (rd_spending/GDP) · spillover`. `S/GDP` is the
**R&D-stock intensity**; in a balanced state `S/GDP = (rd_spending/GDP)/δ_R`, so the stock intensity
is the flow ratio scaled by `1/δ_R`. `φ < 1` encodes diminishing returns to the knowledge stock. Zero
R&D → zero contribution, exactly like the flow form. The stock block (and the `_rd_stock` attribute)
is skipped when the channel is off, so the default run is byte-for-byte the golden.

### Calibration

Estimated from the World Bank **47-country panel** (2000–2023) via
`calibration/calibrate_growth_foundations.py` (output: `growth_foundations_calibration.json`). The
estimand is a cross-country growth regression — average TFP-proxy growth on R&D-stock intensity, net
of a common drift (the constant ↔ the model's `TFP_DRIFT`) and catch-up convergence (initial income
↔ the model's diffusion channel):

```
g_i = a + SENS·X_i^φ + b·ln(GDPpc_0,i) + e_i        X_i = (mean R&D/GDP)/δ_R
```

WB indicators: `GB.XPD.RSDV.GD.ZS` (R&D %GDP), `NY.GDP.PCAP.KD.ZG` (GDP-pc growth, the TFP proxy),
`NY.GDP.PCAP.KD` (GDP-pc level, the convergence control).

| Spec | SENS | SE | R² | notes |
|---|---|---|---|---|
| A. linear, **no convergence** | **−0.055** | 0.031 | 0.06 | R&D looks *negatively* tied to growth |
| B. linear + convergence (φ=1) | 0.073 | 0.033 | 0.46 | sign flips positive once catch-up is controlled |
| **C. power + convergence (φ=0.5)** | **0.058** | 0.020 | 0.50 | semi-endogenous shape; t≈2.85 |
| C′. unconstrained RSS min (φ=0.1) | 0.102 | 0.033 | 0.51 | boundary; ΔR²≈0.015 — not chosen |

Reading the ladder:

1. **The naive cross-section is misleading — the sign flips.** Without controlling for convergence,
   R&D intensity correlates **negatively** with growth (SENS −0.055), because frontier (rich) economies
   do the most R&D yet grow slowly. Conditional on catch-up convergence, R&D-stock intensity is a
   **significant positive** growth driver (SENS ≈ 0.058, SE 0.020). This is the same "the raw slope is
   a confound" lesson as the E4.1 money calibration (where country FE collapsed the slope ~5×).
2. **φ (the curvature) is weakly identified.** R² is nearly flat across the whole grid (0.46→0.51) and
   the unconstrained RSS minimum sits on the lower boundary — an artefact of a flat likelihood, not a
   real interior optimum. We therefore **fix φ = 0.5**, the standard semi-endogenous value (Jones 1995;
   Bloom et al. 2020 diminishing-returns evidence), which the data are consistent with (ΔR² from the
   boundary ≈ 0.015).
3. **The magnitude validates against the R&D literature.** The implied marginal social return to R&D
   at the linear form is **≈ 0.49**, squarely inside the empirical social-return-to-R&D range
   (~0.20–0.55; Jones–Williams 1998, Bloom et al. 2013).

**What the data set, and what they don't.** The panel pins the cross-country **elasticity** (φ) and
**validates** the channel (positive sign conditional on convergence, social return in range). It does
**not** set the model's SENS directly: the regression slope (0.058) is the R&D contribution relative to
a **zero-R&D** counterfactual (~1.8%/yr at the panel mean), whereas the model adds the R&D term *on top
of* `TFP_DRIFT`, which is calibrated low and already absorbs the average R&D effect through the validated
flow form. Using the regression slope would **double-count** the baseline. So the model's
`TFP_RD_STOCK_SENS` is **level-matched** to reproduce the validated flow-form mean R&D contribution at
the panel-mean intensity X̄:

```
SENS_stock · X̄^φ  =  SENS_flow · (X̄ · δ_R)      ⇒   SENS_stock = SENS_flow · δ_R · X̄^(1−φ)
                                                  = 0.30 · 0.15 · 0.098^0.5  ≈  0.0141
```

So the channel is a **drop-in flow→stock functional upgrade** (diminishing returns to the knowledge
stock, shape from the data) that **preserves the validated growth level** — at X̄ the stock term is
≈ 0.44%/yr, matching the flow form's ≈ 0.45%. A country at 2× the mean intensity gets ≈ √2 × the
contribution (φ=0.5 diminishing returns). Headline activation that re-fits `TFP_DRIFT` jointly with
the stock form would be a separate, deliberate re-anchor decision.

**`δ_R = 0.15`** is a literature prior (R&D-capital perpetual-inventory studies, OECD/BLS). It only
rescales the intensity by a constant, so **φ is invariant to δ_R** (and the level-match formula carries
δ_R explicitly, so SENS_stock is consistent for any δ_R choice).

**Caveats (honesty bar, cf. `MONEY_PRICES.md`):**
- The outcome is **GDP-per-capita growth** (no clean global TFP series on the WB API). The model routes
  R&D through TFP, which then raises GDP via the CES core, so the reduced-form SENS is an upper-ish
  bound on the pure-TFP sensitivity; it transfers the cross-country R&D→growth **elasticity** (φ) and
  a level anchored at the sample-mean intensity, not a structural TFP residual.
- The model multiplies by a trade **spillover** (~1 + 0.3·trade); SENS is calibrated at spillover ≈ 1,
  so the model applies a modest additional amplification on top.
- **Coverage (47 of the model's 57 agents), broken down honestly:** the model carries 57 agents, but
  8 are outside the World Bank's country universe — 7 are synthetic "Rest of …" regional aggregates
  (no coherent country R&D series) and TWN is not WB-covered — so the WB panel maxes out at **49**. Of
  those, **2** drop for thin R&D coverage (BGD has 0 years of `GB.XPD.RSDV.GD.ZS`; NGA only 2, below
  the 8-year minimum), leaving **47**. This is a structural coverage limit, not a collection failure,
  and it does **not** bias the parameters: φ is fixed and SENS is level-matched, so the excluded
  countries would only refine the validation, not move `TFP_RD_STOCK_SENS` or φ. The frozen artifact
  records the full `coverage` block (universe, estimated, excluded-with-reasons). Fetches retry
  transient WB-API failures so the 47-country panel is reproducible. Maximal coverage (adding TWN from
  national statistics, BGD/NGA from UNESCO UIS) would mean mixing non-WB sources — deferred unless the
  channel is activated as headline.

## Channel 2 — SSP1–5 forward TFP-drift presets

`SSP_TFP_DRIFT_PRESETS[SSP_SCENARIO]` selects the post-2024 baseline TFP drift. The presets are
**grounded on the published SSP marker GDP-per-capita pathways** (Dellink et al. 2017 OECD ENV-Growth;
IIASA SSP database), not asserted:

1. Take the published 2100 global GDP-pc levels — SSP5 ≈ \$120k, SSP1 ≈ \$77k, SSP2 ≈ \$63k,
   SSP4 ≈ \$46k, SSP3 ≈ \$24k.
2. Back out the implied 2010–2100 per-capita growth; this reproduces the published **1.0%–2.8%**
   envelope (SSP3 0.98% … SSP5 2.80%).
3. Scale the **validated** SSP2 drift (0.018) by each scenario's growth **ratio to SSP2** (a
   balanced-growth approximation: TFP-drift ratios track per-capita-GDP-growth ratios).

| Scenario | implied GDP-pc growth | ratio to SSP2 | TFP drift |
|---|---|---|---|
| SSP5 fossil-fueled | 2.80%/yr | 1.355 | **0.024** |
| SSP1 sustainability | 2.29%/yr | 1.110 | **0.020** |
| **SSP2 middle (default)** | **2.07%/yr** | **1.000** | **0.018** |
| SSP4 inequality | 1.71%/yr | 0.828 | **0.015** |
| SSP3 regional rivalry | 0.98%/yr | 0.473 | **0.009** |

These are selectable forward **scenario** presets, not a headline change: `SSP_SCENARIO` defaults to
`SSP2` → 0.018, identical to the prior single forward drift.

## Golden safety

The 2015–2023 backtest is entirely in the historical window (`year ≤ SSP_FORWARD_FROM_YEAR`), so the
SSP presets never bind there, and `RD_STOCK_GROWTH = False` keeps the flow R&D form — the default run
is **bit-identical** to the pre-E4.2 golden (RMSE 0.590 / 1.146 / 0.135). The R&D-stock channel is
additionally dormant in the historical window: even activated, the 2015–2023 fit is unchanged (R&D
contributes through the forward projection, not the calibration window). Verified by
`tests/test_growth_foundations.py` (`test_default_golden_preserved`, `test_defaults_are_golden_safe`).

## Activating

```python
# R&D-stock Jones core (forward growth from the knowledge stock):
run_historical_backtest(params_override={"RD_STOCK_GROWTH": True})
# A different SSP forward scenario:
run_historical_backtest(params_override={"SSP_SCENARIO": "SSP1"})
```

Headline activation of `RD_STOCK_GROWTH` would be a deliberate re-anchor decision (like E4.1's): it
does not move the golden, but it changes long-horizon (post-2024) growth, so it should be taken
explicitly and recorded in `docs/RE_ANCHOR.md`. Until then the channel ships calibrated-but-off.

## Files

- `gim/core/metrics.py` — both channels in `update_tfp_endogenous`.
- `gim/core/calibration_params.py` — `RD_STOCK_GROWTH`, `TFP_RD_STOCK_SENS`/`_ELASTICITY`,
  `RD_STOCK_DEPRECIATION`, `SSP_SCENARIO`, `SSP_TFP_DRIFT_PRESETS`.
- `calibration/calibrate_growth_foundations.py` — the R&D-stock calibration; output
  `growth_foundations_calibration.json`.
- `tests/test_growth_foundations.py` — golden-safety + SSP ordering + R&D-stock behaviour.
