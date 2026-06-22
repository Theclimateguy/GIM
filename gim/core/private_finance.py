"""Stock-flow-consistent private finance (F2.3/E3.3 — THE-38/THE-44).

Adds a private-sector credit stock and a **financial accelerator** on top of the T1.1 sovereign
debt identity, plus an explicit **bank balance sheet + money** (E3.3): every loan creates a matching
deposit, so broad money = deposits = loans, with an enforceable closed identity. Default ON in the
headline (accounting is golden-safe). The optional money->inflation transmission is a separate,
calibratable behavioural switch.

Mechanism (per agent, per year):

    leverage      = private_debt / GDP
    excess        = max(0, leverage - SFC_LEVERAGE_REF)
    credit_appetite *= (1 - SFC_ACCEL_SENS * excess)          # accelerator damps credit when levered
    new_credit    = SFC_CREDIT_APPETITE * GDP * appetite
    repayment     = SFC_REPAY_RATE * private_debt
    private_debt += new_credit - repayment                    # SFC flow: ΔDebt = credit - repayment
    credit_premium = min(SFC_PREMIUM_CAP, SFC_PREMIUM_SENS * excess)   # raises the borrowing rate

The credit premium is read by `compute_effective_interest_rate` (additive), so over-leverage
raises debt service and dampens growth — a Bernanke-Gertler-style financial accelerator. In a
closed world every loan is a matching deposit (bank liability); we carry the debt (asset) side and
treat the deposit side as its mirror. A full bank/money-stock balance sheet is the next D3 step.

State is held on runtime attributes (`economy._private_debt`, `economy._credit_premium`) so no CSV
column / hash-bound artifact changes are needed.
"""
from __future__ import annotations

from .core import AgentState, WorldState
from .params import resolve_params


def update_private_finance(agent: AgentState, world: WorldState) -> None:
    cal = resolve_params(world)
    if not getattr(cal, "SFC_FINANCE", False):
        return
    econ = agent.economy
    gdp = max(float(econ.gdp), 1e-6)

    pd = getattr(econ, "_private_debt", None)
    if pd is None:
        pd = getattr(cal, "SFC_INIT_LEVERAGE", 1.0) * gdp

    leverage = pd / gdp
    excess = max(0.0, leverage - getattr(cal, "SFC_LEVERAGE_REF", 1.5))
    appetite = max(0.0, 1.0 - getattr(cal, "SFC_ACCEL_SENS", 0.5) * excess)
    new_credit = getattr(cal, "SFC_CREDIT_APPETITE", 0.10) * gdp * appetite
    repayment = getattr(cal, "SFC_REPAY_RATE", 0.08) * pd
    net_flow = new_credit - repayment
    pd = max(0.0, pd + net_flow)  # stock-flow-consistent update (loans / bank assets)

    # [E3.3] Full bank balance sheet: a loan creates a matching deposit, so deposits (bank liability)
    # and broad money move with the same net flow as loans. In this closed banking system money is
    # endogenous (loans create deposits), and the closed identity deposits == loans holds by
    # construction -- guarded by `sfc_balance_residual` below.
    deposits = getattr(econ, "_bank_deposits", None)
    if deposits is None:
        deposits = max(0.0, pd - net_flow)  # opening deposit stock mirrors the opening loan stock
    deposits = max(0.0, deposits + net_flow)  # same net flow -> deposits track loans (closed banking)

    econ._private_debt = pd
    econ._bank_deposits = deposits
    econ._money_supply = deposits  # broad money = bank deposits (endogenous money)
    econ._credit_premium = min(
        getattr(cal, "SFC_PREMIUM_CAP", 0.10),
        getattr(cal, "SFC_PREMIUM_SENS", 0.04) * excess,
    )


def sfc_balance_residual(agent: AgentState) -> float:
    """Closed-banking identity residual: |loans - deposits| / max(loans, 1). ~0 when consistent (E3.3)."""
    loans = getattr(agent.economy, "_private_debt", None)
    deposits = getattr(agent.economy, "_bank_deposits", None)
    if loans is None or deposits is None:
        return 0.0
    return abs(loans - deposits) / max(abs(loans), 1.0)
