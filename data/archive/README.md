# Archived state artifacts

These files were **retired as sources of truth** during the 2023-canon unification
(2026-06-30). They are kept for provenance and reproducibility, not for runtime use.

## Why archived

The single source of truth for the compiled actor state is now
`data/agent_states_operational.csv` (base year **2023**, 57 actors), validated against
WDI / UN / GCB:

| Aggregate | Canon (2023) | Real 2023 | Δ |
|---|---|---|---|
| World GDP | $106.8T | IMF $105.4T / WB $106.2T | +0.6…+1.3% |
| Population | 8.06B | UN ~8.05B | ~0% |
| CO₂ (fossil+cement) | 37.9 Gt | GCB 37.4 Gt | +1.4% |

All three blocks (gim core, gim-lib `gim2`, GIM2.app) resolve to the canon via
`gim.runtime.default_state_csv()` / `gim.paths.CANONICAL_STATE_CSV`. No source or test
hardcodes a dated forward-projection filename anymore.

## What these were

These are **forward model output** (a 3-year projection 2023→2026 produced by the
engine), not observed/compiled data. As a "current state" they systematically
under-projected reality: world GDP grew only ~0.6%/yr (vs ~3% real), CO₂ fell ~5%/yr
(vs flat), and global temperature cooled — artifacts of the forward step, not the base.

| File | What it is |
|---|---|
| `agent_states_operational_2026.csv` | forward projection (macro) |
| `agent_states_operational_2026_anchored.csv` | forward + anchoring of social/latent scores |
| `agent_states_operational_2026_calibrated.csv` | forward + calibrated social scores (former default of analytics/UI) |
| `agent_states_operational_2026.projection.json` | projection run metadata |

The three CSVs share an identical macro core (GDP/pop/CO₂); they differ only in social
latent scores.

## How to regenerate (if ever needed as an explicit scenario)

```
python3 -m scripts.project_operational_state --state-csv data/agent_states_operational.csv \
    --years 3 --output data/archive/agent_states_operational_2026.csv
python3 scripts/anchor_initial_state.py   # writes the anchored variant into data/archive/
```

Forward projections are a legitimate analysis output — they just must not masquerade as
the compiled base state.
