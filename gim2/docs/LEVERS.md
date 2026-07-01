# Grounded lever → core mapping (THE-64)

v2 levers map to **real** `step_world` parameters/state — not the v1 softmax risk
channels. Source of truth: [`../levers.py`](../levers.py). Param targets scale each
member's *sampled* base value (`new = base·(1 + coeff·m)`), so a lever rides on top
of ensemble uncertainty.

## Calibration — anchored to Appendix A (THE-64)

Coefficients are **not hand-set**. *Param* coefficients are **derived from the
Appendix-A priors** (`data/parameter_priors.csv` → `gim.core.priors`) so that
**magnitude 1.0 moves a parameter to its prior edge** at the prior's central value
(`coeff = (edge − p1)/p1`, computed once at import in `_edge_coeff`). *Pulse*
coefficients are anchored to **cited literature shocks**. The band `[0.15, 1.25]`
keeps `0.15…1.0` inside the prior/literature range; `1.0…1.25` is explicit stress
extrapolation.

| param lever | anchored to | magnitude 1.0 → |
|---|---|---|
| `decarbonization` | DECARB prior [0.040, 0.066]; EMISSIONS [0.90, 1.05] | DECARB 0.066, EMISSIONS 0.90 |
| `growth` | SSP-drift ±25%; savings ±5%; R&D [0.10, 0.60] | each → prior high |
| `carbon_price` | ½ of the DECARB prior step + $130/tCO₂×0.003 passthrough | DECARB ½-step; energy +39% |
| `energy_shock` | 2022 oil shock (EIA/IEA) | energy +60%, output −15% |
| `food_shock` | 2007–08 / 2010–11 FAO surge | food +60%, supply −20% |
| `trade_sanctions` | gravity sanction studies (Felbermayr 2020) | trade barrier +0.30 (≈ −30% dyad trade) |
| `stagflation` | 1973–75 stagflation | unemployment +3pp, inflation +4pp (3 yr) |

`tests/test_gim2_levers.py::test_param_levers_anchored_to_appendix_a` asserts the
param levers actually reach the prior edges.

| Lever | Kind | Core target(s) | Effect path (endogenous) |
|---|---|---|---|
| `carbon_price` | param | `CARBON_PRICE_PASSTHROUGH` (×), `DECARB_RATE_STRUCTURAL` (×) | energy price ↑ (cost-push inflation) + emissions ↓ |
| `decarbonization` | param | `DECARB_RATE_STRUCTURAL` (×), `EMISSIONS_SCALE` (↓) | emission intensity ↓ → CO₂ ↓ → warming ↓ |
| `growth` | param | `SSP_FORWARD_TFP_DRIFT`, `SAVINGS_BASE`, `TFP_RD_SHARE_SENS` | higher productivity/savings → GDP ↑ |
| `energy_shock` | pulse | `prices['energy']` ×, `resources['energy'].production` ↓ | import bill ↑ → inflation ↑ → debt stress |
| `food_shock` | pulse | `prices['food']` ×, `resources['food'].production` ↓ | tighter food supply → social tension ↑ → protest |
| `trade_sanctions` | pulse (actors) | `relation.trade_barrier` ↑, `relation.conflict_level` ↑ | trade fragmentation → GDP ↓, conflict pressure |
| `stagflation` | pulse (3 yr) | `economy.unemployment` ↑, `economy.inflation` ↑ | exogenous stagflation sustained three years |

**Mechanisms (no model math added).** *param* levers compose onto the per-run
`ParameterSet` via `with_overrides` — the exact mechanism ensembles use. *pulse*
levers mutate state during the run — the exact mechanism the SCC pulse uses on
`carbon_pools`. The frozen model then propagates every consequence.

**Pulse timing.** Pulses (re)apply at years `1..pulse_sustain` (energy/food = 2,
trade_sanctions/stagflation = 3, one-off = 1). `econ_add` is additive to the value
the model produced that year (non-compounding), clamped to the parameter band
(`UNEMPLOYMENT_MIN/MAX`, `INFLATION_MIN/MAX`). `relation_add` is applied in both
directions and clamped to `[0,1]`.

**Actor scope.** `trade_sanctions` is actor-scoped (`pulse_scope="actors"`); with no
actors given it defaults to the two largest economies. All other levers are global.

**Honesty guard.** `levers.run_member` with an empty selection reproduces
`gim.ensemble._run_member` byte-for-byte (`tests/test_gim2_levers.py`), so
base-vs-scenario deltas are apples-to-apples and never drift from the validated
ensemble.
