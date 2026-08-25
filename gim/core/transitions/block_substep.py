"""Block-layer propagate sub-step (spec §11, THE-128).

For agents listed in calibration_params.BLOCK_LAYER_AGENTS (default: empty —
the core is bit-identical with the flag off) the intra-country block model
contributes social deltas during propagate: the fitted interaction channel
(price-income squeeze → tension, tension → trust erosion; Levada calibration)
adjusts society.social_tension / trust_gov the same way update_social_state
does — direct writes during propagate, audited by the write guard, finalized
only in reconcile per the authorized-writers contract.

Insertion point: after the update_public_finances loop, before
update_inflation_unemployment (economy.inflation still carries the previous
step's value — the block equations are fitted on lagged annual data).
"""

from __future__ import annotations

from ..params import resolve_params


def apply_block_policy_bridge(world) -> None:
    """Baseline-phase policy bridge (spec §11 / THE-127).

    For flagged agents the block model steps one year at the top of the annual
    step and refines the agent's policy-carrying parameters BEFORE the core
    generates policies:

      key rate     -> economy._block_policy_rate (fraction) — replaces the
                      generic Taylor base in compute_effective_interest_rate
      milex share  -> agent._block_military_share (fraction of GDP) — replaces
                      cal.MILITARY_SPEND_BASE in update_public_finances

    The block model's oil input is driven by the core's own world energy price
    (Brent_2023 scaled by the price index), closing the loop core -> blocks ->
    core. Block state is carried on the agent across steps. No-op when
    BLOCK_LAYER_AGENTS is empty.
    """
    params = resolve_params(world)
    agents = getattr(params, "BLOCK_LAYER_AGENTS", ())
    if not agents:
        return
    from ...blocks.core_adapter import step_policy_bridge

    energy_price = float(getattr(world.global_state, "prices", {}).get("energy", 1.0))
    year = int(getattr(world.global_state, "_calendar_year_base", 2023)) \
        + int(world.time) + 1
    # scenario hook, not a numeric parameter: ParameterSet snapshots only
    # int/float/tuple values, so the callable is read from the module directly
    from .. import calibration_params as _calmod
    war_fn = getattr(_calmod, "BLOCK_WAR_INTENSITY_FN", None)
    for agent_id in agents:
        agent = world.agents.get(agent_id)
        if agent is None:
            continue
        carried = getattr(agent, "_block_bridge_state", None)
        state, outputs = step_policy_bridge(
            carried, year, energy_price,
            war_intensity=war_fn(year) if war_fn is not None else None)
        if state is None:
            continue
        agent._block_bridge_state = state
        agent.economy._block_policy_rate = outputs["policy_rate"]
        agent._block_military_share = outputs["military_share"]
        agent.economy._block_inflation = outputs["inflation"]
        agent.economy._block_invest_tilt = outputs.get("invest_rent_tilt", 0.0)


def apply_block_layer_substep(world) -> None:
    params = resolve_params(world)
    agents = getattr(params, "BLOCK_LAYER_AGENTS", ())
    if not agents:
        return
    from ...blocks.core_adapter import compute_social_deltas

    for agent_id in agents:
        agent = world.agents.get(agent_id)
        if agent is None:
            continue
        econ = agent.economy
        gdp_prev = getattr(econ, "_macro_gdp_prev", None)
        if gdp_prev and gdp_prev > 0:
            growth_pct = (float(econ.gdp) / float(gdp_prev) - 1.0) * 100.0
        else:
            growth_pct = 0.0
        inflation_pct = float(econ.inflation) * 100.0
        from ...blocks.dynamics import scenario_war_intensity
        year = int(getattr(world.global_state, "_calendar_year_base", 2023)) \
            + int(world.time)
        from .. import calibration_params as _calmod
        war_fn = getattr(_calmod, "BLOCK_WAR_INTENSITY_FN", None)
        wi = war_fn(year) if war_fn is not None else scenario_war_intensity(year)
        d_tension, d_trust = compute_social_deltas(
            inflation_pct, growth_pct, wi,
            tension_level=float(agent.society.social_tension))
        soc = agent.society
        soc.social_tension = min(1.0, max(0.0, soc.social_tension + d_tension))
        soc.trust_gov = min(1.0, max(0.0, soc.trust_gov + d_trust))
