# Performance & async policy (THE-66)

## Member-size policy

| context | members | rationale |
|---|---|---|
| **interactive** (in-app) | `INTERACTIVE_MEMBERS = 120` | responsive (~1–2 s scenario); fans already stable |
| **background** (full run) | `BACKGROUND_MEMBERS = 500` | paper-grade ensemble; run off the UI thread with progress |

`gim2.perf.recommended_members(interactive=…)` returns the size; the app uses 120
for live runs and offers a "full 500×" background job with SSE progress + cancel.

## Baseline cache

The base ensemble depends only on the config, **not** on the lever selection, so
`gim2.scenario.baseline_trajectories` memoises it (LRU, 4 configs). `compute_scenario`
and `compute_dose` reuse it → a second scenario at the same config only recomputes
the scenario arm.

## Measured (quick bench: 40×, 20 countries, 10 years; `python3 -m gim2.perf --quick`)

| mode | seconds |
|---|---|
| ensemble | 0.53 |
| sensitivity (Morris r=6) | 2.69 |
| weak_signals | 0.13 |
| scenario (cold) | 1.04 |
| **scenario (warm-base)** | **0.54** ← cache halves it |
| dose (3pt, warm-base) | 1.06 |

The full paper-grade bench is `python3 -m gim2.perf --full` (500×, 57 countries) —
run on demand, not in CI (tens of seconds). Extrapolating the cold scenario from
40→500 members puts the full scenario in the tens-of-seconds range, which is why it
is a **background** job; the interactive 120× path stays in the ~1–2 s band.

## Async / cancel

Heavy modes (`ensemble` / `scenario` / `dose_response`) stream `progress` over SSE
and honour `POST /run/<id>/cancel` cooperatively (the member loop checks the cancel
flag and raises `RunCancelled` → `error{code:"cancelled"}`). Light modes
(`sensitivity` / `weak_signals` / `meta`) run synchronously.
