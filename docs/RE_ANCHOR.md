# GIM17 Grand Re-Anchor (E2.4 / THE-35) — Phase 1

The headline activation of the validated channels, with the new golden. Decisions and the
findings the re-anchor surfaced (the valuable part).

## Headline configuration (new production defaults)

**Activated (ON):** land-use CO₂ (residual 0.6 GtCO₂/yr), SFC private finance, culture→social
links (pdi/uai/lto), and **CINC grounding of `military_power`** (`GROUND_MILITARY_POWER=True`,
Phase 2b) — applied at world build, replacing the curated CSV scalar with the observable
capability share (mean-rescaled).

**CINC side-effect (worth knowing):** because GIM integrates climate damage through the full
economy+geopolitics over 200 yr, the SCC is *sensitive to the capability grounding*. The
CINC-grounded headline SCC at modern 2%/200y is **~$197** (near the EPA/RFF central), vs ~$326 with
the arbitrary `military_power=1.0` scalar. The grounded value is the more defensible one. Test
bands widened to reflect this sensitivity (`test_benchmark_alignment`).

**Ensemble / tail only (OFF in the deterministic headline):** smooth carbon-cycle feedback,
abrupt carbon tipping, fat-tailed crisis severity, growth-effect damage upper. These carry deep
uncertainty and (the feedback especially) blow up the deterministic long-horizon SCC — they belong
in the ensemble, not the headline.

**Deferred (Phase 2):** nested-CES (`NESTED_CES=False`) — it materially reshapes the emissions/GDP
trajectory and needs its own energy-parameter recalibration (GAMMA_ENERGY/shares/scale_factor)
before activation; flipping it now would ship a broken golden.

**Unchanged:** `TFP_DRIFT=0.010` (SSP2 is a scenario preset, not the headline — SSP2 forward growth
conflicts with the 2015-2023 historical fit).

## New golden (re-anchored)

`1.0260 / 1.6058 / 0.1344` (GDP tn / CO₂ GtCO₂ / temp °C RMSE, 2015-2023) — within the prior
regression band; the activated headline channels are golden-safe over the 8-year window. Fixture
regenerated; suite green (bar 2 sandbox-only `test_ui_server` filesystem errors).

## Findings the re-anchor surfaced

1. **Raw GCB land-use (4.5 GtCO₂/yr) double-counts.** `EMISSIONS_SCALE=0.9755` already implicitly
   absorbs most historical LUC. The data-derived **residual** that closes the 1990-2023 CO₂ gap is
   **~0.6 GtCO₂/yr** (emission-driven climate backtest: ppm_rmse 9.76 → 2.30; the gross value
   overshoots to ppm_rmse ~54 and corrupts the spin-up).
2. **The smooth permafrost feedback can't sit in the deterministic headline.** At γ=1.5 it makes the
   200-yr SCC explode to **~$1657** (compounding carbon-cycle feedback under the marginal pulse).
   EPA/RFF central excludes strong permafrost feedback → feedback is ensemble/tail.
3. **GIM's headline SCC is legitimately above EPA/RFF.** At modern 2%/200y it is **~$326**, above the
   EPA-2023/RFF-SP central (~$190), because GIM's damage function is higher (5.4%/3°C, cross-validated
   T1.4, ~2.5× DICE) and land-use adds long-horizon CO₂. We **report** this rather than detune
   validated damages to force $190; the pre-Phase-4 "$191 ≈ EPA" was a coincidence.
4. **SSP2 forward growth conflicts with the historical backtest** — kept `TFP_DRIFT=0.010` for the
   headline; SSP2 (0.018) remains a scenario preset (`ssp_growth_preset`).

## Remaining

- **Phase 2 — nested-CES recalibration** (THE-36): joint re-fit of the energy parameters under the
  KLE core, then activate.
- **CINC headline wiring** (optional): make `ground_military_power` a build-time default behind a flag.
- **Ensemble/SCC distribution** should sample the tail channels (feedback, tipping, severity,
  growth-upper) so the headline + uncertainty band together tell the honest story.
