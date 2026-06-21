# GIM17 Unique-Layer Influence Audit (F3, step 1)

GIM's differentiator is its social / geopolitical / cultural / institutional layers, but they
are the least validated. Before validating them against external data, the first honest
question is empirical: **does each input actually move any output?** A variable carried in
state and loaded from CSV but never affecting a trajectory is decorative complexity, not a
feature — and decorative richness is corrosive to an "objective" model.

`gim/influence_audit.py` perturbs each input (same shift for every agent) and measures the
normalised change in aggregate outputs (world GDP, social tension, trust, regime stability,
unemployment) after a short deterministic run.

## Finding: 7 of 8 Hofstede dimensions are inert

Influence scores (normalised aggregate-output change vs baseline, +20-point shift):

| dimension | influence | verdict |
|---|---|---|
| `idv` (individualism) | 2.9e-02 | **load-bearing** (feeds inequality sensitivity in the social block) |
| `pdi`, `mas`, `uai` | 0.0 | inert (code reads exist but feed dead/unused paths) |
| `lto`, `ind`, `traditional_secular`, `survival_self_expression` | 0.0 | inert (no effective use) |

So GIM carries **8 cultural dimensions but only 1 measurably affects any outcome.** The
load-bearing *categorical* cultural variable is `regime_type` (Democracy/Autocracy), used
substantially in geopolitics (conflict targeting) and decision-making (`actions.py`) — that one
is real. The continuous Hofstede vector is almost entirely decorative.

## Recommendation (for F3)

Two honest options, not silently leaving decorative inputs:

1. **Wire in the theory-supported dimensions** with grounded, validated linkages, e.g.
   `uai` (uncertainty avoidance) → risk aversion → savings / policy caution;
   `lto` (long-term orientation) → savings & R&D shares;
   `pdi` (power distance) → institutional quality / inequality;
   then validate each link's sign and magnitude against cross-country evidence.
2. **Remove** the dimensions that have no defensible, testable linkage, rather than carry
   complexity that implies predictive content the model does not have.

The audit test (`tests/test_influence_audit.py`) guards the finding: if a dimension is later
wired in, the test flips and forces the docs/validation to be updated.

## Next F3 steps

Same influence audit applied to the institutional and geopolitical inputs; then external-data
validation (UCDP/ACLED conflicts, V-Dem / regime-transition, Global Sanctions Database) with
skill-vs-base-rate scoring, mirroring the climate/economics benchmarks.
