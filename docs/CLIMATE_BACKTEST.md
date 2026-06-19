# GIM17 Long-Window Climate Backtest (T1.3)

The coupled economic backtest runs only 2015-2023 - too short to constrain the
climate-response parameters (equilibrium climate sensitivity, ocean heat
capacities). T1.3 adds an observational window long enough to identify them.

## Data (`scripts/build_climate_observations.py`)

All series are primary-source, fetched June 2026:

| Series | Source | File |
|---|---|---|
| Fossil+cement CO2 emissions, 1750-2024 | Global Carbon Budget via Our World in Data (`OWID_WRL`) | `data/global_co2_emissions_owid.csv` |
| Atmospheric CO2, ppm, 1990-2023 | NOAA GML global annual mean (`co2_annmean_gl.txt`) | fixture |
| Temperature anomaly, 1990-2023 | HadCRUT.5.1.0.0, rebased to 1850-1900 | fixture |

The temperature rebasing offset (`0.3573608687647059`) is fixed so the 2015-2023
values reproduce the legacy economic-backtest fixture **bit-for-bit** (guarded by a
test) - the same series and convention, extended back to 1990. Cumulative emissions
1750-2023 total ~1810 GtCO2 (~494 GtC), matching the GCB headline.

## Method (`gim/climate_backtest.py`)

The backtest reuses the **exact** production climate physics
(`gim.core.climate.update_global_climate`): the 4-pool IPCC-AR6 impulse-response
carbon cycle and the Geoffroy two-layer energy balance. The model is run
free-running from the **pre-industrial equilibrium in 1750** (pre-industrial CO2
stock, empty pools, zero anomaly) and driven forward by observed emissions, so by
1990 the carbon pools and surface/ocean temperatures reflect the real emission
history rather than an arbitrary initial guess. Only 1990-2023 is scored.

Two modes:

- **emission** - the carbon cycle produces CO2 from emissions; tests the full
  emissions -> concentration -> forcing -> temperature chain.
- **concentration** - over the scored window the EBM is forced by *observed* CO2
  (`prescribed_co2_gt`), isolating the energy-balance response so ECS can be
  identified independently of carbon-cycle error. This is the set-up used by
  observational ECS studies (Otto et al. 2013; Lewis & Curry 2018).

## Findings

**1. Carbon cycle is ~10 ppm low (emission mode).** Driven by fossil+cement CO2
alone, predicted atmospheric CO2 sits a near-constant ~10 ppm below observed across
1990-2023. This is the missing **land-use-change** carbon source: the model
represents only fossil emissions endogenously. Documented limitation; candidate for
a future LUC term.

**2. ECS is identified over the long window - at the physical heat capacity.**
Joint temperature-RMSE grid (concentration-driven, 1990-2023):

| C_surface \ ECS | 1.5 | 2.0 | 2.5 | 3.0 | 3.5 | 4.0 |
|---|---|---|---|---|---|---|
| 6  | .364 | .235 | .151 | **.144** | .199 | .269 |
| 8  | .383 | .260 | .174 | **.144** | .173 | .229 |
| 10 | .402 | .285 | .199 | .154 | .159 | .197 |
| 18 (prod) | .473 | .374 | .297 | .237 | .196 | .173 |

At the physical Geoffroy surface heat capacity (~6-8) the curve has a clear interior
minimum at **ECS = 3.0** - the IPCC AR6 central estimate. The window *does* constrain
ECS.

**3. The production `HEAT_CAP_SURFACE = 18` is a short-window artifact.** Over
2015-2023, 18 actually fits marginally better (temp RMSE 0.138 vs 0.156 at 8) because
8 years is dominated by interannual noise around a near-flat trend. But 18 over-damps
the multi-decadal transient: with it, temperature RMSE falls monotonically in ECS and
the best fit pins at the 4C ceiling. The long window resolves the degeneracy in favour
of (C_surface ~ 8, ECS = 3.0).

## Recommended follow-up (not applied here)

A **joint multi-window recalibration** of `{ECS, HEAT_CAP_SURFACE, HEAT_CAP_DEEP,
OCEAN_EXCHANGE}` against 1990-2023 (trend) **and** 2015-2023 (levels) simultaneously,
moving `HEAT_CAP_SURFACE` toward its physical value. This is deferred because lowering
it in isolation worsens the 2015-2023 golden temperature RMSE; it is a deliberate
calibration decision, not a silent change. The production values are unchanged by
T1.3; the long-window machinery and evidence are now in place to drive that
recalibration.

## Reproduce

```
python scripts/build_climate_observations.py     # rebuild data from source values
python -m gim.climate_backtest                    # print both modes + ECS sweep
python -m unittest tests.test_climate_backtest    # 7 tests
```
