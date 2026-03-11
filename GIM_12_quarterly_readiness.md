# GIM_12 Quarterly Readiness Assessment

## Verdict

`GIM_12` is not natively ready for homogeneous `3-month` forecasting.

The current simulation loop is structurally annual:

- `simulation.py` increments `world.time` by `1` per step and the public CLI runs in `SIM_YEARS`.
- sanctions, wars and climate shocks are tracked in year counters;
- demographic, fiscal, resource and macro updates are parameterized as annual transitions;
- credit logic explicitly computes `next_year_*` risks.

Because of that, simply reinterpreting one step as one quarter would distort calibration.

## Main blockers

### 1. Time unit is a year in the core loop

`legacy/GIM_11_1/gim_11_1/simulation.py`

- `run_simulation(..., years: int, ...)`
- `for _ in range(years):`
- `world.time += 1`

### 2. Demography is applied as annual growth

`legacy/GIM_11_1/gim_11_1/social.py`

- birth and death rates are annual-style rates;
- `population *= 1 + growth_rate` is applied once per step;
- migration uses step-level caps that are tuned as yearly shares.

### 3. Resource system is annual

`legacy/GIM_11_1/gim_11_1/resources.py`

- energy caps use `WORLD_ANNUAL_SUPPLY_CAP_ZJ`;
- production caps are expressed as `prod_cap_zj_per_year`;
- reserve depletion and regeneration are applied once per step with yearly semantics.

### 4. Climate and shock durations are annualized

`legacy/GIM_11_1/gim_11_1/climate.py`

- `update_global_climate` defaults to `dt=1.0`;
- extreme event probabilities are calibrated per step;
- `climate_shock_years` is decremented once per step and event penalties persist for multiple yearly steps.

### 5. Political and conflict durations are annual

`legacy/GIM_11_1/gim_11_1/political_dynamics.py`

- sanctions use `min_duration = 2` and decrement `sanction_years` by one each step.

`legacy/GIM_11_1/gim_11_1/geopolitics.py`

- `war_years` increments by one each step.

### 6. Macro-financial dynamics are calibrated per year

`legacy/GIM_11_1/gim_11_1/economy.py`

- capital depreciation is annual;
- TFP drift and diffusion are annual;
- fiscal flows, interest burden and borrowing caps are applied per step as yearly quantities;
- `max_new_debt = 0.05 * gdp` is a yearly borrowing cap.

### 7. Credit diagnostics are explicitly yearly

`legacy/GIM_11_1/gim_11_1/credit_rating.py`

- metrics include `next_year_war_risk`, `next_year_revolution_risk` and `sanction_risk_next_year`.

### 8. Inflation is not yet endogenously updated in the core

`GIM_12` stores `economy.inflation`, but the current legacy core does not update it each step.

This matters for quarterly forecasting because a homogeneous subannual forecast requires explicitly modeled fast-moving price dynamics.

## What is still possible now

Two different things should be separated:

### A. True quarterly simulation

This is **not** safe to claim for the current `GIM_12` core.

### B. Quarterly crisis diagnostics

This is feasible as an overlay:

- keep the world state from the calibrated annual core;
- compute crisis metrics at a finer reporting cadence;
- interpolate or stress-test fast-moving variables such as inflation pressure, FX stress, oil stress, sanctions pressure and protest pressure.

This is exactly why the new `CrisisMetricsEngine` is useful: it creates a faster diagnostic layer without pretending the underlying state transition is already quarterly.

## Recommended path to true quarterly support

If we want real `3-month` simulation later, the minimum technical path is:

1. Introduce explicit `dt_years` in the step function.
2. Rescale all annual rates and caps:
   - demography;
   - depreciation;
   - TFP drift;
   - borrowing caps;
   - migration caps;
   - sanctions and war durations;
   - extreme-event probabilities.
3. Convert yearly thresholds into duration-aware thresholds.
4. Split the pipeline into slow and fast blocks:
   - quarterly macro/resource loop;
   - monthly or event loop for sanctions, protests, incidents and crises.
5. Recalibrate against the current `GIM_12` annual baseline so that quarterly mode does not break the already achieved calibration.

## Working conclusion

Current state:

- annual core simulation: yes;
- homogeneous quarterly core simulation: no;
- quarterly crisis reporting layer over the annual core: yes, and this should be the immediate path.
