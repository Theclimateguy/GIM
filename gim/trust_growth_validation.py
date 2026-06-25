"""S3 — trust -> growth channel validation (social-domain analogue of the D6 check).

The premise of a Knack-Keefer (1997) / Algan-Cahuc (2010) reproduction is a *marginal* social-capital ->
TFP/investment -> growth elasticity (~+0.5-0.8pp growth per +10pp trust). Tracing GIM shows trust_gov is
read into the economy in exactly ONE place -- the credit-rating "management" score (gim/core/credit_rating)
-- which is a reported diagnostic that does NOT feed the effective interest rate (and hence not
investment or growth). So:

  FINDING (structural): GIM has NO marginal trust->growth channel. The effective interest rate, and thus
  the cost of capital and investment, are invariant to trust_gov. A smooth Knack-Keefer elasticity is
  therefore not applicable to the current model -- a candidate extension (trust -> TFP), not a defect to
  paper over.

  CHANNEL THAT EXISTS (validated): the only trust->growth pathway is the NONLINEAR regime-collapse
  threshold (gim/core/social.check_regime_stability): once trust < REGIME_COLLAPSE_TRUST_THRESHOLD (0.20)
  and tension > REGIME_COLLAPSE_TENSION_THRESHOLD (0.80), output takes a one-off REGIME_COLLAPSE_GDP_MULT
  hit. We validate that the collapse MAGNITUDE matches the macroeconomic-disaster / cost-of-instability
  literature (Barro & Ursua 2008 disasters ~typically 20% peak-to-trough; Aisen & Veiga 2013; civil-war /
  state-collapse output losses ~10-30%), and anchor REGIME_COLLAPSE_GDP_MULT to it. The collapse
  THRESHOLDS stay Tier-C expert priors (no canonical number; sensitivity-disciplined).

See docs/calibration/SOCIAL_VALIDATION_PROGRAM.md.
"""

from __future__ import annotations

from typing import Dict

from .core.core import (
    AgentState,
    ClimateSubState,
    CulturalState,
    EconomyState,
    GlobalState,
    ResourceSubState,
    RiskState,
    SocietyState,
    TechnologyState,
    WorldState,
)
from .core.economy import compute_effective_interest_rate
from .core.social import check_regime_stability


def _agent(
    *, gdp: float = 1.0, trust: float = 0.6, tension: float = 0.2, regime_stability: float = 0.7
) -> AgentState:
    economy = EconomyState(
        gdp=gdp, capital=3.0 * gdp, population=50_000_000.0, public_debt=0.8 * gdp, fx_reserves=0.2,
        unemployment=0.06, inflation=0.02,
    )
    economy.gdp_per_capita = economy.gdp * 1e12 / economy.population
    return AgentState(
        id="A", type="country", name="A", region="test", economy=economy,
        resources={
            "energy": ResourceSubState(own_reserve=10.0, production=1.0, consumption=1.0),
            "food": ResourceSubState(own_reserve=10.0, production=1.0, consumption=1.0),
            "metals": ResourceSubState(own_reserve=10.0, production=1.0, consumption=1.0),
        },
        society=SocietyState(trust_gov=trust, social_tension=tension, inequality_gini=40.0),
        climate=ClimateSubState(climate_risk=0.3),
        culture=CulturalState(),
        technology=TechnologyState(),
        risk=RiskState(water_stress=0.3, regime_stability=regime_stability,
                       debt_crisis_prone=0.3, conflict_proneness=0.2),
    )


def interest_rate_trust_sensitivity() -> Dict[str, float]:
    """Max change in the effective interest rate as trust_gov sweeps [0.05, 0.95] (all else fixed).

    ~0 demonstrates that GIM has no marginal trust->growth channel: the rate (-> cost of capital ->
    investment) does not respond to trust.
    """
    rates = []
    for i in range(19):
        trust = 0.05 + 0.05 * i
        rates.append(compute_effective_interest_rate(_agent(trust=trust), None))
    return {"rate_min": min(rates), "rate_max": max(rates), "rate_span": max(rates) - min(rates)}


def regime_collapse_gdp_drop(gdp: float = 1.0) -> Dict[str, float]:
    """One-off GDP drop fraction when an agent crosses the regime-collapse threshold.

    Drives the SHIPPED check_regime_stability with trust below / tension above the collapse thresholds
    and measures the realised output loss -- the only trust->growth pathway GIM has.
    """
    agent = _agent(gdp=gdp, trust=0.10, tension=0.90, regime_stability=0.5)
    g0 = agent.economy.gdp
    cap0 = agent.economy.capital
    check_regime_stability(agent, None)  # world=None branch applies the collapse directly to economy
    return {
        "gdp_drop_frac": 1.0 - agent.economy.gdp / g0,
        "capital_drop_frac": 1.0 - agent.economy.capital / cap0,
        "regime_crisis_active_years": float(agent.risk.regime_crisis_active_years),
    }


__all__ = [
    "interest_rate_trust_sensitivity",
    "regime_collapse_gdp_drop",
]
