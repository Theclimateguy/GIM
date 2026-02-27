# GIM_12

Production snapshot of the updated model with:
- scalable country set from input CSV (`up to MAX_COUNTRIES`, default 100),
- CSV validation,
- batched/parallel LLM policy calls,
- yearly creditworthiness rating (1..26),
- offline Leaflet credit map generation from final year.

## Quick Start

```bash
cd /Users/theclimateguy/Documents/jupyter_lab/GIM/GIM_12
export DEEPSEEK_API_KEY="..."
./scripts/run_10y_llm.sh
```

Default behavior:
- `SAVE_CSV_LOGS=1`
- `GENERATE_CREDIT_MAP=1`
- writes logs into `./logs/`
- writes final map `*_credit_map.html` in `./logs/`

## Main Env Vars

- `STATE_CSV` default `agent_states.csv`
- `MAX_COUNTRIES` default `100`
- `SIM_YEARS` default `10` in script
- `POLICY_MODE` (`llm|simple|growth|auto`)
- `LLM_MAX_CONCURRENCY` default `12`
- `LLM_BATCH_SIZE` default `20`
- `SAVE_CSV_LOGS` default `1`
- `GENERATE_CREDIT_MAP` default `1`

## CSV Validation

Input CSV is validated before simulation:
- required columns must exist,
- required fields must be non-empty,
- numeric fields must parse as float.

## Credit Rating Methodology

See:
- `credit_rating_methodology.md` (full scoring explanation)
- implementation: `gim_11_1/credit_rating.py`

## Offline Map

`credit_map_leaflet.py` uses local assets only by default:
- `data/world_countries.geojson`
- `vendor/leaflet/leaflet.js`
- `vendor/leaflet/leaflet.css`

No internet is required for map generation/opening.
