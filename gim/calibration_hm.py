"""History-matching calibration (Phase 2-B).

Rather than point-fitting parameters, history matching rules *out* regions of parameter
space that are implausible given the observations, leaving a "Not Ruled Out Yet" (NROY)
posterior. It is the standard approach for expensive simulators (Craig et al. 1997;
Williamson et al. 2013, used for climate-model tuning) and composes naturally with the
Phase-1 priors and the parameter-isolated backtest.

For a parameter draw theta, the implausibility for output o is

    I_o(theta) = RMSE(model_o(theta), observed_o) / tol_o

where tol_o bundles observational + model-discrepancy uncertainty. The combined
implausibility is ``max_o I_o``; a draw is NROY if it is <= ``threshold`` (the standard
3-sigma cut, Pukelsheim's rule). Surviving draws constrain the parameters.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from .core.priors import Prior, key_priors
from .historical_backtest import load_historical_observed_fixture, run_historical_backtest
from .scoring import rmse

# Per-output tolerances (combined observational + model-discrepancy uncertainty), in the
# output's own units (GDP T$, CO2 GtCO2, temperature C).
DEFAULT_TOLERANCES: Dict[str, float] = {"world_gdp": 6.0, "global_co2": 2.0, "temperature": 0.15}

# Parameters that materially drive the 2015-2023 backtest outputs (from P1-D sensitivity).
DEFAULT_CALIBRATION_PARAMS: List[str] = [
    "ECS_DEFAULT",
    "HEAT_CAP_SURFACE",
    "EMISSIONS_SCALE",
    "DECARB_RATE_STRUCTURAL",
    "ALPHA_CAPITAL",
    "GAMMA_ENERGY",
]


def _observed_series():
    obs = load_historical_observed_fixture()
    gdp = {int(y): float(sum(v.values())) for y, v in obs["gdp_trillions_by_year"].items()}
    co2 = {int(y): float(v) for y, v in obs["global_co2_gtco2"].items()}
    temp = {int(y): float(v) for y, v in obs["temperature_c_preindustrial"].items()}
    return gdp, co2, temp


def backtest_rmses(param_overrides: Dict[str, float]) -> Dict[str, float]:
    """RMSE of the 2015-2023 backtest vs observations for the given parameter overrides."""
    gdp_obs, co2_obs, temp_obs = _observed_series()
    res = run_historical_backtest(
        params_override=param_overrides,
        temperature_variability_sigma_override=0.0,  # deterministic single member (fast)
    )
    gdp_pred = {int(y): float(sum(v.values())) for y, v in res.predicted_gdp_trillions.items()}
    co2_pred = {int(y): float(v) for y, v in res.predicted_global_co2_gtco2.items()}
    temp_pred = {int(y): float(v) for y, v in res.predicted_temperature_c.items()}
    return {
        "world_gdp": rmse(gdp_pred, gdp_obs),
        "global_co2": rmse(co2_pred, co2_obs),
        "temperature": rmse(temp_pred, temp_obs),
    }


def implausibility(rmses: Dict[str, float], tolerances: Dict[str, float] = DEFAULT_TOLERANCES) -> Dict[str, float]:
    per = {o: rmses[o] / tolerances[o] for o in rmses if o in tolerances}
    per["max"] = max(per.values()) if per else float("inf")
    return per


@dataclass
class HistoryMatchResult:
    names: List[str]
    threshold: float
    tolerances: Dict[str, float]
    members: List[dict]

    def nroy(self) -> List[dict]:
        return [m for m in self.members if m["nroy"]]

    def constraints(self) -> Dict[str, Dict[str, float]]:
        """Per-parameter prior range vs NROY range (fraction retained = how much it constrains)."""
        out: Dict[str, Dict[str, float]] = {}
        nroy = self.nroy()
        for n in self.names:
            prior_vals = [m["draw"][n] for m in self.members]
            span = (max(prior_vals) - min(prior_vals)) or 1e-12
            entry = {"prior_min": min(prior_vals), "prior_max": max(prior_vals)}
            if nroy:
                nv = [m["draw"][n] for m in nroy]
                entry.update({
                    "nroy_min": min(nv),
                    "nroy_max": max(nv),
                    "retained_fraction": (max(nv) - min(nv)) / span,
                })
            out[n] = entry
        return out

    def to_dict(self) -> dict:
        return {
            "names": self.names,
            "threshold": self.threshold,
            "tolerances": self.tolerances,
            "n_members": len(self.members),
            "n_nroy": len(self.nroy()),
            "constraints": self.constraints(),
            "best": min(self.members, key=lambda m: m["implausibility"]["max"]),
        }


def history_match(
    names: Optional[Sequence[str]] = None,
    n_samples: int = 40,
    threshold: float = 3.0,
    tolerances: Optional[Dict[str, float]] = None,
    seed: int = 2026,
    priors: Optional[Dict[str, Prior]] = None,
) -> HistoryMatchResult:
    names = list(names) if names is not None else list(DEFAULT_CALIBRATION_PARAMS)
    priors = priors or key_priors()
    tolerances = tolerances or DEFAULT_TOLERANCES
    rng = random.Random(seed)

    members: List[dict] = []
    for _ in range(n_samples):
        draw = {n: priors[n].sample(rng) for n in names}
        rms = backtest_rmses(draw)
        imp = implausibility(rms, tolerances)
        members.append({"draw": draw, "rmses": rms, "implausibility": imp, "nroy": imp["max"] <= threshold})
    return HistoryMatchResult(list(names), threshold, tolerances, members)


def constrained_priors(
    result: HistoryMatchResult, base_priors: Optional[Dict[str, Prior]] = None
) -> Dict[str, Prior]:
    """Turn an NROY posterior into priors: calibrated params restricted to their NROY range.

    The result feeds straight into the ensemble (`gim.ensemble`) for a calibrated, tightened
    projection — closing the loop priors -> calibration -> constrained ensemble.
    """
    priors = dict(base_priors or key_priors())
    cons = result.constraints()
    for name in result.names:
        c = cons.get(name, {})
        lo, hi = c.get("nroy_min"), c.get("nroy_max")
        if lo is not None and hi is not None and hi > lo:
            priors[name] = Prior(
                name, "uniform", (lo + hi) / 2.0, 0.0, lo, hi,
                "history-matching NROY", "calibrated to 2015-2023 backtest",
            )
    return priors


__all__ = [
    "history_match",
    "backtest_rmses",
    "implausibility",
    "constrained_priors",
    "HistoryMatchResult",
    "DEFAULT_TOLERANCES",
    "DEFAULT_CALIBRATION_PARAMS",
]
