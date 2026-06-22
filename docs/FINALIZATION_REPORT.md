# GIM17 Phase 5 — Finalization Report (June 2026)

Capstone for the staged finalization run. What was done, what was found, what remains. See
`docs/ROADMAP.md` for current standing + next steps, `docs/RE_ANCHOR.md` for the headline-activation
decision, and the per-area docs.

## Decisions executed

1. **Staged calibration** (keep the validated golden as headline; calibrate the default-off
   channels; defer joint activation to an explicit re-anchor).
2. **Culture: wire 3, remove 4.** Wired `pdi/uai/lto`; removed `mas/ind/traditional_secular/
   survival_self_expression`; kept `idv` + `regime_type`.
3. **F3 on real datasets** (World Bank live; UCDP/SWIID/CINC/SIPRI/GSDB via local bulk).
4. **Git repaired first.**

## Per-stage outcome

| Stage | Outcome | Commit |
|---|---|---|
| 0 git | Corrupted index + stale locks repaired losslessly (494/494 files matched HEAD). | `b6a571e`* |
| 1 data | Ingestion pipeline (WB WDI+WGI live; UCDP/SWIID/CINC/SIPRI/GSDB bulk parser) + source map. | `b6a571e` |
| 2 calib | Growth-damage SCC map recomputed; **golden bit-identical**; SCC-drift finding (below). | `b6a571e` |
| 3 culture | 4 inert dims removed; `pdi/uai/lto` wired (switchable, default-off); audit/test updated. | `8201328` |
| 4 F3 grounding | CINC grounding runs (CN 0.205/US 0.147/IN 0.096); conflict backtest harness (BSS). | `a50a838` |
| 5 stress audit | Threshold-gated inputs confirmed conditionally load-bearing (not decorative). | `f9648d7` |
| 6 verify | Suite green except 2 sandbox-only FS errors; this report. | (this commit) |

\* Stage 0/1/2 artifacts share commit `b6a571e`.

## Key findings

**1. SCC drifted up ~48% since the pre-Phase-4 note (the most important quantitative item).**
At modern RFF-SP/EPA-2023 2% discounting, 200-yr horizon, level-only:

| growth coeff | SCC now | pre-Phase-4 doc | drift |
|---|---|---|---|
| 0.0 | **$273** | $184 | +48% |
| 0.0003 | $473 | $314 | +51% |
| 0.0007 | $720 | $490 | +47% |

The Phase-4 additions (endogenous inflation/labour, Taylor rule, multi-GHG forcing, AR(1)
variability) lifted the whole curve. The level-only baseline now **overshoots the EPA/RFF central
(~$190) by ~45%**, so the F1 objectivity anchor no longer holds at the production default. The
joint re-anchor must re-fit the discount/damage anchor to bring level-only SCC back to the
EPA/RFF central before layering the growth-effect spread.

**2. Culture: only `idv` was ever load-bearing; the 4 removed dims were decorative.** After wiring,
with the channel on, all 4 retained dims register (idv 6.7e-2, pdi 2.7e-2, lto 2.6e-2, uai 2.5e-2);
off, only idv. The wiring is switchable and default-off, so the golden stays 1.026/1.606/0.134.

**3. The "inert" risk/geo inputs are conditionally load-bearing, not decorative.** Under stress:
`military_power` 6.3e-2 (active war, relative probe), `debt_crisis_prone` 1.6e-2 (debt stress);
`conflict_proneness` weak; `security_index` gates onset. `military_power` is a **relative** (CINC)
quantity — a uniform probe cannot see it. None removed.

## Validation status

* Golden backtest: **1.026 / 1.606 / 0.134** throughout (unchanged).
* Test suite: **~334 tests green**; the only failures are 2 `test_ui_server` cases that fail on the
  build sandbox's no-`unlink` filesystem (file-replacement in `results/`) — environment-only, they
  pass on a normal filesystem.
* New/updated tests: `test_influence_audit` (rewritten), `test_stress_audit` (new).

## What remains (honest)

1. **Joint re-anchor (production finalization).** Re-fit discounting/damage so level-only SCC
   returns to the EPA/RFF central (~$190 @ 2%/200y), then turn on the validated default-off channels
   together — growth-effect damages, fat-tailed crisis severity, `CULTURE_SOCIAL_LINKS`, CINC-grounded
   `military_power` — and re-anchor the golden to the new dynamics. This is the single remaining
   "activation" decision the staged plan deliberately isolated.
2. **F3 external validation needs the bulk downloads.** Run `scripts/ingest_external_data.py` locally
   to pull UCDP/SWIID/CINC/SIPRI/GSDB, then `scripts/conflict_backtest.py` yields the actual
   skill-vs-base-rate (BSS/AUC). The World Bank anchors are reachable; the bulk archives are not from
   a restricted sandbox.
3. **F2 economics depth** (nested-CES + SFC private finance) and **land-use CO₂** remain the large
   structural items (separate efforts; each re-anchors the golden).
4. **Conflict-onset generativity.** Rule-based policy does not self-generate war onsets; onset realism
   (vs UCDP) is a modelling item beyond input-scoring.

## Push note

All work is committed on branch `GIM17` (through `a50a838` + this report). The build sandbox has no
GitHub credentials, so `git push origin GIM17` must be run from your machine to publish.
