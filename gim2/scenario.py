"""Deterministic orchestration for the v2 line (THE-65, keystone).

Each ``compute_*`` returns a pure, chart-ready JSON dict (no ``trace`` / ``equiv_cli``)
built ONLY from the frozen validated math in :mod:`gim`. The CLI handlers
(``run_*_cli``) and the HTTP engine (:mod:`gim2.engine_service`) both call the same
``compute_*`` — so ``engine JSON == CLI JSON`` by construction (parity test).
"""

from __future__ import annotations

import os
import shlex
import threading
from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from gim.ensemble import EnsembleConfig, METRICS, _aggregate
from gim.runtime import default_state_csv

from . import SCHEMA
from . import levers as L
from . import projections as P

Progress = Optional[Callable[[int, int], None]]

# Validated conflict readout (paper §; Fig. 2b). Live recomputation is a heavy
# backtest (scripts/conflict_auc_inference.py) — the About panel *displays* this
# validated figure rather than recomputing it per request.
CONFLICT_AUC = 0.736
CONFLICT_AUC_CI = (0.59, 0.86)
CONFLICT_AUC_P = 0.001
CONFLICT_AUC_REPRODUCE = "python3 scripts/conflict_auc_inference.py"


# --------------------------------------------------------------------------- #
# config + member execution (frozen primitives via gim2.levers.run_member)
# --------------------------------------------------------------------------- #


def build_config(
    *,
    state_csv: Optional[str],
    members: int,
    years: int,
    max_agents: int,
    seed: int,
    prior_set: str,
    jobs: int = 0,
) -> EnsembleConfig:
    return EnsembleConfig(
        state_csv=state_csv or default_state_csv(),
        n_members=int(members),
        years=int(years),
        base_year=2023,
        max_agents=int(max_agents),
        master_seed=int(seed),
        prior_set=prior_set,
        n_jobs=int(jobs),
    )


def _member_worker(args: Tuple[EnsembleConfig, "L.LeverSelection", int]) -> List[Dict[str, float]]:
    config, selection, index = args
    return L.run_member(config, selection, index=index)


def run_trajectories(
    config: EnsembleConfig,
    selection: "L.LeverSelection",
    *,
    progress: Progress = None,
    progress_offset: int = 0,
    progress_total: Optional[int] = None,
    cancel: Optional[threading.Event] = None,
) -> List[List[Dict[str, float]]]:
    n = config.n_members
    total = progress_total or n
    args = [(config, selection, i) for i in range(n)]
    out: List[Optional[List[Dict[str, float]]]] = [None] * n
    n_jobs = config.n_jobs or (os.cpu_count() or 1)

    if n_jobs <= 1:
        for i, a in enumerate(args):
            if cancel is not None and cancel.is_set():
                raise RunCancelled()
            out[i] = _member_worker(a)
            if progress:
                progress(progress_offset + i + 1, total)
    else:
        import multiprocessing as mp
        from concurrent.futures import ProcessPoolExecutor, as_completed

        # Use a *fork* context: spawn re-execs the interpreter, which under a frozen
        # PyInstaller onefile means re-extracting the whole bundle per worker (hangs
        # the sidecar). Fork shares the already-loaded process — fast and frozen-safe.
        try:
            ctx = mp.get_context("fork")
        except ValueError:  # pragma: no cover - non-fork platforms
            ctx = mp.get_context()

        with ProcessPoolExecutor(max_workers=n_jobs, mp_context=ctx) as ex:
            futs = {ex.submit(_member_worker, a): a[2] for a in args}
            done = 0
            for fut in as_completed(futs):
                if cancel is not None and cancel.is_set():
                    for f in futs:
                        f.cancel()
                    raise RunCancelled()
                out[futs[fut]] = fut.result()
                done += 1
                if progress:
                    progress(progress_offset + done, total)
    return [t for t in out if t is not None]


class RunCancelled(Exception):
    """Raised when a run's cancel flag is set."""


# --------------------------------------------------------------------------- #
# baseline cache (E4) — the base ensemble depends only on the config, not on the
# lever selection, so scenario/dose reuse it across lever changes for ~2× speedup.
# --------------------------------------------------------------------------- #

INTERACTIVE_MEMBERS = 120   # responsive size for in-app runs
BACKGROUND_MEMBERS = 500    # full paper-grade size for background jobs

_BASE_CACHE: "OrderedDict[tuple, List[List[Dict[str, float]]]]" = OrderedDict()
_BASE_CACHE_LOCK = threading.Lock()
_BASE_CACHE_MAX = 4


def _base_key(config: EnsembleConfig) -> tuple:
    return (config.state_csv, config.n_members, config.years, config.max_agents,
            config.master_seed, config.prior_set)


def baseline_trajectories(
    config: EnsembleConfig, *, progress: Progress = None, progress_offset: int = 0,
    progress_total: Optional[int] = None, cancel: Optional[threading.Event] = None, use_cache: bool = True,
) -> List[List[Dict[str, float]]]:
    """The lever-free base ensemble, memoised by config (read-only metric lists, safe to share)."""
    key = _base_key(config)
    if use_cache:
        with _BASE_CACHE_LOCK:
            hit = _BASE_CACHE.get(key)
            if hit is not None:
                _BASE_CACHE.move_to_end(key)
        if hit is not None:
            if progress and progress_total:
                progress(progress_offset + config.n_members, progress_total)
            return hit
    trajs = run_trajectories(config, L.LeverSelection(), progress=progress,
                             progress_offset=progress_offset, progress_total=progress_total, cancel=cancel)
    if use_cache:
        with _BASE_CACHE_LOCK:
            _BASE_CACHE[key] = trajs
            _BASE_CACHE.move_to_end(key)
            while len(_BASE_CACHE) > _BASE_CACHE_MAX:
                _BASE_CACHE.popitem(last=False)
    return trajs


def clear_baseline_cache() -> None:
    with _BASE_CACHE_LOCK:
        _BASE_CACHE.clear()


def _years_axis(config: EnsembleConfig) -> List[int]:
    return list(range(config.years + 1))


def _paired_delta(base: List[List[Dict[str, float]]], scen: List[List[Dict[str, float]]]) -> List[List[Dict[str, float]]]:
    """Per-member, per-year scenario − base over the shared METRICS (paired seeds)."""
    deltas: List[List[Dict[str, float]]] = []
    for b, s in zip(base, scen):
        deltas.append([{k: float(s[t][k]) - float(b[t][k]) for k in METRICS} for t in range(len(b))])
    return deltas


# --------------------------------------------------------------------------- #
# selection plumbing
# --------------------------------------------------------------------------- #


def _selection_from_items(
    items: Sequence[Any], magnitude: Optional[float], actors: Optional[Sequence[str]]
) -> "L.LeverSelection":
    selection = L.make_selection(items, default_magnitude=magnitude, actors=actors)
    unknown = [lid for lid in selection.magnitudes if lid not in L.GROUNDED_LEVERS]
    if unknown:
        raise ValueError(
            f"unknown lever(s): {', '.join(unknown)}; allowed: {', '.join(sorted(L.GROUNDED_LEVERS))}"
        )
    return selection


# --------------------------------------------------------------------------- #
# compute_* (pure projections)
# --------------------------------------------------------------------------- #


def compute_ensemble(
    *, state_csv=None, members=200, years=10, max_agents=100, seed=2026, prior_set="key", jobs=0,
    progress: Progress = None, cancel=None,
) -> Dict[str, Any]:
    config = build_config(state_csv=state_csv, members=members, years=years,
                          max_agents=max_agents, seed=seed, prior_set=prior_set, jobs=jobs)
    trajs = run_trajectories(config, L.LeverSelection(), progress=progress, cancel=cancel)
    bands = _aggregate(trajs, config.years)
    years_axis = _years_axis(config)
    return {
        "schema": SCHEMA,
        "mode": "ensemble",
        "config": _config_block(config),
        "projection": P.ensemble_projection(bands, years_axis, len(trajs)),
    }


def compute_scenario(
    *, state_csv=None, levers=(), magnitude=None, actors=None, members=200, years=10,
    max_agents=100, seed=2026, prior_set="key", jobs=0, progress: Progress = None, cancel=None,
) -> Dict[str, Any]:
    selection = _selection_from_items(levers, magnitude, actors)
    config = build_config(state_csv=state_csv, members=members, years=years,
                          max_agents=max_agents, seed=seed, prior_set=prior_set, jobs=jobs)
    total = 2 * config.n_members
    base = baseline_trajectories(config, progress=progress,
                                 progress_offset=0, progress_total=total, cancel=cancel)
    scen = run_trajectories(config, selection, progress=progress,
                            progress_offset=config.n_members, progress_total=total, cancel=cancel)
    base_bands = _aggregate(base, config.years)
    scen_bands = _aggregate(scen, config.years)
    delta_bands = _aggregate(_paired_delta(base, scen), config.years)
    years_axis = _years_axis(config)
    return {
        "schema": SCHEMA,
        "mode": "scenario",
        "config": _config_block(config),
        "selection": selection.to_dict(),
        "validation": L.validate_selection(selection),
        "projection": P.delta_projection(delta_bands, base_bands, scen_bands, years_axis, len(scen)),
        "baseline": P.ensemble_projection(base_bands, years_axis, len(base)),
        "scenario": P.ensemble_projection(scen_bands, years_axis, len(scen)),
        "brief": _relative_brief(delta_bands, years_axis, selection),
    }


def compute_sensitivity(
    *, state_csv=None, metric="world_gdp", years=10, params=None, r=10, levels=4,
    max_agents=100, seed=2026,
) -> Dict[str, Any]:
    from gim import scc as scc_mod
    from gim.core.priors import key_priors
    from gim.sensitivity import bounds_for, morris, make_output_fn

    priors = key_priors()
    if params:
        names = [n for n in params if n in priors]
        missing = [n for n in params if n not in priors]
    else:
        names = [n for n in scc_mod.SCC_PRIOR_PARAMS if n in priors]
        missing = []
    if not names:
        raise ValueError("no sensitivity parameters resolved against the priors")
    fn = make_output_fn(metric, state_csv or default_state_csv(), years=int(years),
                        max_agents=int(max_agents), base_year=2023, seed=int(seed))
    result = morris(names, bounds_for(priors, names), fn, r=int(r), levels=int(levels), seed=int(seed))
    out = {
        "schema": SCHEMA,
        "mode": "sensitivity",
        "metric": metric,
        "config": {"years": int(years), "max_agents": int(max_agents), "seed": int(seed),
                   "r": int(r), "levels": int(levels), "params": names},
        "projection": P.tornado_projection(metric, result),
    }
    if missing:
        out["warnings"] = [f"ignored non-prior params: {', '.join(missing)}"]
    return out


def compute_weak(
    *, state_csv=None, levers=(), magnitude=None, actors=None, years=12, max_agents=100, seed=2026,
) -> Dict[str, Any]:
    from gim.weak_signal import weak_signal_scan

    selection = _selection_from_items(levers, magnitude, actors)
    config = build_config(state_csv=state_csv, members=1, years=years,
                          max_agents=max_agents, seed=seed, prior_set="key", jobs=1)
    base = L.run_member(config, L.LeverSelection(), index=0)
    scen = L.run_member(config, selection, index=0)
    series = {m: [float(pt[m]) for pt in scen] for m in METRICS}
    scan = weak_signal_scan(series)
    return {
        "schema": SCHEMA,
        "mode": "weak_signals",
        "config": _config_block(config),
        "selection": selection.to_dict(),
        "scenario_series": series,
        "baseline_series": {m: [float(pt[m]) for pt in base] for m in METRICS},
        "weak_signals": _jsonify(scan),
    }


def compute_scc(
    *, state_csv=None, horizons=(30, 100, 200), pulse_gtco2=10.0, distribution=False,
    samples=50, max_agents=100, seed=2026,
) -> Dict[str, Any]:
    from gim import scc as scc_mod

    csv = state_csv or default_state_csv()
    multi = scc_mod.scc_multi_horizon(csv, horizons=tuple(int(h) for h in horizons),
                                      pulse_gtco2=float(pulse_gtco2), seed=int(seed),
                                      max_agents=int(max_agents), base_year=2023)
    out: Dict[str, Any] = {
        "schema": SCHEMA,
        "mode": "scc",
        "config": {"horizons": [int(h) for h in horizons], "pulse_gtco2": float(pulse_gtco2),
                   "max_agents": int(max_agents), "seed": int(seed)},
        "central_usd_per_tco2": {int(h): float(v) for h, v in multi.items()},
    }
    if distribution:
        dist = scc_mod.scc_distribution(csv, n_samples=int(samples), years=int(min(horizons)),
                                        pulse_gtco2=float(pulse_gtco2), max_agents=int(max_agents),
                                        base_year=2023, master_seed=int(seed))
        out["distribution"] = _jsonify(dist)
    return out


def compute_meta(*, kind: str, state_csv=None, max_agents=100, seed=2026) -> Dict[str, Any]:
    if kind == "scc":
        return {"schema": SCHEMA, "mode": "meta.scc",
                **{k: v for k, v in compute_scc(state_csv=state_csv, distribution=True, samples=40,
                                                max_agents=max_agents, seed=seed).items()
                   if k not in {"schema", "mode"}}}
    if kind == "backtest":
        from gim.historical_backtest import run_historical_backtest

        result = run_historical_backtest()
        d = result.to_dict()
        return {
            "schema": SCHEMA, "mode": "meta.backtest",
            "start_year": d["start_year"], "end_year": d["end_year"],
            "gdp_rmse_trillions": d["gdp_rmse_trillions"],
            "global_co2_rmse_gtco2": d["global_co2_rmse_gtco2"],
            "temperature_rmse_c": d["temperature_rmse_c"],
            "temperature_bias_c": d["temperature_bias_c"],
            "series": {
                "co2": {"predicted": d["predicted_global_co2_gtco2"], "actual": d["actual_global_co2_gtco2"]},
                "temperature": {"predicted": d["predicted_temperature_c"], "actual": d["actual_temperature_c"]},
            },
        }
    if kind == "conflict_auc":
        from gim.conflict_benchmark import compare_to_benchmarks

        comparison = compare_to_benchmarks(CONFLICT_AUC, bss=0.05)
        return {
            "schema": SCHEMA, "mode": "meta.conflict_auc",
            "validated": True, "reproduce": CONFLICT_AUC_REPRODUCE,
            "projection": P.roc_projection(CONFLICT_AUC, CONFLICT_AUC_CI, CONFLICT_AUC_P, _jsonify(comparison)),
        }
    raise ValueError(f"unknown meta kind: {kind!r}")


# --------------------------------------------------------------------------- #
# shared helpers
# --------------------------------------------------------------------------- #


def _config_block(config: EnsembleConfig) -> Dict[str, Any]:
    return {
        "state_csv": config.state_csv,
        "n_members": config.n_members,
        "years": config.years,
        "max_agents": config.max_agents,
        "master_seed": config.master_seed,
        "prior_set": config.prior_set,
    }


_METRIC_LABEL = {
    "world_gdp": ("ВВП", "трлн$"),
    "temperature": ("T", "°C"),
    "co2": ("CO₂", "Гт"),
    "mean_social_tension": ("напряжённость", ""),
    "n_debt_crises": ("долговые кризисы", ""),
    "n_wars": ("войны", ""),
    "conflict_risk": ("риск конфликта", ""),
}


def _relative_brief(delta_bands: Dict[str, Dict[str, List[float]]], years_axis: Sequence[int],
                    selection: "L.LeverSelection") -> str:
    horizon = years_axis[-1] if years_axis else 0
    levers = ", ".join(f"{lid}×{mag:.2f}" for lid, mag in selection.magnitudes.items()) or "—"
    parts: List[str] = [f"Относительно базовой траектории к +{horizon} лет (рычаги: {levers}):"]
    for metric in ("world_gdp", "temperature", "co2", "mean_social_tension"):
        p50 = delta_bands.get(metric, {}).get("p50", [])
        if not p50:
            continue
        label, unit = _METRIC_LABEL.get(metric, (metric, ""))
        val = p50[-1]
        parts.append(f"{label} {val:+.3g}{(' ' + unit) if unit else ''} (медиана Δ)")
    return " ".join(parts[:1]) + " " + "; ".join(parts[1:]) + "."


def _jsonify(obj: Any) -> Any:
    """Recursively coerce numpy scalars/arrays/sets so json.dumps never chokes."""
    import math

    try:
        import numpy as np
    except Exception:  # pragma: no cover
        np = None  # type: ignore
    if np is not None:
        if isinstance(obj, np.generic):
            obj = obj.item()
        elif isinstance(obj, np.ndarray):
            return [_jsonify(v) for v in obj.tolist()]
    if isinstance(obj, dict):
        return {str(k): _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_jsonify(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


# --------------------------------------------------------------------------- #
# CLI handlers (add equiv_cli; share compute_* with the engine)
# --------------------------------------------------------------------------- #


def _equiv(parts: Sequence[str]) -> str:
    return " ".join(shlex.quote(str(p)) for p in parts)


def _world_cli(args) -> List[str]:
    flags: List[str] = []
    if getattr(args, "state_csv", None):
        flags += ["--state-csv", args.state_csv]
    if getattr(args, "state_year", None):
        flags += ["--state-year", str(args.state_year)]
    flags += ["--max-agents", str(args.max_agents), "--seed", str(args.seed)]
    return flags


def run_ensemble_cli(args) -> Dict[str, Any]:
    out = compute_ensemble(state_csv=args.state_csv, members=args.members, years=args.years,
                           max_agents=args.max_agents, seed=args.seed, prior_set=args.prior_set, jobs=args.jobs)
    cli = ["python3", "-m", "gim2", "ensemble", "--members", args.members, "--years", args.years,
           "--prior-set", args.prior_set, *_world_cli(args)]
    out["equiv_cli"] = _equiv(cli)
    return out


def run_scenario_cli(args) -> Dict[str, Any]:
    out = compute_scenario(state_csv=args.state_csv, levers=args.lever, magnitude=args.magnitude,
                           actors=args.actors, members=args.members, years=args.years,
                           max_agents=args.max_agents, seed=args.seed, prior_set=args.prior_set, jobs=args.jobs)
    cli = ["python3", "-m", "gim2", "scenario", "--members", args.members, "--years", args.years,
           "--prior-set", args.prior_set]
    for lid in args.lever:
        cli += ["--lever", lid]
    if args.magnitude is not None:
        cli += ["--magnitude", args.magnitude]
    if args.actors:
        cli += ["--actors", *args.actors]
    cli += _world_cli(args)
    out["equiv_cli"] = _equiv(cli)
    return out


def run_sensitivity_cli(args) -> Dict[str, Any]:
    out = compute_sensitivity(state_csv=args.state_csv, metric=args.metric, years=args.years,
                              params=args.params, r=args.r, levels=args.levels,
                              max_agents=args.max_agents, seed=args.seed)
    cli = ["python3", "-m", "gim2", "sensitivity", "--metric", args.metric, "--years", args.years,
           "--r", args.r, "--levels", args.levels, *_world_cli(args)]
    if args.params:
        cli += ["--params", *args.params]
    out["equiv_cli"] = _equiv(cli)
    return out


def run_weak_cli(args) -> Dict[str, Any]:
    out = compute_weak(state_csv=args.state_csv, levers=args.lever, magnitude=args.magnitude,
                       actors=args.actors, years=args.years, max_agents=args.max_agents, seed=args.seed)
    cli = ["python3", "-m", "gim2", "weak", "--years", args.years]
    for lid in args.lever:
        cli += ["--lever", lid]
    if args.magnitude is not None:
        cli += ["--magnitude", args.magnitude]
    if args.actors:
        cli += ["--actors", *args.actors]
    cli += _world_cli(args)
    out["equiv_cli"] = _equiv(cli)
    return out


def run_scc_cli(args) -> Dict[str, Any]:
    out = compute_scc(state_csv=args.state_csv, horizons=args.horizons, pulse_gtco2=args.pulse_gtco2,
                      distribution=args.distribution, samples=args.samples,
                      max_agents=args.max_agents, seed=args.seed)
    cli = ["python3", "-m", "gim2", "scc", "--horizons", *[str(h) for h in args.horizons],
           "--pulse-gtco2", args.pulse_gtco2, *_world_cli(args)]
    if args.distribution:
        cli += ["--distribution", "--samples", args.samples]
    out["equiv_cli"] = _equiv(cli)
    return out


def run_meta_cli(args) -> Dict[str, Any]:
    out = compute_meta(kind=args.kind, state_csv=args.state_csv, max_agents=args.max_agents, seed=args.seed)
    out["equiv_cli"] = _equiv(["python3", "-m", "gim2", "meta", args.kind, *_world_cli(args)])
    return out


__all__ = [
    "build_config", "run_trajectories", "RunCancelled",
    "compute_ensemble", "compute_scenario", "compute_sensitivity", "compute_weak",
    "compute_scc", "compute_meta",
    "run_ensemble_cli", "run_scenario_cli", "run_sensitivity_cli", "run_weak_cli",
    "run_scc_cli", "run_meta_cli",
    "CONFLICT_AUC", "CONFLICT_AUC_CI", "CONFLICT_AUC_P",
]
