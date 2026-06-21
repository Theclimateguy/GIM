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

## Fuller picture: risk / geo / tech inputs (baseline scenario)

Extending the audit to the risk/geopolitical/technology inputs (12-yr calm baseline):

| input | influence | reading |
|---|---|---|
| `risk.regime_stability` | 1.1e-01 | load-bearing |
| `society.inequality_gini` | 6.7e-02 | load-bearing |
| `risk.water_stress` | 3.3e-02 | load-bearing |
| `culture.idv` | 2.9e-02 | load-bearing |
| `risk.conflict_proneness` | 5.3e-04 | weak in baseline |
| `risk.debt_crisis_prone`, `technology.security_index`, `technology.military_power` | 0.0 | **threshold-gated** (see caveat) |

**Critical caveat — baseline vs stressed.** The audit measures influence in the *default calm
scenario*. Inputs that gate **threshold/crisis dynamics** — `military_power`, `security_index`,
`debt_crisis_prone`, and largely `conflict_proneness` — are inert here only because no
war/debt-crisis fires in a 12-year calm run. They are **conditionally load-bearing** and must be
re-audited under a *stressed* scenario (forced conflict / debt stress) before any conclusion.
This is categorically different from the 7 Hofstede dimensions, which are inert because they are
**not effectively wired into any dynamics at all** (the grep confirms 0 effective reads for
lto/ind/traditional_secular; the pdi/mas/uai/survival reads feed dead paths). Only the Hofstede
vector is *decorative*; the threshold-gated inputs are real but scenario-dependent.

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
