# Where the model stands and where it should go next

A candid assessment of the finished version 17: what is solid enough to use, what the real
limitations are, whether they block using the model, and the priority order for further work.

## Current standing

**Solid and validated.**
- Economy reproduces 2015–2023 national-income history; the headline now uses the objective
  capital–energy-substitution (nested-CES) production core with full price/balance closure, which
  improved the fit (GDP error 1.03→0.59, CO₂ 1.61→1.15, temperature 0.135).
- Climate matches the mainstream scientific assessment (temperature sensitivity, the 1990–2023
  warming and carbon record).
- Cost of carbon is in the modern consensus range (~$140/tCO₂ at modern 2% discounting), with the
  growth/discounting sensitivity carried and documented explicitly.
- Government finance is strictly accounting-consistent, including through debt crises; the private
  side now carries a closed stock-flow-consistent bank balance sheet (money = deposits = loans).
- The distinctive social / political / geopolitical / cultural layers are validated to the honest
  bar for low-signal domains: the conflict-risk measure clearly beats a naive base rate
  (AUC ≈ 0.74, Brier skill ≈ +0.14) against the standard armed-conflict record.
- A dedicated weak-signal detection module (Mahalanobis joint-state anomaly + structural break +
  critical slowing-down) supports what-if / early-warning analysis (`gim/weak_signal.py`).
- Everything rides on real uncertainty machinery: ensembles, sensitivity analysis, history
  matching, skill scoring.

**Known limitations (all documented, none hidden).**
1. ~~**No full price/balance closure.**~~ **[Resolved.]** The headline now closes the energy and
   capital markets through prices, with a full closed bank balance sheet (money = deposits = loans).
   Full general-equilibrium clearing of *all* markets is still not attempted (a deliberate
   non-equilibrium stance), but the price/balance closure the model lacked is now in the base.
2. **Climate benchmarks settled by evidence-based decisions (not exhaustively forced).** The
   non-CO₂ forcing keeps the calibrated net as the headline (the AR6 central over-warms the validated
   record), the strongest carbon-cycle feedbacks stay ensemble-only (deterministic feedback explodes
   the cost-of-carbon), and the cost-of-carbon is reported with its growth/discounting sensitivity
   rather than tuned to a target. See `docs/climate/CLIMATE_BENCHMARKS.md`.
3. ~~**The economy's production core is simple.**~~ **[Resolved.]** The headline now uses a
   calibrated capital–energy-substitution (nested-CES) core with cost-minimising energy demand; the
   remaining economic gap is market clearing (item 1 above), not the production recipe.

## Are these limitations blockers for using the model?

**No, not for the model's intended use.** The intended use is scenario exploration and
uncertainty-aware comparison ("what tends to happen, and how confident can we be"), not pinpoint
multi-year forecasting — which no credible global model achieves anyway. For that purpose:

- The **lack of full market clearing** matters for questions that hinge on precise relative-price
  equilibria. For broad trajectories and the climate–economy–society interactions the model is built
  for, gradual price adjustment is a legitimate modelling stance (the respected macro-econometric
  models make the same choice deliberately). It is a depth limitation, not a correctness flaw.
- **Climate-benchmark completeness** is already at the headline standard; the missing pieces are
  uncertainty extras, not defaults that would mislead a user.

So these are directions for *deepening* the model, not barriers to *using* it.

## Is the economy too simple? (the honest answer)

**Partly yes, and the instinct is right — with three important qualifications.**

1. **For this class of model, a capital–labour–energy production formula is the mainstream choice,
   not an outlier.** The canonical global climate-economy models (the DICE/RICE/FUND family) use the
   same textbook production form with exogenous productivity. So at the supply-core level the model
   is in standard company, and — unlike those models — it has been validated against a decade of real
   income data.

2. **What usually makes such a core feel "too simple" — that it can't represent substituting away
   from energy when energy gets expensive — has already been addressed.** The model now has the
   capital-versus-energy substitution channel wired into emissions: a carbon price raises the
   effective energy price, the cost-minimising mix shifts away from energy, and emissions fall. That
   response was validated against the empirical record of carbon-pricing schemes and lands in the
   right range. So the *policy-relevant* weakness of a bare textbook core is largely closed already.

3. **Against the model's own ambition, the economy is nonetheless the weakest of the strong layers.**
   The model's distinctive value — sovereign finance, endogenous inflation and unemployment, the
   geopolitical and social coupling — is genuinely ahead of standard climate-economy models. The
   production backbone is the conventional, validated part; the value is in the coupling. The
   general-equilibrium research models use a richer nested production structure with calibrated
   substitution and full market clearing, and that is the bar if the goal is to match them on the
   pure-economics axis.

**Verdict.** The simple core is defensible and not a blocker for use, and the single most important
consequence of its simplicity (the carbon-price response) is already handled. But if the economy is
to be brought fully up to the level of the rest of the model, the production side should be deepened
— and that is the top economic priority below.

## Priority order for further development

1. **[DONE] Activate the richer production structure (capital–energy substitution) in the supply
   core.** The calibrated (base-normalized) nested-CES core is now the headline, with energy demand
   derived from cost minimisation. It reduces exactly to the old core at the base point, so
   activation preserved the calibration — and it *improved* the historical fit (GDP RMSE 1.03→0.63,
   CO₂ 1.61→1.11). The "too simple production core" critique is closed at the structural level.
2. **[DONE] Market clearing for the energy and capital markets.** Both now clear by price in the
   headline (energy demand and investment respond to the energy price and the cost of capital);
   activated as base with the capital-clearing sensitivity calibrated so the fit is preserved/improved
   (GDP 0.63→0.59). This is the price/balance closure the model had been missing.
3. **[DONE] Full private banking / money.** The private side now has a closed bank balance sheet —
   every loan creates a matching deposit, broad money = deposits = loans (enforceable identity), on
   top of the strict government-debt accounting. Behavioural money→price transmission is a small
   remaining calibratable extension.
4. **[DONE] Close the climate-benchmark gaps by evidence-based decisions.** Non-CO₂ forcing keeps the
   calibrated net as the headline (AR6 central over-warms the validated record); carbon-cycle
   feedbacks stay ensemble-only (deterministic feedback explodes the cost-of-carbon); the
   cost-of-carbon is reported with its growth/discounting sensitivity rather than tuned to a target.
   See `docs/climate/CLIMATE_BENCHMARKS.md`.
5. **Forward-looking expectations** for investment and saving (or a documented defence of the current
   backward-looking choice). *Partially addressed* by SSP2-anchored forward growth; the behavioural
   expectations channel remains future work.
6. **[DONE — calibrated mechanism] Stronger growth foundations.** The long-run productivity drivers
   are now made explicit and calibrated (E4.2, `docs/GROWTH_FOUNDATIONS.md`): a Jones semi-endogenous
   R&D-**stock** TFP-growth channel calibrated on the World Bank 47-country panel (R&D-stock intensity
   is a significant positive growth driver conditional on convergence, SENS≈0.058; the naive slope is
   a frontier confound), and SSP1–5 forward-drift presets grounded on the published SSP marker
   GDP-per-capita pathways (reproducing the 1.0%–2.8% growth envelope). Both ship **switchable and
   off/SSP2-default** — golden-safe; headline activation of the R&D-stock core remains a deliberate
   re-anchor decision. Forward growth was already SSP2-anchored with GDP skill-vs-naive reported.

Items 1–4 (the objective production core + full price/balance closure + climate-benchmark decisions)
are **done and now the base model**. Items 5–6 are partially addressed refinements (forward-looking
behavioural expectations and a fuller growth foundation), documented as future work. None is a
prerequisite for using the model today for its intended scenario-and-uncertainty purpose.
