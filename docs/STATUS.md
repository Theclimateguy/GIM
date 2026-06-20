# GIM17 — Status & Roadmap

Short, thesis-style snapshot of where the model stands and what is next. See
`docs/WORKLOG_GIM17.md` for the detailed per-stage log.

## State (current)

**Integrity / accounting — Tier-1 closed.**
- Debt stock-flow identity (Finding B-1): enforceable invariant, residual ~1e-16.
- Resource ledger (Finding C-1): global reserves = sum of country reserves, enforceable.
- Strict CI gate enforces 6 invariants incl. both macro-accounting identities.

**Climate — physically grounded and validated.**
- Long observational window 1990-2023 from primary sources (GCB, NOAA, HadCRUT5),
  spin-up from 1750.
- Climate-only backtest (emission- and concentration-driven) on the model's real
  physics; ECS identified at 3.0 (IPCC AR6 central).
- Joint recalibration: HEAT_CAP_SURFACE 18->8, OCEAN_EXCHANGE 0.7->1.0 - improved both
  windows (long 0.24->0.16, short 0.138->0.134) at physical parameter values.

**Economy / politics.**
- Welfare (CRRA) + Social Cost of Carbon (pulse method; 30/100/200-yr horizons).
- Endogenous inflation (Phillips + energy cost-push), unemployment (Okun), and a
  Taylor-rule central bank, closing climate -> prices -> labor -> tension -> politics -> debt.
- Ensembles (N=500), Morris/Sobol sensitivity, history-matching/NROY, skill scoring.

**Climate emulator (AR6-consistent).**
- Multi-GHG non-CO2 forcing (AR6 components + per-gas scenario levers).
- AR(1) red-noise internal variability.
- Benchmarked vs FAIR/MAGICC: ECS = 3.0 and TCR = 1.79 (AR6 1.8) - matches both.
- SSP 2100 warming envelopes encoded; baseline classifies as ~SSP1-2.6.

**Weak / pending (Phase 5).**
- Carbon cycle ~10 ppm low (no land-use-change source).
- Default non-CO2 net is the lumped calibrated path, not yet the full AR6 net (P4-B2).
- No per-SSP emission-driver presets (emulator matches AR6; drivers missing).
- Economic backtest panel only 2015-2023 (a 1990 initial state is needed to extend it).
- Damage function is level-effect (no growth-effect persistence).

## Status: Tier-1 + Phase 4 COMPLETE

Tier-1 (THE-10/11/18/19) and Phase 4 / Tier-2 (THE-15 + THE-20..25) are all Done and pushed.

## Roadmap (Phase 5 - THE-16)

1. **DICE/RICE reproduction** - reproduce Nordhaus ~$31/tCO2 in the GIM welfare/SCC frame.
2. **Per-SSP scenario-driver presets** - run SSP2-4.5 / SSP3-7.0 end-to-end.
3. **Land-use CO2** source (close the ~10 ppm carbon-cycle gap); adopt full AR6 net (P4-B2).
4. **Energy-sector detail** - fossil/renewables/nuclear tracks with learning-by-doing.
5. **Growth-effect damages**, market clearing, and the paper.
