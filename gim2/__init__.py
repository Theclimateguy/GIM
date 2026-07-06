"""GIM17 v2.0 — deterministic analytical line.

This is the **clean v2 line** (Linear epics THE-63…71). It is a thin surface over
the *validated, frozen* GIM17 math in :mod:`gim` — it adds **no new model math**.
Every run orchestrates functions the paper already validates:

* ensembles            — :func:`gim.ensemble.run_ensemble`
* Morris / Sobol       — :mod:`gim.sensitivity`
* weak signals         — :mod:`gim.weak_signal`
* social cost of carbon— :mod:`gim.scc`
* retro backtest        — :mod:`gim.historical_backtest`
* conflict AUC          — :mod:`gim.conflict_benchmark`

coupled annually through the deterministic core ``gim.core.simulation.step_world``.

v2 deliberately drops the *exploratory* layer (softmax ``game_runner`` over the 10
risk-classes, "criticality", LLM personas / hybrid games) from its default surface.
That code is **not deleted** — it stays in :mod:`gim` and is reachable from v2 only
when ``GIM_EXPLORATORY`` is set, so the archived v1 app remains reproducible.

See ``gim2/README.md`` for the structure decision and ``gim2/docs/ARCHIVE_v1.md``
for v1 archival.
"""

from __future__ import annotations

import os

__version__ = "2.1.0-dev"

# The version of the frozen math line v2 wraps (must stay in lock-step with gim).
ENGINE_LINE = "18.1.1"

SCHEMA = "gim-engine/2"


def is_exploratory_enabled() -> bool:
    """True when the non-validated exploratory layer is explicitly opted into.

    v2 hides the softmax game / criticality / LLM-persona layer by default
    (THE-71). Setting ``GIM_EXPLORATORY=1`` re-exposes it for the archived v1
    workflows without forking the codebase.
    """
    return os.environ.get("GIM_EXPLORATORY", "").strip().lower() in {"1", "true", "yes", "on"}


__all__ = ["__version__", "ENGINE_LINE", "SCHEMA", "is_exploratory_enabled"]
