# GIM_14

`GIM_14` is a clean local repository built from the active simulation core in `legacy/GIM_11_1` plus the current state/data pipeline artifacts from `GIM_12`.

This migration is intentionally non-destructive:

- the original `GIM` repository stays untouched
- `GIM_14` is a separate local git repository
- only the active simulation core, data, scripts, and documentation snapshots were copied over
- old archive folders such as `V10_3_prod` were not imported into the new tree

## Layout

```text
GIM_14/
├── gim/
│   ├── __init__.py
│   ├── __main__.py
│   ├── paths.py
│   └── core/
├── data/
├── docs/
├── scripts/
├── tests/
├── vendor/
├── pyproject.toml
└── README.md
```

## What Was Brought Forward

- simulation core from `legacy/GIM_11_1/gim_11_1/`
- current compiled state from `GIM_12/agent_states.csv`
- current source pipeline snapshot from `GIM_12/data/agent_state_pipeline/`
- helper scripts from `GIM_12/scripts/`
- documentation snapshots from `GIM_12/`
- map assets from `GIM_12/data/` and `GIM_12/vendor/`

## Running

Smoke-test run without LLM:

```bash
cd /Users/theclimateguy/Documents/jupyter_lab/GIM_14
POLICY_MODE=simple SIM_YEARS=1 SAVE_CSV_LOGS=0 GENERATE_CREDIT_MAP=0 python3 -m gim
```

LLM run via helper script:

```bash
cd /Users/theclimateguy/Documents/jupyter_lab/GIM_14
export DEEPSEEK_API_KEY="..."
./scripts/run_10y_llm.sh
```

## Testing

```bash
cd /Users/theclimateguy/Documents/jupyter_lab/GIM_14
python3 -m unittest discover -s tests -v
```

## Notes

- This repo reflects the current workspace snapshot, including local uncommitted source/data updates that existed in `GIM` at migration time.
- The attached migration brief referenced a later tree with `GIM_13`; that layer is not present in the current source repo, so `GIM_14` unifies the active simulation core and current data/pipeline assets that are actually available.

