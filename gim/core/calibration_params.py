import math

from .state_artifact import ACTIVE_STATE_ARTIFACT

# Tag legend:
#   [PWT10] Penn World Tables 10.01
#   [WDI23] World Bank WDI 2023
#   [WEO25] IMF World Economic Outlook 2025
#   [IPCC_AR6] IPCC AR6 WG1/WG2
#   [DICE16] Nordhaus DICE-2016R2, used only where structure matches
#   [SIPRI23] SIPRI military spending database 2023
#   [GCP2023] Global Carbon Project fossil CO2 history used for emissions-scale refresh
#   [BACKTEST] Bundled 2015-2023 historical backtest calibration
#   [XSECTION] Cross-sectional identification on the bundled 2015 country slice
#   [PRIOR] Expert prior pending empirical calibration
#   [ARTIFACT] Pipeline-bound compiled-state artifact; only change via state rebuild

SOURCE_TAG_NOTES = {
    "PWT10": "Penn World Tables 10.01 cross-country medians and accounting priors.",
    "WDI23": "World Bank WDI 2023 world-average macro and fiscal shares.",
    "WEO25": "IMF World Economic Outlook 2025 debt and borrowing priors.",
    "IPCC_AR6": "IPCC AR6 physical climate parameters and carbon-cycle references.",
    "DICE16": "DICE-2016R2 parameters only where the equation family is structurally aligned.",
    "SIPRI23": "SIPRI military burden averages.",
    "GCP2023": "Global Carbon Project fossil CO2 history used to derive emissions scaling during manifest refresh.",
    "BACKTEST": "Historical backtest calibration against the bundled 2015-2023 GDP/CO2/temperature fixture.",
    "XSECTION": "Cross-sectional identification against the bundled 2015 country slice.",
    "PRIOR": "Expert prior in the current model, not yet empirically calibrated.",
    "ARTIFACT": "Pipeline-bound compiled-state artifact that must only change with a state rebuild.",
}

# Production block.
# [#19 returns-to-scale, 2026-07] The exponents sum to alpha+beta+gamma = 0.30+0.60+0.042 = 0.942,
# i.e. mild decreasing returns to scale (DRS, ~6%). This is a DELIBERATE, documented choice, and —
# crucially — it is NOT the hidden ~43% long-run output bias a textbook Cobb-Douglas reading would
# imply. GIM does not use the production function as an absolute output LEVEL: each country's
# `economy._scale_factor = gdp/gdp_potential` re-anchors the level at the base year (see economy.py),
# so the exponent SUM has no compounding level effect; growth is carried by TFP/capital/convergence
# dynamics, not by the scale term. Verified by experiment (test_returns_to_scale): renormalizing to
# CRS (sum=1.0) moves 2100 global GDP by only ~-7% (gamma->0.10) to ~-9% (beta->0.658) — small, and the
# sign/size depend on which factor absorbs the renormalization AND on the damage/growth regime, versus
# the issue's predicted -43%. The 2015 level is bit-identical regardless of the exponent sum. DRS is the
# reduced-form proxy for unmodelled overhead/congestion/governance costs (Basu & Fernald 1997). The
# energy share gamma=0.042 sits inside the capital-energy / energy-augmented production literature
# range [0.03, 0.06] (Koetse, de Groot & Florax 2008, Energy Economics 30:2206). Factor shares are
# from PWT10 (labor ~0.63, capital ~0.33, energy residual ~0.04; Feenstra-Inklaar-Timmer 2015).
ALPHA_CAPITAL = 0.30  # [PWT10]
BETA_LABOR = 0.60  # [PWT10]
GAMMA_ENERGY = 0.042  # [BACKTEST] Stage B/C robust rolling baseline (2015-2023); energy share in Koetse 2008 [0.03,0.06].
# [F2.1] Production function. Default (NESTED_CES=False) is the validated Cobb-Douglas K^a L^b E^g
# core -> golden bit-identical. NESTED_CES=True uses a KLE nest (inner CES on capital-energy with
# substitution CES_SIGMA_KE, outer Cobb-Douglas vs labour) that reduces EXACTLY to Cobb-Douglas at
# SIGMA_KE=1; below 1, capital and energy are gross complements so carbon-price/energy-cost
# responses are meaningful. Activated at the economics re-anchor (level still anchored by _scale_factor).
NESTED_CES = True  # [F2.1/E3.1] HEADLINE: calibrated nested-CES (KLE) production core (objective economics).
CES_SIGMA_KE = 0.4  # [F2.1] capital-energy substitution elasticity (KLEM ~0.3-0.5).
# [E3.1] Nested-CES emissions normalization. The capital-energy substitution shifts the cross-country
# output composition, which shifts aggregate emissions (output is redistributed across countries with
# different carbon intensities). This dedicated multiplier re-anchors aggregate emissions to the 2015-2023
# record WITHOUT touching the data-derived, artifact-bound EMISSIONS_SCALE (which stays at its manifest
# value). Only applied when NESTED_CES is on; calibrated so the CO2 backtest is minimized (~1.11).
NESTED_CES_EMISSIONS_NORM = 1.056  # [BACKTEST] equivalent to EMISSIONS_SCALE 0.9755->1.03 under nested-CES.
# [D1-real] CES cost-min energy-demand -> emissions coupling. The inner KE CES implies a
# cost-minimizing energy demand per unit output that falls with the (carbon-inclusive) energy price
# with elasticity sigma_KE: (E/Y) ∝ p_E^(-sigma_KE). Since fossil emissions track energy use,
# emission intensity inherits the same elasticity. This is the channel that makes carbon/energy
# prices reduce emissions via substitution (the point of D1) -- derived from producer theory, not
# imposed. Switchable; at the reference price (p_E = ENERGY_PRICE_REF) the factor is 1 -> golden-safe.
ENERGY_PRICE_SUBSTITUTION = False   # [D1] route the energy price into emission intensity via sigma_KE.
ENERGY_PRICE_REF = 1.0              # [D1] reference (calibration) energy price; factor==1 here.
CARBON_PRICE_USD_PER_TCO2 = 0.0     # [D1] optional explicit carbon price ($/tCO2); 0 => no policy.
ENERGY_DEMAND_PRICE_RESPONSE = True  # [E3.1] HEADLINE: cost-minimizing energy demand: energy consumption
                                    # responds to the energy price with elasticity CES_SIGMA_KE
                                    # (E ∝ p_E^-sigma). Default off -> golden-safe; activated with the
                                    # nested-CES core. sigma_KE~0.4 also matches empirical short-run
                                    # energy-demand price elasticity (~0.3-0.4).
CARBON_PRICE_PASSTHROUGH = 0.003    # [D1] fractional economy-wide energy-price rise per $1/tCO2
                                    # (~15% at $50: plausible mid for mixed energy carbon-intensity).
                                    # With sigma_KE=0.4 this yields a LONG-RUN ~5.5% emission cut at
                                    # $50/tCO2 -- above the observed SHORT-RUN ETS effect (~1-2.5%);
                                    # the gap is the adjustment-friction wedge (GIM = frictionless
                                    # equilibrium substitution). See docs/climate/CARBON_PRICE_CHANNEL.md.
# [F2.2] Partial market clearing for resource (energy/food/metals) prices. Default OFF keeps the
# validated sluggish tatonnement (partial price adjustment, step PRICE_ADJUST_ALPHA) -> golden
# bit-identical. When ON, the price jumps within-period to the level that equates a constant-
# elasticity demand to the fixed supply (p* = p_cur*(demand/supply)^(1/eps)) — i.e. the market
# clears each step. Bridges toward the GE class for the energy market without a full CGE; the
# non-equilibrium default is a deliberate, defended stance (E3ME).
MARKET_CLEARING = True               # [F2.2/E3] HEADLINE: within-period resource price clearing (full closure).
MARKET_DEMAND_ELASTICITY = 0.4       # [F2.2] price elasticity of resource demand (energy ~0.3-0.5).
PRICE_ADJUST_ALPHA = 0.15            # [F2.2] sluggish-adjustment step for the (non-clearing) fallback rule.
# [F2.3] Resource-price equilibrium anchor. Both price rules above (clearing and the sluggish
# tatonnement fallback) are a multiplicative walk with NO restoring force: any *persistent* one-
# directional supply/demand imbalance compounds the price to a clamp bound and pins there
# (energy -> ceiling as reserves deplete; food/metals -> floor under structural over-supply). This
# adds a weak log-space mean-reversion toward a per-resource anchor (the calibration reference price,
# captured once at the base year) AFTER the walk step, so no single persistent imbalance can pin a
# price: scarcity still moves it (the pull is weak) but it settles at a finite level instead of the
# clamp. At the anchor the pull term is exactly zero, so the base-year price update is unchanged
# (golden-safe on a static base year). Set 0.0 to recover the exact pre-anchor walk.
PRICE_ANCHOR_PULL = 0.15            # [F2.3] per-year share of the log-gap to the anchor pulled back.
# [F2.4] Resource demand growth. Base-year resource consumption was carried forward as a frozen
# constant (only the price-response terms nudged it), so food demand never tracked population and
# metals demand never tracked income -> permanent over-supply -> price pinned to the floor.
# Consumption now grows each year with realized population and per-capita income growth, with per-
# resource elasticities. Energy keeps its own cost-min demand path (elasticities 0 here). At zero
# pop/income growth the factor is 1, and the first (base) year has no prior to grow from -> golden-
# safe on a static base year. The per-year factor is clamped to a sane band so a recovery/crisis
# swing can't shock demand.
RESOURCE_DEMAND_GROWTH_MIN = 0.8    # [F2.4] per-year demand-growth factor floor.
RESOURCE_DEMAND_GROWTH_MAX = 1.25   # [F2.4] per-year demand-growth factor ceiling.
FOOD_DEMAND_POP_ELASTICITY = 1.0      # [F2.4] calories track population ~1:1.
FOOD_DEMAND_INCOME_ELASTICITY = 0.25  # [F2.4] richer diets add a little (Engel: food is income-inelastic).
METALS_DEMAND_POP_ELASTICITY = 0.0
METALS_DEMAND_INCOME_ELASTICITY = 0.7 # [F2.4] material intensity rises sub-proportionally with income.

# [F-metals 2026-08-24] The base-year metals `production` in the state CSV is TOTAL market supply
# (it equals consumption at the base year). update_resource_stocks treated it as PRIMARY and then
# added recycled secondary supply on top, injecting a permanent oversupply of
# metals_recycling_rate x consumption from the first step onward -- supply 388.9 -> 565.5 in one
# year, D/S ~0.69 thereafter, price walking to its 0.30 floor while the observed World Bank index
# rose 55%. True => net recycling out of the base primary so year-one supply equals the loaded
# total. Default False => unchanged, golden bit-identical.
METALS_BASE_PRIMARY_NET_OF_RECYCLING = True  # [F-metals] ON: was a permanent ~45% supply glut.

# [F-buffer 2026-08-24] Cap on the price-damping buffer, in YEARS OF CONSUMPTION per resource.
# update_global_resource_prices damps the clearing price by how much standing stock is available
# to absorb a flow imbalance, but it reads `global_reserves`, which is not the same quantity for
# every resource: food carries ~0.05 years (~18 days of genuine carry-over stock -- and food is
# the one resource whose price validates against the observed World Bank index), while energy
# carries 50 YEARS, i.e. proven resources in the ground, which cannot clear a market within the
# year. The result is buffer_ratio -> 1 and an energy price frozen at 1.0 across the whole
# 2015-2023 window against an observed move of +62%.
# Anchors for the caps: IEA member countries are obliged to hold 90 days of net energy imports
# (~0.25 yr); exchange and producer inventories for base metals run a few weeks to a few months
# (~0.25 yr); FAO cereal stocks-to-use is ~30% (~0.30 yr, above the ~0.05 the fixture already
# implies, so food is left untouched by the cap).
# 0.0 => uncapped for that resource. ON at the anchored values below.
PRICE_BUFFER_YEARS_ENERGY = 0.25   # [DATA: IEA 90-day net-import stockholding obligation]
PRICE_BUFFER_YEARS_FOOD = 0.30     # [DATA: FAO cereal stocks-to-use ~30%; above the ~0.05 the
                                   #  fixture implies, so the cap leaves food untouched]
PRICE_BUFFER_YEARS_METALS = 0.25   # [DATA: exchange + producer inventories, weeks to months]

# [F-fx 2026-08-24] Share of world GDP represented by the sum of all agents' NET resource import
# bills. Resource quantities are physical and prices are indices, so their product is not
# commensurate with GDP -- yet the fx block divided it by GDP and read it as a ratio. Measured,
# the world sum of net import bills was 3190% of world GDP, ~300x too large, which is why
# fx_cover_months came out at a median of 0.053 months (1.6 days of import cover). fx_reserves
# are already in GDP units (median 13.9%, realistic), so only the trade side needs converting.
# Anchor: WTO 2022 world exports of fuels and mining products US$5.16tn (21% of world merchandise
# exports) plus agricultural products ~US$2.2tn, together ~7.4% of world GDP GROSS; the model
# carries NET positions, whose sum is a fraction of gross trade. 0.0 => disabled (raw units),
# golden bit-identical.
RESOURCE_TRADE_GDP_SHARE = 0.04

# [F-fx 2026-08-24] Months-of-import-cover is defined against TOTAL imports; the model carries
# only the resource bill. WTO 2022: fuels and mining products 21% of world merchandise exports,
# agricultural products ~9% -> resource goods are ~30% of merchandise trade, so total imports are
# roughly 3.3x the resource bill. 1.0 => unchanged.
IMPORT_COVER_TOTAL_MULTIPLIER = 3.3

# [F-fx 2026-08-24] Write the structural resource trade balance into economy.net_exports.
# Without it net_exports is written only by executed bilateral trade deals, which no scripted
# policy proposes, so the current account is identically zero and the fx-crisis trigger cannot
# fire in any deterministic run. False => unchanged, golden bit-identical.
STRUCTURAL_TRADE_BALANCE = True  # [F-fx] ON: the current account was identically zero without it.

# [F-fx 2026-08-24] Share of the current account that reaches official FX reserves. Nothing in
# the model accumulated reserves from a trade surplus, so once reserve cover fell below the
# crisis threshold nothing could rebuild it and the fx crisis was a permanent trap (measured mean
# duration 8.35 years against a real-world 1-3). Only part of the current account reaches
# official reserves; the rest is private capital flow the model does not carry. 0.0 => off.
FX_RESERVE_ACCUMULATION_SHARE = 0.0  # [F-fx] implemented, left OFF: economically right, but
                                     # without an exchange rate to correct the deficit it drives
                                     # the fx onset rate to 8% of agent-years against 3-5%
                                     # observed. Needs the FX block to carry a nominal rate first.

# [F-fx 2026-08-24] Share by which an agent's trade DEFICIT is compressed while an fx crisis is
# active -- the stand-in for the import compression a depreciation would produce, since GIM
# carries no nominal exchange rate. Without it a deficit country can never rebuild reserves and
# the fx crisis is a permanent trap. Empirical anchor: current-account reversals during currency
# crises run to several percent of GDP within a year. 0.0 => off.
FX_CRISIS_DEFICIT_COMPRESSION = 0.0

# [F-fx 2026-08-24] Make FX_CRISIS_MAX_YEARS actually bound the episode. It capped the counter
# but did not end the crisis, so an agent whose reserve cover never recovered stayed in an
# absorbing crisis state forever (measured mean duration 8.35 years against a real-world 1-3).
# False => unchanged, golden bit-identical.
FX_CRISIS_MAX_YEARS_TERMINATES = True  # [F-fx] ON: the bound now ends the episode.

# [F-fx 2026-08-24] Agents that cannot have a conventional currency crisis, because they do not
# issue the currency they use or because they issue a reserve currency. The fx trigger reads
# reserve cover, and these are precisely the agents that hold thin reserves BY DESIGN -- the
# United States carries the lowest reserve ratio in the whole set (0.86% of GDP) because it
# issues the reserve currency, and euro-area members hold little because the ECB holds it.
# Without this exemption the repaired trigger flagged Italy and Spain in 2016 in the historical
# backtest, which is a false positive against the record: neither had, or could have had, a
# currency crisis (Paper/revision/results/e17_fx_channel_validation.json).
# Euro area within the modelled set: AUT BEL DEU ESP FIN FRA IRL ITA NLD PRT (+ the AG_EUROPE
# aggregate, which is euro-dominated). Reserve-currency issuers: USA (USD), JPN (JPY), GBR (GBP),
# CHE (CHF). HKG runs a hard USD peg backed by reserves far above its monetary base.
# The model carries no monetary-union concept of its own; this list is the minimal stand-in and
# should become a state column if the FX block is ever given a nominal exchange rate.
# Matched against BOTH agent.id and agent.name, because the operational state uses ISO codes
# while the historical-backtest fixture uses C01..C20 with full country names.
FX_CRISIS_MONETARY_EXEMPT_AGENTS = [
    # euro area
    "AUT", "BEL", "DEU", "ESP", "FIN", "FRA", "IRL", "ITA", "NLD", "PRT", "AG_EUROPE",
    "Austria", "Belgium", "Germany", "Spain", "Finland", "France", "Ireland", "Italy",
    "Netherlands", "Portugal",
    # reserve-currency issuers and the HKD hard peg
    "USA", "JPN", "GBR", "CHE", "HKG",
    "United States", "Japan", "United Kingdom", "Switzerland", "Hong Kong SAR, China",
]
ENERGY_DEMAND_POP_ELASTICITY = 0.0    # [F2.4] energy demand handled by ENERGY_DEMAND_PRICE_RESPONSE.
# [F-energy 2026-08-24] Was 0.0 with the note "energy demand handled by
# ENERGY_DEMAND_PRICE_RESPONSE" -- but a price response is a one-time shift for a constant price,
# so energy demand grew with neither population nor income. Combined with static supply that made
# demand/supply exactly 1.0000 every year and froze the energy price at its initial value for the
# whole 2015-2023 window, against an observed World Bank move of +62%. Value anchored on the IEA
# intensity arithmetic: global primary energy intensity improved ~2%/yr over 2010-2019 and ~1.2%/yr
# over 2019-2023 against ~3%/yr world GDP growth, implying ~0.33-0.6. Taking the middle of that
# range rather than the value that best fits nine observations.
ENERGY_DEMAND_INCOME_ELASTICITY = 0.5
# [E3.2] Capital-market clearing. Investment responds to the price of capital: the gap between the
# marginal product of capital (return, ~ALPHA_CAPITAL*Y/K) and its cost (effective interest rate +
# depreciation). Anchored at each country's baseline gap so the calibration steady state is unchanged
# (golden-safe). When on, a rate/policy/debt shock that raises the cost of capital lowers investment
# -> capital -> output, propagating financial shocks through the capital price. Switchable (default off).
CAPITAL_MARKET_CLEARING = True       # [E3.2/E3] HEADLINE: capital-market clearing (full closure).
CAPITAL_CLEARING_SENS = 0.3          # [BACKTEST] investment elasticity to the (return - cost) gap;
                                     # calibrated to 0.3 so full closure preserves/improves the fit.
CAPITAL_CLEARING_MIN = 0.5           # floor on the investment multiplier.
CAPITAL_CLEARING_MAX = 1.5           # ceiling on the investment multiplier.

# [F2.3] Stock-flow-consistent private finance + financial accelerator (switchable; default OFF ->
# golden bit-identical). Private credit stock on top of the T1.1 sovereign identity; over-leverage
# damps credit appetite and raises a borrowing-rate premium (Bernanke-Gertler accelerator).
SFC_FINANCE = True                   # master switch. [E2.4 re-anchor] ACTIVATED in headline (golden-safe).
SFC_INIT_LEVERAGE = 1.0              # initial private_debt / GDP (world private credit ~1x GDP).
SFC_CREDIT_APPETITE = 0.10           # gross new credit as a share of GDP / yr (pre-accelerator).
SFC_REPAY_RATE = 0.08               # annual repayment as a share of outstanding private debt.
SFC_LEVERAGE_REF = 1.5              # leverage above which the accelerator bites.
SFC_ACCEL_SENS = 0.50               # credit-appetite damping per unit excess leverage.
SFC_PREMIUM_SENS = 0.04             # interest-rate premium per unit excess leverage.
SFC_PREMIUM_CAP = 0.10              # cap on the credit premium.

# [F2.5] Limited-foresight investment weight. 0.0 (default) = pure adaptive expectations -> golden
# bit-identical; >0 blends a one-step expected-return (recent GDP growth) signal into the savings
# rate. GIM's recursive/adaptive default is a defended ABM-macro stance (see docs/ECONOMICS_BENCHMARK
# D5); this provides a switchable forward-looking tilt for sensitivity analysis.
EXPECTATIONS_FORESIGHT = 0.0  # [F2.5] limited-foresight blend weight (0 = adaptive).
# [E4.3] Near-rational (model-consistent) expectations. When EXPECTATIONS_HORIZON>0, the forward-looking
# investment tilt sources its expected-growth signal from an H-step EVENT-FROZEN projection of the model
# (gim/core/expectations.py) rather than the backward Delta-gdp proxy -- a near-rational/level-1 forecast
# (a recursion guard makes the projection's own inner steps fall back to the adaptive rule). Default 0
# -> the operator never runs and no extra state is written -> golden bit-identical. The shared world-
# level forecast is recomputed every EXPECTATIONS_REFRESH_EVERY years (cost control; see the cost spike
# -- yearly is ~6x, every 5yr ~2x on a 200yr run). Design default-on value: HORIZON=3, REFRESH_EVERY=5.
EXPECTATIONS_HORIZON = 0          # forecast horizon in years (0 = off / pure adaptive). On-value: 3.
EXPECTATIONS_REFRESH_EVERY = 5    # recompute the shared world-level forecast every k years (1 = yearly).
# [E4.3] Weight on the model-consistent expected inflation in the Phillips anchor (labor_market.py):
# pi_expected = (1-w)*adaptive + w*forecast. Default 0 -> pure adaptive (golden). Grounded on-value
# ~0.65 = the forward-looking share of the HYBRID New-Keynesian Phillips curve (Gali & Gertler 1999;
# GGLS 2005: gamma_f ~ 0.6-0.7). NB activating it moves the inflation persistence away from the
# adaptive rho=0.5 that E4.1 validated, toward the hybrid-NKPC forward-looking regime -- a deliberate
# expectation-regime switch, hence off by default (the validated headline keeps pure-adaptive).
EXPECTATIONS_INFLATION_WEIGHT = 0.0
SAVINGS_BASE = 0.24  # [WDI23]
CAPITAL_DEPRECIATION = 0.05  # [PWT10]
SAVINGS_BASELINE_OFFSET = 0.70  # [PRIOR]
SAVINGS_STABILITY_SENS = 0.60  # [PRIOR]
SAVINGS_TENSION_SENS = 0.40  # [PRIOR]
SAVINGS_MIN = 0.05
SAVINGS_MAX = 0.40

# Welfare / social cost of carbon (Phase 3).
ELASTICITY_MARGINAL_UTILITY = 1.45  # [DICE16] eta: CRRA elasticity of marginal utility (DICE-2016R2)
PURE_TIME_PREFERENCE = 0.015        # [DICE16] rho: pure rate of social time preference per year (DICE-2016R2)
TECH_OUTPUT_SENS = 0.60  # [PRIOR]
GDP_ADJUST_SPEED_BASE = 0.30  # [PRIOR]
GDP_ADJUST_SPEED_GAP_SENS = 0.35  # [PRIOR]
OBS_MAX_NEIGHBORS = 8  # [PRIOR]
POLICY_LOG_DEPTH = 3  # [PRIOR] Visible action/outcome memory horizon for agent prompts.

# TFP block.
TFP_RD_SHARE_SENS = 0.30  # [BACKTEST] Stage B/C robust rolling baseline (2015-2023).
# [E4.2] R&D capital-stock (Jones semi-endogenous) growth channel. Default OFF -> the flow R&D-share
# form above is used (golden bit-identical). When RD_STOCK_GROWTH is on, TFP growth comes from the
# R&D-stock intensity (perpetual inventory of rd_spending) with diminishing returns (phi<1).
# CALIBRATED from the World Bank 47-country panel (2000-2023) via calibration/calibrate_growth_
# foundations.py; see docs/GROWTH_FOUNDATIONS.md. The panel VALIDATES the channel (conditional on
# catch-up convergence R&D-stock intensity is a significant positive growth driver, implied social
# return ~0.49 in the literature range; the naive no-convergence slope is negative -- a frontier
# confound) and pins the cross-country ELASTICITY phi (weakly identified -> fixed at the literature-
# standard 0.5; Jones 1995, Bloom et al. 2020). SENS is LEVEL-MATCHED to reproduce the validated flow-
# form mean R&D contribution (= SENS_flow*delta_R*X_bar^(1-phi)), NOT the raw regression slope -- a
# drop-in flow->stock form upgrade that preserves the growth level (the regression slope is relative
# to zero R&D and would double-count TFP_DRIFT). Channel stays OFF pending a deliberate headline
# re-anchor; the R&D channel is dormant in the 2015-2023 backtest, so the golden is unaffected.
RD_STOCK_GROWTH = False
RD_STOCK_DEPRECIATION = 0.15    # [LIT] R&D knowledge-stock depreciation (perpetual inventory; OECD/BLS ~0.15).
TFP_RD_STOCK_SENS = 0.0141      # [CALIBRATED] level-matched to the flow form at the WB-panel mean (phi=0.5).
TFP_RD_STOCK_ELASTICITY = 0.50  # [LIT/DATA] phi<1: diminishing returns; weakly identified, fixed at 0.5.
TFP_TRADE_SPILLOVER_SENS = 0.30  # [PRIOR]
TFP_DRIFT = 0.01  # [PRIOR] historical baseline TFP drift (calibrated to the 2015-2023 backtest).
# [E3.4/SSP] Forward (post-2024) baseline TFP drift anchored to SSP2 "middle of the road" (~0.018),
# so long-horizon projections (SCC, 2100) sit on a recognised scenario instead of the lower emergent
# rate. HEADLINE-ON; golden-safe because the 2015-2023 backtest is entirely in the historical window
# (year <= SSP_FORWARD_FROM_YEAR) and keeps TFP_DRIFT. See docs/climate/SCENARIO_ALIGNMENT.md (SSP_TFP_DRIFT).
SSP_FORWARD_GROWTH = True       # use the SSP2 forward baseline drift after SSP_FORWARD_FROM_YEAR.
SSP_FORWARD_FROM_YEAR = 2024    # last historical year (forward = strictly after this).
SSP_FORWARD_TFP_DRIFT = 0.018   # SSP2 baseline TFP drift (Dellink et al. 2017 / Riahi et al. 2017).
# [E4.2] SSP1-5 forward TFP-drift presets, GROUNDED on the published SSP marker GDP-per-capita
# pathways (Dellink et al. 2017 OECD ENV-Growth; IIASA SSP database). Derivation: take the published
# 2100 global GDP-pc levels (SSP5~$120k, SSP1~$77k, SSP2~$63k, SSP4~$46k, SSP3~$24k), back out the
# implied 2010-2100 per-capita growth (reproduces the published 1.0%-2.8% envelope), and scale the
# VALIDATED SSP2 drift (0.018) by each scenario's growth ratio to SSP2 (balanced-growth approximation:
# TFP-drift ratios track per-capita-GDP-growth ratios). Ordering SSP5>SSP1>SSP2>SSP4>SSP3. These are
# selectable forward SCENARIO presets, not a headline change: SSP_SCENARIO defaults to "SSP2" -> 0.018,
# reproducing the prior single forward drift (golden + forward unchanged). See docs/GROWTH_FOUNDATIONS.md.
SSP_SCENARIO = "SSP2"
SSP_TFP_DRIFT_PRESETS = {
    "SSP1": 0.020,  # Sustainability — high productivity growth (2.29%/yr GDP-pc).
    "SSP2": 0.018,  # Middle of the road (validated anchor; 2.07%/yr GDP-pc).
    "SSP3": 0.009,  # Regional rivalry — lowest growth (0.98%/yr GDP-pc).
    "SSP4": 0.015,  # Inequality (1.71%/yr GDP-pc).
    "SSP5": 0.024,  # Fossil-fueled development — highest growth (2.80%/yr GDP-pc).
}
TFP_DIFFUSION_SENS = 0.02  # [PRIOR]
# [GROWTH 2026-06] Conditional convergence (Barro-Sala-i-Martin catch-up): TFP growth rises with the
# log gap in GDP-per-capita to the frontier (the richest agent). Calibrated to the 2015-2023 real PPP
# cross-section (World Bank NY.GDP.MKTP.PP.KD): realgrowth = 0.0106 + 0.0093*log(frontier_pc/own_pc),
# R2=0.38; the frontier intercept ~1% is already TFP_DRIFT, so this term only adds the catch-up slope.
# Without it the model grew every country at the ~frontier ~1%/yr, badly under-shooting China/India
# (~5.7% real). The earlier 2015-state capital bug (cap/GDP 0.23x) masked this by ramping capital.
# [#13 2026-07] Externally VALIDATED. A conditional beta-convergence OLS (HC1) on the bundled WB
# real-PPP 2015-2023 cross-section (calibration/calibrate_tfp_convergence.py) gives a catch-up slope
# 0.0144 (SE 0.0039, 95% CI [0.0068, 0.022], R^2 0.44, n=20). The in-model 0.0093 lies INSIDE that CI
# and inside the acceptance band [0.005, 0.025], and is consistent with the cross-section convergence
# literature (Barro & Sala-i-Martin 1992 ~0.020; Mankiw-Romer-Weil 1992 ~0.018) and well below the
# Islam (1995) within-panel ~0.092. Kept at 0.0093 (the lower-CI, more conservative catch-up) rather
# than re-fitting a noisy 20-country sample; TFP_CONVERGENCE_SE documents the uncertainty for GSA (#18).
TFP_CONVERGENCE_SENS = 0.0093  # [DATA validated] catch-up slope per log-unit of GDP-per-capita gap to frontier.
TFP_CONVERGENCE_SE = 0.0039    # [DATA] HC1 standard error of the convergence slope (uncertainty propagation).
TFP_CONVERGENCE_GAP_CAP = 4.0  # cap the log gap so the poorest agents don't get an unbounded boost.
TFP_GROWTH_MIN = -0.05
TFP_GROWTH_MAX = 0.05
# Growth-effect climate damage (F4): warming above the 2023 baseline persistently lowers TFP
# growth (Burke et al. 2015 / Kotz et al. 2024), distinct from the level-effect output
# multiplier. DEFAULT 0.0 => OFF (golden backtest preserved). Reference "on" value ~0.001/degC
# gives a bounded persistent growth drag spanning toward the empirical growth-effect range.
# [#17 2026-07] Burke, Hsiang & Miguel (2015, Nature 527:235) growth-effect calibration. Their global
# pooled response implies a TFP-growth drag of ~0.0015/degC of warming above the optimum for already-warm
# economies; the on-value GROWTH_DAMAGE_TFP_COEFF=0.0015 reproduces that central drag. KEPT OFF by default
# (0.0): the level-effect vs growth-effect distinction is genuinely unsettled (Newell, Prest & Sexton 2021
# find data cannot discriminate), and turning it on is a large, contestable structural claim that would
# dominate the 2100 trajectory -- so it stays a documented, calibrated SWITCHABLE scenario, not headline,
# and the golden stays bit-identical. Sensitivity is reported in docs/climate/DAMAGE_FUNCTION.md.
GROWTH_DAMAGE_TFP_COEFF = 0.0  # [F4/Burke2015 on-value 0.0015] per-degC TFP-growth drag above 2023 baseline; 0 => off.

# Self-organized-criticality crisis severity (F5): make crisis shock DEPTH fat-tailed (power-law /
# Richardson) instead of fixed. The severity multiplier is mean-1, so the AVERAGE shock equals the
# existing fixed magnitude; only the tail changes. DEFAULT OFF (golden backtest preserved).
CRISIS_SEVERITY_POWERLAW = False  # [F5] enable fat-tailed crisis severity.
CRISIS_SEVERITY_ALPHA = 1.5       # [RICHARDSON] power-law exponent for event severity (~1.5-1.6).
CRISIS_SEVERITY_MAX = 20.0        # truncation of the severity power law.

# [GEO] HEADLINE geographic coupling (conflict / trade / tension / climate). The model's distinctive
# claim is cross-domain coupling; grounding it in a real spatial graph (gim/geography.py, shapely) makes
# shock propagation geographically realistic. ACTIVATED in the headline: the 2015-2023 backtest stays in
# band (GDP RMSE 0.590->0.592, CO2 1.148->1.147, T unchanged), so quality/robustness are preserved while
# realism rises. Set the relevant flag False to recover the former flat (geography-free) behaviour.

# [GEO/S5] Adjacency conflict contagion. Real interstate conflict is strongly local (UCDP ~92% of dyads
# between neighbours, ~46x chance) vs GIM's relational escalation (~2.7x); the term lifts it to ~9.6x and
# improves the conflict ranking (AUC 0.772 -> 0.805). Anchored only as an expert weight.
GEOGRAPHY_CONFLICT_LINKS = True  # HEADLINE: adjacency border-friction + conflict contagion.
GEO_CONTAGION_W = 0.03            # weight of the contiguity premium + neighbour-conflict spillover.

# [GRAVITY] Bilateral trade ∝ GDP_i·GDP_j / distance^delta instead of a flat 0.5, so the shock-propagation
# network is realistic. delta is the literature distance elasticity (Head & Mayer 2014 ~0.9), an anchored
# structural prior, NOT tuned. Mapped to mean ~0.5 so only network STRUCTURE changes, not the trade level.
# Strongest geo channel: anchored + clean cascade shape. (Needs shapely; see pyproject.)
TRADE_GRAVITY_INIT = True        # HEADLINE: gravity trade initialisation.
TRADE_GRAVITY_DIST_ELASTICITY = 0.9  # distance decay exponent (Head & Mayer 2014).

# [GEO] Social-tension spatial contagion: unrest diffuses across neighbours (Arab-Spring-style; Braha
# 2012 PLoS ONE; Hale 2013 regime-change cascades). Spatial lag toward the neighbourhood mean. Weakest
# channel — directionally right (near ~2.2x far) but modest, and the weight is an expert prior.
GEOGRAPHY_TENSION_LINKS = True   # HEADLINE: neighbour social-tension spillover.
GEO_TENSION_SPILLOVER_W = 0.05    # per-step pull of tension toward the geographic-neighbourhood mean.

# [GEO] Climate-risk spatial correlation: climate hazards (drought, heatwave, monsoon failure) are
# spatially clustered, so a country's climate risk co-moves with its neighbours'. Pulls the risk target
# toward the neighbourhood mean. Expert-prior weight.
GEOGRAPHY_CLIMATE_LINKS = True   # HEADLINE: regional climate-risk spillover.
GEO_CLIMATE_SPILLOVER_W = 0.10    # pull of the climate-risk target toward the neighbourhood mean.

# Fiscal and sovereign block.
BASE_INTEREST_RATE = 0.02  # [WEO25]
# [#14 2026-07] Sovereign-spread block anchored to the empirical literature (calibration/
# calibrate_sovereign_spreads.py + sovereign_spreads_calibration.json). THRESHOLD=0.60 is the
# Maastricht 60%-of-GDP reference AND the Reinhart & Rogoff (2010) EM debt threshold (not arbitrary).
# LINEAR raised 0.03->0.06 so the NEUTRAL-risk marginal spread at the threshold is ~2.1 bp per pp of
# debt/GDP, matching Hilscher & Nosbusch (2010, JF 65:1639); 90% range [0.043,0.086]. QUADRATIC=0.10
# keeps the Arora & Cerisola (2001) nonlinear acceleration (implied neutral spreads 94bp @0.9, 252bp
# @1.2 debt/GDP; steeper when risk/fragility-stressed). Macro backtest is unaffected (4th-decimal).
DEBT_SPREAD_THRESHOLD = 0.60  # [DATA: Maastricht 60% + Reinhart-Rogoff EM threshold]
DEBT_SPREAD_LINEAR = 0.06  # [DATA: Hilscher-Nosbusch 2010 ~2.1 bp/pp at neutral risk]
DEBT_SPREAD_QUADRATIC = 0.10  # [DATA: Arora-Cerisola 2001 nonlinear acceleration]
DEBT_SPREAD_RISK_BASE = 0.50  # [PRIOR]
DEBT_SPREAD_RISK_SENS = 0.50  # [PRIOR]
DEBT_SPREAD_FRAGILITY_BASE = 0.70  # [PRIOR]
DEBT_SPREAD_FRAGILITY_SENS = 0.60  # [PRIOR]
RATE_SPREAD_CAP = 0.25
RATE_MAX = 0.35
CONTAGION_DEBT_THRESHOLD = 0.90  # [PRIOR]
CONTAGION_SPREAD_SENS = 0.02  # [PRIOR]
CONTAGION_SPREAD_CAP = 0.05
TAX_RATE_BASE = 0.22  # [WDI23]
SOCIAL_SPEND_BASE = 0.15  # [WDI23]
MILITARY_SPEND_BASE = 0.035  # [SIPRI23]
CLIMATE_ADAPT_BASE = 0.005  # [PRIOR]
CLIMATE_ADAPT_RISK_SENS = 0.015  # [PRIOR]
MAX_NEW_DEBT_GDP = 0.05  # [WEO25]
RD_SPENDING_DECAY = 0.85  # [PRIOR]

# Climate and carbon-cycle block.
CARBON_POOL_FRACTIONS = (0.2173, 0.2240, 0.2824, 0.2763)  # [IPCC_AR6]
CARBON_POOL_TIMESCALES = (math.inf, 394.4, 36.54, 4.304)  # [IPCC_AR6]
ECS_DEFAULT = 3.0  # [IPCC_AR6] best estimate; the 1990-2023 climate backtest (sweep_ecs/best_ecs) has a
# clear temperature-RMSE minimum at 3.0 (0.096 vs 0.135 at 3.5). The ~0.16 C under-warming at the 2023
# endpoint is the El-Nino spike above the forced trend, not evidence for higher ECS (#3b investigated 2026-06).
ECS_MIN = 1.5  # [IPCC_AR6]
ECS_MAX = 4.0  # [IPCC_AR6]
F_NONCO2_DEFAULT = 0.40  # [IPCC_AR6]
F_NONCO2_BASE_YEAR = 2015  # [IPCC_AR6]
F_NONCO2_TREND = 0.012  # [IPCC_AR6] historical/in-window slope (kept exactly for the calibrated window).
# [#11 2026-07] Forward non-CO2 ERF from the SSP2-4.5 marker table instead of the unbounded linear
# extrapolation. HEADLINE-ON and golden-safe: the historical window (year <= F_NONCO2_FORWARD_FROM_YEAR)
# still uses the validated linear lumped path, so the 1990-2023 climate calibration (ECS=3.0) and all
# backtest goldens are byte-unchanged; only the post-2024 forward trajectory bends from the linear 1.42
# W/m2 (2100) down to the physically-realistic SSP2-4.5 plateau ~0.73 W/m2. This lowers long-horizon
# (SCC/2100) non-CO2 warming and removes a forward over-forcing bias. Scenario follows SSP_SCENARIO.
# See data/forcing/rcmip_nonco2_ssp245.csv and gim/core/forcing.py.
F_NONCO2_FORWARD_TABLE = True   # use the SSP marker forward non-CO2 ERF table after the handoff year.
F_NONCO2_FORWARD_FROM_YEAR = 2024  # last year on the calibrated linear path (forward = strictly after).
HEAT_CAP_SURFACE = 8.0  # [BACKTEST] T1.3 joint multi-window recal: Geoffroy physical ~8 (was 18, a short-window artifact).
HEAT_CAP_DEEP = 100.0  # [DICE16]
OCEAN_EXCHANGE = 1.0  # [BACKTEST] T1.3 joint multi-window recal: stronger heat uptake reconciles 1990-2023 trend with 2015-2023 levels (was 0.7).
# [#12 2026-07] Re-derived from the OBSERVED record (1990-2023 HadCRUT5/NOAA fixture) instead of the
# 8-member 2015-2023 ensemble. Method (Hawkins & Sutton 2009; Frankcombe et al. 2015): drive the 2-box
# EBM with observed CO2 (concentration-mode backtest) -> forced GMST; residual = observed - forced;
# fit AR(1). Result: AR(1) residual fit sigma=0.097 (95% CI 0.074-0.120), rho=0.13 (95% CI -0.23..0.40).
# The OPERATING sigma is set to 0.088 -- the value INSIDE that CI that matches the independent spread
# cross-check the issue requests: the 8-member ensemble's predicted GMST std (0.104) then equals the
# observed 2015-2023 spread (0.103), curing the prior under-dispersion (sigma=0.08 -> pred_std 0.092). It
# also brackets the lower edge of the CMIP6 unforced GMST spread (0.10-0.15 1sigma, Deser et al. 2020). The
# ensemble-MEAN forced fit is unchanged (RMSE 0.099, the climate-backtest forced value) -- only the per-
# member noise amplitude rose to realism, so the member-mean backtest RMSE stays within tolerance. rho fell
# sharply from the assumed ENSO-like 0.65 to ~0.13: once the EBM forced response is removed the annual GMST
# residuals are close to white (rho not significantly != 0 over this short window) -- the prior 0.65 was an
# unvalidated assumption. See calibration/calibrate_variability_ar1.py + variability_ar1_calibration.json.
# Window is short for ENSO (2-7yr) -> wide CI, reported honestly.
TEMP_NATURAL_VARIABILITY_SIGMA = 0.088  # [DATA] spread-matched within AR(1) CI [0.074,0.120]; pred_std==obs_std.
TEMP_NATURAL_VARIABILITY_AR1_RHO = 0.13  # [DATA] lag-1 autocorr of observed forced residuals (was assumed 0.65).
TEMP_BACKTEST_ENSEMBLE_SIZE = 8  # [BACKTEST]
FORCING_LOG_COEFF = 5.35  # [IPCC_AR6]

# [E2.1] Land-use-change (LUC) CO2 source (switchable; default 0 -> golden bit-identical).
# Global Carbon Project LUC ~4-5 GtCO2/yr historical (declining). Turning this on requires
# re-deriving EMISSIONS_SCALE, which today implicitly absorbs LUC -> rides with the E2.4 re-anchor
# (enabling it standalone would double-count). Prior in data/parameter_priors.csv.
LAND_USE_CO2_GTCO2_YR = 0.6  # [GCB2023] [E2.4 re-anchor] ACTIVATED in headline. Data-derived RESIDUAL
# (not the GCB gross ~4.5): EMISSIONS_SCALE=0.9755 already implicitly absorbs most historical LUC, so
# the residual that closes the 1990-2023 CO2 gap is ~0.6 (ppm_rmse 9.76->2.30). Calibrated on the
# emission-driven climate backtest; the gross GCB value would double-count and overshoot (ppm_rmse 54).

# [E2.2] Smooth carbon-cycle feedback (permafrost/peat), temperature-gated (switchable; default OFF).
# An ADDED term on top of the AR6-anchored forced response (ECS 3.0 / TCR 1.79) -> does NOT dilute
# ECS; effectively inflates TCRE/tail. AR6 WG1 Ch.5: permafrost CO2+CH4 feedback is positive but
# very uncertain. Split: a CO2-pool flux + a simplified steady-state CH4-equivalent forcing term.
CARBON_CYCLE_FEEDBACK = False               # master switch.
CARBON_FEEDBACK_T_REF = 0.0                 # warming reference (model temp is anomaly above PI).
CARBON_FEEDBACK_CO2_GTCO2_PER_C = 0.0       # GtCO2/yr per degC warming (permafrost/peat CO2).
CARBON_FEEDBACK_CH4_WM2_PER_C = 0.0         # extra CH4 forcing (W/m2) per degC (simplified).

# [E2.3] Abrupt carbon-release tipping (episodic, fat-tailed), temperature-gated (switchable; default OFF).
# Peat-fire / abrupt permafrost-CH4 / clathrate / forest dieback as a Richardson power-law pulse via
# gim.criticality.abrupt_carbon_release. Excludes regrowing boreal wildfire (cyclical). Stochastic ->
# rides the ensemble as carbon-cycle tail risk; default off keeps the deterministic golden identical.
CARBON_TIPPING = False                      # master switch.
CARBON_TIPPING_T_THRESHOLD = 1.5            # warming (degC above PI) where tipping hazard begins.
CARBON_TIPPING_BASE_PROB = 0.0              # annual onset probability at the threshold.
CARBON_TIPPING_TEMP_SENS = 0.02             # extra annual onset probability per degC above threshold.
CARBON_TIPPING_SCALE_GTCO2 = 5.0            # mean pulse size (GtCO2-eq) when an event fires.
CARBON_TIPPING_ALPHA = 1.5                  # Richardson power-law exponent (fat tail).
EMISSIONS_SCALE = ACTIVE_STATE_ARTIFACT.emissions_scale  # [GCP2023] Derived during manifest refresh and bound to the active state manifest.
TECH_DECARB_K = 0.12  # [PRIOR]
DECARB_RATE_OBSERVED_REFERENCE = (
    ACTIVE_STATE_ARTIFACT.decarb_reference_rate or ACTIVE_STATE_ARTIFACT.decarb_rate
)  # [DATA] GCP fossil CO2 / World Bank PPP GDP fit over 2000-2023 excluding 2020-2021; see calibration/decarb_rate_calibration.json.
DECARB_RATE_STRUCTURAL = ACTIVE_STATE_ARTIFACT.decarb_rate  # [ARTIFACT] now stamped from the observed prior.
# [FIX #2 2026-06] The manifest decarb_rate was re-stamped from the legacy 0.052 to the data-derived
# observed prior (0.016/yr; DECARB_RATE_OBSERVED_REFERENCE). At 0.052 the no-policy baseline decarbonized
# ~3.3x faster than observed (emissions fell ~3%/yr, CO2 *declined* with zero policy). The 0.052 was a
# fudge cancelling the broken 2015-state capital ramp (cap/GDP 0.23x -> ~5%/yr GDP growth); once that
# capital is fixed and TFP convergence added, 0.016 (the real CO2/GDP-PPP intensity decline) fits both
# the 2015-2023 backtest and the forward +2.4 ppm/yr growth. Policy levers accelerate decarbonisation on
# top via the structural multiplier.
DECARB_RATE = DECARB_RATE_STRUCTURAL  # Backward-compatible alias pending a full rename across the legacy layer.

# [DECARB/DEV 2026-06] Development-dependent structural decarbonisation: a country's CO2/GDP-intensity
# decline rises with income (renewables + post-industrial shift + offshoring of heavy industry). Mirror
# image of TFP_CONVERGENCE (poor grow fast; rich decarbonise fast). Calibrated to the 2015-2023 per-country
# cross-section (WB CO2 EN.GHG.CO2.MT.CE.AR5 / real PPP GDP NY.GDP.MKTP.PP.KD):
#   decarb_i = DECARB_DEV_BASE + DECARB_DEV_SLOPE*ln(gdp_per_capita_$),  R2=0.46.
# The single global DECARB_RATE_STRUCTURAL (0.016) is the emissions-weighted aggregate; it understates
# the per-country median (~0.031) because the global figure is dominated by the still-industrialising
# developing world. China sits ~+0.013 above the development line (its renewable build-out). When this
# switch is off, the legacy single global rate is used (and the decarb sensitivity sweep still applies).
DECARB_DEVELOPMENT_DEPENDENT = True
DECARB_DEV_BASE = -0.0779
DECARB_DEV_SLOPE = 0.0107
DECARB_DEV_MIN = 0.0    # floor: no structural *rise* in intensity (industrialisers held at 0, not negative).
DECARB_DEV_MAX = 0.060  # cap at the fastest observed decarboniser (Netherlands).

STRUCTURAL_TRANSITION_POLICY_SENS = 0.50  # [PRIOR]
STRUCTURAL_TRANSITION_TAX_SENS = 0.05  # [PRIOR]
STRUCTURAL_TRANSITION_MULT_MIN = 1.0
STRUCTURAL_TRANSITION_MULT_MAX = 1.15
CO2_INTENSITY_FLOOR = 0.02  # [PRIOR]
FUEL_TAX_EMISSIONS_SENS = 0.12  # [PRIOR]
FUEL_TAX_EFFECT_MIN = 0.60
FUEL_TAX_EFFECT_MAX = 1.40
POLICY_REDUCTION_MAX = 0.90

# Labor market & inflation (Phillips curve + Okun's law) - P4-A.
# Endogenous unemployment (Okun) and inflation (expectations-augmented Phillips with an
# energy cost-push term), so both respond to the output gap and to climate/resource price
# shocks instead of sitting at their initial values.
POTENTIAL_OUTPUT_GROWTH = 0.025  # [PRIOR] trend/potential real GDP growth (output-gap reference).
NAIRU = 0.045  # [PRIOR] non-accelerating-inflation rate of unemployment (~natural rate).
OKUN_COEFF = 0.3  # [OKUN] Okun's law: +1pp growth above potential lowers unemployment ~0.3pp.
UNEMP_ADJ_SPEED = 0.5  # [PRIOR] partial-adjustment speed of unemployment toward its Okun target.
UNEMPLOYMENT_MIN = 0.01
UNEMPLOYMENT_MAX = 0.35
INFLATION_TARGET = 0.02  # [PRIOR] central-bank/anchor inflation.
INFLATION_EXPECTATION_ANCHOR = 0.5  # [PRIOR] weight on the anchor vs last year's inflation (adaptive expectations).
PHILLIPS_SLOPE = 0.25  # [PRIOR] flat modern Phillips curve: +1pp unemployment gap -> +0.25pp inflation.
INFLATION_COSTPUSH_COEFF = 0.05  # [PRIOR] energy-price pass-through: +20% energy price -> +1pp inflation.
# [F-food 2026-08-24] Food-price pass-through, the symmetric term. Food had NO channel into the
# economy at all -- E16 forced the food price to 5x and every downstream output moved by exactly
# zero to five decimal places -- while being the larger CPI component nearly everywhere (food and
# non-alcoholic beverages: US 8%, UK 12%, euro area 15.5%, Japan 19.5%, China 31%, India 45%;
# household energy 3-9.5%). Derivation of the default: a GDP-weighted global CPI food weight of
# ~0.16, times a commodity-to-retail pass-through of ~0.25 (the model's food price is a producer
# index; processing, transport and retail margins absorb most of a commodity move), gives ~0.04 --
# close to the energy coefficient, which carries the same two-stage structure. 0.0 => off.
INFLATION_COSTPUSH_FOOD_COEFF = 0.04  # ON: see the derivation above. Switched on only after
# FOOD_SUPPLY_PRICE_ELAST, since feeding the pre-repair food price -- which ran to 4.68 by 2053
# on frozen supply -- into consumer inflation would have injected an artifact into the CPI.

# [F-food 2026-08-24] Food supply growth. Production was frozen at its base-year value in every
# forward year while demand grew with population and income, driving demand/supply to 1.33 and
# the food price to 4.68 by 2053. Anchors: FAO global food production growth ~2%/yr historically,
# decelerating; agricultural supply price elasticity ~0.1-0.3 short run, 0.3-0.6 long run. The
# price elasticity is what keeps real food prices roughly flat in the observed record -- a high
# price draws out supply -- so it matters more than the trend for the model's behaviour under a
# crop shock. 0.0 => off, golden bit-identical.
# [F-food-climate 2026-08-24] Fractional food-yield loss per degree C of warming above the 2023
# baseline. The model had no climate -> crop channel at all, which is why Appendix B's crop
# scenario injects a yield cut by hand. Prior: Zhao et al. 2017 PNAS 114(35):9326-9331 --
# wheat 6.0%, rice 3.2%, maize 7.4%, soybean 3.1% per degree, from four independent method
# families that converge (global gridded models, local point models, statistical regressions,
# field-warming experiments). Unweighted mean ~4.9%/degC; production weighting toward maize
# pushes it toward ~5.5%. The estimate EXCLUDES CO2 fertilisation, adaptation and genetic
# improvement, so it composes with FOOD_SUPPLY_PRICE_ELAST -- which is the model's adaptation
# mechanism -- without double counting. 0.0 => off.
FOOD_YIELD_TEMP_SENS = 0.049  # ON: unweighted mean of Zhao's four published per-crop values.

FOOD_YIELD_GROWTH = 0.0
FOOD_SUPPLY_PRICE_ELAST = 0.143  # [DATA: Haile et al. 2016 AJAE; Iqbal et al. 2018 Agric.
# Economics] Aggregate own-price long-run GROWING-AREA elasticity across corn, soy, wheat and
# rice (short run 0.024; crop-level long run 0.045 rice to 0.793 soy). Used as a deliberately
# CONSERVATIVE proxy for total supply response: the true total adds a yield-intensity margin on
# top of area, putting the aggregate nearer 0.2-0.3, but 0.143 is the directly estimated
# published aggregate and 0.2-0.3 would be my inference on top of it. The difference is small in
# outcome -- 2053 food price 1.244 at 0.143 against 1.172 at 0.20 and 1.097 at 0.30.
# Composes with FOOD_YIELD_TEMP_SENS without double counting: Zhao's yield loss excludes
# adaptation, and this elasticity IS the adaptation. Validation: the pair gives a 2053 food
# price of 1.244, i.e. +24.4%, inside the IPCC SRCCL assessed range of a 1-29% cereal price
# increase by 2050 from climate change (SSP1-3, RCP6.0) -- an anchor it was not fitted to.
FOOD_SUPPLY_RESPONSE_MAX = 2.0  # cap on the price-level supply multiplier
# [E4.1] HEADLINE: quantity-theory money->price transmission. Weight on EXCESS broad-money growth
# (broad money = bank deposits from the SFC block) above the stable-velocity reference g* + pi*
# (= POTENTIAL_OUTPUT_GROWTH + INFLATION_TARGET) in the Phillips curve. 0.0 -> term skipped (the
# pre-E4.1 golden). Activated at the data-calibrated 0.027 (dynamic-panel short-run pass-through,
# LSDV w/ lagged inflation; rho~0.51 independently validates ANCHOR=0.5; modern low-inflation WB
# panel 2000-2023; calibration/calibrate_money_inflation_pass.py -- the naive cross-section 0.235 was
# ~9x inflated by between-country regime heterogeneity + persistence). Golden re-anchored on
# activation (4th-decimal backtest move). See docs/MONEY_PRICES.md.
MONEY_INFLATION_PASS = 0.027
INFLATION_MIN = -0.02
INFLATION_MAX = 0.30

# Monetary policy reaction (Taylor rule) - P4-C. The central bank sets the policy base
# rate above/below its neutral level in response to the inflation gap and the output gap
# (proxied by the unemployment gap, NAIRU - u). Zero deviation at inflation==target and
# u==NAIRU, so the calibration steady state is preserved.
TAYLOR_PHI_PI = 0.5  # [TAYLOR1993] response to the inflation gap.
TAYLOR_PHI_Y = 0.5   # [TAYLOR1993] response to the output gap (via the unemployment gap).
TAYLOR_DEVIATION_CAP = 0.06  # cap on the |policy deviation| from the neutral base rate.

# Climate damage and resilience block.
# [#17 2026-07] Level-damage quadratic re-anchored to Howard & Sterner (2017, JAERE 4:1135) preferred
# central meta-estimate: ~7% GDP loss at +3 degC above pre-industrial -> DAMAGE_QUAD_COEFF = 0.07/9 =
# 0.0078 (was 0.006 -> 5.4% at 3C; the issue's "0.6% at 3C" premise was a miscalculation). The damage
# multiplier is now normalised to the 2023 baseline climate (see climate.climate_damage_multiplier) so
# the 2023-anchored GDP is not double-counted; damages accrue on INCREMENTAL warming. Range across the
# literature: DICE-2016R2 ~0.0026 (2.1% at 3C, lower), Howard-Sterner incl-catastrophic ~0.0115 (10%+,
# upper). 0.0078 is the productivity-corrected central.
DAMAGE_QUAD_COEFF = 0.0078  # [DATA: Howard & Sterner 2017 preferred central, ~7% GDP at +3C]
# [#17] Warming "benefit" disabled: post-2023 net GDP gains from further warming are not supported
# (Howard-Sterner/Burke/Kotz show net damages already at current warming). MAX=0 => benefit term off.
DAMAGE_BENEFIT_PEAK = 0.30  # [DEPRECATED #17] retained for back-compat; inactive while BENEFIT_MAX=0.
DAMAGE_BENEFIT_MAX = 0.0  # [#17] disabled (was 0.006); no net warming benefit beyond the 2023 baseline.
DAMAGE_BENEFIT_STDDEV = 0.50  # [DEPRECATED #17] retained for back-compat; inactive while BENEFIT_MAX=0.
DAMAGE_RISK_ADJ = 0.005  # [PRIOR]
RESILIENCE_STABILITY_W = 0.40  # [PRIOR]
RESILIENCE_TECH_W = 0.30  # [PRIOR]
RESILIENCE_TRUST_W = 0.15  # [PRIOR]
RESILIENCE_ADAPT_W = 0.15  # [PRIOR]
RESILIENCE_TECH_REF = 2.0  # [PRIOR]
RESILIENCE_ADAPT_REF = 0.03  # [PRIOR]
BIODIVERSITY_RISK_DAMP = 0.60  # [PRIOR]
BIODIVERSITY_TEMP_DAMAGE = 0.004  # [PRIOR]

# Climate risk block.
CRISK_RESPONSE_RATE = 0.06  # [PRIOR]
CRISK_TEMP_SENSITIVITY = 0.45  # [PRIOR]
CRISK_BASE_CONST = 0.30  # [PRIOR]
CRISK_WATER_WEIGHT = 0.45  # [PRIOR]
CRISK_GINI_WEIGHT = 0.15  # [PRIOR]

# Extreme events block.
EVENT_BASE_PROB = 0.012  # [PRIOR]
EVENT_MAX_EXTRA_PROB = 0.07  # [PRIOR]
EVENT_TEMP_WARMING_SENS = 0.15  # [PRIOR]
EVENT_RESILIENCE_DAMP = 0.40  # [PRIOR]
EVENT_PROB_MAX = 0.50
EVENT_SEVERITY_BASE = 0.03  # [PRIOR]
EVENT_SEVERITY_RISK_SENS = 0.15  # [PRIOR]
EVENT_SEVERITY_RESILIENCE_DAMP = 0.50  # [PRIOR]
EVENT_POP_LOSS_BASE = 0.004  # [PRIOR]
EVENT_POP_LOSS_RISK_SENS = 0.015  # [PRIOR]
EVENT_POP_RESILIENCE_DAMP = 0.35  # [PRIOR]
EVENT_SHOCK_PENALTY_CAP = 0.10
EVENT_SHOCK_PENALTY_SEVERITY_SENS = 0.50  # [PRIOR]
EVENT_SHOCK_YEARS = 2
EVENT_TENSION_JUMP_BASE = 0.03  # [PRIOR]
EVENT_TENSION_JUMP_RISK_SENS = 0.10  # [PRIOR]
EVENT_TRUST_STABILITY_THRESHOLD = 0.60  # [PRIOR]
EVENT_TRUST_REWARD_BASE = 0.02  # [PRIOR]
EVENT_TRUST_REWARD_RESILIENCE_SENS = 0.02  # [PRIOR]
EVENT_TRUST_PENALTY_BASE = 0.02  # [PRIOR]
EVENT_TRUST_PENALTY_RISK_SENS = 0.03  # [PRIOR]

# Social and demographic block.
FOOD_RESERVE_WEIGHT = 0.20  # [PRIOR]
FOOD_AVAILABILITY_MAX = 2.0  # [PRIOR]
PROSPERITY_LOGIT_SENS = 1.20  # [PRIOR]
# [#15 2026-07] Logistic demographic transition (Lutz et al. 2001; Preston 1975), switchable. Default
# OFF -> the legacy linear birth/death income terms are used (golden bit-identical). When ON, the
# absolute-income logistic replaces the linear term + the relative-prosperity damp (no double income
# channel). Anchored to published WPP/Lutz cross-country crude rates and validated against the UN WPP
# 2015-2023 global population trajectory (calibration/calibrate_demographics.py): birth high at low
# income (~42/1000), falling through middle income (inflection ~$8k), plateauing ~9/1000 at high income;
# underlying death rate falls with income from ~17/1000 to ~7/1000 (income channel only -- no age
# structure, so the rich-country aging CDR rebound is not modelled; documented limitation). Headline
# activation needs re-tuning BIRTH_PROSPERITY_DAMP and a backtest re-anchor -> kept off pending that.
DEMOGRAPHIC_LOGISTIC = False
CBR_LOGISTIC_MIN = 0.009        # high-income crude birth-rate plateau (~9/1000; WPP high-income).
CBR_LOGISTIC_MAX = 0.044        # low-income crude birth rate (~44/1000; WPP Sub-Saharan low-income).
CBR_LOGISTIC_MID_GDP_PC = 6000.0  # log-income inflection; tuned so world natural increase ~0.95%/yr (WPP).
CBR_LOGISTIC_K = 1.6            # transition steepness in log-income (Lutz et al. logistic).
CDR_LOGISTIC_MIN = 0.007        # high-income underlying crude death-rate floor (~7/1000, age-fixed).
CDR_LOGISTIC_MAX = 0.017        # low-income crude death rate (~17/1000; pre-transition).
CDR_LOGISTIC_MID_GDP_PC = 2500.0  # log-income inflection of the mortality decline (Preston).
CDR_LOGISTIC_K = 1.5            # mortality-decline steepness in log-income.
BASE_BIRTH_RATE = 0.025  # [WDI23]
BIRTH_GDP_PC_DECAY = 0.000001  # [PRIOR]
BIRTH_PROSPERITY_DAMP = 0.50  # [PRIOR]
BIRTH_SCARCITY_DAMP = 0.60  # [PRIOR]
BIRTH_GINI_DAMP = 0.30  # [PRIOR]
BIRTH_RATE_MIN = 0.006
BIRTH_RATE_MAX = 0.040
BASE_DEATH_RATE = 0.012  # [WDI23]
DEATH_GDP_PC_DECAY = 0.0000005  # [PRIOR]
DEATH_SCARCITY_SENS = 1.0  # [PRIOR]
DEATH_GINI_SENS = 0.40  # [PRIOR]
DEATH_PROSPERITY_DAMP = 0.20  # [PRIOR]
DEATH_RATE_MIN = 0.004
DEATH_RATE_MAX = 0.030
MIGRATION_BASE_RATE = 0.001  # [PRIOR]
MIGRATION_MAX_SHARE = 0.003  # [PRIOR]
MIGRATION_INCOME_PUSH_W = 0.60  # [PRIOR]
MIGRATION_CONFLICT_PUSH_W = 0.40  # [PRIOR]
MIGRATION_DEST_CONFLICT_DAMP = 0.50  # [PRIOR]
TRUST_GDP_PC_SENS = 0.00005  # [PRIOR]
TRUST_GDP_PC_REF = 10000.0  # [PRIOR]
# [#16 2026-07] Trust-erosion sensitivities anchored to the cross-country trust/wellbeing literature
# (Algan & Cahuc 2014 AER 104:2060; Guriev & Papaioannou 2022 JEL 60:753). The robust, scale-free
# result is the RELATIVE weight: unemployment erodes institutional trust ~2x as much as inflation per
# percentage point (the "misery index" weighting; Di Tella, MacCulloch & Oswald 2001 AER 91:335;
# Stevenson & Wolfers 2008). The prior 1:1 (-0.025/-0.025) is rebalanced to 2:1 (-0.030/-0.015),
# preserving the average flow magnitude (~0.0225) so the calibrated trust trajectory and the conflict/
# crisis validations are preserved (the GDP/CO2/temp backtest is unaffected -- trust feeds tension/
# stability, not the macro core). Trust here is a per-step flow (no explicit mean reversion; balanced by
# the positive GDP-per-capita drift), so these are flow sensitivities, not level elasticities.
TRUST_UNEMPLOYMENT_SENS = -0.030  # [DATA: misery-index 2:1 weighting vs inflation]
TRUST_INFLATION_SENS = -0.015  # [DATA: misery-index 2:1 weighting]
TRUST_GINI_SENS = -0.0004  # [DATA: negative inequality->trust gradient; Gould & Hijzen 2016 IMF WP/16/176]
TRUST_TENSION_SENS = -0.08  # [PRIOR] internal trust<-tension coupling (not an external elasticity).
TRUST_TENSION_THRESHOLD = 0.30  # [PRIOR]
# [#16] Switchable inequality x unemployment interaction (Gould & Hijzen 2016: inequality erodes trust
# MORE during downturns). Default 0.0 -> off (golden-safe); on-value adds -COEF*gini_frac*unemployment.
TRUST_GINI_UNEMP_INTERACT = 0.0  # [DATA on-value ~0.02] interaction trust penalty; 0 => off.
# [2026-07-12] The "balanced by the positive GDP-per-capita drift" claim above does not hold under
# calibrated values: at TRUST_GDP_PC_SENS=0.00005 the GDP-per-capita term is ~0.0004-0.0005/yr even
# for a rich country, while TRUST_GINI_SENS alone contributes ~-0.0165/yr at a realistic gini
# (35-45) -- ~40x larger and never reached zero under card-driven play (batch-verified: a scripted
# maximize-social-spending/R&D policy and its exact opposite produced statistically indistinguishable
# avg_stability trajectories over 12 seeds to 2050, -34.2 vs -34.6). trust_gov has no equilibrium
# term of its own (unlike price's PRICE_ANCHOR_PULL below), so it drifts down at a near-constant
# rate until clamped, then the SOCIAL_TRUST_ANCHOR_SENS/TENSION_SENS coupling below turns that into
# a self-reinforcing collapse. Same shape as the pre-fix resource-price walk (e0fa89f). Default 0.0
# => off, golden-safe: turns on a weak per-agent mean-reversion toward each agent's own base-year
# (2023) trust_gov, captured once (see _trust_anchors in social.py), mirroring PRICE_ANCHOR_PULL's
# log-space pull but linear (trust_gov is already an additive [0,1] quantity, not multiplicative).
TRUST_ANCHOR_PULL = 0.10  # [F-social] per-year share of the gap to each agent's base-year trust
# pulled back. ON at 0.10 as of 2026-08-24. The deviation form (V6, below) fixed the DRIFT but not
# the UNIT ROOT -- a walk without drift still has an eigenvalue of exactly 1, and E3 measured the
# spectral radius unchanged at ~1.075-1.10 with V6 shipped, its dominant eigenvector still loading
# on trust_gov. Mean reversion is a separate mechanism from the functional form, and prices already
# carry it (PRICE_ANCHOR_PULL = 0.15, which the note above says trust should mirror).
# Strength chosen on evidence, not on fit (Paper/revision/results/e11_trust_form_variants.json and
# e3_spectral_trust_mode.json):
#   0.05  rho FALLS at 2026 but RISES at 2046 (1.0765 -> 1.0996) -- rejected, inconsistent,
#         despite giving the strongest shock response
#   0.10  rho falls consistently at all three linearisation points (1.075/1.100/1.077 ->
#         1.036/1.037/1.039), drift halves again (-0.0056 -> -0.0024/yr), cross-country
#         dispersion still 1.72x its starting value (pre-V6: 1.21), shock response +0.0197
#         (pre-V6: +0.0083)  <-- taken
#   0.20  lowest rho but dispersion falls to 1.45 and the shock response to +0.0116
# The 2015-2023 fit moves by 0.001% and the resource-price implausibilities do not move at all,
# so this is not a fit-driven choice.

# [F-social-form 2026-08-24] The comment above diagnoses the symptom (no equilibrium term); the
# cause is one level up. Three of the five trust drivers enter as LEVELS rather than deviations
# from a reference, so a country sitting at a constant and entirely normal gini, unemployment and
# inflation loses trust every year forever, and no anchor strength can cancel a constant -- it only
# moves where the constant settles (measured: at TRUST_ANCHOR_PULL=0.20 all 57 agents still drift
# down, Paper/revision/results/e2_trust_drift_artifact.json). The tension driver already uses the
# correct deviation form (TRUST_TENSION_THRESHOLD below); these switches give the other four the
# same form -- unemployment against NAIRU, inflation against INFLATION_TARGET, gini and income
# against each agent's own base-year value. All default False => level form, golden bit-identical.
TRUST_GINI_DEVIATION_FORM = True  # [V6 2026-08-24] ON: E11 acceptance passed on the price-aware backtest.
TRUST_UNEMP_DEVIATION_FORM = True  # [V6 2026-08-24] ON: E11 acceptance passed on the price-aware backtest.
TRUST_INFLATION_DEVIATION_FORM = True  # [V6 2026-08-24] ON: E11 acceptance passed on the price-aware backtest.
TRUST_GDPPC_DEVIATION_FORM = True  # [V6 2026-08-24] ON: E11 acceptance passed on the price-aware backtest.

# [F-social-form 2026-08-24] Same defect, tension side. INEQUALITY_EFFECT_SENS * gini is ~+0.02/yr
# at a realistic gini and never returns to zero; tension then drains trust through
# TRUST_TENSION_SENS, closing the self-reinforcing loop. TENSION_REF_PER_AGENT additionally frees
# the per-agent tension reference from its accidental gating on TRUST_ANCHOR_PULL.
# All default False => level form, golden bit-identical.
TENSION_GINI_DEVIATION_FORM = True  # [V6 2026-08-24] ON: E11 acceptance passed on the price-aware backtest.
TENSION_STRESS_DEVIATION_FORM = True  # [V6 2026-08-24] ON: E11 acceptance passed on the price-aware backtest.
TENSION_REF_PER_AGENT = True  # [V6 2026-08-24] ON: E11 acceptance passed on the price-aware backtest.

# [F-climate-social 2026-08-24] CONTESTED PRIOR -- SHIPS OFF. Per-year social-tension increment
# per unit of climate_risk, i.e. a CONTINUOUS climate -> society channel. Today climate reaches
# society only through discrete extreme events, which the deterministic headline runs switch off,
# so at the headline configuration climate does not touch tension at all.
# Prior: Hsiang, Burke & Miguel 2013 (Science 341, 1235367), meta-analysis of 60 studies -- per
# 1 SD of warming, interpersonal violence +4%, intergroup conflict +14%.
# Disputed: Buhaug et al. 2014 (Climatic Change 127:391-397) contest the sample selection and
# analytical coherence and read the literature as mixed and inconclusive; Hsiang et al. reply
# identifying five errors in that reanalysis. Unsettled.
# Direction defensible, magnitude not identified, so this is a tail/sensitivity switch and not a
# headline mechanism -- the same treatment CARBON_TIPPING_* gets. A run that enables it must say
# so. Suggested exploratory band 0.002-0.010 (the lower end maps to the HBM interpersonal-violence
# figure, the upper end to the intergroup-conflict figure); 0.0 => off, golden bit-identical.
TENSION_CLIMATE_SENS = 0.0
INEQUALITY_EFFECT_SENS = 0.0005  # [PRIOR]
SOCIAL_STRESS_UNEMPLOYMENT_SENS = 0.01  # [PRIOR]
SOCIAL_STRESS_INFLATION_SENS = 0.005  # [PRIOR]
SOCIAL_TRUST_ANCHOR_SENS = 0.06  # [PRIOR]
SOCIAL_TRUST_ANCHOR_REF = 0.50  # [PRIOR]

# [F3] Culture -> social-block links (switchable; default OFF => golden bit-identical).
# Wires the three theory-supported Hofstede dimensions into the always-on trust/tension
# update (the same block where `idv` is load-bearing), centred on CULTURE_DIM_REF so the
# calibration baseline is minimally perturbed. Signs validated against cross-country evidence:
#   pdi (power distance)        -> weaker accountability institutions -> lower trust        (-)
#   uai (uncertainty avoidance) -> stronger anxiety/reaction to econ stress -> more tension  (+)
#   lto (long-term orientation) -> patience/deferred gratification -> damped short-run unrest (-)
# The 4 dropped dims (mas, ind, traditional_secular, survival_self_expression) had no
# defensible, testable economic/social linkage (F3 audit) and were removed.
CULTURE_SOCIAL_LINKS = True  # [F3] [E2.4 re-anchor] ACTIVATED in headline (golden-safe; pdi/uai/lto load-bearing).
CULTURE_DIM_REF = 50.0        # Hofstede mid-scale reference (0-100) for centring.
CULTURE_PDI_TRUST_SENS = 0.02     # power distance -> institutional trust (Hofstede; PDI~corruption/ineq).
CULTURE_UAI_STRESS_SENS = 0.50    # uncertainty avoidance -> econ-stress reaction amplification.
CULTURE_LTO_PATIENCE_SENS = 0.30  # long-term orientation -> tension damping (savings/patience).

# [F3 / E2.4 re-anchor] Ground `technology.military_power` in the CINC (Composite Index of National
# Capability, Correlates of War) at world build, replacing the curated CSV scalar with an observable
# 0-1 capability share (mean-rescaled to ~1). Default True in the headline. Conflict-gated, so the
# (calm) golden backtest is unaffected; it shifts conflict/geo scenario dynamics. Validated vs
# published CINC (China 0.205 / US 0.147 / India 0.096) in gim/capability.py.
GROUND_MILITARY_POWER = True  # [F3] CINC grounding at build (headline).
# [F3+ / Tier-1 milex re-anchor] Populate `economy.military_spending` from the SIPRI 2023
# grounding file (data/external/sipri_milex_2023.csv; 50 country actors direct, AG_* aggregates
# summed over region members — 99.9% of the SIPRI world total) BEFORE CINC grounding, activating
# the military-expenditure component of the CINC (4 components instead of the 3-proxy fallback).
# Rationale: the pop/energy/GDP proxy fits milex LEVELS (r~0.76 cross-section) but is
# ANTI-correlated with 2021-24 militarization dynamics (share-change corr -0.115) — see
# docs/MILEX_GROUNDING_ANALYSIS.md. Conflict-gated like F3 itself, so the calm
# golden backtest is unaffected; the UCDP conflict backtest scores the state-CSV
# conflict_proneness column and is likewise unchanged. Shifts conflict/geo scenario dynamics
# (war odds, mil_gap threat terms, credit military-balance).
MILEX_CINC_COMPONENT = True  # [F3+] SIPRI milex component in CINC (headline).

# [GIM19 §11 / THE-128] Agents whose intra-country block model contributes social
# deltas as a propagate sub-step. Empty tuple => the sub-step is a no-op and the
# core run is bit-identical to the pre-block-layer baseline.
BLOCK_LAYER_AGENTS: tuple = ()
# [GIM19 B2] Optional war-intensity override for the block layer: a callable
# year -> intensity. None => scenario_war_intensity (historical escalation with
# post-2026 de-escalation). Scenario sweeps (bifurcation map) set this.
BLOCK_WAR_INTENSITY_FN = None
# [GIM19 B5] Credit channel for block-layer agents: investment semi-elasticity
# to the REAL policy-rate gap (block nominal rate − block CPI − neutral real
# base). The generic capital-market clearing anchors gap0 at the first
# observed gap, so a persistent war-rate LEVEL never transmits — for block
# agents the anchor is the neutral base instead, and this sensitivity applies
# (~1.0 per unit rate gap ≈ 1% investment per pp, standard macro range).
BLOCK_CREDIT_SENS = 1.0  # [PRIOR]
GINI_GROWTH_SENS = 6.0  # [PRIOR]
GINI_RECESSION_SENS = 4.0  # [PRIOR]
GINI_RECESSION_TENSION_OFFSET = 0.50  # [PRIOR]
GINI_FISCAL_SENS = -60.0  # [PRIOR]
GINI_TENSION_SENS = 1.2  # [PRIOR]
GINI_TENSION_REF = 0.40  # [PRIOR]
GINI_MIN = 20.0
GINI_MAX = 70.0
REGIME_COLLAPSE_TRUST_THRESHOLD = 0.20  # [PRIOR]
REGIME_COLLAPSE_TENSION_THRESHOLD = 0.80  # [PRIOR]
REGIME_COLLAPSE_CAPITAL_MULT = 0.70  # [PRIOR]
REGIME_COLLAPSE_GDP_MULT = 0.80  # [PRIOR]
REGIME_COLLAPSE_DEBT_MULT = 0.70  # [PRIOR]
REGIME_COLLAPSE_TRUST_FLOOR = 0.25  # [PRIOR]
REGIME_COLLAPSE_TENSION_CAP = 0.60  # [PRIOR]
REGIME_COLLAPSE_STABILITY_HIT = 0.20  # [PRIOR]
DEBT_CRISIS_DEBT_THRESHOLD = 1.20  # [PRIOR]
DEBT_CRISIS_RATE_THRESHOLD = 0.12  # [PRIOR]
DEBT_CRISIS_DEBT_MULT = 0.60  # [PRIOR]
DEBT_CRISIS_GDP_MULT = 0.93  # [PRIOR] softened onset haircut to avoid overshoot in Argentina-like stress paths
DEBT_CRISIS_UNEMPLOYMENT_MAX = 0.30  # [PRIOR]
DEBT_CRISIS_UNEMPLOYMENT_HIT = 0.05  # [PRIOR]
DEBT_CRISIS_TRUST_HIT = 0.15  # [PRIOR]
DEBT_CRISIS_TENSION_HIT = 0.15  # [PRIOR]
DEBT_CRISIS_STABILITY_HIT = 0.15  # [PRIOR]
FX_CRISIS_EXTERNAL_DEBT_THRESHOLD = 0.50  # [PRIOR]
FX_CRISIS_CURRENT_ACCOUNT_DEFICIT_THRESHOLD = -0.04  # [PRIOR]
FX_CRISIS_RESERVE_MONTHS_THRESHOLD = 3.0  # [PRIOR]
FX_CRISIS_RESERVE_OFFSET_WEIGHT = 1.0  # [PRIOR]
FX_CRISIS_IMPORT_LEAKAGE_WEIGHT = 0.15  # [PRIOR]
FX_CRISIS_DEBT_MULT = 1.10  # [PRIOR]
FX_CRISIS_GDP_MULT = 0.85  # [PRIOR]
FX_CRISIS_UNEMPLOYMENT_HIT = 0.06  # [PRIOR]
FX_CRISIS_TRUST_HIT = 0.12  # [PRIOR]
FX_CRISIS_TENSION_HIT = 0.14  # [PRIOR]
FX_CRISIS_STABILITY_HIT = 0.12  # [PRIOR]
FX_CRISIS_PERSIST_GDP_MULT = 0.98  # [PRIOR]
FX_CRISIS_PERSIST_TRUST_HIT = 0.02  # [PRIOR]
FX_CRISIS_PERSIST_TENSION_HIT = 0.015  # [PRIOR]
FX_CRISIS_RECOVERY_RESERVE_MONTHS = 3.0  # [PRIOR]
FX_CRISIS_MAX_YEARS = 4  # [PRIOR]
# Crisis persistence guardrail-safe plateau candidate selected from
# calibration/crisis_persistence_calibration.json.
DEBT_CRISIS_PERSIST_GDP_MULT = 0.965  # [DATA plateau-guardrail]
DEBT_CRISIS_PERSIST_TRUST_HIT = 0.025  # [DATA plateau-guardrail]
DEBT_CRISIS_PERSIST_TENSION_HIT = 0.02  # [DATA plateau-guardrail]
DEBT_CRISIS_EXIT_THRESHOLD = 0.70  # [DATA plateau-guardrail]
DEBT_CRISIS_EXIT_RATE = 0.08  # [DATA plateau-guardrail]
DEBT_CRISIS_MAX_YEARS = 6  # [DATA plateau-guardrail]
REGIME_CRISIS_PERSIST_GDP_MULT = 0.96  # [DATA plateau-guardrail]
REGIME_CRISIS_PERSIST_CAPITAL_MULT = 0.975  # [DATA plateau-guardrail]
REGIME_CRISIS_MAX_YEARS = 5  # [DATA plateau-guardrail]

# Metric block.
DEBT_STRESS_THRESHOLD = 1.0  # [PRIOR]
DEBT_STRESS_CAP = 3.0  # [PRIOR]
PROTEST_RISK_TENSION_W = 0.60  # [PRIOR]
PROTEST_RISK_DISTRUST_W = 0.30  # [PRIOR]
PROTEST_RISK_GINI_W = 0.10  # [PRIOR]
PROTEST_RISK_FRAGILITY_BASE = 0.50  # [PRIOR]
PROTEST_RISK_FRAGILITY_SENS = 0.50  # [PRIOR]

# Credit rating block.
CR_RATING_PRIME_MAX = 3  # [PRIOR]
CR_RATING_INVESTMENT_MAX = 12  # [PRIOR]
CR_RATING_SUB_INVESTMENT_MAX = 18  # [PRIOR]
CR_RATING_DISTRESSED_MAX = 23  # [PRIOR]
CR_RATING_MIN = 1  # [PRIOR]
CR_RATING_MAX = 26  # [PRIOR]
CR_SANCTION_PRESSURE_STRONG_WEIGHT = 2.0  # [PRIOR]
CR_SANCTION_PRESSURE_DIVISOR = 8.0  # [PRIOR]
CR_WAR_HIGH_CONFLICT_THRESHOLD = 0.55  # [PRIOR]
CR_WAR_MIL_PRESSURE_SCALE = 1.5  # [PRIOR]
CR_WAR_LINK_CONFLICT_W = 0.55  # [PRIOR]
CR_WAR_LINK_TRUST_W = 0.25  # [PRIOR]
CR_WAR_LINK_MILITARY_W = 0.20  # [PRIOR]
CR_WAR_NEXT_WAR_W = 0.65  # [PRIOR]
CR_WAR_NEXT_CONFLICT_PRONE_W = 0.20  # [PRIOR]
CR_WAR_NEXT_HAWKISH_W = 0.15  # [PRIOR]
CR_SANCTION_HOSTILITY_CONFLICT_W = 0.55  # [PRIOR]
CR_SANCTION_HOSTILITY_TRUST_W = 0.45  # [PRIOR]
CR_SANCTION_NEXT_HOSTILITY_W = 0.60  # [PRIOR]
CR_SANCTION_NEXT_PROPENSITY_W = 0.40  # [PRIOR]
CR_SOCIAL_GINI_LO = 30.0  # [PRIOR]
CR_SOCIAL_GINI_HI = 65.0  # [PRIOR]
CR_SOCIAL_UNEMPLOYMENT_LO = 0.05  # [PRIOR]
CR_SOCIAL_UNEMPLOYMENT_HI = 0.25  # [PRIOR]
CR_SOCIAL_INFLATION_LO = 0.02  # [PRIOR]
CR_SOCIAL_INFLATION_HI = 0.15  # [PRIOR]
CR_SOCIAL_FOOD_YEARS_CAP = 2.0  # [PRIOR]
CR_SOCIAL_FOOD_STRESS_W = 0.15  # [PRIOR]
CR_SOCIAL_STRUCTURAL_GINI_W = 0.30  # [PRIOR]
CR_SOCIAL_STRUCTURAL_UNEMPLOYMENT_W = 0.20  # [PRIOR]
CR_SOCIAL_STRUCTURAL_INFLATION_W = 0.15  # [PRIOR]
CR_SOCIAL_STRUCTURAL_WATER_W = 0.20  # [PRIOR]
CR_SOCIAL_MANAGEMENT_TRUST_W = 0.35  # [PRIOR]
CR_SOCIAL_MANAGEMENT_POLICY_W = 0.25  # [PRIOR]
CR_SOCIAL_MANAGEMENT_STABILITY_W = 0.20  # [PRIOR]
CR_SOCIAL_MANAGEMENT_SPENDING_W = 0.20  # [PRIOR]
CR_SOCIAL_SPENDING_LO = 0.04  # [PRIOR]
CR_SOCIAL_SPENDING_HI = 0.20  # [PRIOR]
CR_FINANCIAL_DEBT_GDP_LO = 0.6  # [PRIOR]
CR_FINANCIAL_DEBT_GDP_HI = 1.8  # [PRIOR]
CR_FINANCIAL_RATE_LO = 0.04  # [PRIOR]
CR_FINANCIAL_RATE_HI = 0.20  # [PRIOR]
CR_FINANCIAL_NOW_DEBT_W = 0.35  # [PRIOR]
CR_FINANCIAL_NOW_RATE_W = 0.25  # [PRIOR]
CR_FINANCIAL_NOW_STRESS_W = 0.25  # [PRIOR]
CR_FINANCIAL_NOW_CRISIS_W = 0.15  # [PRIOR]
CR_FINANCIAL_NEXT_STRESS_W = 0.65  # [PRIOR]
CR_FINANCIAL_NEXT_GROWTH_W = 0.35  # [PRIOR]
CR_FINANCIAL_BLEND_NOW_W = 0.60  # [PRIOR]
CR_FINANCIAL_BLEND_NEXT_W = 0.40  # [PRIOR]
CR_GROWTH_DETERIORATION_LO = 0.01  # [PRIOR]
CR_GROWTH_DETERIORATION_HI = 0.20  # [PRIOR]
CR_WAR_BLEND_AT_WAR_W = 0.60  # [PRIOR]
CR_WAR_BLEND_NEXT_W = 0.40  # [PRIOR]
CR_REV_PROTEST_W = 0.30  # [PRIOR]
CR_REV_TENSION_W = 0.25  # [PRIOR]
CR_REV_TRUST_W = 0.20  # [PRIOR]
CR_REV_FRAGILITY_W = 0.15  # [PRIOR]
CR_REV_TREND_W = 0.10  # [PRIOR]
CR_REV_TREND_LO = 0.0  # [PRIOR]
CR_REV_TREND_HI = 0.20  # [PRIOR]
CR_SOCIAL_RISK_REV_W = 0.55  # [PRIOR]
CR_SOCIAL_RISK_STRUCT_W = 0.30  # [PRIOR]
CR_SOCIAL_RISK_COLLAPSE_W = 0.15  # [PRIOR]
CR_SOCIAL_RISK_MANAGEMENT_W = 0.20  # [PRIOR]
CR_SANCTIONS_BLEND_NOW_W = 0.55  # [PRIOR]
CR_SANCTIONS_BLEND_NEXT_W = 0.45  # [PRIOR]
CR_RESERVE_ENERGY_YEARS = 3.0  # [PRIOR]
CR_RESERVE_FOOD_YEARS = 2.0  # [PRIOR]
CR_RESERVE_METALS_YEARS = 3.0  # [PRIOR]
CR_RESERVE_RISK_ENERGY_W = 0.50  # [PRIOR]
CR_RESERVE_RISK_FOOD_W = 0.30  # [PRIOR]
CR_RESERVE_RISK_METALS_W = 0.20  # [PRIOR]
CR_MACRO_GROWTH_W = 0.35  # [PRIOR]
CR_MACRO_UNEMPLOYMENT_W = 0.20  # [PRIOR]
CR_MACRO_INFLATION_W = 0.15  # [PRIOR]
CR_MACRO_FX_BUFFER_W = 0.15  # [PRIOR]
CR_MACRO_RESERVE_W = 0.15  # [PRIOR]
CR_MACRO_UNEMPLOYMENT_LO = 0.05  # [PRIOR]
CR_MACRO_UNEMPLOYMENT_HI = 0.22  # [PRIOR]
CR_MACRO_INFLATION_LO = 0.02  # [PRIOR]
CR_MACRO_INFLATION_HI = 0.12  # [PRIOR]
CR_MACRO_FX_BUFFER_CAP = 0.20  # [PRIOR]
CR_TOTAL_FINANCIAL_W = 0.25  # [PRIOR]
CR_TOTAL_WAR_W = 0.20  # [PRIOR]
CR_TOTAL_SOCIAL_W = 0.22  # [PRIOR]
CR_TOTAL_SANCTIONS_W = 0.13  # [PRIOR]
CR_TOTAL_MACRO_W = 0.20  # [PRIOR]

CALIBRATION_STATUS = {
    "ALPHA_CAPITAL": "validated",
    "BETA_LABOR": "validated",
    "GAMMA_ENERGY": "backtest",
    "SAVINGS_BASE": "validated",
    "CAPITAL_DEPRECIATION": "validated",
    "TFP_RD_SHARE_SENS": "backtest",
    "TFP_TRADE_SPILLOVER_SENS": "prior",
    "OBS_MAX_NEIGHBORS": "prior",
    "POLICY_LOG_DEPTH": "prior",
    "TAX_RATE_BASE": "validated",
    "SOCIAL_SPEND_BASE": "validated",
    "MILITARY_SPEND_BASE": "validated",
    "CLIMATE_ADAPT_BASE": "prior",
    "CLIMATE_ADAPT_RISK_SENS": "prior",
    "MAX_NEW_DEBT_GDP": "validated",
    "CARBON_POOL_FRACTIONS": "validated",
    "CARBON_POOL_TIMESCALES": "validated",
    "ECS_DEFAULT": "validated",
    "F_NONCO2_DEFAULT": "validated",
    "HEAT_CAP_SURFACE": "backtest",
    "FORCING_LOG_COEFF": "validated",
    "EMISSIONS_SCALE": "validated",
    "TEMP_NATURAL_VARIABILITY_SIGMA": "data",
    "TEMP_NATURAL_VARIABILITY_AR1_RHO": "data",
    "TEMP_BACKTEST_ENSEMBLE_SIZE": "backtest",
    "TECH_DECARB_K": "prior",
    "DECARB_RATE_OBSERVED_REFERENCE": "data",
    "DECARB_RATE_STRUCTURAL": "artifact",
    "DECARB_RATE": "artifact",
    "STRUCTURAL_TRANSITION_POLICY_SENS": "prior",
    "STRUCTURAL_TRANSITION_TAX_SENS": "prior",
    "DAMAGE_QUAD_COEFF": "data",
    "GROWTH_DAMAGE_TFP_COEFF": "data",
    "DAMAGE_BENEFIT_PEAK": "deprecated",
    "DAMAGE_BENEFIT_MAX": "deprecated",
    "DAMAGE_RISK_ADJ": "questionable",
    "CRISK_RESPONSE_RATE": "prior",
    "CRISK_TEMP_SENSITIVITY": "prior",
    "CRISK_WATER_WEIGHT": "prior",
    "CRISK_GINI_WEIGHT": "questionable",
    "EVENT_BASE_PROB": "prior",
    "EVENT_MAX_EXTRA_PROB": "prior",
    "EVENT_RESILIENCE_DAMP": "prior",
    "BASE_BIRTH_RATE": "validated",
    "BASE_DEATH_RATE": "validated",
    "MIGRATION_BASE_RATE": "prior",
    "TRUST_UNEMPLOYMENT_SENS": "data",
    "TRUST_INFLATION_SENS": "data",
    "TRUST_GINI_SENS": "data",
    "GINI_FISCAL_SENS": "prior",
    "REGIME_COLLAPSE_TRUST_THRESHOLD": "prior",
    "REGIME_CRISIS_PERSIST_GDP_MULT": "data",
    "REGIME_CRISIS_PERSIST_CAPITAL_MULT": "data",
    "REGIME_CRISIS_MAX_YEARS": "data",
    "DEBT_CRISIS_DEBT_THRESHOLD": "prior",
    "DEBT_CRISIS_PERSIST_GDP_MULT": "data",
    "DEBT_CRISIS_PERSIST_TRUST_HIT": "data",
    "DEBT_CRISIS_PERSIST_TENSION_HIT": "data",
    "DEBT_CRISIS_EXIT_THRESHOLD": "data",
    "DEBT_CRISIS_EXIT_RATE": "data",
    "DEBT_CRISIS_MAX_YEARS": "data",
    "FX_CRISIS_EXTERNAL_DEBT_THRESHOLD": "prior",
    "FX_CRISIS_CURRENT_ACCOUNT_DEFICIT_THRESHOLD": "prior",
    "FX_CRISIS_RESERVE_MONTHS_THRESHOLD": "prior",
    "FX_CRISIS_RESERVE_OFFSET_WEIGHT": "prior",
    "FX_CRISIS_IMPORT_LEAKAGE_WEIGHT": "prior",
    "FX_CRISIS_DEBT_MULT": "prior",
    "FX_CRISIS_GDP_MULT": "prior",
    "FX_CRISIS_UNEMPLOYMENT_HIT": "prior",
    "FX_CRISIS_TRUST_HIT": "prior",
    "FX_CRISIS_TENSION_HIT": "prior",
    "FX_CRISIS_STABILITY_HIT": "prior",
    "FX_CRISIS_PERSIST_GDP_MULT": "prior",
    "FX_CRISIS_PERSIST_TRUST_HIT": "prior",
    "FX_CRISIS_PERSIST_TENSION_HIT": "prior",
    "FX_CRISIS_RECOVERY_RESERVE_MONTHS": "prior",
    "FX_CRISIS_MAX_YEARS": "prior",
    "PROTEST_RISK_TENSION_W": "prior",
    "PROTEST_RISK_DISTRUST_W": "prior",
    "PROTEST_RISK_GINI_W": "prior",
}
