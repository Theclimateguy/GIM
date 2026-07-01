# GIM2 — deterministic analytical app line

This directory is the **clean v2 line** (Linear project *GIM17 v2.0*, epics
THE-63…71). It is a thin, validated surface over the frozen GIM17 math in
[`../gim`](../gim) — **no new model math** lives here.

## Why a new line

v1 (the macOS app under [`../macapp`](../macapp)) headlines the *least*-validated
layer: the softmax `game_runner` over 10 abstract risk-classes, "criticality", and
LLM personas / hybrid games. The paper (`paper/gim_paper_ru.pdf`) holds that layer
**off** as uncertainty and validates the **deterministic core**: nested-CES economy
+ climate + damage Ω(T)=1−0.006·T² + resources, coupled annually via
`gim.core.simulation.step_world`. v2 surfaces *only* what the paper validates.

## Validated machinery reused (no math added)

| v2 capability        | reused from `gim` (frozen)                       |
|----------------------|--------------------------------------------------|
| ensemble fans        | `gim.ensemble.run_ensemble`                      |
| Morris / Sobol       | `gim.sensitivity.morris` / `.sobol`              |
| weak signals         | `gim.weak_signal.weak_signal_scan`               |
| social cost of carbon| `gim.scc.social_cost_of_carbon` / `.scc_*`       |
| retro backtest       | `gim.historical_backtest.run_historical_backtest`|
| conflict AUC         | `gim.conflict_benchmark` + `gim.criticality`     |
| deterministic step   | `gim.core.simulation.step_world`                 |

## Structure decision (THE-63)

```
gim2/
  __init__.py          version + GIM_EXPLORATORY flag helper + SCHEMA
  __main__.py          `python3 -m gim2 …` reproducible CLI
  levers.py            E2 — grounded lever ontology (params/state, not softmax)
  scenario.py          E3 — base-vs-scenario two-ensemble delta fans
  dose_response.py     E3 — lever-magnitude sweep → terminal delta
  projections.py       E3/E5 — chart-ready JSON (fan/delta/dose/tornado/roc)
  engine_service.py    E3 — deterministic HTTP+SSE engine (schema gim-engine/2)
  perf.py              E4 — timing bench + baseline cache
  app/                 v2 SwiftUI app (reuses Theme/Brand/Components from ../macapp)
  docs/                lever mapping + bridge contract v2 + v1 archive note
```

* `gim/core` stays the model core. The **exploratory** modules (`game_runner`,
  `hybrid_simulator`, softmax `assistant` tools) are **not deleted** — they remain
  in `gim` and are reachable from v2 only when `GIM_EXPLORATORY=1`
  (`gim2.is_exploratory_enabled()`). See THE-71.
* The Swift app reuses `Theme` / `Brand` / `Components` from `../macapp` verbatim.

## Substantive-quantity rule

v2 outputs are **relative** (scenario − baseline) as **ensembles**, never absolute
point values or softmax "24% strike". Conflict is reported as **relative risk**
(AUC), never an absolute probability. Levers are physically grounded (carbon price,
energy/food supply, trade/sanctions intensity, stagflation macro shock, growth
parameters) mapped to real `step_world` state/parameters — see `levers.py`.

## Reproducibility

Every engine run reports an `equiv_cli`: the exact `python3 -m gim2 …` invocation
that reproduces it. Parity tests assert `engine JSON == CLI JSON` for every
deterministic mode (`tests/test_gim2_parity.py`).
