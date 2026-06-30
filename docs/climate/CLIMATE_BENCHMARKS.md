# Climate-benchmark standing (E3.4 / THE-45)

The three remaining climate-benchmark questions, closed by evidence-based decisions rather than
changes that would degrade the validated fit. Each decision is the honest one: where the data
supports a change we make it; where forcing a benchmark number would worsen the historical fit, we
retain the calibrated value and document why.

## A. Non-CO₂ greenhouse-gas forcing — retain the calibrated net (do not force the AR6 central)

The headline non-CO₂ effective radiative forcing is the **calibrated lumped net** (~0.45 W/m² at
2019), decomposed into AR6/IGCC-anchored components (CH₄, N₂O, halocarbons, ozone, aerosol) that are
available as **per-gas scenario levers** (e.g. a 50% methane-mitigation run). The AR6 *central* net
is higher (~0.57 W/m², +0.11).

**Decision: keep the calibrated net as the headline default.** Adopting the AR6 central was measured
and it **worsens the validated temperature fit**: with everything else at the AR6-anchored values
(climate sensitivity 3.0), raising non-CO₂ to ~0.57 pushes the 1990–2023 temperature RMSE from 0.135
to 0.146 and the warm bias from +0.016 to +0.050 °C — the model over-warms. The calibrated net is
precisely the value that reconciles the AR6 climate sensitivity with the *observed* warming; the
~0.11 W/m² difference sits well inside AR6's own non-CO₂ forcing uncertainty. Matching the observed
warming is the validation target, so we retain the calibrated net and expose the AR6 components for
scenario use. This is a deliberate, documented choice, not an omission.

## B. Carbon-cycle feedbacks — ensemble-only, not in the deterministic headline

Land-use CO₂ is in the headline (E2.1). The temperature-driven carbon-cycle feedbacks — permafrost/
peat (smooth) and abrupt release (tipping) — are **switchable and off in the headline by design**.

**Decision: keep them ensemble-only.** A deterministic permafrost feedback explodes the long-horizon
SCC (a marginal-pulse experiment runs the feedback to ~$1657 at 200 yr) and the EPA/RFF central
explicitly excludes strong permafrost feedback. These are deep-uncertainty terms; the honest place
for them is the sampled ensemble / tail, where they express uncertainty without mis-stating the
deterministic headline. (See `docs/CARBON_CYCLE_FEEDBACK.md`.)

## C. Social cost of carbon — reported honestly, above the EPA/RFF central by design

Headline SCC (objective economic core: nested-CES production + price/balance closure + SSP-anchored
forward growth + CINC-grounded capabilities):

| discounting | 200-yr SCC |
|---|---|
| modern RFF-SP/EPA Ramsey (near-zero ρ, η≈1.24) | **~$95 / tCO₂** |
| Nordhaus-native (ρ=1.5%, η=1.45) | ~$42 / tCO₂ |

> **17.3.0 update.** The development-structured recalibration (TFP conditional convergence +
> development-dependent decarbonisation) gives a faster, empirically-calibrated forward growth path,
> which discounts future damages more and lowers the SCC: modern Ramsey ~$140 → **~$95**, range
> ~$140–380 → **~$95–280**, Nordhaus ~$43 → ~$42. Under DICE-2016R2's own lower damages the
> marginal-pulse engine now returns **~$20** (was ~$31) — i.e. DICE *underestimates* damages relative
> to GIM's empirically-calibrated function and faster growth.

**Decision: report the value; document the sensitivity; do not tune to a target.** GIM's modern
SCC (~$95) lands within the broad modern consensus range, below the EPA-2023 ($190) /
RFF-SP ($185) central. Crucially, the SCC is **genuinely sensitive to the forward economic
structure** — it ranges ~$95–280 across the objective-core variants (production form, price
closure, SSP-anchored growth), which is the well-known growth/discounting sensitivity of the SCC
amplified by GIM's integrated structure. Rather than tune any single variant to hit $190 (which
would mean detuning the cross-validated damages, 5.4%/3 °C in T1.4), we report the headline value and
state the sensitivity band. The growth-effect damage channel and carbon-cycle feedbacks add further
upside in the ensemble/SCC distribution. This sensitivity is itself a result worth reporting in the
paper. (See `docs/WELFARE_SCC.md`, `docs/BENCHMARK_ALIGNMENT.md`.)

## Summary

| Item | Decision | Rationale |
|---|---|---|
| AR6 net non-CO₂ | retain calibrated net (headline); AR6 components as scenario levers | AR6 central over-warms the validated 1990–2023 record; gap within AR6 uncertainty |
| Carbon-cycle feedbacks | ensemble-only | deterministic feedback explodes the SCC; deep uncertainty belongs in the tail |
| Social cost of carbon | report ~$95 (modern near-zero-ρ Ramsey; 17.3.0), within the broad modern range; document the ~$95–280 sensitivity | report the value and its growth/discounting sensitivity rather than detune to hit a target |
