# GIM_14 Calibration Layer

This file describes the current calibration posture of `GIM_14`.

At the moment, `GIM_14` should be understood as:

- a clean runnable simulator repository
- a migrated data and runtime base
- a staging ground for the next proper calibration pass

It should not yet be understood as a fully re-ported calibration framework.

## 1. What Is Operational Today

Operational today:

- compiled state loading from [data/agent_states.csv](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/data/agent_states.csv)
- state CSV schema and bounds validation in [gim/core/world_factory.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/world_factory.py)
- yearly simulation via [gim/core/simulation.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/simulation.py)
- smoke validation via [tests/test_smoke.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/tests/test_smoke.py)

## 2. What Is Preserved As Calibration Context

Preserved as context rather than active machinery:

- the calibration ledger from the `GIM_13` workstream
- the expectation that `EMISSIONS_SCALE` should become data-derived
- the expectation that climate and macro calibration should be tested with historical backtests
- the separation between world-physics calibration and political/crisis calibration

## 3. Validation Commands

Current `GIM_14` health checks:

```bash
cd /Users/theclimateguy/Documents/jupyter_lab/GIM_14
python3 -m unittest discover -s tests -v
```

Current smoke CLI run:

```bash
cd /Users/theclimateguy/Documents/jupyter_lab/GIM_14
POLICY_MODE=simple SIM_YEARS=1 SAVE_CSV_LOGS=0 GENERATE_CREDIT_MAP=0 python3 -m gim
```

## 4. Next Calibration Porting Steps

The next serious calibration work in `GIM_14` should follow this order:

1. port the historical backtest harness
2. port or rebuild the calibration parameter registry
3. port data-derived climate artifact handling
4. port country-prior support
5. only then continue the next econometric and climate calibration passes

## 5. Bottom Line

`GIM_14` is now ready as the main working repository.

Calibration continuity is preserved in documentation and in the carried-forward data/runtime surfaces, but the richer executable calibration layer still needs to be ported into this repo before the next deep calibration cycle.

