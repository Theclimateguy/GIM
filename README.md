# Global Integrated Model — version 17 (GIM17)

A year-by-year simulation of the world as interacting countries (~50 countries plus regional
groupings), integrating **economy, climate, climate damage, resources, society, politics,
geopolitics, culture, risk/crises and finance** into one model. It is built for scenario
exploration and uncertainty-aware analysis — "what tends to happen, and how confident can we be" —
not pinpoint forecasting.

**New here? Start with [`docs/MODEL_LAYERS.md`](docs/MODEL_LAYERS.md)** — a plain-language tour of
every layer, what it can do, and its limits. For where the model stands and what comes next, see
[`docs/ROADMAP.md`](docs/ROADMAP.md).

## Status (version 17, finalized)

- Economy reproduces 2015–2023 national-income history; climate matches the mainstream scientific
  assessment (temperature sensitivity and the 1990–2023 warming/carbon record).
- Headline regression ("golden") backtest: GDP error ≈ 0.59, global CO₂ error ≈ 1.15, temperature
  error ≈ 0.135 — improved by the objective economic core and held stable since.
- The headline economic core is **objective and fully closed**: a calibrated capital–energy
  substitution (nested-CES) production function, cost-minimising energy demand, energy/resource and
  capital markets that clear by price, a closed stock-flow-consistent bank balance sheet
  (money = deposits = loans), and SSP2-anchored forward growth.
- Cost of carbon in the modern consensus range (~$140/tCO₂ at modern 2% discounting, with a
  documented growth/discounting sensitivity); conflict-risk validated against the standard
  armed-conflict record (AUC ≈ 0.74, Brier skill ≈ +0.14 vs the base rate).
- Strict, accounting-consistent government finance (including through debt crises).
- A dedicated **weak-signal detection** module (Mahalanobis joint-state anomaly + structural-break
  change-point + critical-slowing-down) for what-if / early-warning analysis (`gim/weak_signal.py`).
- Deep-uncertainty mechanisms (carbon-cycle feedbacks, fat-tailed crisis severity, growth-effect
  damages) remain **switches, off by default**, so the headline run stays anchored and they are
  explored separately as uncertainty.

## Install

```bash
pip install -e .          # Python 3.10+
```

## Quick start

```bash
python3 -m gim                                   # core multi-year world simulation
python3 -m gim question "Will Red Sea tensions escalate?"
python3 -m gim game --case misc/cases/maritime_pressure_game.json --dashboard
python3 -m gim metrics --agents Iran "United States"
python3 -m gim calibrate --suite operational_v1
python3 -m gim ui --host 127.0.0.1 --port 8090   # local analytical dashboard
```

Subcommands: `world`, `question`, `game`, `hybrid`, `metrics`, `calibrate`, `brief`, `console`, `ui`.
Full command reference: [`COMMAND_REFERENCE.md`](COMMAND_REFERENCE.md). Run artifacts are written to
timestamped folders under `results/` (each with a `run_manifest.json`).

## Documentation

Full index: [`docs/README.md`](docs/README.md). Key entry points:

- Plain-language overview — [`docs/MODEL_LAYERS.md`](docs/MODEL_LAYERS.md)
- Where it stands / next steps — [`docs/ROADMAP.md`](docs/ROADMAP.md)
- Model specification & methodology — [`docs/GIM17_UNIFIED_MODEL_SPEC.md`](docs/GIM17_UNIFIED_MODEL_SPEC.md), [`docs/MODEL_METHODOLOGY.md`](docs/MODEL_METHODOLOGY.md)
- Calibration ledger — [`docs/CALIBRATION_REFERENCE.md`](docs/CALIBRATION_REFERENCE.md)
- Finalization summary — [`docs/FINALIZATION_REPORT.md`](docs/FINALIZATION_REPORT.md)

## Tests

```bash
python3 -m unittest discover -s tests             # full suite
./scripts/run_validation_package_gim17.sh         # release validation (non-LLM)
```

## Version

`17.1.1`. Preprint snapshot: the accompanying paper is finalized in academic English with fully
reproducible figures (engine and results unchanged from 17.1.0). The 17.1.0 release added the
statistical-rigor and analysis layer on top of the 17.0.0 core (unchanged):
reproducible conflict-AUC inference (bootstrap CI + permutation test), Morris-screening robustness
and ensemble Monte-Carlo convergence checks, and an identification of the (lagged) economy→society
channel. Ships a committed, reproducible figure generator and the accompanying paper.
Highlights of the 17.0.0 core: Python 3.10+ and lean repo; enforceable
accounting/integrity invariants; deterministic reproducible runs; full uncertainty machinery
(evidence-based priors, Monte-Carlo ensembles, sensitivity analysis, history matching, skill
scoring); an objective, fully-closed economic core (nested-CES production + market clearing + closed
SFC bank balance sheet + SSP2 forward growth); a weak-signal detection module; and the version-17
finalization across all layers. See [`CHANGELOG.md`](CHANGELOG.md) and
`docs/FINALIZATION_REPORT.md`.
