# AUDIT_GIM14

Date: 2026-03-15  
Repo: `GIM_14`  
Branch: `GIM14`

Audit method:
- code walk over `gim/core/`, `docs/`, manifests, and tests
- runtime checks with `python3 -m unittest discover -s tests -v`
- targeted smoke scenarios for planes `3a-3e`
- observation dump on a 20-agent world and manifest/hash verification

## PASS

- `1a` Import graph for `gim/core/*` is acyclic. No cycles were detected, and the yearly orchestration still sits in `simulation.py` above the domain modules.
- `1c` `build_observation()` is side-effect free. Deep-copy comparison on a 20-agent world returned `world_mutated=False`.
- `4b` No hidden leakage from dataclass-private attrs was found in observation JSON. `_gdp_prev` does not leak through `asdict()`.
- `4c` Summary strings only include active crises. Watch flags with `active_years=0` are excluded from the summary path.
- `2b` Climate dynamics are internally coherent. Carbon stock is updated through explicit pools with decay, and the hot-path smoke test stayed materially warmer than the control after 5 steps: `2.5842C` vs `1.2924C`.
- `2c` Structural decarbonization is multiplicative and path-dependent. In the audit run, emissions intensity fell monotonically over the first 5 policy-on steps: `0.239808 -> 0.191161`, and stored structural progress never decreased: `1.09 -> 8.45`.
- `2d` Crisis persistence semantics from P1 are implemented: onset is harsher than persistence, counters are capped, and counters reset on recovery. This is also covered by `tests/test_crisis_persistence.py`.
- `2e` TFP endogenous growth includes the intended three channels: drift, R&D, and trade-linked diffusion.
- `3b` Climate-to-economy cascade works end-to-end. After 5 steps, the hot world produced lower GDP and higher debt stress than the cool control: GDP `2.0231T` vs `2.0953T`, debt/GDP `0.4532` vs `0.4320`.
- `3c` War and sanctions cascade works end-to-end. In the audit scenario, actor `A` entered war on step 1, had `sanctioning_count=2` on steps 1-3, average trade intensity fell `0.4500 -> 0.3777` by step 2, GDP fell `2.0000 -> 1.1829`, and the step-2 observation contained `regime_crisis`, `active_war`, and `sanctions_pressure`.
- `3d` Negative control is stable. A Norway-like agent ran 20 steps with `crisis_flags=[]` on every step and average GDP growth `+1.75%`.
- `5c` State artifact manifest is synchronized with the operational CSV. `state_csv_sha256` matches the actual file hash and the row count is `57/57`.
- `6d` The test suite is green. `105` tests passed and `3` tests were skipped for optional dependency paths (`requests` and `scipy`), not because of breakage.

## WARN

- `1b` Single-writer state ownership is not enforced. Representative examples:
  - `economy.gdp` is written in [gim/core/economy.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/economy.py#L31), [gim/core/actions.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/actions.py#L74), [gim/core/geopolitics.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/geopolitics.py#L84), and [gim/core/social.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/social.py#L217).
  - `economy.capital` is written in [gim/core/economy.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/economy.py#L28), [gim/core/climate.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/climate.py#L260), [gim/core/geopolitics.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/geopolitics.py#L253), and [gim/core/social.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/social.py#L176).
  - `trust_gov` and `social_tension` are written in [gim/core/social.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/social.py#L120), [gim/core/actions.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/actions.py#L75), [gim/core/geopolitics.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/geopolitics.py#L91), [gim/core/climate.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/climate.py#L280), and [gim/core/institutions.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/institutions.py#L352).
  This does not break runtime behavior today, but it violates the stated ownership criterion and makes calibration/debugging harder.
- `1a` The import graph is acyclic, but it is not exactly the target topology from the spec. [gim/core/calibration_params.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/calibration_params.py#L3) depends on `state_artifact`, so `calibration_params` is not a true zero-dependency leaf.
- `2a` The methodology doc is stale relative to code. [docs/MODEL_METHODOLOGY.md](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/docs/MODEL_METHODOLOGY.md#L857) still states `E^0.10`, while [gim/core/economy.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/economy.py#L35) uses `GAMMA_ENERGY = 0.07`. The doc also implies `_scale_factor` is part of initialization, but the actual initialization is lazy inside [gim/core/economy.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/economy.py#L54).
- `2f` Credit rating does not feed borrowing costs. [gim/core/credit_rating.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/credit_rating.py#L126) computes a rating and zone from macro, social, war, and sanction inputs, but [gim/core/economy.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/economy.py#L77) never reads `credit_rating` or `credit_zone` when setting the effective interest rate. The feedback loop is one-way.
- `3a` The canonical debt-spiral smoke point from the spec does not persist under current semantics. In the audit run with `debt/GDP=1.25`, crisis started on step 1, but onset moved debt/GDP to `0.7585`, so the debt crisis cleared on step 2. Persistence only appeared for much more extreme starting ratios (`~3.0x GDP` in the audit run). The core reason is the onset haircut in [gim/core/social.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/social.py#L215), where debt is multiplied by `0.60` while GDP is multiplied by `0.90`.
- `4a` Observation completeness is only partial for some crisis types. The observation exposes debt, trust, tension, and war indicators correctly, but it does not expose an explicit climate damage multiplier and it does not expose inbound sanction state by neighbor. See [gim/core/observation.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/observation.py#L15), [gim/core/observation.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/observation.py#L51), and [gim/core/metrics.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/metrics.py#L117).
- `4d` Observation payload is above the target budget. The average serialized observation size for a 20-agent world is `9599.5` bytes and the max is `9685`, which is above the `<8KB` criterion.
- `5a` Parameter provenance is strong in spirit but does not match the requested four-tag taxonomy exactly. [gim/core/calibration_params.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/calibration_params.py#L5) uses source-specific tags such as `[PWT10]`, `[WDI23]`, `[IPCC_AR6]`, `[BACKTEST]`, and `[XSECTION]` instead of collapsing everything into `[DATA]` / `[LIT]` / `[PRIOR]` / `[ALIAS]`. Under the requested scheme, `24` uppercase assignments are currently untagged, and [gim/core/calibration_params.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/calibration_params.py#L95) is an alias without an explicit `[ALIAS]` marker.
- `6a` Direct unit coverage is uneven. There are no direct tests for `actions`, `credit_rating`, `geopolitics`, `institutions`, `metrics`, `political_dynamics`, or `resources`.
- `6b` Historical backtest is not a strict golden-value anchor yet. [tests/test_historical_backtest.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/tests/test_historical_backtest.py#L21) checks an envelope and hard caps, not fixed values `GDP 1.073 / CO2 1.639 / Temp 0.136` with a narrow tolerance.
- `6c` Several regression categories from the spec are still missing: no test for observation size, no dedicated test for observation leakage beyond the current dataclass behavior, no 10-step debt-spiral integration test, and no explicit test that structural transition progress remains nondecreasing after policy removal.
- Policy integration errors are silently masked. [gim/core/simulation.py](/Users/theclimateguy/Documents/jupyter_lab/GIM_14/gim/core/simulation.py#L281) catches any exception from a policy function and falls back to `simple_rule_based_policy`, which is resilient at runtime but makes custom-policy failures easy to miss in integration work.

## OPEN

- Decide whether single-writer ownership is a real architecture goal. If yes, refactor state transitions behind sanctioned writer functions. If no, document the allowed writer set per field and assert only that `simulation.py` does not mutate state directly.
- Add the missing `credit_rating -> interest premium` link, or explicitly downgrade the design expectation for plane `2f`.
- Tighten the debt-crisis onset semantics if the canonical near-threshold debt spiral is supposed to persist. Today the debt haircut dominates the GDP haircut on the onset year.
- Introduce an observation-budget policy for 20-agent worlds: top-`k` neighbors, compressed global block, or separate planning/briefing views.
- Normalize provenance into the requested four-tag taxonomy, or generate a machine-readable mapping layer from the existing source-specific tags.
- Convert the backtest into a hard regression anchor with explicit golden values and narrow tolerances.
- Add the missing integration tests for observation size/leakage, debt spiral, and structural-decay persistence.
- Use the operational near-miss suite to calibrate the remaining crisis priors. The persistence family is still clearly marked as `[PRIOR]`.

## Parameter Provenance Snapshot

| Parameter | Current tag | Requested class | Source / note | Last update |
| --- | --- | --- | --- | --- |
| `ALPHA_CAPITAL` | `[PWT10]` | `[LIT]` | PWT production prior | `2026-03-14` `9fc0df43` |
| `BETA_LABOR` | `[PWT10]` | `[LIT]` | PWT production prior | `2026-03-14` `9fc0df43` |
| `GAMMA_ENERGY` | `[XSECTION]` | `[DATA]` | 2015 bundled cross-section fit | `2026-03-14` `7511b385` |
| `TFP_RD_SHARE_SENS` | `[BACKTEST]` | `[DATA]` | 2015-2023 historical backtest | `2026-03-14` `b1d4f6fb` |
| `EMISSIONS_SCALE` | `[GCP2023]` | `[DATA]` | Manifest-bound emissions scaling | `2026-03-14` `9fc0df43` |
| `DECARB_RATE_STRUCTURAL` | `[ARTIFACT]` | `[DATA]` | Manifest-bound structural rate, current value `0.052` | `2026-03-14` `9fc0df43` |
| `DECARB_RATE` | none on line | `[ALIAS]` expected | Alias of `DECARB_RATE_STRUCTURAL` | `2026-03-14` `9fc0df43` |
| `DEBT_CRISIS_DEBT_THRESHOLD` | `[PRIOR]` | `[PRIOR]` | Debt-crisis onset threshold | `2026-03-14` `9fc0df43` |
| `DEBT_CRISIS_PERSIST_GDP_MULT` | `[PRIOR]` | `[PRIOR]` | Debt-crisis persistence GDP drag | `2026-03-15` `fbb990f9` |
| `DEBT_CRISIS_PERSIST_TRUST_HIT` | `[PRIOR]` | `[PRIOR]` | Debt-crisis persistence trust hit | `2026-03-15` `16eeed94` |
| `DEBT_CRISIS_PERSIST_TENSION_HIT` | `[PRIOR]` | `[PRIOR]` | Debt-crisis persistence tension hit | `2026-03-15` `16eeed94` |
| `DEBT_CRISIS_MAX_YEARS` | `[PRIOR]` | `[PRIOR]` | Debt-crisis persistence cap | `2026-03-15` `fbb990f9` |
| `REGIME_CRISIS_PERSIST_GDP_MULT` | `[PRIOR]` | `[PRIOR]` | Regime-crisis persistence GDP drag | `2026-03-15` `fbb990f9` |
| `REGIME_CRISIS_PERSIST_CAPITAL_MULT` | `[PRIOR]` | `[PRIOR]` | Regime-crisis persistence capital drag | `2026-03-15` `16eeed94` |
| `REGIME_CRISIS_MAX_YEARS` | `[PRIOR]` | `[PRIOR]` | Regime-crisis persistence cap | `2026-03-15` `fbb990f9` |

Parameter-count summary:
- uppercase assignments inspected: `180`
- uppercase assignments with an explicit current-style tag: `156`
- uppercase assignments untagged under the requested scheme: `24`
- crisis persistence family remains entirely in `[PRIOR]`
