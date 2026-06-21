"""Influence audit for GIM's unique layers (F3): are they load-bearing or decorative?

GIM's differentiator is its social / geopolitical / cultural / institutional layers, but they
are the least validated. Before validating them against external data, the first honest
question is empirical: **does each input actually move the model's outputs at all?** A variable
that is carried in state and loaded from CSV but never changes any trajectory is decorative
complexity, not a feature.

This module perturbs each input (the same value for every agent) and measures the normalised
downstream change in aggregate outputs after a short deterministic run. The result is an
*influence score* per input; ~0 means the input is inert (decorative).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List

from gim.core.policy import make_policy_map
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv

STATE_CSV = "data/agent_states_operational_2026_calibrated.csv"


def _aggregate_outputs(world) -> Dict[str, float]:
    agents = list(world.agents.values())
    n = max(1, len(agents))
    return {
        "world_gdp": sum(a.economy.gdp for a in agents),
        "mean_social_tension": sum(a.society.social_tension for a in agents) / n,
        "mean_trust_gov": sum(a.society.trust_gov for a in agents) / n,
        "mean_regime_stability": sum(a.risk.regime_stability for a in agents) / n,
        "mean_unemployment": sum(a.economy.unemployment for a in agents) / n,
    }


def _run(setter: Callable[[object], None] | None, years: int, max_agents: int, seed: int,
         culture_links: bool = False) -> Dict[str, float]:
    world = make_world_from_csv(STATE_CSV, max_agents=max_agents, base_year=2026)
    if culture_links:
        from gim.core.params import default_params
        world.params = default_params().with_overrides({"CULTURE_SOCIAL_LINKS": True})
    world.global_state._temperature_variability_sigma = 0.0  # deterministic forced run
    if setter is not None:
        for agent in world.agents.values():
            setter(agent)
    policies = make_policy_map(world.agents.keys(), mode="simple")
    for _ in range(years):
        step_world(world, policies)
    return _aggregate_outputs(world)


def _rel_change(base: Dict[str, float], pert: Dict[str, float]) -> float:
    """Aggregate normalised |change| across outputs (mean of per-output relative deltas)."""
    total = 0.0
    for k in base:
        denom = abs(base[k]) if abs(base[k]) > 1e-9 else 1.0
        total += abs(pert[k] - base[k]) / denom
    return total / len(base)


@dataclass(frozen=True)
class Perturbation:
    name: str
    setter: Callable[[object], None]


def culture_perturbations(delta: float = 20.0) -> List[Perturbation]:
    """Shift each retained Hofstede dimension by +delta points (0-100 scale) for every agent.

    F3: only the 4 retained dims remain. `idv` is load-bearing in the always-on social block;
    `pdi/uai/lto` are wired via the switchable CULTURE_SOCIAL_LINKS channel (run the audit with
    ``culture_links=True`` to measure them). The 4 inert dims (mas/ind/traditional_secular/
    survival_self_expression) were removed from the model entirely.
    """
    dims = ["pdi", "idv", "uai", "lto"]

    def make(dim):
        def setter(agent):
            cur = getattr(agent.culture, dim, None)
            if cur is not None:
                setattr(agent.culture, dim, max(0.0, min(100.0, float(cur) + delta)))
        return setter

    return [Perturbation(f"culture.{d}", make(d)) for d in dims]


def risk_geo_perturbations(delta: float = 0.2) -> List[Perturbation]:
    """Shift key risk / geopolitical / technology inputs (0-1 or level scales) per agent."""
    specs = [
        ("risk.conflict_proneness", lambda a, v: setattr(a.risk, "conflict_proneness", _clamp01(a.risk.conflict_proneness + v))),
        ("risk.debt_crisis_prone", lambda a, v: setattr(a.risk, "debt_crisis_prone", _clamp01(a.risk.debt_crisis_prone + v))),
        ("risk.water_stress", lambda a, v: setattr(a.risk, "water_stress", _clamp01(a.risk.water_stress + v))),
        ("risk.regime_stability", lambda a, v: setattr(a.risk, "regime_stability", _clamp01(a.risk.regime_stability + v))),
        ("technology.security_index", lambda a, v: setattr(a.technology, "security_index", _clamp01(a.technology.security_index + v))),
        ("technology.military_power", lambda a, v: setattr(a.technology, "military_power", max(0.0, a.technology.military_power * (1.0 + v)))),
        ("society.inequality_gini", lambda a, v: setattr(a.society, "inequality_gini", max(0.0, min(100.0, a.society.inequality_gini + 100.0 * v)))),
    ]
    return [Perturbation(name, (lambda s=setter: (lambda agent: s(agent, delta)))()) for name, setter in specs]


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def run_influence_audit(
    perturbations: List[Perturbation] | None = None,
    *,
    years: int = 12,
    max_agents: int = 12,
    seed: int = 2026,
    culture_links: bool = False,
) -> Dict[str, float]:
    """Influence score per perturbation (normalised aggregate-output change vs baseline).

    ``culture_links=True`` enables the switchable CULTURE_SOCIAL_LINKS channel so the wired
    pdi/uai/lto links are exercised (otherwise only `idv` moves outputs).
    """
    perturbations = perturbations or culture_perturbations()
    base = _run(None, years, max_agents, seed, culture_links=culture_links)
    out: Dict[str, float] = {}
    for p in perturbations:
        pert = _run(p.setter, years, max_agents, seed, culture_links=culture_links)
        out[p.name] = _rel_change(base, pert)
    return out


def decorative_inputs(scores: Dict[str, float], threshold: float = 1e-6) -> List[str]:
    """Inputs whose influence score is below threshold => inert / decorative."""
    return sorted(k for k, v in scores.items() if v < threshold)


def _main() -> None:
    scores = run_influence_audit()
    print("Influence audit (normalised aggregate-output change vs baseline):")
    for name, score in sorted(scores.items(), key=lambda kv: -kv[1]):
        tag = "  <-- DECORATIVE (inert)" if score < 1e-6 else ""
        print(f"  {name:38s} {score:.2e}{tag}")


if __name__ == "__main__":
    _main()
