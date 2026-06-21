# GIM17 Phase 5 — Finalization Plan & Working Status (June 2026)

Objective, staged plan to take GIM17 from "methodology delivered, channels default-off" to a
finalized academic predictive instrument spanning economy, climate, social, war, geopolitics
and culture. Companion to `docs/PHASE5_FINALIZATION.md` (the honest delivered-vs-remaining
ledger). This document records the locked decisions and the per-stage work.

## Locked decisions (owner: Nazar, June 2026)

1. **Calibration scope = staged.** Keep the validated golden backtest (1.026 / 1.606 / 0.134)
   as the headline; first calibrate the default-off channel coefficients and ship them as an
   explicit level-vs-growth spread; the *joint activation + re-anchor* is a separate, later
   decision taken once the quantitative headline impact is visible.
2. **Inert blocks: wire 3, remove 4.** Wire the theory-supported Hofstede dimensions with
   validated links — `uai`→risk aversion / precautionary savings, `lto`→savings & R&D shares,
   `pdi`→institutional quality / inequality — and **remove** the 4 with no defensible linkage
   (`mas`, `ind`, `traditional_secular`, `survival_self_expression`). Keep `idv` (already
   load-bearing) and `regime_type` (the load-bearing categorical cultural var).
3. **F3 external data = real datasets.** Ground and validate against UCDP/PRIO (conflict),
   WGI (stability), SWIID (inequality), CINC/SIPRI (capability), GSDB (sanctions) — not
   literature priors alone. Honest bar: **skill vs base-rate**, not AR6-grade precision.
4. **Git first.** Repair the repository state before any model change.

## Stage map

| Stage | Work | Output | Status |
|---|---|---|---|
| 0 | Repair git (corrupted index + stale locks) | clean tree on branch GIM17 | **done** |
| 1 | External-data ingestion pipeline (F3) | `scripts/ingest_external_data.py`, `data/external/` | **pipeline delivered; live bulk pull pending local run** |
| 2 | Calibrate default-off channel coefficients (golden-preserving) | `scripts/calibrate_growth_damage_coeff.py`, `results/calibration/` | **done — surfaced SCC drift (below)** |
| 3 | Wire 3 culture dims, remove 4 inert | `gim/core/*`, CSV, influence-audit test | pending |
| 4 | F3 grounding + UCDP conflict backtest (skill-vs-base-rate) | `scripts/conflict_backtest.py` | pending (needs Stage-1 bulk files) |
| 5 | Stress re-audit of threshold-gated inputs | extended `gim/influence_audit.py` | pending |
| 6 | Whole-model verification + finalization report | green suite, regression, report | pending |

## Stage 0 — git repair (done)

The repo had a **corrupted/emptied index** (every tracked file shown as deleted/untracked) and
two stale empty lock files (`.git/index.lock`, `.lock`) from a crashed git process on 18 June.
Diagnosis was lossless: of 494 files in HEAD (`ce0ef04`), 0 missing on disk and 0 content
differences — i.e. **no real uncommitted work**; only the index was broken. Repaired with
`git reset --mixed HEAD` (rebuilds the index from HEAD, never touches the working tree) after
clearing the stale locks. Tree now clean on branch GIM17.

> Environment note: the working copy is on a mount that permits create/rename but **not unlink**.
> Deletions must be done via `git rm --cached` + move-to-trash or in-place truncation, not `rm`.

## Stage 1 — external data (pipeline delivered)

`scripts/ingest_external_data.py` pulls the World Bank anchors live (GDP, population, energy,
**SIPRI-sourced military expenditure**, Gini, and the four WGI governance series) for the GIM
ISO3 country set, and parses hand-downloaded bulk archives (UCDP, SWIID, CoW-NMC, SIPRI, GSDB)
placed in `data/external/raw/`. `data/external/SOURCES.md` is the full source map with download
URLs; `data/external/worldbank_sample_verified.csv` holds live-verified samples (e.g. US milex
$916.0 bn / Russia $109.2 bn for 2023, ex-WB API).

Reachability findings (June 2026): the World Bank API is reachable and clean for WDI; WGI is
reachable only via the versioned archive endpoint (source 57). UCDP's API host and the
SWIID/CINC/SIPRI/GSDB bulk archives are **not retrievable from the restricted build sandbox**
(no binary download) — they must be fetched on a normal network by running the script locally.

## Stage 2 — coefficient calibration (done) + a material finding

`scripts/calibrate_growth_damage_coeff.py` recomputes the SCC at modern RFF-SP/EPA-2023 2%
Ramsey discounting (ρ=0.2%, η=1.24), 200-yr horizon, as a function of the growth-effect damage
coefficient. Golden invariant confirmed intact at the default (1.0256 / 1.6059 / 0.1343).

**Finding — the SCC curve drifted up ~45–50% since the pre-Phase-4 F4 note:**

| `GROWTH_DAMAGE_TFP_COEFF` | SCC 200y (current) | SCC 200y (pre-Phase-4 doc) | drift |
|---|---|---|---|
| 0.0 (level-only) | **$273** | $184 | +48% |
| 0.0003 (moderate) | **$473** | $314 | +51% |
| 0.0007 (Burke/Kotz) | **$720** | $490 | +47% |

The Phase-4 channels added *after* the F4 note (endogenous inflation/labour via Phillips+Okun,
Taylor-rule monetary policy, multi-GHG non-CO₂ forcing, AR(1) temperature variability) shifted
the whole SCC curve up. Consequence: the **level-only baseline ($273) now overshoots the
EPA-2023 ($190) / RFF-SP ($185) central by ~45%** — the F1 objectivity anchor no longer holds at
the production default. This is precisely the re-anchor signal the *staged* plan was designed to
surface **before** flipping any channel on. Ledger: `results/calibration/growth_damage_coeff.json`.

**Implication for the activation decision:** the joint re-anchor (Stage toward production
finalization) should re-fit the discounting/damage anchor so the level-only SCC returns to the
EPA/RFF central, *then* layer the growth-effect spread on top — otherwise the model ships an SCC
biased ~45% high relative to the modern benchmark it claims to match.

## Remaining stages (concrete next steps)

- **Stage 3 (culture):** in `data/agent_states_operational*.csv` drop columns
  `mas, ind, traditional_secular, survival_self_expression`; add validated links for `uai`
  (→ savings/risk premium), `lto` (→ R&D & savings shares), `pdi` (→ institutional-quality /
  inequality sensitivity) in the economy/social blocks; update `gim/influence_audit.py` +
  `tests/test_influence_audit.py` so the 3 newly-wired dims register as load-bearing and the
  removed ones are gone. Re-confirm the golden (culture is conflict/social-gated; expect ~no move).
- **Stage 4 (F3 validation):** run `scripts/ingest_external_data.py` locally; anchor initial
  states (WGI→`regime_stability`, SWIID→`inequality_gini`, CINC→`military_power`); build
  `scripts/conflict_backtest.py` scoring GIM conflict onset against UCDP 1990–2023 with
  **skill vs the empirical base rate** (the geopolitics analogue of the climate backtest).
- **Stage 5 (stress re-audit):** re-run the influence audit under a *forced* conflict/debt-stress
  scenario to confirm `military_power`, `security_index`, `debt_crisis_prone`,
  `conflict_proneness` are conditionally load-bearing (not inert) before any removal.
- **Stage 6 (verification):** full suite green, golden regression, SCC/skill regression in CI,
  and the finalization report; ideally an independent subagent verification pass.

## Honest bounds

The unique social-geopolitical-cultural layers will never reach AR6/PWT identifiability —
conflict and unrest are intrinsically lower-signal. The defensible finalization bar there is
skill-vs-base-rate, transparent priors, and removal of decorative complexity — not point
prediction. The economy/climate cores are benchmark-grade; the SCC re-anchor (Stage-2 finding)
is the most important open quantitative item for the "objective model" claim.
