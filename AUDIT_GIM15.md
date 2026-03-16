# AUDIT_GIM15

Date: 2026-03-16  
Repo: `GIM15`  
Branch: `GIM15`

This audit supersedes prior snapshots archived under `misc/old_docs/`.

## Scope

This pass focused on documentation correctness versus current code and calibration artifacts:

- `README.md`
- `docs/CALIBRATION_REFERENCE.md`
- `docs/CALIBRATION_LAYER.md`
- `docs/MODEL_METHODOLOGY.md`
- version metadata (`gim/__init__.py`, `pyproject.toml`)

## Verification Run

Executed:

```bash
python3 -m unittest discover -s tests -v
```

Result:

- `133` tests
- `OK` (`3` skipped: optional dependency paths)

Observed calibration checks:

- historical backtest: GDP RMSE `1.050`, CO2 RMSE `1.630`, temperature RMSE `0.136`
- operational suites: `operational_v1` and `operational_v2` regression checks pass
- `operational_v2` sensitivity: high-sensitivity discriminating paths remain detected
- rolling walk-forward (`2015->2023`) Stage B/C completed with robust block-4 set:
  - `TFP_RD_SHARE_SENS = 0.300000`
  - `GAMMA_ENERGY = 0.042000`
  - `DECARB_RATE_STRUCTURAL = 0.031200`
  - `HEAT_CAP_SURFACE = 18.000000`
- OOS comparison (`baseline vs robust`) on one-step windows:
  - objective `1.8357 -> 1.8125`
  - temperature RMSE `0.0776 -> 0.0753`

## Audit Conclusion

- Documentation now reflects the active runtime flow and current calibration contracts.
- Stale and drift-prone statements (old test counts, obsolete methodology fragments, outdated decarb reference text) were removed.
- Historical audit material was moved out of the root into `misc/old_docs/`.

## Open Risks (Explicitly Tracked)

- `DECARB_RATE_STRUCTURAL` remains a compound residual parameter until an explicit energy-sector module is introduced.
- Several parameters in `gim/core/calibration_params.py` are still `[PRIOR]` and require future empirical passes.
