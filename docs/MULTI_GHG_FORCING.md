# GIM17 Multi-GHG Non-CO2 Forcing (P4-B)

The non-CO2 effective radiative forcing (ERF) was a single lumped term. P4-B keeps that
calibrated **net** path unchanged by default but decomposes it into AR6/IGCC-anchored
components, each exposed as a perturbable scenario/policy lever.

## Components (`gim/core/forcing.py`)

Reference ERF (W/m2, ~2019 vs 1750), from IPCC AR6 WG1 Ch.7 (Forster et al. 2021) and
the Indicators of Global Climate Change update (Forster et al. 2023):

| Component | ERF | Note |
|---|---|---|
| CH4 | +0.55 | methane (direct) |
| N2O | +0.21 | nitrous oxide |
| halogen | +0.41 | halocarbons / ODS + replacements |
| O3 | +0.47 | tropospheric ozone |
| aerosol | -1.06 | net aerosol-radiation + aerosol-cloud (cooling) |
| minor | -0.01 | contrails + land-use albedo + BC-on-snow + strat. H2O |
| **net** | **+0.57** | ~AR6 2019 non-CO2 anthropogenic |

## Behaviour

- `nonco2_forcing(params, year)` with no scales returns **exactly** the lumped calibrated
  path (`F_NONCO2_DEFAULT + F_NONCO2_TREND·(year−base)`), so the climate calibration and
  the 2015-2023 backtest golden values are untouched.
- `nonco2_forcing(params, year, {"CH4": 0.5})` halves methane's contribution: the net
  shifts by `(0.5−1)·0.55 = −0.275 W/m2`.
- `nonco2_forcing_components(...)` rescales the reference vector to sum to the net for the
  year - an auditable, sign-correct attribution (GHGs warm, aerosols cool).
- `set_nonco2_component_scales(world, {...})` attaches levers to a world; the climate step
  reads them automatically.

Examples of the policy hook this enables: methane mitigation (`CH4 < 1`), aerosol clean-up
"unmasking" (`aerosol < 1` raises the net -> more warming), halocarbon phase-out.

## Validation

`tests/test_forcing.py` (11 tests): reference net in the AR6 range, physical signs,
default == lumped path, components sum to net, methane/aerosol lever direction and
magnitude, unknown-component guard, and an end-to-end run where a strong methane cut
yields a cooler 8-year trajectory than baseline. Golden backtest unchanged
(1.026 / 1.606 / 0.134).

## Follow-up (P4-B2)

Adopt the full AR6 *net* path (~+0.57 at 2019, ~0.11 W/m2 above the current lumped value)
with per-component annual time series. This shifts the climate trajectory and so must be
done jointly with a re-run of the T1.3b climate recalibration - deliberately deferred.
