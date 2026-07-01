# GIM18 Stressed-Scenario Influence Audit (F3 / Stage 5)

The baseline influence audit (`docs/UNIQUE_LAYER_AUDIT.md`) runs a *calm* 12-year path and finds
`military_power`, `security_index`, `debt_crisis_prone`, `conflict_proneness` inert. The honest
caveat there was that this is a **scenario artefact**: those inputs gate threshold/crisis dynamics
that never fire when nothing is stressed. Before treating them like the decorative Hofstede dims,
they must be re-audited under stress. `gim/stress_audit.py` does this.

## Method

`build_stressed_world` creates a stressed world: every agent gets elevated debt (debt/GDP ~1.4),
conflict-proneness and lowered security margin, plus **injected active wars** on 3 dyads (both
directions). Influence is then measured with the *correct probe* per input:

* `debt_crisis_prone`, `conflict_proneness` — **uniform** probe (every agent), like the base audit.
* `military_power`, `security_index` — these are **relative** (CINC-share) quantities. A uniform
  shift cancels in the belligerent power-ratio that drives war outcomes, so they require a
  **differential** (single-agent) probe. This is a measurement requirement, not a model defect.

## Result (deterministic; `tests/test_stress_audit.py`)

| input | influence (stressed) | probe | reading |
|---|---|---|---|
| `technology.military_power` | **6.3e-02** | single-agent | conditionally load-bearing (active war) |
| `risk.debt_crisis_prone` | **1.6e-02** | uniform | conditionally load-bearing (debt stress) |
| `risk.conflict_proneness` | 1.0e-04 | uniform | weak even under stress |
| `technology.security_index` | 0.0 | single-agent | gates conflict *onset*, not active-war outcomes |

Compare the calm base audit, where all four read ~0.

## Conclusion

The threshold-gated risk/geo inputs are **conditionally load-bearing, not decorative.**
`military_power` (under an active war) and `debt_crisis_prone` (under debt stress) move world
aggregates substantially; `conflict_proneness` is weak; `security_index` gates *onset* and needs an
onset scenario (not an already-injected war) to register. This is categorically different from the
4 removed Hofstede dimensions, which were inert because they were **not wired into any dynamics**.

**Decision: none of the threshold-gated inputs are removed.** Their predictive validation belongs
in an explicit conflict/debt scenario — i.e. the UCDP conflict backtest (Stage 4), not the
structural influence audit. `military_power`'s relativity also means the CINC grounding
(`gim/capability.py`) is the right representation: it is a share, and only relative differences
matter.

## Caveat

Wars do **not** ignite from elevated risk inputs alone under the rule-based ("simple") policy —
they had to be injected. So this audit measures the influence of the inputs *given* a crisis, not
the model's propensity to *enter* one. The latter (onset realism) is exactly what the UCDP
skill-vs-base-rate backtest is for.
