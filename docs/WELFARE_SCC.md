# GIM17 Welfare & Social Cost of Carbon (Phase 3)

This is the DICE/RICE valuation layer: a social-welfare functional and an endogenous Social
Cost of Carbon, letting the model put a dollar value on climate and on a ton of CO₂.

## Welfare (`gim/welfare.py`)

Consumption is derived from the model's own output and savings (`C = Y − I`), and per-capita
consumption feeds a CRRA utility with Ramsey discounting:

    W = Σ_t  L_t · U(c_t) / (1+ρ)^t,   U(c) = (c^(1−η) − 1)/(1−η)   [ln c if η=1]

with **η = `ELASTICITY_MARGINAL_UTILITY`** (DICE 1.45) and **ρ = `PURE_TIME_PREFERENCE`**
(DICE 1.5%/yr) — both in the per-run ParameterSet, both with literature priors spanning the
Nordhaus↔Stern discounting debate (η ∈ [1.0, 2.0], ρ ∈ [0.001, 0.03]).

## Social Cost of Carbon (`gim/scc.py`)

The standard marginal-pulse method (DICE/FUND/PAGE): run a baseline and a perturbed trajectory
with a CO₂ pulse injected FAIR-style into the carbon pools, and take the discounted,
welfare-weighted consumption loss per ton:

    SCC = Σ_{t≥t0}  [ U'(c_t)/U'(c_{t0}) · (1+ρ)^−(t−t0) · ΔC_t ]  /  pulse_tonnes

Baseline and pulsed runs share a seed (**common random numbers**), so the difference is purely
the pulse's physical effect — deterministic and clean.

```bash
SCC_YEARS=30 SCC_SAMPLES=50 python3 scripts/run_scc.py
```

**Results** (default 2026 state, 30-year horizon): central **SCC ≈ $22/tCO₂**; the
probabilistic SCC (varying ECS, the damage coefficient, η, ρ, heat capacity, emissions scale)
is **right-skewed** — median ≈ $13, p95 ≈ $32 — the characteristic shape of modern IAM SCC
distributions (cf. RFF-SP / Rennert et al. 2022). The absolute level is **horizon-sensitive**:
a 30-year horizon truncates long-run damages, so these sit at the lower end of the DICE
(~$31) → EPA-2023 (~$190) range; a multi-century horizon raises the SCC substantially.

## Verification

`tests/test_welfare.py` (CRRA properties, discounting) and `tests/test_scc.py` (positive SCC
in plausible range, **marginality**: per-ton SCC invariant to pulse size, determinism, skewed
distribution). The SCC is linear in pulse size (5 Gt and 10 Gt give the same per-ton value),
confirming the marginal interpretation.

## Next

- Longer (multi-century) horizon for a full DICE-comparable SCC level.
- Optional welfare-optimization mode (optimal mitigation path maximizing W) for full DICE parity.
