"""IPCC SSP/RCP alignment and FAIR/MAGICC-style climate benchmarking (T2.1 + Phase-4 benchmark).

Establishes that GIM's physical climate core is consistent with the IPCC AR6 reduced-complexity
climate models (FAIR, MAGICC) on the two assessment metrics that define a climate emulator, and
locates GIM's emergent baseline within the AR6 SSP warming envelopes.

1. **Equilibrium climate sensitivity (ECS).** Production ECS = 3.0 C, the AR6 best estimate.
2. **Transient climate response (TCR).** `transient_climate_response()` drives GIM's two-box EBM
   under the idealised 1%/yr CO2 ramp to doubling (~year 70) and reads the warming. Post-T1.3b
   recalibration this is ~1.79 C - the AR6 best estimate is 1.8 C (likely 1.4-2.2). Matching both
   ECS and TCR is the standard bar for an AR6-consistent emulator (FAIR/MAGICC are tuned to the
   same two numbers).
3. **SSP warming envelopes.** `AR6_SSP_WARMING_2100` holds the AR6 WG1 SPM assessed 2081-2100
   warming for each SSP; `classify_warming()` reports which scenario band a given 2100 warming sits
   in, so GIM runs can be labelled in IPCC-comparable terms.

The TCR computation disables internal variability so it measures the *forced* response only.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .core.climate import update_global_climate
from .core.core import CO2_PREINDUSTRIAL_GT
from .core.params import build_params
from .core.world_factory import make_world_from_csv

STATE_CSV = "data/agent_states_operational_2026_calibrated.csv"

# --- AR6 WG1 reference values (Forster et al. 2021; SPM.1 / Ch.7) -----------------------
AR6_ECS = (3.0, 2.5, 4.0)   # best, likely-low, likely-high
AR6_TCR = (1.8, 1.4, 2.2)   # best, likely-low, likely-high

# AR6 WG1 SPM Table SPM.1: best estimate and very-likely range of 2081-2100 global warming
# relative to 1850-1900, by scenario (deg C).
AR6_SSP_WARMING_2100: Dict[str, Tuple[float, float, float]] = {
    "SSP1-1.9": (1.4, 1.0, 1.8),
    "SSP1-2.6": (1.8, 1.3, 2.4),
    "SSP2-4.5": (2.7, 2.1, 3.5),
    "SSP3-7.0": (3.6, 2.8, 4.6),
    "SSP5-8.5": (4.4, 3.3, 5.7),
}


def transient_climate_response(params=None, ramp_years: int = 70) -> float:
    """GIM EBM warming at CO2 doubling under a 1%/yr ramp (the TCR), forced response only."""
    p = params if params is not None else build_params()
    world = make_world_from_csv(STATE_CSV, max_agents=2, base_year=1850)
    world.params = p
    gs = world.global_state
    gs.co2 = CO2_PREINDUSTRIAL_GT
    gs.temperature_global = 0.0
    gs.temperature_ocean = 0.0
    gs.carbon_pools = []
    gs.temp_history = []
    gs._calendar_year_base = 1850
    gs._temperature_variability_sigma = 0.0      # forced response only
    gs._enable_temperature_variability = False
    c0 = CO2_PREINDUSTRIAL_GT
    temp = 0.0
    for t in range(ramp_years + 1):
        world.time = t
        for a in world.agents.values():
            a.climate.co2_annual_emissions = 0.0
        update_global_climate(world, dt=1.0, prescribed_co2_gt=c0 * (1.01 ** t))
        temp = gs.temperature_global
    return temp


def equilibrium_climate_sensitivity(params=None) -> float:
    p = params if params is not None else build_params()
    return float(p.ECS_DEFAULT)


def classify_warming(warming_c: float) -> List[str]:
    """SSP scenarios whose very-likely 2100 warming range contains ``warming_c``."""
    return [s for s, (_b, lo, hi) in AR6_SSP_WARMING_2100.items() if lo <= warming_c <= hi]


def closest_ssp(warming_c: float) -> str:
    """SSP scenario whose best-estimate 2100 warming is nearest ``warming_c``."""
    return min(AR6_SSP_WARMING_2100, key=lambda s: abs(AR6_SSP_WARMING_2100[s][0] - warming_c))


def ar6_consistency_report(params=None) -> Dict[str, object]:
    """Summary of GIM vs AR6 on ECS and TCR."""
    ecs = equilibrium_climate_sensitivity(params)
    tcr = transient_climate_response(params)
    return {
        "ecs": ecs,
        "ecs_ar6": AR6_ECS,
        "ecs_within_ar6_likely": AR6_ECS[1] <= ecs <= AR6_ECS[2],
        "tcr": tcr,
        "tcr_ar6": AR6_TCR,
        "tcr_within_ar6_likely": AR6_TCR[1] <= tcr <= AR6_TCR[2],
    }
