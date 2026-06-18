# GIM17 Work Log

Lean engineering log for the GIM16 → GIM17 modernization. One entry per stage:
decision, rationale, what changed, how it was verified. Read this first when resuming.

## Goal

Industry-grade **predictive** model that quantifies the weight of **natural capital**
(climate variables in particular) in economy, politics, and conflict. GIM16 is frozen as
the reference baseline; GIM17 is the evolving next version.

## Roadmap (phases)

- **Phase 0 — Foundation** (current): reproducibility, integrity invariants, balance
  closure, determinism, CI.
- **Phase 1 — Uncertainty**: ensemble/Monte-Carlo runtime, global sensitivity (Sobol/Morris),
  probabilistic outputs.
- **Phase 2 — Calibration & validation**: Bayesian/history-matching calibration on an
  extended panel; skill scoring vs. baselines (RMSE/CRPS, interval coverage).
- **Phase 3 — Welfare/SCC**: utility, discounting, calibrated damage function, optimization
  mode → endogenous social cost of carbon.
- **Phase 4 — Structural depth**: FAIR/MAGICC climate benchmarking, SSP/RCP alignment,
  optional regional/trade/financial detail.
- **Phase 5 — Benchmarking & paper**: reproduce DICE/RICE/E4A reference runs; document.

## Conventions

- Target runtime: **Python ≥ 3.10** (compatibility is a hard requirement).
- GIM16 is never modified. All work lands in `GIM17/`.
- Each stage is independently auditable and ends with a verification step.

---

## Stage A — Bootstrap GIM17 + Python 3.10+ compatibility

**Status:** complete.

**Changes**
- Created `GIM17/` from GIM16 (code, data, docs, golden backtest artifacts).
  Excluded from the copy: `.git/`, `__pycache__/`, `*.pyc`, `results/` run folders
  (302 MB of regenerable artifacts), and the large regenerable raw archives under
  `data/agent_state_pipeline/cache/*.zip` (~98 MB). Result: 429 MB → 6 MB.
  `results/backtest/` (1.6 MB golden/OOS artifacts) was kept.
- `pyproject.toml`: name `gim17`, version `17.0.0.dev0`, `requires-python = ">=3.10"`.
- `gim/__init__.py`: `__version__ = "17.0.0.dev0"`.
- `gim/dashboard.py`: removed a `Δ` escape inside an f-string expression (illegal
  before Python 3.12) by using the literal `Δ`. This was the **only** hard syntax blocker
  preventing the package from importing on 3.10/3.11.
- `.gitignore`: keep `results/backtest/`, ignore other `results/` run folders.

**Verification (Python 3.10.12)**
- AST parse of every `gim/**/*.py`: 0 syntax errors (was 1: `dashboard.py`).
- `import gim` → `17.0.0.dev0`; world builds (57 actors); `python -m gim.core` 3-year run
  writes a valid `run_manifest.json`.
- Test suite: ~172 tests pass. The only 2 errors (`test_ui_server` manifest tests) occur
  **only in `TemporaryDirectory` teardown** because the sandbox's FUSE mount rejects
  fd-relative `os.unlink(..., dir_fd=...)` with EPERM. Reproduced: fd-relative unlink fails
  on the mount, succeeds on `/tmp`. This is an environment limitation, not a code defect,
  and does not occur on a native filesystem.

**Open items**
- Git: GIM17 is not yet a git repo. Proposed: init, add the GitHub remote
  (`Theclimateguy/GIM`), create branch `GIM17`, initial commit. Deferred pending owner
  confirmation (touches the live GitHub repo / requires push credentials).
