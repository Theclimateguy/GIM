"""Accounting / integrity invariant layer for the GIM17 yearly transition.

This module turns previously-silent reconciliation behaviour into explicit,
auditable signals. It consumes the two artifacts the reconcile phase already
produces every step:

- the bounds / debt-residual report from ``simulation._invariant_report``
- the per-agent critical-field accounting from
  ``transitions.reconcile.reconcile_critical_fields`` (which records, per channel,
  how each critical field moved and how much the final clamp adjusted it).

It distinguishes two classes of invariant:

ENFORCEABLE (strict mode raises ``InvariantViolation``):
  1. bounds          - no post-clamp field is out of its allowed range
  2. reconcile_clamp - the final clamp in ``reconcile.py`` moved a value by more
                       than ``RECONCILE_CLAMP_TOL`` (i.e. reconcile is silently
                       masking an out-of-bounds propagated value)
  3. channel_telescope - the per-channel deltas sum to the net propagation delta
                       (snapshot-wiring consistency)

DIAGNOSTIC (reported, never raises - documented known gap, see docs/INVARIANTS.md):
  4. debt_fiscal_residual - deviation of the realised debt change from the clean
                       fiscal identity ``Δdebt = (gov_spending - taxes) + interest``.
                       Currently non-zero by construction (borrowing cap, debt
                       zero-flooring inside ``economy.py``, and crisis debt shocks).

Mode is resolved from ``GIM17_INVARIANT_MODE`` (``off`` | ``observe`` | ``strict``),
default ``observe`` (compute + log, never raise).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

CRITICAL_FIELDS = ("gdp", "capital", "public_debt", "trust_gov", "social_tension")
CHANNEL_KEYS = ("sanctions_conflict", "policy_trade", "climate_macro", "social_feedback")

# Enforceable tolerances.
RECONCILE_CLAMP_TOL = 1e-6
CHANNEL_TELESCOPE_TOL = 1e-6
TRADE_BALANCE_TOL = 1e-6  # |sum(net_exports)| / world_gdp for a closed world economy

# Diagnostic threshold (reported, not enforced) used only for run-level flagging.
DEBT_FISCAL_RESIDUAL_FLAG_SHARE = 0.05

_VALID_MODES = {"off", "observe", "strict"}


class InvariantViolation(RuntimeError):
    """Raised in strict mode when an enforceable invariant is breached."""


def resolve_invariant_mode(explicit: Optional[str] = None) -> str:
    raw = explicit if explicit is not None else os.getenv("GIM17_INVARIANT_MODE")
    if not raw:
        return "observe"
    mode = str(raw).strip().lower()
    return mode if mode in _VALID_MODES else "observe"


def summarize_clamp(critical_accounting: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate the final reconcile-clamp adjustments (final - raw) per field."""
    by_field = {f: {"count": 0, "max_abs": 0.0} for f in CRITICAL_FIELDS}
    worst: List[Dict[str, Any]] = []
    max_abs_overall = 0.0
    for agent_id, rec in critical_accounting.items():
        adj = rec.get("reconcile_adjustment", {})
        for f in CRITICAL_FIELDS:
            mag = abs(float(adj.get(f, 0.0)))
            if mag > 0.0:
                by_field[f]["count"] += 1
                if mag > by_field[f]["max_abs"]:
                    by_field[f]["max_abs"] = mag
                if mag > max_abs_overall:
                    max_abs_overall = mag
                if mag > RECONCILE_CLAMP_TOL:
                    worst.append({"agent_id": agent_id, "field": f, "adjustment": float(adj.get(f, 0.0))})
    worst.sort(key=lambda item: abs(item["adjustment"]), reverse=True)
    return {"by_field": by_field, "max_abs": max_abs_overall, "over_tol": worst[:10]}


def summarize_channel_telescope(critical_accounting: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Check per-channel deltas sum to the recorded net propagation delta."""
    max_abs = 0.0
    worst: List[Dict[str, Any]] = []
    for agent_id, rec in critical_accounting.items():
        channels = rec.get("channels", {})
        net = channels.get("net_propagation", {})
        for f in CRITICAL_FIELDS:
            summed = sum(float(channels.get(ch, {}).get(f, 0.0)) for ch in CHANNEL_KEYS)
            diff = abs(summed - float(net.get(f, 0.0)))
            if diff > max_abs:
                max_abs = diff
            if diff > CHANNEL_TELESCOPE_TOL:
                worst.append({"agent_id": agent_id, "field": f, "diff": diff})
    worst.sort(key=lambda item: item["diff"], reverse=True)
    return {"max_abs": max_abs, "over_tol": worst[:10]}


def summarize_step(
    *,
    year: int,
    invariant_report: Dict[str, Any],
    critical_accounting: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Build one compact, auditable invariant record for a finalized year."""
    return {
        "year": int(year),
        "bounds": {
            "breach_count": int(invariant_report.get("breach_count", 0)),
            "breaches": list(invariant_report.get("breaches", []))[:20],
        },
        "reconcile_clamp": summarize_clamp(critical_accounting),
        "channel_telescope": summarize_channel_telescope(critical_accounting),
        "debt_fiscal_residual": {
            "abs_share_max": float(invariant_report.get("debt_residual_abs_share_max", 0.0)),
            "abs_share_mean": float(invariant_report.get("debt_residual_abs_share_mean", 0.0)),
            "count": int(invariant_report.get("debt_residual_count", 0)),
            "top": list(invariant_report.get("debt_accounting_residual_top10", []))[:10],
        },
        "trade_balance": dict(invariant_report.get("trade_balance", {})),
        "resource_consistency": dict(invariant_report.get("resource_consistency", {})),
    }


def evaluate_violations(summary: Dict[str, Any]) -> List[str]:
    """Return messages for breached ENFORCEABLE invariants (empty == clean)."""
    violations: List[str] = []
    year = summary.get("year")
    bounds = summary.get("bounds", {})
    if int(bounds.get("breach_count", 0)) > 0:
        violations.append(
            f"year {year}: {bounds['breach_count']} post-clamp bounds breach(es): "
            f"{bounds.get('breaches', [])[:3]}"
        )
    clamp = summary.get("reconcile_clamp", {})
    if float(clamp.get("max_abs", 0.0)) > RECONCILE_CLAMP_TOL:
        violations.append(
            f"year {year}: reconcile clamp adjusted a critical field by "
            f"{clamp['max_abs']:.3e} (> {RECONCILE_CLAMP_TOL:.0e}); offenders={clamp.get('over_tol', [])[:3]}"
        )
    tele = summary.get("channel_telescope", {})
    if float(tele.get("max_abs", 0.0)) > CHANNEL_TELESCOPE_TOL:
        violations.append(
            f"year {year}: channel deltas do not sum to net propagation "
            f"(max diff {tele['max_abs']:.3e}); offenders={tele.get('over_tol', [])[:3]}"
        )
    trade = summary.get("trade_balance", {})
    if float(trade.get("abs_share", 0.0)) > TRADE_BALANCE_TOL:
        violations.append(
            f"year {year}: world trade balance not closed "
            f"(|sum net_exports|/gdp={trade['abs_share']:.3e} > {TRADE_BALANCE_TOL:.0e}, "
            f"sum={trade.get('net_exports_sum')})"
        )
    return violations


def enforce(summary: Dict[str, Any], mode: str) -> None:
    """In strict mode, raise InvariantViolation if any enforceable invariant is breached."""
    if mode != "strict":
        return
    violations = evaluate_violations(summary)
    if violations:
        raise InvariantViolation(" | ".join(violations))


def aggregate_run(step_summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compact run-level roll-up for the run manifest."""
    if not step_summaries:
        return {"mode": resolve_invariant_mode(), "years": 0}

    total_bounds = sum(int(s["bounds"]["breach_count"]) for s in step_summaries)
    max_clamp = max(float(s["reconcile_clamp"]["max_abs"]) for s in step_summaries)
    max_tele = max(float(s["channel_telescope"]["max_abs"]) for s in step_summaries)
    max_trade = max(float(s.get("trade_balance", {}).get("abs_share", 0.0)) for s in step_summaries)

    worst_debt = max(
        step_summaries,
        key=lambda s: float(s["debt_fiscal_residual"]["abs_share_max"]),
    )
    worst_share = float(worst_debt["debt_fiscal_residual"]["abs_share_max"])

    # Resource consistency diagnostic (Finding C-1): which pools ever run exhausted while
    # production continues, and the worst global-vs-aggregated-country reserve divergence.
    exhausted_pools = sorted({
        name
        for s in step_summaries
        for name, rc in s.get("resource_consistency", {}).items()
        if rc.get("global_exhausted_with_active_production")
    })
    ratio_samples = [
        rc["global_to_own_ratio"]
        for s in step_summaries
        for rc in s.get("resource_consistency", {}).values()
        if rc.get("global_to_own_ratio") is not None
    ]

    per_year = [
        {
            "year": s["year"],
            "bounds_breaches": int(s["bounds"]["breach_count"]),
            "max_reconcile_clamp": float(s["reconcile_clamp"]["max_abs"]),
            "max_channel_telescope": float(s["channel_telescope"]["max_abs"]),
            "trade_balance_abs_share": float(s.get("trade_balance", {}).get("abs_share", 0.0)),
            "debt_residual_abs_share_max": float(s["debt_fiscal_residual"]["abs_share_max"]),
            "debt_residual_abs_share_mean": float(s["debt_fiscal_residual"]["abs_share_mean"]),
        }
        for s in step_summaries
    ]

    return {
        "mode": resolve_invariant_mode(),
        "years": len(step_summaries),
        "enforceable": {
            "total_bounds_breaches": total_bounds,
            "max_reconcile_clamp": max_clamp,
            "max_channel_telescope": max_tele,
            "max_trade_balance_abs_share": max_trade,
            "clean": (
                total_bounds == 0
                and max_clamp <= RECONCILE_CLAMP_TOL
                and max_tele <= CHANNEL_TELESCOPE_TOL
                and max_trade <= TRADE_BALANCE_TOL
            ),
        },
        "diagnostic_debt_fiscal_residual": {
            "worst_abs_share": worst_share,
            "worst_year": worst_debt["year"],
            "worst_top": worst_debt["debt_fiscal_residual"]["top"][:5],
            "flagged": worst_share > DEBT_FISCAL_RESIDUAL_FLAG_SHARE,
            "note": "Diagnostic only (not enforced). See docs/INVARIANTS.md Finding B-1.",
        },
        "diagnostic_resource_consistency": {
            "pools_exhausted_with_active_production": exhausted_pools,
            "min_global_to_own_ratio": (min(ratio_samples) if ratio_samples else None),
            "max_global_to_own_ratio": (max(ratio_samples) if ratio_samples else None),
            "flagged": bool(exhausted_pools),
            "note": "Diagnostic only (not enforced). See docs/INVARIANTS.md Finding C-1.",
        },
        "per_year": per_year,
    }


__all__ = [
    "InvariantViolation",
    "RECONCILE_CLAMP_TOL",
    "CHANNEL_TELESCOPE_TOL",
    "TRADE_BALANCE_TOL",
    "DEBT_FISCAL_RESIDUAL_FLAG_SHARE",
    "resolve_invariant_mode",
    "summarize_clamp",
    "summarize_channel_telescope",
    "summarize_step",
    "evaluate_violations",
    "enforce",
    "aggregate_run",
]
