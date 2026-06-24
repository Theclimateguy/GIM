# Near-rational expectations (E4.3)

Status: **both sites wired, switchable, OFF by default** (`EXPECTATIONS_HORIZON = 0`) — the golden
2015–2023 backtest is bit-identical to the pre-E4.3 baseline. Investment and the inflation anchor both
read the forward forecast; parameters are literature-grounded (not backtest-fit — expectations barely
bite in-sample). Headline activation is the next, separate decision. THE-62.

## Why

GIM forms expectations *backward*: investment uses a one-step realised-growth proxy
(`EXPECTATIONS_FORESIGHT`, [economy.py](../gim/core/economy.py)) and the inflation anchor is adaptive
(a fixed 50/50 blend of target and last year's inflation,
[labor_market.py](../gim/core/labor_market.py)). E4.3 lets agents instead form *model-consistent*
expectations — by simulating the model forward — without turning GIM into an equilibrium model class.

## Mechanism — the expectation operator

[`gim/core/expectations.py`](../gim/core/expectations.py) exposes `update_expectations(world)`. When
`EXPECTATIONS_HORIZON = H > 0` it:

1. **deep-copies** the world into a throwaway shadow;
2. **freezes** it — `enable_extreme_events=False`, deterministic `mode="simple"` policies (never an LLM
   call), and a **derived RNG seed** so the projection never touches the main stochastic stream;
3. runs `step_world` **H times** on the shadow under a **recursion guard** (`_in_expectation` on the
   shadow's `global_state`);
4. reads each agent's forecast off the shadow path — expected annual growth `(gdp_H/gdp_0)^(1/H)−1`,
   expected inflation = mean of the projected path — caches it on `world._expected_paths`, and discards
   the shadow.

### Near-rational / level-1 (the honest core)

The recursion guard makes the projection's *own* inner steps fall back to the cheap adaptive rule.
So agents forecast by simulating the real model forward **under the assumption that their future selves
use the simple backward rule** — a one-level (level-1) forecast. Full rational expectations would
require the inner selves to also forecast, an infinite regress that only a fixed-point solver closes.
We deliberately truncate at one level. **This is the chosen departure from textbook RE**, and it is
what keeps GIM a recursive, path-dependent, non-equilibrium simulation rather than a different model
class (no solver, no linearisation, no perfect-foresight stacking). It is contained and additive: one
module, one boolean guard, one call-site swap.

### Shared, world-level, refresh-cadenced

The projection runs **once per refresh**, not per agent: every agent reads its own forecast off the
same shared path, so cost is O(T·H), not O(T·N·H). `EXPECTATIONS_REFRESH_EVERY = k` recomputes the
forecast every k years (agents re-plan periodically; a fresh forecast every year is unnecessary).
`update_expectations` is called at the **top of `step_world`, before the `CriticalWriteGuard`
context** — that guard is process-global and its `__exit__` clears it, so the inner projection steps
must run their guards strictly sequentially (not nested inside the outer step's guard).

## Sites

- **Investment / saving — wired.** [economy.py](../gim/core/economy.py)::`update_capital_endogenous`:
  when `HORIZON>0` and a forecast is cached, the forward-looking tilt sources its expected-growth
  signal from `expected_growth(world, agent_id)` instead of the backward Δgdp proxy. Falls back to the
  backward proxy when off, or when no forecast is available (e.g. inside the projection itself).
- **Inflation anchor — wired.** [labor_market.py](../gim/core/labor_market.py): the Phillips anchor
  blends in the model-consistent expected inflation, `π_expected = (1−w)·adaptive + w·forecast π`,
  weight `EXPECTATIONS_INFLATION_WEIGHT` (default 0). The grounded on-value **w ≈ 0.65** is the
  forward-looking share of the hybrid New-Keynesian Phillips curve (Galí & Gertler 1999; GGLS 2005,
  γ_f ≈ 0.6–0.7). **Regime caveat:** activating it shifts inflation persistence away from the adaptive
  ρ=0.5 that E4.1 independently validated ([MONEY_PRICES.md](MONEY_PRICES.md)) toward the hybrid-NKPC
  forward-looking regime — a deliberate expectation-regime switch, which is why the validated headline
  keeps it off. In-sample the model-consistent forecast ≈ the adaptive anchor, so turning the inflation
  site on alone leaves the 2015–2023 backtest **bit-identical** (it diverges only forward / under shocks).

## Parameters (grounded on-values; defaults stay off)

| Parameter | Default | On-value | Anchor |
|---|---|---|---|
| `EXPECTATIONS_HORIZON` | 0 | 3 | investment/forecast planning horizon |
| `EXPECTATIONS_REFRESH_EVERY` | 5 | 5 | cost (≈2× at H=3; see spike) |
| `EXPECTATIONS_FORESIGHT` | 0 | 0.5 | bounded investment tilt (F2.5) |
| `EXPECTATIONS_INFLATION_WEIGHT` | 0 | 0.65 | hybrid-NKPC forward share (Galí–Gertler) |

These are **literature-anchored priors, not a GIM-backtest fit** — the 2015–2023 window can't identify
forward-looking behaviour (it barely bites in-sample, as the bit-identical activation shows). Validation
is by forward ablation and the regime checks above. Full activation of both sites with the on-values
keeps the backtest within the validated band (GDP RMSE 0.590→0.593, CO₂ 1.148→1.131).

## Cost (measured on the real 57-country world)

A throwaway cost spike measured `t_step ≈ 44 ms`, `t_deepcopy ≈ 20 ms` (0.47× a step — *not* the
bottleneck, so no reduced shadow-state is needed), operator(H=3) ≈ 147 ms. Overhead vs baseline on a
200-year run:

| refresh | H=3 | H=5 |
|---|---|---|
| every year (k=1) | 4.4× | 6.3× |
| **every 5 yr (k=5)** | **1.7×** | **2.1×** |

So the design default-on values are `HORIZON=3, REFRESH_EVERY=5` (≈2×). The 2015–2023 backtest is 9
years, so cost there is sub-second. Note the multiplier is **linear on Monte-Carlo ensembles** — this
is a headline/scenario feature, not something to leave on for every ensemble member.

## Golden safety

`EXPECTATIONS_HORIZON = 0` (default) → `update_expectations` is a no-op that writes no extra state →
byte-identical golden. Even with the operator **on** but both tilts off (`HORIZON>0, FORESIGHT=0,
INFLATION_WEIGHT=0`) the run stays golden — the event-frozen, separately-seeded projection never
perturbs the main RNG or critical fields. The **inflation site on alone** is also bit-identical
in-sample (the forecast ≈ the adaptive anchor). Verified by
[tests/test_expectations.py](../tests/test_expectations.py): `test_default_golden_preserved`,
`test_operator_alone_is_golden`, `test_recursion_guard_suppresses_operator`, `test_inflation_on_alone_is_golden`,
`test_inflation_site_applies_forecast` (proves the anchor actually blends the forecast).

## Honesty caveats

- **Level-1 truncation** is an approximation of rational expectations, documented above — not full RE.
- **Frozen-policy assumption.** The projection assumes baseline (`simple`) policy behaviour forward,
  regardless of the outer run's actual (e.g. scenario) policies — a deliberate, cheap, deterministic
  freeze.
- **The 2015–2023 backtest cannot strongly validate this** — expectations mostly bite forward and in
  crises (same caveat as the R&D-stock channel). Validation is by forward ablation (how H shifts
  trajectories / SCC) and behavioural checks, anchored to the adaptive-learning literature (Evans &
  Honkapohja).

## Activating

```python
run_historical_backtest(params_override={
    "EXPECTATIONS_HORIZON": 3, "EXPECTATIONS_REFRESH_EVERY": 5,
    "EXPECTATIONS_FORESIGHT": 0.5, "EXPECTATIONS_INFLATION_WEIGHT": 0.65,
})
```

Headline activation is a deliberate future decision (record in `docs/RE_ANCHOR.md`).

## Files

- `gim/core/expectations.py` — the operator, recursion guard, shared cache, forecast accessors.
- `gim/core/simulation.py` — `update_expectations(world)` called at the top of `step_world`.
- `gim/core/economy.py` — the investment-site forward/backward swap.
- `gim/core/labor_market.py` — the inflation-anchor forward/adaptive blend.
- `gim/core/calibration_params.py` — `EXPECTATIONS_HORIZON`, `EXPECTATIONS_REFRESH_EVERY`,
  `EXPECTATIONS_INFLATION_WEIGHT`.
- `tests/test_expectations.py` — golden-safety, operator caching, recursion guard, both site swaps.
