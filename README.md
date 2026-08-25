# Global Integrated Model — GIM 20.1

A year-by-year deterministic simulation of the world as **57 country agents** (50 countries plus
regional groupings), coupling **economy, climate and the carbon cycle, resources, society and
politics, geopolitics, and discrete crises with stock-flow-consistent finance** in one closed loop.
It is built for scenario exploration and uncertainty-aware analysis — what tends to happen, and how
confident one can be — not for point forecasting.

This branch is the release that accompanies the paper. It contains the model, its data, its tests
and the validation evidence, and nothing else.

## The paper

[`Paper/gim_paper_v2_8K.pdf`](Paper/gim_paper_v2_8K.pdf), with LaTeX source alongside it.

> **An unrefereed preprint.** Not peer reviewed, not published in any journal; numbers and claims
> may change in revision. Please cite the software record (`CITATION.cff`), not the manuscript.

The evidence behind its claims — null models, ablations and benchmark scripts with their JSON
results — is under [`Paper/revision/`](Paper/revision/). Figures are regenerated from committed
model output by [`scripts/make_paper_figures.py`](scripts/make_paper_figures.py), and the
retrospective baseline by
[`scripts/regenerate_backtest_baseline.py`](scripts/regenerate_backtest_baseline.py).

Russia is modelled here as one consolidated country agent, identically to the other 56 — the model
the paper describes.

## What's inside

Every run starts from one validated 2023 baseline: 57 actors covering essentially all of world
output (GDP ≈ $107T, population ≈ 8.06B, CO₂ ≈ 38 Gt), reconciled against World Bank, UN and Global
Carbon Project data to within about 1%.

- **A closed economic core.** Nested-CES capital–energy production, cost-minimising energy demand,
  resource and capital markets that clear by price, and a closed stock-flow-consistent bank balance
  sheet. Long-run growth and emissions are development-structured and fit to the 2015–2023 World
  Bank panel.
- **Anchored against the record.** Retrospective evaluation on 2015–2023 and a free-running
  out-of-sample window at 2020–2023, scored on output, emissions, temperature **and resource
  prices** — the last against World Bank commodity indices, benchmarked on a no-skill flat price.
- **Stability measured rather than asserted.** Numerical linearization of the annual map, twin runs
  from perturbed initial states, and a 500-member history-matched parametric ensemble
  (`scripts/run_stability_analysis.py`, `scripts/run_ensemble.py`).
- **Spatial coupling.** Shocks propagate over a literature-anchored trade-gravity graph, with
  switchable conflict, tension and climate contagion.
- **Weak-signal detection.** Mahalanobis anomaly, structural-break and critical-slowing-down
  indicators over the joint state (`gim/weak_signal.py`).
- **Deep-uncertainty mechanisms are switches, off by default** — carbon-cycle feedbacks,
  fat-tailed crises, growth-effect damages, and a contested climate-to-tension channel — so the
  headline run stays anchored and they are explored separately.

Headline retrospective error: country-level output ≈ 0.60 T$, global CO₂ ≈ 0.94 Gt, temperature
≈ 0.145 °C. Resource prices beat a flat-price null on all three (energy 0.99, food 0.80, metals
0.96, where below 1 is better).

## Install

```bash
pip install -e .          # Python 3.10+
```

## Quick start

```bash
python3 -m gim                                   # multi-year world simulation
python3 -m gim question "Will Red Sea tensions escalate?"
python3 -m gim metrics --agents Iran "United States"
python3 -m gim calibrate --suite operational_v1
```

Subcommands: `world`, `question`, `game`, `hybrid`, `metrics`, `calibrate`, `brief`, `console`. Full
reference: [`COMMAND_REFERENCE.md`](COMMAND_REFERENCE.md). Run artifacts land in timestamped folders
under `results/`, each with a `run_manifest.json`.

## The game layer

The same 57-actor core wrapped as a single-player decision game (thirty annual turns from 2023, a
deck of dilemma cards compiled into real policy actions, seven catastrophe gates). Its purpose here
is methodological: players and scripted archetypes push the world into corners smooth history never
visits, so the game acts as an adversarial sampler of the tails, and it has surfaced structural
degeneracies that no retrospective test could reach. Section 7 of the paper reports the tail census
and the two degeneracies it found.

A browser build is at [godmode-rwhp.onrender.com](https://godmode-rwhp.onrender.com/) — source at
[github.com/Theclimateguy/GODMODE](https://github.com/Theclimateguy/GODMODE), and not part of this
repository.

## Documentation

Full index: [`docs/README.md`](docs/README.md). Entry points:

- Plain-language overview — [`docs/MODEL_LAYERS.md`](docs/MODEL_LAYERS.md)
- Specification and methodology — [`docs/UNIFIED_MODEL_SPEC.md`](docs/UNIFIED_MODEL_SPEC.md),
  [`docs/MODEL_METHODOLOGY.md`](docs/MODEL_METHODOLOGY.md)
- Stability analysis — [`docs/STABILITY_ANALYSIS.md`](docs/STABILITY_ANALYSIS.md)
- Integration benchmark — [`docs/INTEGRATION_BENCHMARK.md`](docs/INTEGRATION_BENCHMARK.md)
- Calibration ledger — [`docs/calibration/CALIBRATION_REFERENCE.md`](docs/calibration/CALIBRATION_REFERENCE.md)
- Data contract — [`docs/agent_state_data_contract.md`](docs/agent_state_data_contract.md)

## Tests

```bash
python3 -m pytest tests/ -q
```

## Version & history

Per-version detail and the full lineage are in [`CHANGELOG.md`](CHANGELOG.md). The 20.1 entry lists
the five validation defects this release repairs and what each cost the historical fit.

## License

Apache-2.0 — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
