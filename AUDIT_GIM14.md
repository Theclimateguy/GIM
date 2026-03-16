# AUDIT_GIM14

Date: 2026-03-16  
Repo: `GIM_14`  
Branch: `GIM14`

This audit supersedes the prior snapshot archived at `misc/old_docs/AUDIT_GIM14_2026-03-15.md`.

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

Observed calibration checks from the same run:

- historical backtest: GDP RMSE `1.050`, CO2 RMSE `1.630`, temperature RMSE `0.136`
- decarb sensitivity: active `0.052` remains best among tested candidates
- operational suites: `operational_v1` and `operational_v2` regression checks pass
- `operational_v2` sensitivity: high-sensitivity discriminating paths remain detected

## Audit Conclusion

- Documentation now reflects the active runtime flow and current calibration contracts.
- Stale and drift-prone statements (old test counts, obsolete methodology fragments, outdated decarb reference text) were removed.
- Historical audit material was moved out of the root into `misc/old_docs/`.

## Open Risks (Explicitly Tracked)

- `DECARB_RATE_STRUCTURAL = 0.052` remains a compound residual parameter until an explicit energy-sector module is introduced.
- Several parameters in `gim/core/calibration_params.py` are still `[PRIOR]` and require future empirical passes.
