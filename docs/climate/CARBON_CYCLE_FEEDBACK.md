# GIM18 Carbon-Cycle Completion: Land-Use CO₂ + Feedbacks (E2 / THE-31)

Closes the carbon-cycle gaps before the SCC re-anchor (sequencing: cycle is upstream of the SCC
denominator). All channels are **switchable and default-OFF**, so the golden backtest stays
bit-identical (1.026 / 1.606 / 0.134); they ride the ensemble/SCC as sampled uncertainty and are
turned on for headline runs only at the E2.4 re-anchor.

## E2.1 — Land-use-change (LUC) CO₂ source

`LAND_USE_CO2_GTCO2_YR` (default 0.0) adds a global LUC flux to `total_emissions` in
`update_global_climate` (EQ-CLI-002 pools). Anchored to Global Carbon Project net LUC
(~4–5 GtCO₂/yr over 1990–2023, declining). Prior: triangular, mode 4.5, [3.0, 6.0].

**Double-count caveat.** Today `EMISSIONS_SCALE` (0.9755) is calibrated to reproduce observed CO₂
*including* the LUC contribution implicitly. Enabling explicit LUC therefore requires re-deriving
`EMISSIONS_SCALE` downward in the same step — so LUC is turned on **with the E2.4 re-anchor**, not
standalone. Direction check (8-yr window, LUC=5): warming ↑, CO₂ nudges up against the known
low-bias / negative CO₂ skill (F1) — the expected sign.

## E2.2 — Smooth carbon-cycle feedback (permafrost / peat)

`CARBON_CYCLE_FEEDBACK` (default False), temperature-gated:

```
dT  = max(0, temperature_global − CARBON_FEEDBACK_T_REF)   # model temp is anomaly above PI
CO₂ flux  += CARBON_FEEDBACK_CO2_GTCO2_PER_C · dT           # into the pools this step
f_total   += CARBON_FEEDBACK_CH4_WM2_PER_C · dT             # simplified steady-state CH₄ forcing
```

It is an **added** term on top of the AR6-anchored forced response (ECS 3.0 / TCR 1.79) — it does
not dilute the anchored ECS; it effectively inflates TCRE and the long-horizon tail. Priors
(AR6 WG1 Ch.5; Schuur 2015; McGuire 2018): permafrost CO₂ ~ triangular mode 1.5 GtCO₂/yr/°C,
[0, 5]; CH₄ forcing ~ mode 0.03 W/m²/°C, [0, 0.1] — wide, right-skewed, default 0.

CH₄ is modelled as a simplified steady-state forcing term (not a dynamic CH₄ pool); a dynamic pool
and the abrupt (fat-tailed) releases are E2.3, wired into the F5 criticality layer.

## E2.3 — Abrupt carbon-release tipping (delivered)

`CARBON_TIPPING` (default False). `gim.criticality.abrupt_carbon_release(rng, T, …)` draws a
temperature-gated, fat-tailed (Richardson-α, mean-1 power-law) annual pulse:

```
p     = clamp(CARBON_TIPPING_BASE_PROB + CARBON_TIPPING_TEMP_SENS·max(0, T − T_threshold), 0, 1)
pulse = CARBON_TIPPING_SCALE_GTCO2 · powerlaw_severity(α)   if rng < p else 0   # GtCO2-eq → pools
```

Peat-fire / abrupt permafrost-CH₄ / clathrate / forest-dieback. **Not** the smooth term, and it
explicitly **excludes the regrowing boreal-wildfire fraction** (cyclical, ~net-neutral on a decadal
scale). Stochastic → rides the ensemble as carbon-cycle tail risk; default-off keeps the
deterministic golden identical. The CH₄-vs-CO₂ distinction (short-lived high-GWP spike) is
approximated by the fast carbon pool (τ≈4.3 yr) pending a dynamic CH₄ box.
`tests/test_carbon_feedback.py` covers default-off + active-when-enabled + zero-hazard.

## E2.4 — Re-anchor (next)

Re-derive `EMISSIONS_SCALE` with LUC on; re-fit the discount/damage anchor so level-only SCC returns
to the EPA-2023/RFF-SP central (~$190 @ 2%/200y) from the current ~$273 overshoot; refresh golden
fixtures + artifact manifest; add a CI guard tracking SCC vs the EPA/RFF target.

## Validation

`tests/test_carbon_feedback.py`: defaults off; LUC raises CO₂ & warming; smooth feedback raises
warming & CO₂; explicit-off reproduces the baseline bit-for-bit. Golden unchanged; climate/forcing/
backtest suites green.
