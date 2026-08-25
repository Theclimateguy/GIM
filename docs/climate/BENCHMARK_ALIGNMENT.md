# GIM18 Objectivity Layer — Modern-Benchmark Alignment & Skill (F1)

Two cross-cutting honesty instruments (`gim/benchmark_alignment.py`) that judge GIM against
**current** standards, not the dated DICE/RICE.

## 1. SCC vs modern benchmarks, at comparable discounting

GIM's headline SCC (~$15/$45/$48 at 30/100/200 yr) uses **Nordhaus discounting**
(ρ=1.5%, η=1.45). The modern US consensus (RFF-SP / EPA-2023) uses a **near-term-2% Ramsey**
scheme (ρ≈0.2%, η≈1.24). Recomputing GIM at that scheme:

| | 100 yr | 200 yr |
|---|---|---|
| GIM, Nordhaus discounting | ~$46 | ~$55 |
| **GIM, modern 2% discounting** | **~$97** | **~$191** |

Modern benchmarks ($/tCO₂, 2020$): **EPA-2023 = $190**, **RFF-SP/GIVE = $185** (both 2%);
US-gov interim $51 (3%); DICE-2016R2 ~$31–51 (high discount, dated).

**Result:** at the modern 2% discounting and a sufficient horizon, **GIM reproduces the
EPA-2023 / RFF-SP central SCC (~$190)**. The "low" headline value was the discount-rate
convention, not a model deficiency. Remaining upside vs EPA/RFF (which GIM does *not* yet
capture) is **growth-effect damage persistence** — a Phase-5 item. DICE is retained only as a
low-discount sanity point, never a target.

## 2. Skill vs naive baselines (the honest accuracy metric)

The IMF-WEO evaluation (Celasun et al. 2021) shows even professional 2–5-year GDP forecasts
often fail to beat a naive "recent-average" forecast. So the defensible accuracy metric is the
**skill score** `1 − RMSE_model / RMSE_persistence` (>0 beats naive), not raw RMSE.

GIM 2015–2023 backtest skill vs persistence:

| series | skill | verdict |
|---|---|---|
| temperature | **+0.15** | beats naive ✓ |
| world GDP | **+0.09** | modestly beats naive ✓ (consistent with how hard this is) |
| global CO₂ | **−0.17** | **worse than naive** — GIM over-decarbonises vs flat 2015–23 CO₂ |

The CO₂ result is a deliberately-surfaced weakness: GIM's structural decarbonisation rate
(SSP1-2.6-like baseline) hurts the short-window CO₂ fit. This flags the **decarbonisation-rate
calibration** as the priority finalization target for the emissions dimension.

## Usage

```python
from gim.benchmark_alignment import scc_alignment_report, backtest_skill_report
scc_alignment_report(horizons=(100, 200))   # GIM SCC native + modern-2% vs EPA/RFF/DICE
backtest_skill_report()                      # skill vs naive for the global series
```

## Validation

`tests/test_benchmark_alignment.py` (4 tests): modern benchmarks sane + discount-ordered;
lower discount raises SCC; GIM-at-2% reproduces the EPA/RFF central band ($150–230) at 200 yr;
skill report structure + temperature/GDP beat naive.

## Follow-ups

Make `backtest_skill_report` a CI-reported headline; extend skill scoring to the social /
geopolitical outputs once those have observational targets (F3); fix the CO₂ decarb-rate so
GIM stops losing to naive on emissions.
