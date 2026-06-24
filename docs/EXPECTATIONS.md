# Near-rational expectations (E4.3)

Status: **scaffold landed, switchable, OFF by default** (`EXPECTATIONS_HORIZON = 0`) — the golden
2015–2023 backtest is bit-identical to the pre-E4.3 baseline. **Investment site wired**; the inflation
anchor is designed but deferred to a second pass. Calibration / headline activation are future work.
THE-62.

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
- **Inflation anchor — designed, deferred.** `π_expected = (1−w)·adaptive + w·forecast π`, a new weight
  `EXPECTATIONS_INFLATION_WEIGHT` defaulting to 0. Held to a second pass because the adaptive anchor's
  persistence (ρ=0.5) was just independently validated by E4.1 ([MONEY_PRICES.md](MONEY_PRICES.md)).

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
byte-identical golden. Even with the operator **on** but the tilt off (`HORIZON>0, FORESIGHT=0`) the
run stays golden — the event-frozen, separately-seeded projection never perturbs the main RNG or
critical fields. Verified by [tests/test_expectations.py](../tests/test_expectations.py):
`test_default_golden_preserved`, `test_operator_alone_is_golden`, `test_recursion_guard_suppresses_operator`.

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
    "EXPECTATIONS_HORIZON": 3, "EXPECTATIONS_REFRESH_EVERY": 5, "EXPECTATIONS_FORESIGHT": 0.5,
})
```

Headline activation is a deliberate future decision (calibrate `H` / the tilt; record in
`docs/RE_ANCHOR.md`).

## Files

- `gim/core/expectations.py` — the operator, recursion guard, shared cache.
- `gim/core/simulation.py` — `update_expectations(world)` called at the top of `step_world`.
- `gim/core/economy.py` — the investment-site forward/backward swap.
- `gim/core/calibration_params.py` — `EXPECTATIONS_HORIZON`, `EXPECTATIONS_REFRESH_EVERY`.
- `tests/test_expectations.py` — golden-safety, operator caching, recursion guard, forward≠backward.
