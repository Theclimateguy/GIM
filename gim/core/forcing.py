"""Multi-GHG non-CO2 forcing decomposition (P4-B).

The model's non-CO2 effective radiative forcing (ERF) was a single lumped term
(`F_NONCO2_DEFAULT + F_NONCO2_TREND*(year - base)`). This module keeps that calibrated
**net** path unchanged by default (so the climate calibration and the backtest golden
values are untouched) but decomposes it into named, AR6/IGCC-anchored components and
exposes each as a perturbable scenario/policy lever:

    CH4, N2O, halogen (halocarbons), O3 (tropospheric ozone), aerosol (net ari+aci),
    minor (contrails + land-use albedo + BC-on-snow + stratospheric H2O).

Reference component ERF (W/m2, ~2019 vs 1750) from IPCC AR6 WG1 Ch.7 (Forster et al.
2021) / the Indicators of Global Climate Change update (Forster et al. 2023). These sum
to the AR6 net non-CO2 anthropogenic ERF of ~+0.57 W/m2.

Per-gas levers: `component_scales={"CH4": 0.5}` halves methane's contribution; the net
forcing then shifts by `(0.5 - 1) * REFERENCE["CH4"]`. This is the natural-capital /
policy hook (methane mitigation, aerosol clean-up, etc.) without disturbing the default.

Note: the AR6 *net* (~0.57 at 2019) is ~0.11 W/m2 above the model's lumped value at the
same date; adopting the full AR6 net is a separate, calibrated follow-up (P4-B2) because
it shifts the climate trajectory and would re-open the T1.3b joint recalibration.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# [#11] SSP marker -> forward non-CO2 ERF table file (data/forcing/). Only SSP2 is shipped; other
# scenarios fall back to the lumped path until their table is added (same columns, drop-in).
# Resolved via paths.DATA_ROOT so gim-lib's package-internal data relocation applies here too.
from ..paths import DATA_ROOT as _DATA_ROOT

_FORCING_DIR = _DATA_ROOT / "forcing"
_NONCO2_TABLE_FILES: Dict[str, str] = {"SSP2": "rcmip_nonco2_ssp245.csv"}


@lru_cache(maxsize=8)
def _load_nonco2_forward_table(scenario: str) -> Optional[Tuple[Tuple[int, float], ...]]:
    """Load the (year, ERF) forward non-CO2 table for an SSP marker, or None if absent."""
    fname = _NONCO2_TABLE_FILES.get(scenario)
    if not fname:
        return None
    path = _FORCING_DIR / fname
    if not path.exists():
        return None
    rows: List[Tuple[int, float]] = []
    with open(path, newline="") as fh:
        for raw in csv.reader(fh):
            if not raw or raw[0].lstrip().startswith("#") or raw[0].strip() == "year":
                continue
            rows.append((int(raw[0]), float(raw[1])))
    return tuple(sorted(rows)) if rows else None


def _interp_table(table: Tuple[Tuple[int, float], ...], year: int) -> float:
    """Piecewise-linear interpolation of a sorted (year, value) table, clamped at the ends."""
    if year <= table[0][0]:
        return table[0][1]
    if year >= table[-1][0]:
        return table[-1][1]
    for (y0, v0), (y1, v1) in zip(table, table[1:]):
        if y0 <= year <= y1:
            return v0 + (v1 - v0) * (year - y0) / (y1 - y0)
    return table[-1][1]


def _nonco2_scenario() -> str:
    """Active SSP marker for the non-CO2 forward table (string params are module-level)."""
    from . import calibration_params as cal

    return getattr(cal, "SSP_SCENARIO", "SSP2")


# AR6/IGCC component ERF (W/m2, ~2019 vs 1750). Order is documentation only.
NONCO2_ERF_REFERENCE: Dict[str, float] = {
    "CH4": 0.55,        # methane (direct WMGHG ERF)
    "N2O": 0.21,        # nitrous oxide
    "halogen": 0.41,    # halocarbons / ODSs + replacements
    "O3": 0.47,         # tropospheric ozone
    "aerosol": -1.06,   # net aerosol-radiation + aerosol-cloud (cooling)
    "minor": -0.01,     # contrails + land-use albedo + BC-on-snow + strat. H2O
}

# Net of the reference decomposition (~AR6 2019 non-CO2 anthropogenic ERF).
NONCO2_ERF_REFERENCE_NET = sum(NONCO2_ERF_REFERENCE.values())


_COMPONENT_SCALES_ATTR = "_nonco2_component_scales"


def set_nonco2_component_scales(world, scales: Optional[Dict[str, float]]) -> None:
    """Attach per-gas non-CO2 forcing scenario levers to a world (or clear with None).

    Example: ``set_nonco2_component_scales(world, {"CH4": 0.5})`` runs a 50% methane
    mitigation scenario. Unknown component names raise immediately.
    """
    if scales:
        for name in scales:
            if name not in NONCO2_ERF_REFERENCE:
                raise KeyError(f"unknown forcing component {name!r}")
    setattr(world.global_state, _COMPONENT_SCALES_ATTR, dict(scales) if scales else None)


def _linear_lumped(params, year: int) -> float:
    """The original linear non-CO2 net ERF path (W/m2)."""
    year_offset = year - params.F_NONCO2_BASE_YEAR
    return max(0.0, params.F_NONCO2_DEFAULT + params.F_NONCO2_TREND * year_offset)


def lumped_nonco2_forcing(params, year: int) -> float:
    """The model's net non-CO2 ERF for a calendar year (W/m2).

    [#11] Through the calibrated/historical window (year <= F_NONCO2_FORWARD_FROM_YEAR, default
    2024) this is exactly the validated LINEAR lumped path -> the 1990-2023 climate calibration and
    the backtest goldens are untouched. AFTER that year, when F_NONCO2_FORWARD_TABLE is on and the
    SSP marker's table exists, the forward ERF follows the realistic SSP2-4.5 trajectory (rises then
    plateaus ~0.73 W/m2 by 2100) instead of the unbounded linear extrapolation (~1.42 by 2100). The
    table is anchored at the handoff year to the linear value for C1 continuity. Linear fallback is
    kept whenever the table is absent or the switch is off (golden-safe).
    """
    if getattr(params, "F_NONCO2_FORWARD_TABLE", False):
        from_year = int(getattr(params, "F_NONCO2_FORWARD_FROM_YEAR", 2024))
        if year > from_year:
            table = _load_nonco2_forward_table(_nonco2_scenario())
            if table is not None:
                return max(0.0, _interp_table(table, year))
    return _linear_lumped(params, year)


def nonco2_forcing(
    params,
    year: int,
    component_scales: Optional[Dict[str, float]] = None,
) -> float:
    """Net non-CO2 ERF (W/m2), behaviour-preserving by default.

    With no ``component_scales`` this is exactly the lumped calibrated path. A scale on
    component *c* shifts the net by ``(scale - 1) * REFERENCE[c]`` - i.e. it perturbs that
    gas's AR6 contribution while leaving the rest of the net intact.
    """
    net = lumped_nonco2_forcing(params, year)
    if component_scales:
        for name, scale in component_scales.items():
            if name not in NONCO2_ERF_REFERENCE:
                raise KeyError(f"unknown forcing component {name!r}")
            net += (float(scale) - 1.0) * NONCO2_ERF_REFERENCE[name]
    return max(0.0, net)


def nonco2_forcing_components(
    params,
    year: int,
    component_scales: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """Diagnostic decomposition of the net non-CO2 ERF into AR6-proportional components.

    The reference vector is rescaled so its components sum to the (possibly perturbed)
    net for ``year`` - giving an auditable, sign-correct attribution (positive GHGs,
    negative aerosols) consistent with the scalar ``nonco2_forcing`` value.
    """
    net = nonco2_forcing(params, year, component_scales)
    ref = dict(NONCO2_ERF_REFERENCE)
    if component_scales:
        for name, scale in component_scales.items():
            ref[name] = ref[name] * float(scale)
    ref_net = sum(ref.values())
    if abs(ref_net) < 1e-12:
        return {k: 0.0 for k in ref}
    factor = net / ref_net
    return {k: v * factor for k, v in ref.items()}
