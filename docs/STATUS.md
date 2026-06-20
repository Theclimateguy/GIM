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
- P4-A: endogenous inflation (Phillips + energy cost-push) and unemployment (Okun),
  closing the loop climate -> prices -> labor -> social tension -> politics.
- Ensembles (N=500), Morris/Sobol sensitivity, history-matching/NROY, skill scoring.

**Weak / pending.**
- Non-CO2 forcing is a crude linear term (no separate CH4/N2O/aerosols).
- Carbon cycle ~10 ppm low (no land-use-change source).
- No monetary-policy reaction (rate does not respond to inflation/unemployment).
- Temperature variability is white noise, not AR(1).
- Economic backtest panel only 2015-2023 (a 1990 initial state is needed to extend it).

## Roadmap (Phase 4 -> 5)

1. **P4-B Multi-GHG forcing** - separate CH4/N2O/aerosols, SSP/RCP alignment. Biggest
   remaining climate-realism gap. (next)
2. **P4-C Monetary-policy reaction** - Taylor rule: rate <- inflation / output gap;
   closes the central-bank loop on P4-A.
3. **P4-D AR(1) red-noise** temperature variability + benchmark vs FAIR/MAGICC.
4. **P4-E Land-use CO2** source in the carbon cycle (close the ~10 ppm gap).
5. **P5** - economic panel back to 1990, DICE reproduction, market clearing, paper.
