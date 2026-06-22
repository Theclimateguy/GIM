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
- Headline regression ("golden") backtest: GDP error ≈ 1.03, global CO₂ error ≈ 1.61, temperature
  error ≈ 0.13 — held stable throughout finalization.
- Cost of carbon in the modern consensus range; conflict-risk validated against the standard
  armed-conflict record (clearly beats a naive base rate).
- Strict, accounting-consistent government finance (including through debt crises).
- Speculative/uncertain mechanisms (carbon-cycle feedbacks, fat-tailed crisis severity, growth-effect
  damages, richer production, market clearing) are **switches, off by default**, so the headline run
  stays anchored and they are explored separately as uncertainty.

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

`17.0.0.dev0`. Highlights vs. the frozen version 16: Python 3.10+ and lean repo; enforceable
accounting/integrity invariants; deterministic reproducible runs; full uncertainty machinery
(evidence-based priors, Monte-Carlo ensembles, sensitivity analysis, history matching, skill
scoring); and the version-17 finalization across all layers (see `docs/FINALIZATION_REPORT.md`).
