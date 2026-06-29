"""Grounded lever ontology for the v2 deterministic line (THE-64).

This replaces v1's eight *softmax risk-channels* (`gim.scenario_ontology`) with
**physically-grounded levers** that map to the real state variables and parameters
the deterministic core (`gim.core.simulation.step_world`) actually integrates — the
levers of Appendix B / §6 of the paper. It adds **no model math**: a lever either

* **param** — overrides one or more real ``calibration_params`` values on the
  per-run ``ParameterSet`` (the same isolated mechanism ensembles use), or
* **pulse** — mutates real world/agent/relation state during the run (the same
  mechanism the SCC pulse uses to perturb ``carbon_pools``),

and then lets the frozen model propagate the consequences endogenously.

Magnitude is a bounded intensity in ``[0.15, 1.25]`` (1.0 == the nominal calibrated
shift), so a selector (UI or LLM) cannot invent extreme or negligible intensities.

The member runner :func:`run_member` mirrors ``gim.ensemble._run_member`` exactly
when no levers are selected (it reuses the frozen seed/sampling/metrics helpers), so
a base-vs-scenario comparison is apples-to-apples and never drifts from the
validated ensemble — :mod:`tests.test_gim2_levers` asserts that identity.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from gim.core.params import ParameterSet, default_params
from gim.core.policy import make_policy_map
from gim.core.priors import all_priors, key_priors, sample_parameter_set
from gim.core.resources import normalize_resource_scales_forward
from gim.core.rng import seed_world
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv
from gim.ensemble import EnsembleConfig, _collect_metrics, _member_seed

# Intensity band: 1.0 == nominal calibrated shift (cf. gim.scenario_ontology band).
MAGNITUDE_MIN: float = 0.15
MAGNITUDE_MAX: float = 1.25
DEFAULT_MAGNITUDE: float = 0.60


def clamp_magnitude(value: float) -> float:
    return max(MAGNITUDE_MIN, min(MAGNITUDE_MAX, float(value)))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


# --------------------------------------------------------------------------- #
# Appendix-A anchoring (THE-64 calibration)
# --------------------------------------------------------------------------- #
# Param-lever coefficients are DERIVED from the literature-grounded priors
# (``data/parameter_priors.csv`` → ``gim.core.priors``), so magnitude 1.0 moves a
# parameter to its Appendix-A prior *edge* measured at the prior's central value
# (``new = base·(1 + coeff)`` with ``coeff = (edge − p1)/p1``). The calibration
# therefore tracks the paper's priors instead of being hand-set, and cannot drift.
try:  # the prior table is the single source of truth; fall back if unavailable.
    from gim.core.priors import all_priors as _all_priors

    _PRIORS = _all_priors()
except Exception:  # pragma: no cover - keeps gim2 importable without the CSVs
    _PRIORS = {}

_COEFF_FALLBACK: Dict[Tuple[str, str], float] = {
    ("DECARB_RATE_STRUCTURAL", "high"): 0.269,   # [0.040, 0.066] around 0.052 (GCP/WDI)
    ("EMISSIONS_SCALE", "low"): -0.077,          # [0.90, 1.05] around 0.9755 (GCP2023)
    ("SSP_FORWARD_TFP_DRIFT", "high"): 0.25,     # ±25% band around 0.018 (SSP2/registry)
    ("SAVINGS_BASE", "high"): 0.05,              # ±5% band around 0.24 (WDI23/registry)
    ("TFP_RD_SHARE_SENS", "high"): 1.0,          # [0.10, 0.60] around 0.30 (R&D elasticity)
}


def _edge_coeff(name: str, edge: str) -> float:
    """Coefficient so ``base·(1 + coeff)`` equals the Appendix-A prior ``edge``
    (``"high"``/``"low"``) at the prior's central value ``p1``."""
    prior = _PRIORS.get(name)
    if prior is not None and getattr(prior, "p1", 0.0):
        ref = float(prior.p1)
        target = float(prior.high if edge == "high" else prior.low)
        if ref:
            return round((target - ref) / ref, 4)
    return _COEFF_FALLBACK.get((name, edge), 0.0)


_C_DECARB = _edge_coeff("DECARB_RATE_STRUCTURAL", "high")
_C_EMIT = _edge_coeff("EMISSIONS_SCALE", "low")
_C_TFP_DRIFT = _edge_coeff("SSP_FORWARD_TFP_DRIFT", "high")
_C_SAVINGS = _edge_coeff("SAVINGS_BASE", "high")
_C_RD = _edge_coeff("TFP_RD_SHARE_SENS", "high")

# Literature shock anchors for the pulse levers (magnitude 1.0 == the cited shock).
CARBON_PRICE_USD = 130.0          # high-ambition carbon price ($/tCO2); IMF/World Bank
CARBON_PASSTHROUGH = 0.003        # energy-price rise per $1/tCO2 (CARBON_PRICE_PASSTHROUGH)
_C_CARBON_ENERGY = round(CARBON_PRICE_USD * CARBON_PASSTHROUGH, 3)  # ≈ +0.39 energy price
_C_ENERGY_PRICE = 0.60            # 2022-scale real energy-price spike (EIA/IEA)
_C_ENERGY_PROD = -0.15            # severe supply disruption to domestic output (IEA)
_C_FOOD_PRICE = 0.60              # 2007–08 / 2010–11 FAO food-price-index surge
_C_FOOD_PROD = -0.20             # crop-shortfall supply cut (FAO)
_C_TRADE_BARRIER = 0.30           # comprehensive-sanctions trade drop (Felbermayr et al. 2020)
_C_CONFLICT = 0.05                # accompanying conflict-pressure nudge
_C_UNEMP = 0.03                   # 1973–75 stagflation: unemployment +~3.6pp
_C_INFLATION = 0.04               # 1970s stagflation inflation impulse


# --------------------------------------------------------------------------- #
# Lever spec (declarative data — serialisable for the UI / LLM menu)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ParamTarget:
    """A relative override of one real ``calibration_params`` value.

    ``new = base * (1 + coeff * m)`` — scaling each member's *sampled* base value
    so the lever rides on top of the ensemble's parameter uncertainty.
    """

    name: str
    coeff: float


@dataclass(frozen=True)
class PulseOp:
    """A state mutation applied during the run.

    kinds: ``price_mul`` (global_state.prices[field] *= 1+coeff*m),
    ``prod_mul`` (agent.resources[field].production *= 1+coeff*m),
    ``relation_add`` (relation.field += coeff*m, clamped 0..1, both directions),
    ``econ_add`` (agent.economy.field += coeff*m, clamped to its param band).
    """

    kind: str
    field: str
    coeff: float


@dataclass(frozen=True)
class LeverSpec:
    id: str
    kind: str  # "param" | "pulse"
    channel: str
    label: str
    label_ru: str
    triggers: Tuple[str, ...]
    rationale: str
    indicators: Tuple[str, ...] = ()
    param_targets: Tuple[ParamTarget, ...] = ()
    pulse_ops: Tuple[PulseOp, ...] = ()
    pulse_sustain: int = 1  # (re)apply at years 1..sustain
    pulse_scope: str = "global"  # "global" | "actors"
    default_magnitude: float = DEFAULT_MAGNITUDE


# One grounded lever per physically-meaningful pressure (Appendix B / §6).
# Param coefficients are ANCHORED to the Appendix-A priors (``_edge_coeff`` above);
# pulse coefficients are anchored to cited literature shocks. Magnitude 1.0 == the
# anchored point; the band keeps [0.15, 1.0] inside the prior/literature range and
# treats 1.0–1.25 as explicit stress extrapolation.
GROUNDED_LEVERS: Dict[str, LeverSpec] = {
    "carbon_price": LeverSpec(
        id="carbon_price",
        kind="param",  # hybrid: a partial decarb push + a one-off energy-price level shift
        channel="climate_economy",
        label="Carbon price",
        label_ru="Цена углерода",
        triggers=("цена углерод", "углеродн налог", "carbon price", "carbon tax", "ets"),
        rationale=("Carbon price ≈ $130/tCO₂ (IMF/WB high-ambition) × 0.003 passthrough → "
                   "+39% energy price (one-off level shift); also a partial decarbonization push."),
        indicators=("energy_price", "inflation", "co2", "temperature"),
        param_targets=(
            ParamTarget("DECARB_RATE_STRUCTURAL", round(0.5 * _C_DECARB, 4)),  # half of the prior-edge step
        ),
        pulse_ops=(
            PulseOp("price_mul", "energy", _C_CARBON_ENERGY),
        ),
        pulse_sustain=1,  # permanent price → single level shift (avoids year-on-year compounding)
    ),
    "decarbonization": LeverSpec(
        id="decarbonization",
        kind="param",
        channel="climate",
        label="Decarbonization push",
        label_ru="Декарбонизация",
        triggers=("декарбон", "вич", "renewable", "decarbon", "clean energy", "энергопереход"),
        rationale=("DECARB_RATE_STRUCTURAL → Appendix-A prior high 0.066 (from 0.052) and "
                   "EMISSIONS_SCALE → prior low 0.90 ⇒ lower CO₂ and warming."),
        indicators=("co2", "temperature", "world_gdp"),
        param_targets=(
            ParamTarget("DECARB_RATE_STRUCTURAL", _C_DECARB),
            ParamTarget("EMISSIONS_SCALE", _C_EMIT),
        ),
    ),
    "growth": LeverSpec(
        id="growth",
        kind="param",
        channel="economy",
        label="Growth package (R&D / savings / TFP)",
        label_ru="Пакет роста (НИОКР / сбережения / TFP)",
        triggers=("рост", "ниокр", "инвестиц", "сбережен", "growth", "r&d", "rnd", "savings", "productivity"),
        rationale=("Upper edge of the calibrated growth priors: SSP TFP drift, savings rate and "
                   "R&D sensitivity each → their Appendix-A prior high ⇒ higher GDP."),
        indicators=("world_gdp", "world_population"),
        param_targets=(
            ParamTarget("SSP_FORWARD_TFP_DRIFT", _C_TFP_DRIFT),
            ParamTarget("SAVINGS_BASE", _C_SAVINGS),
            ParamTarget("TFP_RD_SHARE_SENS", _C_RD),
        ),
    ),
    "energy_shock": LeverSpec(
        id="energy_shock",
        kind="pulse",
        channel="resource_economy",
        label="Energy / oil supply shock",
        label_ru="Шок поставок энергии / нефти",
        triggers=("нефт", "газ", "энергошок", "энергетическ кризис", "oil", "gas", "energy shock", "opec"),
        rationale=("2022-scale shock: real energy price +60% (EIA/IEA) and −15% domestic output "
                   "→ import bill → inflation → debt stress."),
        indicators=("energy_price", "inflation", "world_gdp", "n_debt_crises"),
        pulse_ops=(
            PulseOp("price_mul", "energy", _C_ENERGY_PRICE),
            PulseOp("prod_mul", "energy", _C_ENERGY_PROD),
        ),
        pulse_sustain=2,
    ),
    "food_shock": LeverSpec(
        id="food_shock",
        kind="pulse",
        channel="resource_society",
        label="Food / crop shock",
        label_ru="Продовольственный / урожайный шок",
        triggers=("продовольств", "урожай", "зерн", "голод", "food", "crop", "grain", "harvest"),
        rationale=("2007–08 / 2010–11 scale: FAO food price +60% and −20% supply "
                   "→ social tension → protest."),
        indicators=("food_price", "mean_social_tension", "world_gdp"),
        pulse_ops=(
            PulseOp("price_mul", "food", _C_FOOD_PRICE),
            PulseOp("prod_mul", "food", _C_FOOD_PROD),
        ),
        pulse_sustain=2,
    ),
    "trade_sanctions": LeverSpec(
        id="trade_sanctions",
        kind="pulse",
        channel="trade_conflict",
        label="Trade / sanctions intensity",
        label_ru="Интенсивность торговли / санкций",
        triggers=("санкц", "эмбарго", "торгов барьер", "тариф", "sanction", "embargo", "tariff", "trade war"),
        rationale=("Comprehensive-sanctions trade drop ≈ −30% on the named dyads (gravity studies, "
                   "Felbermayr et al. 2020) via the trade barrier, plus a conflict-pressure nudge."),
        indicators=("world_gdp", "n_wars", "mean_social_tension"),
        pulse_ops=(
            PulseOp("relation_add", "trade_barrier", _C_TRADE_BARRIER),
            PulseOp("relation_add", "conflict_level", _C_CONFLICT),
        ),
        pulse_sustain=3,
        pulse_scope="actors",
    ),
    "stagflation": LeverSpec(
        id="stagflation",
        kind="pulse",
        channel="macro",
        label="Exogenous stagflation shock",
        label_ru="Экзогенный стагфляционный шок",
        triggers=("стагфляц", "рецесс", "макрошок", "stagflation", "recession", "macro shock"),
        rationale=("1973–75-scale stagflation: unemployment +3pp and inflation +4pp, sustained "
                   "three years (exogenous)."),
        indicators=("mean_social_tension", "world_gdp"),
        pulse_ops=(
            PulseOp("econ_add", "unemployment", _C_UNEMP),
            PulseOp("econ_add", "inflation", _C_INFLATION),
        ),
        pulse_sustain=3,
    ),
}


# --------------------------------------------------------------------------- #
# Selection (what a UI / LLM / CLI hands the engine)
# --------------------------------------------------------------------------- #


@dataclass
class LeverSelection:
    magnitudes: Dict[str, float] = field(default_factory=dict)  # lever_id -> magnitude (clamped)
    actors: Tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.magnitudes

    def to_dict(self) -> Dict[str, Any]:
        return {"levers": dict(self.magnitudes), "actors": list(self.actors)}


def make_selection(
    items: Sequence[Any],
    *,
    default_magnitude: Optional[float] = None,
    actors: Optional[Sequence[str]] = None,
) -> LeverSelection:
    """Build a clamped selection from CLI/LLM items.

    ``items`` may be lever ids (``"energy_shock"``), ``"id=magnitude"`` strings,
    or ``{"lever": id, "magnitude": m}`` dicts.
    """
    magnitudes: Dict[str, float] = {}
    for item in items:
        lever_id: str = ""
        mag: Optional[float] = None
        if isinstance(item, dict):
            lever_id = str(item.get("lever") or item.get("id") or "").strip()
            if item.get("magnitude") is not None:
                mag = float(item["magnitude"])
        elif isinstance(item, str):
            if "=" in item:
                head, _, tail = item.partition("=")
                lever_id = head.strip()
                try:
                    mag = float(tail.strip())
                except ValueError:
                    mag = None
            else:
                lever_id = item.strip()
        if not lever_id:
            continue
        if mag is None:
            spec = GROUNDED_LEVERS.get(lever_id)
            mag = (spec.default_magnitude if spec else default_magnitude) if default_magnitude is None else default_magnitude
            if mag is None:
                mag = spec.default_magnitude if spec else DEFAULT_MAGNITUDE
        magnitudes[lever_id] = clamp_magnitude(mag)
    return LeverSelection(magnitudes=magnitudes, actors=tuple(actors or ()))


def validate_selection(selection: LeverSelection, world: Any | None = None) -> List[str]:
    """Return human-readable problems; empty means safe to run."""
    problems: List[str] = []
    for lever_id, mag in selection.magnitudes.items():
        if lever_id not in GROUNDED_LEVERS:
            problems.append(
                f"lever '{lever_id}' is not a grounded lever "
                f"(allowed: {', '.join(sorted(GROUNDED_LEVERS))})."
            )
        if not (MAGNITUDE_MIN <= mag <= MAGNITUDE_MAX):
            problems.append(
                f"lever '{lever_id}': magnitude {mag:.3f} outside band "
                f"[{MAGNITUDE_MIN}, {MAGNITUDE_MAX}]."
            )
    needs_actors = any(
        GROUNDED_LEVERS.get(lid) and GROUNDED_LEVERS[lid].pulse_scope == "actors"
        for lid in selection.magnitudes
    )
    if needs_actors and world is not None and not resolve_actors(world, selection.actors):
        problems.append("an actor-scoped lever was selected but no actors resolved.")
    return problems


def match_levers(prompt: str) -> List[str]:
    """Deterministic keyword selector — ids of levers whose triggers fire."""
    import re

    norm = re.sub(r"[^0-9a-zа-яё]+", " ", prompt.lower()).strip()
    hits: List[str] = []
    for lever_id, spec in GROUNDED_LEVERS.items():
        if any(re.search(r"\b" + re.escape(t.strip()), norm) for t in spec.triggers):
            hits.append(lever_id)
    return hits


# --------------------------------------------------------------------------- #
# Actor resolution (light: id-exact or name-substring; sane fallbacks)
# --------------------------------------------------------------------------- #


def resolve_actors(world: Any, actors: Sequence[str]) -> List[str]:
    """Resolve actor names/ids to world agent ids. Empty -> the two largest economies."""
    if not actors:
        ranked = sorted(world.agents.values(), key=lambda a: a.economy.gdp, reverse=True)
        return [a.id for a in ranked[:2]]
    resolved: List[str] = []
    for raw in actors:
        token = str(raw).strip()
        if not token:
            continue
        if token in world.agents:
            resolved.append(token)
            continue
        upper = token.upper()
        if upper in world.agents:
            resolved.append(upper)
            continue
        low = token.lower()
        for agent in world.agents.values():
            if low in agent.name.lower():
                resolved.append(agent.id)
                break
    # de-dup, preserve order
    seen: set[str] = set()
    return [a for a in resolved if not (a in seen or seen.add(a))]


# --------------------------------------------------------------------------- #
# Lever application (param overrides + state pulses) — no model math added
# --------------------------------------------------------------------------- #


def apply_param_levers(params: ParameterSet, selection: LeverSelection) -> ParameterSet:
    """Compose all selected *param* levers onto the sampled ParameterSet."""
    overrides: Dict[str, Any] = {}
    for lever_id, mag in selection.magnitudes.items():
        spec = GROUNDED_LEVERS.get(lever_id)
        if spec is None or not spec.param_targets:
            continue
        for target in spec.param_targets:
            base = float(params.get(target.name, 0.0))
            new = base * (1.0 + target.coeff * mag)
            # If a previous lever already touched this param, compose on the new value.
            if target.name in overrides:
                base2 = float(overrides[target.name])
                new = base2 * (1.0 + target.coeff * mag)
            overrides[target.name] = new
    return params.with_overrides(overrides) if overrides else params


def _econ_band(world: Any, field_name: str) -> Tuple[float, float]:
    params = getattr(world, "params", None) or default_params()
    if field_name == "unemployment":
        return float(params.get("UNEMPLOYMENT_MIN", 0.01)), float(params.get("UNEMPLOYMENT_MAX", 0.35))
    if field_name == "inflation":
        return float(params.get("INFLATION_MIN", -0.02)), float(params.get("INFLATION_MAX", 0.30))
    return 0.0, 1.0


def apply_pulses(world: Any, year: int, selection: LeverSelection, actor_ids: Sequence[str]) -> None:
    """Apply selected *pulse* levers at ``year`` (1-indexed step). Mutates state."""
    actor_set = set(actor_ids)
    for lever_id, mag in selection.magnitudes.items():
        spec = GROUNDED_LEVERS.get(lever_id)
        if spec is None or not spec.pulse_ops:
            continue
        if year < 1 or year > spec.pulse_sustain:
            continue
        scope_ids = actor_set if spec.pulse_scope == "actors" else set(world.agents.keys())
        for op in spec.pulse_ops:
            _apply_pulse_op(world, op, mag, scope_ids)


def _apply_pulse_op(world: Any, op: PulseOp, mag: float, scope_ids: set) -> None:
    if op.kind == "price_mul":
        prices = world.global_state.prices
        prices[op.field] = float(prices.get(op.field, 1.0)) * (1.0 + op.coeff * mag)
        return
    if op.kind == "prod_mul":
        for aid in scope_ids:
            agent = world.agents.get(aid)
            res = agent.resources.get(op.field) if agent else None
            if res is not None:
                res.production = max(0.0, float(res.production) * (1.0 + op.coeff * mag))
        return
    if op.kind == "relation_add":
        for aid in scope_ids:
            rels = world.relations.get(aid, {})
            for partner, rel in rels.items():
                _bump_relation(rel, op.field, op.coeff * mag)
                back = world.relations.get(partner, {}).get(aid)
                if back is not None:
                    _bump_relation(back, op.field, op.coeff * mag)
        return
    if op.kind == "econ_add":
        for aid in scope_ids:
            agent = world.agents.get(aid)
            if agent is None:
                continue
            lo, hi = _econ_band(world, op.field)
            cur = float(getattr(agent.economy, op.field))
            setattr(agent.economy, op.field, max(lo, min(hi, cur + op.coeff * mag)))
        return


def _bump_relation(rel: Any, field_name: str, delta: float) -> None:
    cur = float(getattr(rel, field_name, 0.0))
    setattr(rel, field_name, _clamp01(cur + delta))


# --------------------------------------------------------------------------- #
# Member runner (frozen primitives + lever injection; base == ensemble member)
# --------------------------------------------------------------------------- #


def run_member(
    config: EnsembleConfig,
    selection: LeverSelection,
    *,
    index: int,
    collector: Optional[Callable[[Any], Dict[str, float]]] = None,
) -> List[Dict[str, float]]:
    """One ensemble member with levers injected. Reuses the frozen seed/sampling/
    metrics helpers, so ``selection.is_empty`` with the default collector reproduces
    ``gim.ensemble._run_member`` byte-for-byte (asserted in the tests). A custom
    ``collector(world)->dict`` lets callers capture extra state (e.g. the cascade
    variables) without touching the frozen headline-metric path."""
    coll = collector or _collect_metrics
    seed = _member_seed(config.master_seed, index)
    priors = key_priors() if config.prior_set == "key" else all_priors()
    sampled = sample_parameter_set(default_params(), priors, random.Random(seed))
    sampled = apply_param_levers(sampled, selection)

    world = make_world_from_csv(config.state_csv, max_agents=config.max_agents, base_year=config.base_year)
    world.params = sampled
    seed_world(world, seed)
    normalize_resource_scales_forward(world)
    policies = make_policy_map(world.agents.keys(), mode="simple")
    actor_ids = resolve_actors(world, selection.actors) if not selection.is_empty else []

    trajectory = [coll(world)]
    for t in range(1, config.years + 1):
        step_world(world, policies)
        if not selection.is_empty:
            apply_pulses(world, t, selection, actor_ids)
        trajectory.append(coll(world))
    return trajectory


# --------------------------------------------------------------------------- #
# Ontology spec (the menu handed to a UI / LLM)
# --------------------------------------------------------------------------- #


def ontology_spec(world: Any | None = None) -> Dict[str, Any]:
    spec: Dict[str, Any] = {
        "magnitude_range": [MAGNITUDE_MIN, MAGNITUDE_MAX],
        "default_magnitude": DEFAULT_MAGNITUDE,
        "levers": [
            {
                "id": s.id,
                "kind": s.kind,
                "channel": s.channel,
                "label": s.label,
                "label_ru": s.label_ru,
                "rationale": s.rationale,
                "indicators": list(s.indicators),
                "default_magnitude": s.default_magnitude,
                "needs_actors": s.pulse_scope == "actors",
                "targets": (
                    [{"param": t.name, "coeff": t.coeff} for t in s.param_targets]
                    + [{"op": o.kind, "field": o.field, "coeff": o.coeff} for o in s.pulse_ops]
                ),
            }
            for s in GROUNDED_LEVERS.values()
        ],
    }
    if world is not None:
        spec["actors"] = sorted(agent.name for agent in world.agents.values())
    return spec


__all__ = [
    "MAGNITUDE_MIN",
    "MAGNITUDE_MAX",
    "DEFAULT_MAGNITUDE",
    "LeverSpec",
    "ParamTarget",
    "PulseOp",
    "LeverSelection",
    "GROUNDED_LEVERS",
    "clamp_magnitude",
    "make_selection",
    "validate_selection",
    "match_levers",
    "resolve_actors",
    "apply_param_levers",
    "apply_pulses",
    "run_member",
    "ontology_spec",
]
