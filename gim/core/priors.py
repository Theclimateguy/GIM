"""Parameter prior distributions for Monte-Carlo uncertainty quantification (Phase 1-B).

Two tiers:

1. **Key priors** (`data/parameter_priors.csv`): ~18 climate-economy parameters with
   distributions grounded in the literature and validated against authoritative consensus
   (IPCC AR6 for ECS; DICE-2016R2 / Howard-Sterner / RFF for the damage function; Penn
   World Table / Gollin for production elasticities and depreciation; GCP/WDI for emissions
   and decarbonisation). Each carries an explicit source and rationale.

2. **Long-tail priors**: for every other scalar parameter, a bounded band derived from the
   registry `uncertainty_level` tag (low +/-5%, medium +/-15%, high/unspecified +/-25-35%)
   around the calibrated value. These are first-pass; the sensitivity stage (P1-D) identifies
   which actually matter.

`sample_parameter_set(base, priors, rng)` draws a vector and returns a new immutable
`ParameterSet`, ready to attach to a world for an ensemble member.
"""

from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

from .params import ParameterSet, default_params

_DATA = Path(__file__).resolve().parents[2] / "data"
PRIORS_CSV = _DATA / "parameter_priors.csv"
REGISTRY_CSV = _DATA / "parameters_gim18.csv"

# Half-width of the uniform band for long-tail params, by registry uncertainty_level.
UNCERTAINTY_BAND = {"low": 0.05, "medium": 0.15, "high": 0.35, "unspecified": 0.25}

# Structural bounds/limits that should not be perturbed by the long-tail sampler.
_LONG_TAIL_SKIP_SUFFIXES = ("_MAX", "_MIN", "_CAP", "_FLOOR")


@dataclass(frozen=True)
class Prior:
    """A truncated univariate prior for one parameter."""

    name: str
    dist: str  # normal | lognormal | triangular | uniform | fixed
    p1: float  # normal mean | lognormal median | triangular mode | fixed value
    p2: float  # normal sd | lognormal ln-sigma | (unused otherwise)
    low: float
    high: float
    source: str = ""
    rationale: str = ""

    def _draw(self, rng: random.Random) -> float:
        if self.dist == "normal":
            return rng.gauss(self.p1, self.p2)
        if self.dist == "lognormal":
            return math.exp(rng.gauss(math.log(self.p1), self.p2))
        if self.dist == "triangular":
            return rng.triangular(self.low, self.high, self.p1)
        if self.dist == "uniform":
            return rng.uniform(self.low, self.high)
        if self.dist == "fixed":
            return self.p1
        raise ValueError(f"Unknown distribution: {self.dist!r}")

    def sample(self, rng: random.Random) -> float:
        """Draw a value truncated to [low, high] (resample, then clamp as fallback)."""
        for _ in range(64):
            value = self._draw(rng)
            if self.low <= value <= self.high:
                return value
        return min(self.high, max(self.low, self._draw(rng)))


def _load_explicit() -> Dict[str, Prior]:
    priors: Dict[str, Prior] = {}
    with open(PRIORS_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = row["parameter"].strip()
            priors[name] = Prior(
                name=name,
                dist=row["dist"].strip(),
                p1=float(row["p1"]),
                p2=float(row["p2"]),
                low=float(row["low"]),
                high=float(row["high"]),
                source=row.get("source", ""),
                rationale=row.get("rationale", ""),
            )
    return priors


def _load_uncertainty_tags() -> Dict[str, str]:
    tags: Dict[str, str] = {}
    if not REGISTRY_CSV.exists():
        return tags
    with open(REGISTRY_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            tags[row["parameter"].strip()] = (row.get("uncertainty_level") or "unspecified").strip()
    return tags


def key_priors() -> Dict[str, Prior]:
    """The literature-grounded priors only (the defensible ensemble core)."""
    return _load_explicit()


def all_priors(base: Optional[ParameterSet] = None) -> Dict[str, Prior]:
    """Key priors plus tag-derived bounded bands for every other scalar parameter."""
    base = base or default_params()
    priors = _load_explicit()
    tags = _load_uncertainty_tags()
    for name in base.keys():
        if name in priors:
            continue
        if name.endswith(_LONG_TAIL_SKIP_SUFFIXES):
            continue
        value = base.get(name)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue  # skip vectors (e.g. carbon pools) and non-numeric
        value = float(value)
        band = UNCERTAINTY_BAND.get(tags.get(name, "unspecified"), 0.25)
        if value > 0:
            low, high = value * (1.0 - band), value * (1.0 + band)
        elif value < 0:
            low, high = value * (1.0 + band), value * (1.0 - band)
        else:
            low, high = -band, band
        priors[name] = Prior(name, "uniform", value, 0.0, low, high,
                             "registry uncertainty_level", f"tag-derived +/-{band:.0%} band")
    return priors


def sample_overrides(
    priors: Dict[str, Prior], rng: random.Random, names: Optional[Iterable[str]] = None
) -> Dict[str, float]:
    selected = list(names) if names is not None else list(priors.keys())
    return {n: priors[n].sample(rng) for n in selected if n in priors}


def sample_parameter_set(
    base: ParameterSet,
    priors: Dict[str, Prior],
    rng: random.Random,
    names: Optional[Iterable[str]] = None,
) -> ParameterSet:
    """Return a new ParameterSet with sampled values for the selected priors."""
    return base.with_overrides(sample_overrides(priors, rng, names))


__all__ = [
    "Prior",
    "key_priors",
    "all_priors",
    "sample_overrides",
    "sample_parameter_set",
    "UNCERTAINTY_BAND",
]
