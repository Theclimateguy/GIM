# Parameter Change Policy (GIM15)

## Recalibration decision rule

Recalibration is required if and only if at least one of the following is true:

1. Numeric values in `data/parameters_v15.csv` changed.
2. New free parameters were added to transition equations.
3. Existing equation structure changed (not just variable renaming/extraction).

Recalibration is **not required** for:

- moving existing constants from code into `calibration_params.py` with identical values,
- refactoring code structure without changing equations,
- logging/diagnostics additions.

## Lock file

Current lock:

- `data/parameters_v15.lock.json`

This lock stores SHA-256 of `parameters_v15.csv`.
If SHA changes, run calibration and update lock.

## Minimum post-change checks

1. `python3 -m gim.core --max-countries 8 --mode simple`
2. `python3 -m gim.crisis_validation --max-agents 21`
3. Compare key outputs vs previous baseline report (`GDP`, `debt_ratio`, crisis case labels).

