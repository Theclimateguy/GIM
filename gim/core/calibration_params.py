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
ALPHA_CAPITAL = 0.30  # [PWT10]
BETA_LABOR = 0.60  # [PWT10]
GAMMA_ENERGY = 0.042  # [BACKTEST] Stage B/C robust rolling baseline (2015-2023).
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
TFP_GROWTH_MIN = -0.05
TFP_GROWTH_MAX = 0.05
# Growth-effect climate damage (F4): warming above the 2023 baseline persistently lowers TFP
# growth (Burke et al. 2015 / Kotz et al. 2024), distinct from the level-effect output
# multiplier. DEFAULT 0.0 => OFF (golden backtest preserved). Reference "on" value ~0.001/degC
# gives a bounded persistent growth drag spanning toward the empirical growth-effect range.
GROWTH_DAMAGE_TFP_COEFF = 0.0  # [F4] per-degC TFP-growth drag above the 2023 baseline; 0 => off.

# Self-organized-criticality crisis severity (F5): make crisis shock DEPTH fat-tailed (power-law /
# Richardson) instead of fixed. The severity multiplier is mean-1, so the AVERAGE shock equals the
# existing fixed magnitude; only the tail changes. DEFAULT OFF (golden backtest preserved).
CRISIS_SEVERITY_POWERLAW = False  # [F5] enable fat-tailed crisis severity.
CRISIS_SEVERITY_ALPHA = 1.5       # [RICHARDSON] power-law exponent for event severity (~1.5-1.6).
CRISIS_SEVERITY_MAX = 20.0        # truncation of the severity power law.

# Fiscal and sovereign block.
BASE_INTEREST_RATE = 0.02  # [WEO25]
DEBT_SPREAD_THRESHOLD = 0.60  # [PRIOR]
DEBT_SPREAD_LINEAR = 0.03  # [PRIOR]
DEBT_SPREAD_QUADRATIC = 0.10  # [PRIOR]
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
ECS_DEFAULT = 3.0  # [IPCC_AR6]
ECS_MIN = 1.5  # [IPCC_AR6]
ECS_MAX = 4.0  # [IPCC_AR6]
F_NONCO2_DEFAULT = 0.40  # [IPCC_AR6]
F_NONCO2_BASE_YEAR = 2015  # [IPCC_AR6]
F_NONCO2_TREND = 0.012  # [IPCC_AR6]
HEAT_CAP_SURFACE = 8.0  # [BACKTEST] T1.3 joint multi-window recal: Geoffroy physical ~8 (was 18, a short-window artifact).
HEAT_CAP_DEEP = 100.0  # [DICE16]
OCEAN_EXCHANGE = 1.0  # [BACKTEST] T1.3 joint multi-window recal: stronger heat uptake reconciles 1990-2023 trend with 2015-2023 levels (was 0.7).
TEMP_NATURAL_VARIABILITY_SIGMA = 0.08  # [BACKTEST]
TEMP_NATURAL_VARIABILITY_AR1_RHO = 0.65  # [T2.4] AR(1) "red-noise" persistence of internal variability (ENSO-like ~0.6-0.7); 0 == iid.
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
DECARB_RATE_STRUCTURAL = ACTIVE_STATE_ARTIFACT.decarb_rate  # [ARTIFACT] Pipeline-bound residual structural energy-transition rate.
# NOTE: Empirical CO2/GDP intensity decline is 0.016 (see calibration/decarb_rate_calibration.json).
# The gap between the active 0.052 artifact rate and the empirical fit implicitly absorbs
# energy-mix shift and efficiency gains encoded in the 2015 base state. Decompose this
# compound parameter when the model gets an explicit energy sector / fossil phase-out layer.
DECARB_RATE = DECARB_RATE_STRUCTURAL  # Backward-compatible alias pending a full rename across the legacy layer.
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
DAMAGE_QUAD_COEFF = 0.006  # [PRIOR]
DAMAGE_BENEFIT_PEAK = 0.30  # [PRIOR]
DAMAGE_BENEFIT_MAX = 0.006  # [PRIOR]
DAMAGE_BENEFIT_STDDEV = 0.50  # [PRIOR]
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
TRUST_UNEMPLOYMENT_SENS = -0.025  # [PRIOR]
TRUST_INFLATION_SENS = -0.025  # [PRIOR]
TRUST_GINI_SENS = -0.0004  # [PRIOR]
TRUST_TENSION_SENS = -0.08  # [PRIOR]
TRUST_TENSION_THRESHOLD = 0.30  # [PRIOR]
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
    "TEMP_NATURAL_VARIABILITY_SIGMA": "backtest",
    "TEMP_BACKTEST_ENSEMBLE_SIZE": "backtest",
    "TECH_DECARB_K": "prior",
    "DECARB_RATE_OBSERVED_REFERENCE": "data",
    "DECARB_RATE_STRUCTURAL": "artifact",
    "DECARB_RATE": "artifact",
    "STRUCTURAL_TRANSITION_POLICY_SENS": "prior",
    "STRUCTURAL_TRANSITION_TAX_SENS": "prior",
    "DAMAGE_QUAD_COEFF": "prior",
    "DAMAGE_BENEFIT_PEAK": "questionable",
    "DAMAGE_BENEFIT_MAX": "questionable",
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
    "TRUST_GINI_SENS": "prior",
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
