"""Per-run parameter context (Phase 1, option B2).

Model parameters are read from an immutable :class:`ParameterSet` carried on the
``WorldState`` (``world.params``) instead of the process-global ``calibration_params``
module. This gives each run its own parameter vector with no global mutation, so
Monte-Carlo ensemble members can run in parallel without interfering, and a sampled
parameter draw is fully isolated and auditable.

The default set snapshots the current ``calibration_params`` values (including
artifact-bound ones such as ``EMISSIONS_SCALE``/``DECARB_RATE_STRUCTURAL``), so with
default parameters the model is behaviourally identical to before the refactor.

Usage in the model:

    from .params import resolve_params
    def update_x(agent, world):
        cal = resolve_params(world)   # per-run params; cal.X reads are unchanged
        ...

Sampling for ensembles:

    p = default_params().with_overrides({"ECS_DEFAULT": 3.2, "ALPHA_CAPITAL": 0.32})
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

# A "parameter" is an uppercase module attribute with a numeric or vector value.
_PARAM_TYPES = (int, float, list, tuple)


class ParameterSet:
    """Immutable mapping of parameter name -> value with attribute access."""

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, Any]) -> None:
        object.__setattr__(self, "_values", dict(values))

    def __getattr__(self, name: str) -> Any:
        try:
            return self._values[name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise AttributeError(f"Unknown parameter: {name!r}") from exc

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("ParameterSet is immutable; use with_overrides()")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("ParameterSet is immutable")

    def __contains__(self, name: str) -> bool:
        return name in self._values

    def __len__(self) -> int:
        return len(self._values)

    def get(self, name: str, default: Any = None) -> Any:
        return self._values.get(name, default)

    def keys(self) -> Iterable[str]:
        return self._values.keys()

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._values)

    def with_overrides(self, overrides: Mapping[str, Any]) -> "ParameterSet":
        """Return a new ParameterSet with the given parameters replaced.

        Raises KeyError on unknown parameter names (guards ensemble-sampling typos).
        """
        unknown = [k for k in overrides if k not in self._values]
        if unknown:
            raise KeyError(f"Unknown parameter override(s): {sorted(unknown)}")
        merged = dict(self._values)
        merged.update(overrides)
        return ParameterSet(merged)

    def __deepcopy__(self, memo: dict) -> "ParameterSet":
        # Immutable: safe to share across deepcopied worlds (avoids per-copy bloat).
        return self

    def __repr__(self) -> str:
        return f"ParameterSet({len(self._values)} params)"


def _params_from_module(module: Any) -> Dict[str, Any]:
    return {
        name: getattr(module, name)
        for name in dir(module)
        if name.isupper()
        and not name.startswith("_")
        and isinstance(getattr(module, name), _PARAM_TYPES)
    }


def build_params() -> ParameterSet:
    """Build a ParameterSet by snapshotting the CURRENT ``calibration_params`` values.

    Uncached: each world snapshots the live module values at build time, so calibration
    harnesses that temporarily mutate ``calibration_params`` (e.g. the decarb-rate
    backtest) are reflected in freshly-built worlds.
    """
    from . import calibration_params as cal  # lazy import to avoid import cycle

    return ParameterSet(_params_from_module(cal))


_DEFAULT: "ParameterSet | None" = None


def default_params() -> ParameterSet:
    """Cached default parameter set, used as the fallback when a world has no params."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = build_params()
    return _DEFAULT


def resolve_params(world: Any) -> ParameterSet:
    """Return the world's ParameterSet, falling back to the default set.

    The fallback keeps directly-constructed ``WorldState`` objects (e.g. in tests)
    working without an explicit params assignment.
    """
    params = getattr(world, "params", None)
    return params if isinstance(params, ParameterSet) else default_params()


__all__ = ["ParameterSet", "build_params", "default_params", "resolve_params"]
