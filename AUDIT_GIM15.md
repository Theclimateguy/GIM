# AUDIT_GIM15

Date: 2026-03-17  
Repo: `GIM15`  
Branch: `GIM15`

This audit supersedes prior snapshots archived under `misc/old_docs/`.

## Scope

Documentation consistency review against current release state (`15.1.0`):

- `README.md`
- `COMMAND_REFERENCE.md`
- `docs/CALIBRATION_REFERENCE.md`
- `docs/CALIBRATION_LAYER.md`
- `docs/V15_RELEASE_READINESS.md`
- `docs/VALIDATION_PACKAGE_V15.md`
- version metadata (`gim/__init__.py`, `pyproject.toml`)

## Verification Run

Executed:

```bash
python3 -m unittest discover -s tests -v
```

Result:

- `143` tests
- `OK` (`3` skipped: optional dependency paths)

Observed calibration checks:

- historical backtest: GDP RMSE `1.025`, CO2 RMSE `1.605`, temperature RMSE `0.138`
- operational suites: `operational_v1` and `operational_v2` regression checks pass
- `operational_v2` sensitivity: high-sensitivity discriminating paths remain detected
- rolling walk-forward re-check (`2015->2023`) after 15.1 baseline switch:
  - pairwise mean one-step RMSE: GDP `0.305`, CO2 `1.029`, temp `0.075`
  - block4 mean one-step RMSE: GDP `0.305`, CO2 `1.029`, temp `0.078`
- release validation package:
  - `results/validation/non_llm/wp3_wp5_package_2026-03-17/`
  - `operational_v2` pass rate `5/5` for `simple` and `growth`

## Baseline Status (15.1)

Active baseline defaults:

- `TFP_RD_SHARE_SENS = 0.300000`
- `GAMMA_ENERGY = 0.042000`
- `HEAT_CAP_SURFACE = 18.000000`
- `DECARB_RATE_STRUCTURAL = 0.052000` (artifact-bound from operational manifest)

## Audit Conclusion

- Documentation is aligned to `15.1.0` and current calibration/validation status.
- Command reference and versioning are synchronized with runtime behavior.
- Calibration docs now reflect hybrid baseline logic (switched macro parameters + artifact-bound structural decarb).

## Open Risks (Explicitly Tracked)

- `DECARB_RATE_STRUCTURAL` remains a compound residual parameter until an explicit energy-sector module is introduced.
- Several parameters in `gim/core/calibration_params.py` are still `[PRIOR]` and require future empirical passes.
