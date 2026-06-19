"""Social Cost of Carbon via the marginal-pulse method (Phase 3-B).

The standard IAM approach (DICE/FUND/PAGE): run a baseline trajectory and a perturbed
trajectory with a marginal CO2 pulse, take the discounted, welfare-weighted difference in
consumption (the climate damage caused by the pulse), and divide by the pulse mass:

    SCC = sum_{t>=t0}  [ U'(c_t)/U'(c_t0) * (1+rho)^-(t-t0) * dC_t ]  /  pulse_tonnes

where dC_t = C_baseline_t - C_pulse_t is the consumption lost to the pulse. The pulse is
injected FAIR-style into the carbon pools (partitioned by the IRF fractions), so it decays on
the model's own multi-pool timescales. Baseline and pulsed runs share a seed (common random
numbers), so the difference is purely the pulse's physical effect — deterministic and clean.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .core.climate import _normalize_fractions
from .core.core import CO2_PREINDUSTRIAL_GT
from .core.params import ParameterSet, default_params
from .core.policy import make_policy_map
from .core.rng import seed_world
from .core.simulation import step_world
from .core.world_factory import make_world_from_csv
from .welfare import marginal_utility, per_capita_consumption, world_consumption


def _run_trajectory(
    state_csv: str,
    years: int,
    max_agents: int,
    base_year: int,
    params: ParameterSet,
    seed: int,
    pulse_year: Optional[int] = None,
    pulse_gtco2: float = 0.0,
) -> Tuple[List[float], List[float]]:
    world = make_world_from_csv(state_csv, max_agents=max_agents, base_year=base_year)
    world.params = params
    seed_world(world, seed)
    policies = make_policy_map(world.agents.keys(), mode="simple")

    cons = [world_consumption(world)]
    cons_pc = [per_capita_consumption(world)]
    for y in range(years):
        step_world(world, policies)
        if pulse_year is not None and y == pulse_year and pulse_gtco2 > 0.0:
            fracs = _normalize_fractions(world.params.CARBON_POOL_FRACTIONS)
            pools = world.global_state.carbon_pools
            if len(pools) == len(fracs):
                world.global_state.carbon_pools = [p + pulse_gtco2 * f for p, f in zip(pools, fracs)]
                world.global_state.co2 = max(
                    CO2_PREINDUSTRIAL_GT + sum(world.global_state.carbon_pools), CO2_PREINDUSTRIAL_GT
                )
        cons.append(world_consumption(world))
        cons_pc.append(per_capita_consumption(world))
    return cons, cons_pc


def social_cost_of_carbon(
    state_csv: str = "data/agent_states_operational_2026_calibrated.csv",
    *,
    years: int = 30,
    pulse_year: int = 1,
    pulse_gtco2: float = 10.0,
    params: Optional[ParameterSet] = None,
    seed: int = 2026,
    max_agents: int = 100,
    base_year: int = 2026,
) -> Dict[str, float]:
    """Compute the social cost of carbon ($ / tCO2) via a marginal pulse experiment."""
    p = params or default_params()
    eta = float(p.ELASTICITY_MARGINAL_UTILITY)
    rho = float(p.PURE_TIME_PREFERENCE)

    base_cons, base_cpc = _run_trajectory(state_csv, years, max_agents, base_year, p, seed)
    pulse_cons, _ = _run_trajectory(
        state_csv, years, max_agents, base_year, p, seed,
        pulse_year=pulse_year, pulse_gtco2=pulse_gtco2,
    )

    t0 = pulse_year
    mu0 = marginal_utility(base_cpc[t0], eta)
    pv_tusd = 0.0
    for t in range(t0, len(base_cons)):
        dC = base_cons[t] - pulse_cons[t]  # T$ consumption lost to the pulse
        weight = (marginal_utility(base_cpc[t], eta) / mu0) / ((1.0 + rho) ** (t - t0))
        pv_tusd += weight * dC

    scc = pv_tusd * 1e12 / (pulse_gtco2 * 1e9)  # ($) per (tCO2)
    return {
        "scc_usd_per_tco2": scc,
        "pv_consumption_loss_tusd": pv_tusd,
        "pulse_gtco2": pulse_gtco2,
        "pulse_year": pulse_year,
        "years": years,
        "eta": eta,
        "rho": rho,
    }


SCC_PRIOR_PARAMS = [
    "ECS_DEFAULT",
    "DAMAGE_QUAD_COEFF",
    "ELASTICITY_MARGINAL_UTILITY",
    "PURE_TIME_PREFERENCE",
    "HEAT_CAP_SURFACE",
    "EMISSIONS_SCALE",
]


def scc_distribution(
    state_csv: str = "data/agent_states_operational_2026_calibrated.csv",
    *,
    names: Optional[List[str]] = None,
    n_samples: int = 50,
    years: int = 30,
    pulse_gtco2: float = 10.0,
    max_agents: int = 100,
    base_year: int = 2026,
    master_seed: int = 2026,
) -> Dict[str, object]:
    """Propagate the climate-economy + discounting priors through the SCC pulse experiment.

    Returns the SCC distribution (percentiles + samples) — the modern IAM standard
    (cf. RFF-SP / Rennert et al. 2022), reflecting deep uncertainty in ECS, the damage
    function, and the discounting parameters (eta, rho).
    """
    import random

    from .core.priors import key_priors, sample_parameter_set

    names = names or SCC_PRIOR_PARAMS
    priors = key_priors()
    base = default_params()

    samples: List[float] = []
    for i in range(n_samples):
        member_seed = (master_seed * 1_000_003 + i) & 0x7FFFFFFF
        ps = sample_parameter_set(base, priors, random.Random(member_seed), names=names)
        r = social_cost_of_carbon(
            state_csv, years=years, pulse_gtco2=pulse_gtco2, params=ps,
            seed=base_year, max_agents=max_agents, base_year=base_year,
        )
        samples.append(r["scc_usd_per_tco2"])

    s = sorted(samples)

    def _pct(p: float) -> float:
        if not s:
            return float("nan")
        rank = (p / 100.0) * (len(s) - 1)
        lo = int(rank)
        hi = min(lo + 1, len(s) - 1)
        return s[lo] * (1 - (rank - lo)) + s[hi] * (rank - lo)

    return {
        "n_samples": n_samples,
        "varied_params": names,
        "percentiles": {f"p{int(p)}": _pct(p) for p in (5, 25, 50, 75, 95)},
        "mean": sum(s) / len(s) if s else float("nan"),
        "samples": s,
    }


__all__ = ["social_cost_of_carbon", "scc_distribution", "SCC_PRIOR_PARAMS"]
