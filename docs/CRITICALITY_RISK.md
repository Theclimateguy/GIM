# GIM17 Criticality / SOC Risk Modelling (F5)

## The problem with GIM's current risk model

GIM models systemic risk — debt/FX/regime crises, conflict, cascades — with **fixed thresholds
and fixed-magnitude shocks** (e.g. debt crisis triggers at debt/GDP>1.2 ∧ rate>0.12, then applies
a constant multiplier) plus **Gaussian** variability. This is **thin-tailed**: it produces
step-function crises of roughly fixed size and cannot generate the rare, system-spanning
catastrophes that dominate real tail risk. That is precisely the "catastrophic spread" the model
is meant to characterise — and a thin-tailed risk core structurally **understates** it.

## The better paradigm: power laws + criticality

Two of the most robust empirical regularities in the social sciences say risk is critical, not
Gaussian:

1. **Power-law (SOC) event sizes.** War severity follows `Pr(x) ∝ x^−α` (Richardson 1948;
   confirmed with modern methods by Clauset 2018; reproduced by Cederman's 2003 self-organized-
   criticality model of war). The same scale-free pattern holds for financial crashes, blackouts,
   epidemics. "Among the most accurate and robust findings in world politics." Onsets are roughly
   Poisson. Fixed-magnitude shocks cannot represent this.
2. **Critical slowing down (early-warning signals).** Before a critical transition, complex
   systems show rising **lag-1 autocorrelation** and **variance** (Scheffer et al. 2009, Nature
   461:53) — generic across ecosystems, finance, climate and social systems. This is a *leading
   indicator* of approaching tipping points.

## What is delivered now (F5, step 1)

`gim/criticality.py` — a **Scheffer-style early-warning diagnostic**, computed post-hoc from any
trajectory (ensemble member, backtest, projection), so it adds a criticality risk-monitor with
**zero change to the simulation core** (no calibration/golden risk):

- `rolling_indicators` — sliding-window lag-1 autocorrelation + variance.
- `early_warning_score` — Kendall-tau trend of each; `combined>0.25` ⇒ critical-slowing-down
  warning (both rising).
- `early_warning_scan` — applies it to multiple state series (trust, tension, debt, conflict…).

Validated (`tests/test_criticality.py`) on a synthetic system driven across a bifurcation
(flagged) vs a stationary one (not flagged).

## The fuller plan (next F5 steps)

- **Power-law event magnitudes (switchable, calibrated to Richardson α≈1.5–1.6).** Replace the
  fixed crisis/conflict shock magnitude with a draw from a power-law (truncated Pareto), so crisis
  *severity* is fat-tailed and a few events are system-spanning. Default-off to preserve the golden
  backtest; on = realistic tail risk. This is the highest-value structural change (directly fixes
  the understated catastrophic tail).
- **Cascade / contagion dynamics** on the trade/alliance/debt network: a local crisis can trigger
  an avalanche (GIM already has partial debt-spread contagion — generalise it toward an SOC
  sandpile on the network).
- **Live early-warning** wired into the runtime as a per-agent risk output (not just post-hoc),
  feeding the political/social block.

## Honest assessment

- **Early-warning diagnostic (done):** low-risk, high-value, literature-grounded, no golden impact.
- **Power-law magnitudes (next):** high-value for tail realism, medium risk (changes crisis
  dynamics); do as a switchable, α-calibrated mode.
- **Full SOC sandpile of conflict/state-formation (Cederman-style):** theoretically elegant but a
  large architectural change and **hard to validate as a forecasting tool** — it reproduces the
  *aggregate* power law, not specific events. Worth prototyping as a research branch, not the
  production path. The pragmatic win is fat-tailed magnitudes + EWS, not a full sandpile rewrite.
