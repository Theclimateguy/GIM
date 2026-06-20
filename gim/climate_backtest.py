"""Climate-only backtest over the long observational window (T1.3).

The economic backtest (`gim/historical_backtest.py`) runs the full coupled model
over 2015-2023 - eight years, far too short to identify the climate response
parameters (equilibrium climate sensitivity, ocean heat capacities). This module
isolates the physical climate core and drives it with **observed** global CO2
emissions over **1990-2023 (34 years)**, so the carbon cycle + two-box energy
balance can be scored - and calibrated - against a window long enough to constrain
ECS (per the peer review, Tier-1 / Finding on weak ECS identification).

It deliberately reuses the *exact* production climate physics
(`gim.core.climate.update_global_climate`): the 4-pool IPCC-AR6 impulse-response
carbon cycle and the Geoffroy-style two-layer EBM. Only the forcing input is
swapped - observed emissions instead of the economy's emissions - and the economy
is not stepped at all.

**Spin-up.** To avoid an arbitrary 1990 carbon-pool partition (which would bias the
carbon cycle and, through forcing, the inferred ECS), the run starts from the
pre-industrial equilibrium in 1750 (CO2 = pre-industrial stock, empty pools,
T = 0) and is driven forward with the *observed* historical emissions
(``data/global_co2_emissions_owid.csv``, 1750-2024) so that by 1990 both the carbon
pools and the surface/ocean temperatures reflect the real emission history. Only the
1990-2023 window is scored. The whole trajectory is free-running: a single
pre-industrial initial condition plus observed emissions, nothing else.

Public API:
    load_observations()        -> ClimateObservations
    load_emissions_history()    -> dict[int, float]
    run_climate_backtest(...)   -> ClimateBacktestResult   (predicted vs observed + scores)
    sweep_ecs(...)             -> list[(ecs, temp_rmse)]   (long-window ECS identifiability)
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .core.climate import update_global_climate
from .core.core import CO2_PREINDUSTRIAL_GT, GTCO2_PER_PPM
from .core.params import build_params
from .core.world_factory import make_world_from_csv
from .scoring import rmse, mae

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FIXTURE = os.path.join(_DATA_DIR, "tests", "fixtures", "climate_observations_1990_2023.json")
EMISSIONS_CSV = os.path.join(_DATA_DIR, "data", "global_co2_emissions_owid.csv")

STATE_CSV = "data/agent_states_operational_2026_calibrated.csv"

# Year from which the carbon cycle / EBM are spun up from the pre-industrial state.
SPINUP_START_YEAR = 1750


@dataclass(frozen=True)
class ClimateObservations:
    start_year: int
    end_year: int
    emissions_gtco2: Dict[int, float]
    atmospheric_co2_ppm: Dict[int, float]
    temperature_c: Dict[int, float]

    def years(self) -> List[int]:
        return list(range(self.start_year, self.end_year + 1))


@dataclass
class ClimateBacktestResult:
    ecs: float
    predicted_ppm: Dict[int, float]
    predicted_temperature: Dict[int, float]
    observed_ppm: Dict[int, float]
    observed_temperature: Dict[int, float]
    scores: Dict[str, float] = field(default_factory=dict)


def load_observations(path: str = FIXTURE) -> ClimateObservations:
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    to_int = lambda d: {int(k): float(v) for k, v in d.items()}
    return ClimateObservations(
        start_year=int(raw["start_year"]),
        end_year=int(raw["end_year"]),
        emissions_gtco2=to_int(raw["emissions_gtco2"]),
        atmospheric_co2_ppm=to_int(raw["atmospheric_co2_ppm"]),
        temperature_c=to_int(raw["temperature_c_preindustrial"]),
    )


def load_emissions_history(path: str = EMISSIONS_CSV) -> Dict[int, float]:
    """Full 1750-2024 World emissions series (GtCO2/yr) used for the spin-up."""
    out: Dict[int, float] = {}
    with open(path, "r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[int(row["year"])] = float(row["emissions_gtco2"])
    return out


def _build_climate_world(params_override: Optional[dict]):
    """A minimal world whose climate block we drive directly, from pre-industrial.

    We reuse the calibrated state only to obtain a valid set of agents/params; the
    economy is never stepped. One agent ("carrier") carries the observed global
    emissions each year; all others are zeroed, so `sum(co2_annual_emissions)` over
    agents equals the world total that `update_global_climate` reads. The global
    state is reset to the 1750 pre-industrial equilibrium (pre-industrial CO2 stock,
    empty pools, zero anomaly).
    """
    world = make_world_from_csv(STATE_CSV, max_agents=4, base_year=SPINUP_START_YEAR)
    world.params = build_params() if not params_override else build_params().with_overrides(params_override)

    gs = world.global_state
    gs.co2 = CO2_PREINDUSTRIAL_GT
    gs.temperature_global = 0.0
    gs.temperature_ocean = 0.0
    gs.carbon_pools = []  # empty -> initialised to zero excess on the first step
    gs.temp_history = []
    gs._calendar_year_base = int(SPINUP_START_YEAR)
    # Forced-response backtest: internal (AR(1)) variability is noise here and would
    # conflate with calibration error, so switch it off.
    gs._temperature_variability_sigma = 0.0
    gs._enable_temperature_variability = False
    return world


def run_climate_backtest(
    obs: Optional[ClimateObservations] = None,
    *,
    ecs: Optional[float] = None,
    params_override: Optional[dict] = None,
    emissions_history: Optional[Dict[int, float]] = None,
    mode: str = "emission",
) -> ClimateBacktestResult:
    """Free-run the climate core from the 1750 pre-industrial state.

    ``mode``:
      * ``"emission"`` (default) - drive the 4-pool carbon cycle with observed
        fossil+cement emissions; predicted CO2 and temperature both emerge from the
        model. Tests the full emissions -> concentration -> forcing -> temperature
        chain (and exposes any carbon-cycle bias, e.g. the missing land-use source).
      * ``"concentration"`` - over the scored window, force the EBM with *observed*
        CO2 concentrations (``prescribed_co2_gt``) instead of the model's own carbon
        cycle. This isolates the energy-balance response so ECS can be identified
        cleanly, independent of carbon-cycle error - the set-up used by observational
        ECS studies (Otto et al. 2013; Lewis & Curry 2018). Spin-up (1750-1989) is
        still emission-driven so the 1990 temperature is physically initialised.

    The 1750-1989 portion is an unscored spin-up; 1990-2023 is scored.
    """
    if mode not in ("emission", "concentration"):
        raise ValueError(f"unknown mode {mode!r}")
    obs = obs or load_observations()
    history = emissions_history or load_emissions_history()
    world = _build_climate_world(params_override)
    gs = world.global_state
    agents = list(world.agents.values())
    carrier = agents[0]

    eff_ecs = ecs if ecs is not None else world.params.ECS_DEFAULT
    scored_start, scored_end = obs.start_year, obs.end_year
    run_end = max(history)  # advance through the last emissions year

    predicted_ppm: Dict[int, float] = {}
    predicted_temp: Dict[int, float] = {}

    for year in range(SPINUP_START_YEAR, run_end):
        if year not in history:
            continue
        world.time = year - SPINUP_START_YEAR
        for a in agents:
            a.climate.co2_annual_emissions = 0.0
        carrier.climate.co2_annual_emissions = history[year]
        # In concentration mode, once observed CO2 is available, prescribe it so the
        # EBM is forced by the observed concentration rather than the modelled one.
        prescribed = None
        if mode == "concentration" and year in obs.atmospheric_co2_ppm:
            prescribed = obs.atmospheric_co2_ppm[year] * GTCO2_PER_PPM
        update_global_climate(world, dt=1.0, ecs=eff_ecs, prescribed_co2_gt=prescribed)
        nxt = year + 1
        if scored_start <= nxt <= scored_end:
            predicted_ppm[nxt] = gs.co2 / GTCO2_PER_PPM
            predicted_temp[nxt] = gs.temperature_global

    scores = {
        "ppm_rmse": rmse(predicted_ppm, obs.atmospheric_co2_ppm),
        "ppm_mae": mae(predicted_ppm, obs.atmospheric_co2_ppm),
        "temperature_rmse": rmse(predicted_temp, obs.temperature_c),
        "temperature_mae": mae(predicted_temp, obs.temperature_c),
        "n_years": float(scored_end - scored_start + 1),
    }
    return ClimateBacktestResult(
        ecs=eff_ecs,
        predicted_ppm=predicted_ppm,
        predicted_temperature=predicted_temp,
        observed_ppm=dict(obs.atmospheric_co2_ppm),
        observed_temperature=dict(obs.temperature_c),
        scores=scores,
    )


def sweep_ecs(
    ecs_values: List[float],
    obs: Optional[ClimateObservations] = None,
    *,
    mode: str = "concentration",
    emissions_history: Optional[Dict[int, float]] = None,
) -> List[Tuple[float, float]]:
    """Temperature RMSE vs ECS over the long window - a direct identifiability probe.

    A well-identified ECS shows a clear RMSE minimum over the 34-year window; a flat
    curve would mean the data cannot constrain it. Defaults to ``concentration`` mode
    so the result reflects the energy-balance response alone. Returns
    [(ecs, temperature_rmse)].
    """
    obs = obs or load_observations()
    history = emissions_history or load_emissions_history()
    out = []
    for ecs in ecs_values:
        res = run_climate_backtest(obs, ecs=ecs, mode=mode, emissions_history=history)
        out.append((ecs, res.scores["temperature_rmse"]))
    return out


def best_ecs(
    obs: Optional[ClimateObservations] = None,
    *,
    lo: float = 1.5,
    hi: float = 4.0,
    step: float = 0.1,
    mode: str = "concentration",
) -> Tuple[float, float]:
    """Grid-search the ECS that minimises temperature RMSE. Returns (ecs, rmse)."""
    obs = obs or load_observations()
    history = load_emissions_history()
    n = int(round((hi - lo) / step))
    grid = [round(lo + i * step, 3) for i in range(n + 1)]
    pairs = sweep_ecs(grid, obs, mode=mode, emissions_history=history)
    return min(pairs, key=lambda p: p[1])


def _main() -> None:
    obs = load_observations()
    for mode in ("emission", "concentration"):
        res = run_climate_backtest(obs, mode=mode)
        print(f"[{mode}] climate backtest {obs.start_year}-{obs.end_year}  (ECS={res.ecs:.2f})")
        print(f"    ppm  RMSE={res.scores['ppm_rmse']:.2f}  MAE={res.scores['ppm_mae']:.2f}")
        print(f"    temp RMSE={res.scores['temperature_rmse']:.3f}  MAE={res.scores['temperature_mae']:.3f}")
    print("  ECS sweep (concentration-driven, temperature RMSE):")
    for ecs, r in sweep_ecs([1.5, 2.0, 2.5, 3.0, 3.5, 4.0], obs, mode="concentration"):
        print(f"    ECS={ecs:.1f} -> {r:.3f}")
    b_ecs, b_rmse = best_ecs(obs)
    print(f"  best-fit ECS (concentration) = {b_ecs:.2f}  (temp RMSE={b_rmse:.3f})")


if __name__ == "__main__":
    _main()
