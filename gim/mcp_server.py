"""GIM17 MCP server — exposes the validated deterministic core as LLM tools.

This is a *thin adapter*: every tool wraps an existing, validated function from the
GIM engine (ensemble / SCC / sensitivity / weak-signal / scenario-Δ) and returns a
uniform provenance envelope so an LLM narrates *around* the numbers rather than
inventing them. The engine itself is never modified here.

Design contracts (the rigor line):
  - Determinism: every result echoes model_version + snapshot + seed + params_set.
    Same inputs => identical result (auditable, reproducible).
  - Anti-drift: any caller-supplied override is echoed in ``overrides_applied`` so the
    model can never silently change an input.
  - Fidelity switch: ``quick|standard|publication`` maps to ensemble/sample budget;
    the default is interactive (quick) with an explicit caveat in the output.
  - Offline: the scenario path runs the ``simple`` rule-based policy (no network/LLM),
    so the library is fully detachable for use inside a company perimeter.

Run as an MCP stdio server:  ``gim-mcp``  (or ``python -m gim.mcp_server``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from gim import __version__ as GIM_VERSION
from gim.runtime import default_state_csv, load_world
from gim.ensemble import EnsembleConfig, run_ensemble, METRICS
from gim.scenario_compiler import compile_question
from gim.sim_bridge import SimBridge
from gim.scc import (
    social_cost_of_carbon,
    scc_multi_horizon,
    scc_distribution,
    SCC_PRIOR_PARAMS,
)
from gim.weak_signal import weak_signal_scan
from gim.core.priors import key_priors
from gim.core.rng import seed_world
from gim.core.simulation import step_world
from gim.core.policy import make_policy_map
from gim.state_projection import compiled_state_rows

mcp = FastMCP("gim")

# ---------------------------------------------------------------------------
# Shared vocabulary (also served as the model-card resource for grounding).
# ---------------------------------------------------------------------------

UNITS: Dict[str, str] = {
    "world_gdp": "sum of agent GDP, calibrated model units",
    "world_population": "sum of agent population, persons (model units)",
    "temperature": "°C anomaly above pre-industrial",
    "co2": "atmospheric CO2, Gt (model carbon pool + pre-industrial)",
    "n_debt_crises": "count of agents in debt crisis",
    "n_regime_crises": "count of agents in regime crisis",
    "n_wars": "count of undirected war pairs",
    "mean_social_tension": "mean social tension across agents, 0..1",
    "conflict_risk": "structural conflict risk, 0..1 (conflict_proneness x social tension)",
}

# Metrics that the sensitivity output-function supports (see sensitivity.make_output_fn).
SENSITIVITY_METRICS = ("temperature", "co2", "world_gdp", "mean_social_tension")

FIDELITY_MEMBERS = {"quick": 100, "standard": 500, "publication": 2000}
FIDELITY_SAMPLES = {"quick": 40, "standard": 100, "publication": 400}

DISCLAIMER = (
    "The GIM engine is validated; the LLM narrative around it is not. Treat outputs as "
    "model projections under stated assumptions, not forecasts."
)

DATA_DIR = Path(default_state_csv()).resolve().parent

# The MCP default deliberately pins the *calibrated 2026* snapshot — the one the paper's
# validated headline numbers are computed on — rather than the engine's generic default
# (which is the uncalibrated operational base). Falls back to the engine default if absent.
CALIBRATED_DEFAULT = DATA_DIR / "agent_states_operational_2026_calibrated.csv"


def _resolve_snapshot(snapshot: str) -> tuple[str, str]:
    """Resolve a snapshot id to (csv_path, canonical_id). Accepts 'default', a known
    id (filename stem under the data dir), or a direct path."""
    if snapshot in ("", "default"):
        path = CALIBRATED_DEFAULT if CALIBRATED_DEFAULT.exists() else Path(default_state_csv())
        path = path.resolve()
        return str(path), path.stem
    cand = Path(snapshot)
    if cand.exists():
        return str(cand.resolve()), cand.stem
    by_stem = DATA_DIR / f"{snapshot}.csv"
    if by_stem.exists():
        return str(by_stem.resolve()), by_stem.stem
    raise ValueError(
        f"Unknown snapshot '{snapshot}'. Use 'default', a path, or an id from gim://state/catalog."
    )


def _envelope(
    result: Any,
    *,
    snapshot_id: str,
    seed: int,
    params_set: str,
    budget: Optional[Dict[str, int]] = None,
    overrides_applied: Optional[List[str]] = None,
    units: Optional[Dict[str, str]] = None,
    caveats: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Wrap a raw engine result in the uniform provenance envelope."""
    return {
        "result": result,
        "provenance": {
            "model_version": GIM_VERSION,
            "state_snapshot": snapshot_id,
            "seed": seed,
            "params_set": params_set,
            **(budget or {}),
        },
        "overrides_applied": overrides_applied or [],
        "units": units or {},
        "caveats": caveats or [],
        "disclaimer": DISCLAIMER,
    }


# ===========================================================================
# Resources (read-only grounding — pulled into context, no computation).
# ===========================================================================

@mcp.resource("gim://model/card")
def model_card() -> Dict[str, Any]:
    """Model identity, tracked metrics + units, and the validated-engine disclaimer."""
    return {
        "model": "GIM17 — Global Integrated Model",
        "version": GIM_VERSION,
        "metrics": {m: UNITS.get(m, "") for m in METRICS},
        "tools": [
            "gim_baseline", "gim_ensemble", "gim_scenario_delta",
            "gim_scc", "gim_sensitivity", "gim_weak_signals",
        ],
        "fidelity_levels": list(FIDELITY_MEMBERS),
        "disclaimer": DISCLAIMER,
    }


@mcp.resource("gim://state/catalog")
def state_catalog() -> Dict[str, Any]:
    """Available state snapshots (id + path) that tools accept as ``snapshot``."""
    default_path, default_id = _resolve_snapshot("default")
    default = Path(default_path).resolve()
    snaps = [
        {"id": p.stem, "path": str(p), "is_default": p == default}
        for p in sorted(DATA_DIR.glob("agent_states_*.csv"))
    ]
    return {"default": default_id, "snapshots": snaps}


@mcp.resource("gim://params/priors")
def params_priors() -> Dict[str, Any]:
    """Literature-anchored parameter priors (name -> [low, high]) for sensitivity/SCC."""
    pri = key_priors()
    return {
        "priors": {name: {"low": pr.low, "high": pr.high} for name, pr in pri.items()},
        "scc_params": SCC_PRIOR_PARAMS,
        "sensitivity_metrics": list(SENSITIVITY_METRICS),
    }


# ===========================================================================
# Tools.
# ===========================================================================

@mcp.tool()
def gim_baseline(
    countries: Optional[List[str]] = None,
    snapshot: str = "default",
    state_year: int = 2026,
    max_agents: int = 100,
) -> Dict[str, Any]:
    """Current observable state for selected countries from a calibrated snapshot —
    the grounding anchor ('where are we now') before any projection.

    countries: list of names to include; None => all (capped at max_agents).
    """
    csv_path, snap_id = _resolve_snapshot(snapshot)
    world = load_world(csv_path, max_agents=max_agents, state_year=state_year)
    rows = compiled_state_rows(world)
    if countries:
        wanted = {c.lower() for c in countries}
        rows = [r for r in rows if str(r.get("name", "")).lower() in wanted]
    return _envelope(
        {"states": rows, "n": len(rows)},
        snapshot_id=snap_id, seed=0, params_set="default",
        caveats=["Observable state only; no dynamics simulated."],
    )


@mcp.tool()
def gim_ensemble(
    horizon: int = 10,
    fidelity: str = "quick",
    prior_set: str = "key",
    metrics: Optional[List[str]] = None,
    snapshot: str = "default",
    seed: int = 2026,
    max_agents: int = 100,
) -> Dict[str, Any]:
    """Monte-Carlo fan bands (p5/p25/p50/p75/p95) for the headline macro/climate/conflict
    metrics over ``horizon`` years — the scenario *distribution* for portfolio stress.

    fidelity: quick(100) | standard(500) | publication(2000) members.
    metrics: subset of the 9 headline metrics; None => all.
    """
    n_members = FIDELITY_MEMBERS.get(fidelity, FIDELITY_MEMBERS["quick"])
    csv_path, snap_id = _resolve_snapshot(snapshot)
    cfg = EnsembleConfig(
        state_csv=csv_path, n_members=n_members, years=horizon,
        max_agents=max_agents, master_seed=seed, prior_set=prior_set,
    )
    res = run_ensemble(cfg).to_dict()
    if metrics:
        keep = set(metrics)
        res["metrics"] = {k: v for k, v in res["metrics"].items() if k in keep}
    return _envelope(
        res,
        snapshot_id=snap_id, seed=seed, params_set=prior_set,
        budget={"n_members": n_members, "horizon": horizon},
        units={m: UNITS[m] for m in (metrics or METRICS) if m in UNITS},
        caveats=[f"fidelity={fidelity} (n={n_members}); raise to 'standard'/'publication' for tighter bands."],
    )


@mcp.tool()
def gim_scenario_delta(
    question: str,
    horizon: int = 3,
    actors: Optional[List[str]] = None,
    template_id: Optional[str] = None,
    risk_overrides: Optional[Dict[str, float]] = None,
    snapshot: str = "default",
    state_year: int = 2026,
    max_agents: int = 100,
) -> Dict[str, Any]:
    """Evaluate a what-if scenario described in natural language and return its validated
    risk profile + crisis deltas vs baseline — a bespoke stress test.

    Primary path: ``question`` is parsed deterministically (compile_question) to infer
    actors + template. Escape hatch: pin ``actors`` and/or ``template_id`` explicitly to
    bypass inference; ``risk_overrides`` tunes risk aggregation. All are echoed back.
    Runs the offline ``simple`` policy (no LLM/network).
    """
    csv_path, snap_id = _resolve_snapshot(snapshot)
    world = load_world(csv_path, max_agents=max_agents, state_year=state_year)
    scenario = compile_question(
        question, world, actors=actors,
        horizon_months=horizon * 12, template_id=template_id,
    )
    bridge = SimBridge()
    evaluation, _trajectory = bridge.evaluate_scenario(
        world, scenario, n_years=horizon,
        default_mode="simple", aggregate_overrides=risk_overrides,
    )
    applied: List[str] = []
    if actors:
        applied.append(f"actors pinned: {actors}")
    if template_id:
        applied.append(f"template pinned: {template_id}")
    if risk_overrides:
        applied.append(f"risk_overrides: {risk_overrides}")
    result = {
        "actors": list(getattr(scenario, "actor_names", []) or []),
        "template_id": getattr(scenario, "template_id", template_id),
        "risk_probabilities": evaluation.risk_probabilities,
        "driver_scores": evaluation.driver_scores,
        "dominant_outcomes": evaluation.dominant_outcomes,
        "crisis_signal_summary": evaluation.crisis_signal_summary,
        "crisis_delta_by_agent": evaluation.crisis_delta_by_agent,
        "criticality_score": evaluation.criticality_score,
        "calibration_score": evaluation.calibration_score,
        "physical_consistency_score": evaluation.physical_consistency_score,
        "consistency_notes": evaluation.consistency_notes,
    }
    return _envelope(
        result,
        snapshot_id=snap_id, seed=2026, params_set="default",
        budget={"horizon": horizon},
        overrides_applied=applied,
        caveats=["Risk relative to in-run baseline; deltas in crisis_delta_by_agent."],
    )


@mcp.tool()
def gim_scc(
    mode: str = "point",
    horizons: Optional[List[int]] = None,
    fidelity: str = "quick",
    snapshot: str = "default",
    seed: int = 2026,
    max_agents: int = 100,
) -> Dict[str, Any]:
    """Social cost of carbon ($/tCO2) via a marginal-pulse experiment — for pricing
    transition risk.

    mode: 'point' (single horizon=horizons[0] or 30) | 'multi' (one SCC per horizon) |
          'distribution' (SCC uncertainty band by sampling priors).
    fidelity controls the sample budget for mode='distribution'.
    """
    csv_path, snap_id = _resolve_snapshot(snapshot)
    hs = horizons or [30]
    if mode == "multi":
        raw = scc_multi_horizon(csv_path, horizons=tuple(hs), seed=seed, max_agents=max_agents)
        result = {str(h): v for h, v in raw.items()}
        budget = {"horizons": hs}
    elif mode == "distribution":
        n = FIDELITY_SAMPLES.get(fidelity, FIDELITY_SAMPLES["quick"])
        result = scc_distribution(
            csv_path, years=hs[0], n_samples=n, max_agents=max_agents, master_seed=seed,
        )
        result.pop("samples", None)  # keep the envelope compact; percentiles + mean retained
        budget = {"years": hs[0], "n_samples": n}
    else:  # point
        result = social_cost_of_carbon(csv_path, years=hs[0], seed=seed, max_agents=max_agents)
        budget = {"years": hs[0]}
    return _envelope(
        result,
        snapshot_id=snap_id, seed=seed, params_set="default",
        budget=budget,
        units={"scc": "USD per tCO2"},
        caveats=["SCC is highly sensitive to discount rate (rho) and damage curvature."],
    )


@mcp.tool()
def gim_sensitivity(
    target_metric: str = "temperature",
    horizon: int = 10,
    r: int = 10,
    top_k: int = 12,
    snapshot: str = "default",
    seed: int = 2026,
    max_agents: int = 100,
) -> Dict[str, Any]:
    """Morris elementary-effects screening: which parameters drive ``target_metric`` —
    factor attribution for the risk. Ranked by mu_star (overall influence).

    target_metric: one of temperature | co2 | world_gdp | mean_social_tension.
    Requires numpy (installed via the 'mcp'/'analysis' extra).
    """
    if target_metric not in SENSITIVITY_METRICS:
        raise ValueError(f"target_metric must be one of {SENSITIVITY_METRICS}")
    try:
        from gim.sensitivity import morris, make_output_fn, bounds_for, rank
    except ImportError as exc:  # numpy missing
        return _envelope(
            {"error": f"sensitivity requires numpy: {exc}"},
            snapshot_id=snapshot, seed=seed, params_set="key",
            caveats=["Install numpy (pip install 'gim17[mcp]') to enable this tool."],
        )
    csv_path, snap_id = _resolve_snapshot(snapshot)
    priors = key_priors()
    names = list(priors.keys())[:top_k]
    bounds = bounds_for(priors, names)
    fn = make_output_fn(target_metric, csv_path, years=horizon, max_agents=max_agents, seed=seed)
    raw = morris(names, bounds, fn, r=r, seed=seed)
    ranked = [{"param": n, "mu_star": v, **raw[n]} for n, v in rank(raw, by="mu_star")]
    return _envelope(
        {"target_metric": target_metric, "ranked_drivers": ranked},
        snapshot_id=snap_id, seed=seed, params_set="key",
        budget={"r": r, "n_params": len(names), "horizon": horizon},
        caveats=["Morris screening = relative ranking, not exact variance shares (use Sobol for that)."],
    )


@mcp.tool()
def gim_weak_signals(
    horizon: int = 15,
    series: Optional[Dict[str, List[float]]] = None,
    detrend: bool = True,
    snapshot: str = "default",
    seed: int = 2026,
    max_agents: int = 100,
) -> Dict[str, Any]:
    """Early-warning scan over a trajectory: multivariate anomalies, structural breaks,
    and critical-slowing-down — flags impending regime shifts.

    Primary path: simulates a baseline trajectory over ``horizon`` years and scans the 8
    headline metrics. Escape hatch: pass your own ``series`` (name -> list of values).
    """
    if series is not None:
        report = weak_signal_scan(series, detrend=detrend)
        return _envelope(
            report,
            snapshot_id="caller-supplied", seed=seed, params_set="n/a",
            overrides_applied=["series supplied by caller"],
            caveats=["Scan ran on caller-supplied series, not a simulated trajectory."],
        )
    from gim.ensemble import _collect_metrics  # internal, stable metric collector
    csv_path, snap_id = _resolve_snapshot(snapshot)
    world = load_world(csv_path, max_agents=max_agents)
    seed_world(world, seed)
    policies = make_policy_map(world.agents.keys(), mode="simple")
    built: Dict[str, List[float]] = {m: [] for m in METRICS}
    rec = _collect_metrics(world)
    for m in METRICS:
        built[m].append(rec[m])
    for _ in range(horizon):
        step_world(world, policies)
        rec = _collect_metrics(world)
        for m in METRICS:
            built[m].append(rec[m])
    report = weak_signal_scan(built, detrend=detrend)
    return _envelope(
        report,
        snapshot_id=snap_id, seed=seed, params_set="default",
        budget={"horizon": horizon},
        caveats=[f"detrend={detrend}: signals = departures from normal dynamics, not the trend itself."],
    )


def main() -> None:
    """Console-script entry point: run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
