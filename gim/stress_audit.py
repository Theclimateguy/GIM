"""Stressed-scenario influence audit for GIM's threshold-gated inputs (F3 / Stage 5).

The baseline influence audit (`gim/influence_audit.py`) runs a calm 12-year path and finds the
risk/geo inputs `military_power`, `security_index`, `debt_crisis_prone`, `conflict_proneness`
inert — but that is an artefact of the *calm* scenario: those inputs gate threshold/crisis
dynamics that do not fire when nothing is stressed. They are **conditionally load-bearing**, not
decorative like the removed Hofstede dims, and must be re-audited under stress before any removal.

This module builds a *stressed* world (high debt + injected active wars) and re-measures their
influence with the correct probe:

* `debt_crisis_prone`, `conflict_proneness` — uniform probe (every agent), like the base audit.
* `military_power`, `security_index` — these are **relative** (CINC-share) quantities: a uniform
  shift cancels in the belligerent-ratio that drives war outcomes, so they need a **differential**
  (single-agent) probe to be detected. This is a methodological point, not a model defect.

Conclusion (June 2026): debt_crisis_prone is strongly conditionally load-bearing; military_power
is load-bearing only with an active war and a differential probe, and its effect on *world
aggregates* is modest because it mainly redistributes war losses between belligerents. None are
decorative — none should be removed. Their predictive validation belongs in an explicit conflict
scenario (the UCDP backtest), not the structural audit.
"""
from __future__ import annotations

from typing import Dict

from gim.core.policy import make_policy_map
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv
from gim.influence_audit import STATE_CSV, _aggregate_outputs, _rel_change


def build_stressed_world(max_agents: int = 12, *, debt: bool = True, wars: int = 3):
    """A stressed world: elevated debt/conflict risk + `wars` injected active war dyads."""
    world = make_world_from_csv(STATE_CSV, max_agents=max_agents, base_year=2023)
    world.global_state._temperature_variability_sigma = 0.0  # deterministic
    ids = list(world.agents.keys())
    for a in world.agents.values():
        a.risk.conflict_proneness = min(1.0, a.risk.conflict_proneness + 0.6)
        a.risk.debt_crisis_prone = min(1.0, a.risk.debt_crisis_prone + 0.6)
        a.technology.security_index = max(0.0, a.technology.security_index - 0.5)
        if debt:
            a.economy.public_debt = a.economy.gdp * 1.4  # debt/GDP ~1.4 -> crisis-prone
    for i in range(min(wars, len(ids) // 2)):
        x, y = ids[2 * i], ids[2 * i + 1]
        for a, b in ((x, y), (y, x)):
            rel = world.relations[a][b]
            rel.at_war = True
            rel.war_years = 1
            rel.conflict_level = 0.95
            rel.trust = 0.05
            if hasattr(rel, "war_start_gdp"):
                rel.war_start_gdp = world.agents[a].economy.gdp
            if hasattr(rel, "war_start_pop"):
                rel.war_start_pop = world.agents[a].economy.population
    return world, ids


def _run(setter, years: int, max_agents: int, single_agent: bool):
    world, ids = build_stressed_world(max_agents=max_agents)
    if setter is not None:
        if single_agent:
            setter(world.agents[ids[0]])
        else:
            for a in world.agents.values():
                setter(a)
    policies = make_policy_map(world.agents.keys(), mode="simple")
    for _ in range(years):
        step_world(world, policies)
    return _aggregate_outputs(world)


def run_stress_audit(*, years: int = 10, max_agents: int = 12) -> Dict[str, dict]:
    """Influence of the threshold-gated inputs under stress, each with its appropriate probe."""
    # NOTE: the stressed world already lifts debt_crisis_prone / conflict_proneness by +0.6,
    # which saturates most actors at 1.0 on the validated 2023 base (raw values are higher
    # there than in the retired 2026 forward projection). An upward +0.2 probe would clamp to
    # 1.0 and register no signal — a saturation artefact, not inertness. We therefore probe
    # *downward* (-0.2) from the stressed operating point, which measures the marginal
    # influence of these threshold-gated inputs without a clamp artefact.
    probes = {
        "risk.debt_crisis_prone": (False, lambda a: setattr(
            a.risk, "debt_crisis_prone", max(0.0, a.risk.debt_crisis_prone - 0.2))),
        "risk.conflict_proneness": (False, lambda a: setattr(
            a.risk, "conflict_proneness", max(0.0, a.risk.conflict_proneness - 0.2))),
        "technology.military_power": (True, lambda a: setattr(
            a.technology, "military_power", a.technology.military_power * 1.3)),
        "technology.security_index": (True, lambda a: setattr(
            a.technology, "security_index", max(0.0, min(1.0, a.technology.security_index + 0.3)))),
    }
    out: Dict[str, dict] = {}
    for name, (single, setter) in probes.items():
        base = _run(None, years, max_agents, single)
        pert = _run(setter, years, max_agents, single)
        out[name] = {
            "influence": _rel_change(base, pert),
            "probe": "single-agent (relative)" if single else "uniform",
        }
    return out


def _main() -> None:
    scores = run_stress_audit()
    print("Stressed-scenario influence audit (threshold-gated inputs):")
    for name, d in sorted(scores.items(), key=lambda kv: -kv[1]["influence"]):
        tag = " <- conditionally load-bearing" if d["influence"] > 1e-3 else ""
        print(f"  {name:30s} {d['influence']:.2e}  [{d['probe']}]{tag}")


if __name__ == "__main__":
    _main()
