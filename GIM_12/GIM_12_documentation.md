# GIM_12 Documentation

## Entry Points

- `python -m gim_11_1`
- `python GIM_12.py`
- `./scripts/run_10y_llm.sh`

## Simulation Flow (Yearly)

1. Build observations and generate actions (simple/growth/LLM).
2. Apply political and geopolitical dynamics.
3. Apply economy/resources/climate/social updates.
4. Update memory and compute next-year credit rating.
5. Increment year.

## Credit Rating (Next-Year)

- Range: `1..26` (`26` = default).
- Zones:
  - Green: `1..12`
  - Yellow: `13..20`
  - Red: `21..26`

Computation location:
- `gim_11_1/credit_rating.py`
- function: `update_credit_ratings(...)`
- risk score formula in `_credit_risk_components(...)`
- mapping risk->rating in `_risk_to_rating(...)`

## Outputs

When `SAVE_CSV_LOGS=1`:
- `logs/GIM_11_1_<timestamp>_t0-tN.csv`
- `logs/GIM_11_1_<timestamp>_actions.csv`
- `logs/GIM_11_1_<timestamp>_institutions.csv`
- `logs/GIM_11_1_<timestamp>_t0-tN_credit_map.html` (if `GENERATE_CREDIT_MAP=1`)

## Notes

- Only countries in input CSV participate.
- If CSV has more than `MAX_COUNTRIES`, rows after limit are ignored.
- `Rest of World` can stay in simulation but is excluded from map painting.
