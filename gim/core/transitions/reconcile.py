from __future__ import annotations

from dataclasses import asdict

from .baseline import capture_critical_fields
from .schemas import CriticalFieldSnapshot, ReconciledWrites


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))


def _clamp_nonnegative(value: float) -> float:
    return max(0.0, value)


def reconcile_critical_fields(
    world,
    *,
    baseline: dict[str, CriticalFieldSnapshot],
    propagated: dict[str, CriticalFieldSnapshot],
    channel_snapshots: dict[str, dict[str, CriticalFieldSnapshot]] | None = None,
) -> dict[str, dict]:
    snapshots = dict(channel_snapshots or {})

    def _state_for(
        mapping: dict[str, CriticalFieldSnapshot],
        agent_id: str,
        fallback: CriticalFieldSnapshot,
    ) -> CriticalFieldSnapshot:
        return mapping.get(agent_id, fallback)

    def _delta_dict(
        start_state: CriticalFieldSnapshot,
        end_state: CriticalFieldSnapshot,
    ) -> dict[str, float]:
        return {
            "gdp": end_state.gdp - start_state.gdp,
            "capital": end_state.capital - start_state.capital,
            "public_debt": end_state.public_debt - start_state.public_debt,
            "trust_gov": end_state.trust_gov - start_state.trust_gov,
            "social_tension": end_state.social_tension - start_state.social_tension,
        }

    accounting: dict[str, dict] = {}
    for agent_id, baseline_state in baseline.items():
        agent = world.agents.get(agent_id)
        if agent is None:
            continue
        propagated_state = propagated.get(agent_id, baseline_state)

        net_gdp = propagated_state.gdp - baseline_state.gdp
        raw_gdp = baseline_state.gdp + net_gdp
        final_gdp = _clamp_nonnegative(raw_gdp)

        net_capital = propagated_state.capital - baseline_state.capital
        raw_capital = baseline_state.capital + net_capital
        final_capital = _clamp_nonnegative(raw_capital)

        net_debt = propagated_state.public_debt - baseline_state.public_debt
        raw_debt = baseline_state.public_debt + net_debt
        final_debt = _clamp_nonnegative(raw_debt)

        net_trust = propagated_state.trust_gov - baseline_state.trust_gov
        raw_trust = baseline_state.trust_gov + net_trust
        final_trust = _clamp_unit(raw_trust)

        net_tension = propagated_state.social_tension - baseline_state.social_tension
        raw_tension = baseline_state.social_tension + net_tension
        final_tension = _clamp_unit(raw_tension)

        # Canonical final writes are centralized here.
        agent.economy.gdp = final_gdp
        agent.economy.capital = final_capital
        agent.economy.public_debt = final_debt
        agent.society.trust_gov = final_trust
        agent.society.social_tension = final_tension

        after_security = _state_for(
            snapshots.get("after_security_trade_barrier", {}),
            agent_id,
            baseline_state,
        )
        after_policy_trade = _state_for(
            snapshots.get("after_policy_trade_relations", {}),
            agent_id,
            after_security,
        )
        after_climate_macro = _state_for(
            snapshots.get("after_climate_macro", {}),
            agent_id,
            after_policy_trade,
        )

        accounting[agent_id] = {
            "baseline": asdict(baseline_state),
            "channels": {
                "sanctions_conflict": _delta_dict(baseline_state, after_security),
                "policy_trade": _delta_dict(after_security, after_policy_trade),
                "climate_macro": _delta_dict(after_policy_trade, after_climate_macro),
                "social_feedback": _delta_dict(after_climate_macro, propagated_state),
                "net_propagation": {
                    "gdp": net_gdp,
                    "capital": net_capital,
                    "public_debt": net_debt,
                    "trust_gov": net_trust,
                    "social_tension": net_tension,
                }
            },
            "reconcile_adjustment": {
                "gdp": final_gdp - raw_gdp,
                "capital": final_capital - raw_capital,
                "public_debt": final_debt - raw_debt,
                "trust_gov": final_trust - raw_trust,
                "social_tension": final_tension - raw_tension,
            },
            "final": {
                "gdp": final_gdp,
                "capital": final_capital,
                "public_debt": final_debt,
                "trust_gov": final_trust,
                "social_tension": final_tension,
            },
        }
    return accounting


def build_reconciled_writes(
    world,
    world_metrics: dict[str, float],
    invariants: dict,
) -> ReconciledWrites:
    return ReconciledWrites(
        world_metrics=dict(world_metrics),
        critical_fields_by_agent=capture_critical_fields(world),
        invariants=dict(invariants),
    )


__all__ = [
    "build_reconciled_writes",
    "reconcile_critical_fields",
]
