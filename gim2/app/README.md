# GIM17 v2 app (`gim2/app`)

Clean v2 SwiftUI shell (SwiftPM, macOS 13+, no Xcode). Reuses the v1 design system
(`Theme`, `Brand`) and the engine transport pattern (`EngineClient` / `EngineProcess`),
retargeted to the **deterministic** v2 engine (`python3 -m gim2 engine`).

## Build & verify

```bash
swift build --package-path gim2/app                 # compile
GIM_PYTHON=$(which python3) GIM_REPO_ROOT=$PWD \
  swift run --package-path gim2/app GIM2App --selftest   # headless Swift→engine round-trip
```

`--selftest` boots the engine, runs a small scenario, and prints
`selftest: OK · mode=scenario metrics=N …` (exit 0) — the CI-friendly check that the
Swift↔engine path works without a GUI.

## Screens (deterministic only — THE-71)

| section | epic | engine endpoint(s) |
|---|---|---|
| **Сценарий vs база** | E6 | `/run/scenario` → delta fans + relative brief |
| **Ансамбли · Доза** | E7 | `/run/ensemble`, `/run/dose_response` |
| **Эксперт** (Чувствительность / Слабые сигналы / О модели) | E8 | `/run/sensitivity`, `/run/weak_signals`, `/meta/*` |

There is **no** softmax game / criticality / LLM-persona surface — the exploratory
layer is simply not built into this shell (the archived v1 app under `../../macapp`
keeps it). The engine's ready payload reports `exploratory:false` by default.

## Chart components (E5 — `Charts.swift`)

`FanChartView` (median+IQR+5–95), `DeltaChartView` (zero-line delta), `DoseChartView`,
`TornadoChartView` (Morris), `AUCView` (conflict relative-risk), `BriefView`
(relative brief). All bound to the stable `gim-engine/2` JSON shapes
(`gim2/docs/ENGINE_BRIDGE_CONTRACT_v2.md`).

## Verification status

Compiles (Swift 6.3). The **scenario** path is verified end-to-end by `--selftest`;
the other screens compile and call endpoints already covered by
`tests/test_gim2_engine.py`. Not visually driven (no GUI automation here).
Packaging (frozen engine bundle, `.app`) follows the v1 flow in `../../macapp`.
