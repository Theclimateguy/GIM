"""Количественный, акторно-привязанный каскад между доменами.

Цепочка узлов берёт причинный *порядок* из выбранного рычага, а *величины* — это
измеренные Δ (сценарий − база) из детерминированного прогона, в **пик воздействия**
(год максимального |Δ|). Агрегаты считаются НЕ по всем странам, а по **фокус-набору
акторов**, чтобы локальные эффекты (долг импортёров, ВВП затронутых) не растворялись:

* фокус = явные акторы сценария (санкции), иначе — top-K сильнее всего затронутых
  стран по ВВП;
* агентные узлы (инфляция, безработица, долг, напряжённость, ВВП) — по фокусу;
* глобальные узлы (цены, CO₂) — глобально;
* реляционные узлы (барьер, конфликт) — по связям, затрагивающим акторов сценария.

Доп. переменные собираются отдельным коллектором через :func:`gim2.levers.run_member`
(основной путь 8 валидированных метрик — honesty-guard — не затрагивается).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set

from gim.ensemble import _percentile

from . import levers as L
from .runtime import load_world_for
from .scenario import build_config

# Per-agent crisis timelines captured alongside the domain variables (additive;
# not cascade nodes — used by the per-actor states view).
_AGENT_EXTRA: Dict[str, Any] = {
    "debt_crisis_years": lambda a: float(getattr(a.risk, "debt_crisis_active_years", 0)),
    "fx_crisis_years": lambda a: float(getattr(a.risk, "fx_crisis_active_years", 0)),
    "regime_crisis_years": lambda a: float(getattr(a.risk, "regime_crisis_active_years", 0)),
}

# id -> метаданные узла.
#   scope: global (global_state) | agent (per-agent) | relation (per-relation)
#   kind:  price/sum -> percent of base; rate -> pp; level/count -> absolute
#   agg:   как агрегировать агентные узлы по фокусу (sum | mean)
CASCADE_NODES: Dict[str, Dict[str, Any]] = {
    "energy_price": {"label": "Цена энергии", "scope": "global", "kind": "price",
                     "get": lambda w: float(w.global_state.prices.get("energy", 1.0))},
    "food_price": {"label": "Цена продовольствия", "scope": "global", "kind": "price",
                   "get": lambda w: float(w.global_state.prices.get("food", 1.0))},
    "co2": {"label": "CO₂", "scope": "global", "kind": "sum",
            "get": lambda w: float(w.global_state.co2)},
    "inflation": {"label": "Инфляция", "scope": "agent", "kind": "rate", "agg": "mean",
                  "get": lambda a: float(a.economy.inflation)},
    "unemployment": {"label": "Безработица", "scope": "agent", "kind": "rate", "agg": "mean",
                     "get": lambda a: float(a.economy.unemployment)},
    "debt": {"label": "Госдолг затронутых", "scope": "agent", "kind": "sum", "agg": "sum",
             "get": lambda a: float(a.economy.public_debt)},
    "tension": {"label": "Соц. напряжённость", "scope": "agent", "kind": "level", "agg": "mean",
                "get": lambda a: float(a.society.social_tension)},
    "gdp": {"label": "ВВП затронутых", "scope": "agent", "kind": "sum", "agg": "sum",
            "get": lambda a: float(a.economy.gdp)},
    "trade_barrier": {"label": "Торговый барьер", "scope": "relation", "kind": "level",
                      "field": "trade_barrier"},
    "conflict": {"label": "Конфликтное давление", "scope": "relation", "kind": "level",
                 "field": "conflict_level"},
}

# Причинная цепочка узлов по каждому рычагу (порядок эффекта в ядре).
LEVER_CHAINS: Dict[str, List[str]] = {
    "carbon_price": ["energy_price", "inflation", "co2"],
    "decarbonization": ["co2"],
    "growth": ["gdp"],
    "energy_shock": ["energy_price", "inflation", "debt"],
    "food_shock": ["food_price", "tension"],
    "trade_sanctions": ["trade_barrier", "gdp", "conflict"],
    "stagflation": ["unemployment", "inflation", "tension"],
}


def _med(values: Sequence[float]) -> float:
    return _percentile(sorted(values), 50.0)


def _relation_mean(world: Any, field_name: str, scope: Optional[Set[str]]) -> float:
    vals: List[float] = []
    for src, rels in world.relations.items():
        for dst, rel in rels.items():
            if scope is None or src in scope or dst in scope:
                vals.append(float(getattr(rel, field_name, 0.0)))
    return sum(vals) / len(vals) if vals else 0.0


def _make_collector(relation_scope: Optional[Set[str]]):
    agent_nodes = [(nid, m) for nid, m in CASCADE_NODES.items() if m["scope"] == "agent"]
    global_nodes = [(nid, m) for nid, m in CASCADE_NODES.items() if m["scope"] == "global"]
    relation_nodes = [(nid, m) for nid, m in CASCADE_NODES.items() if m["scope"] == "relation"]

    def collect(world: Any) -> Dict[str, Any]:
        return {
            "g": {nid: float(m["get"](world)) for nid, m in global_nodes},
            "a": {aid: {**{nid: float(m["get"](agent)) for nid, m in agent_nodes},
                        **{k: f(agent) for k, f in _AGENT_EXTRA.items()}}
                  for aid, agent in world.agents.items()},
            "r": {nid: _relation_mean(world, m["field"], relation_scope) for nid, m in relation_nodes},
        }

    return collect


def _chain_with_levers(selection: "L.LeverSelection") -> List[tuple]:
    """Ordered (node_id, originating_lever_id), deduped by node (first lever wins)."""
    seen: Set[str] = set()
    out: List[tuple] = []
    for lid in selection.magnitudes:
        for node in LEVER_CHAINS.get(lid, []):
            if node not in seen:
                seen.add(node)
                out.append((node, lid))
    return out


def _agent_value(rows: List[List[Dict[str, Any]]], year: int, nid: str, agg: str, focus: Sequence[str]) -> float:
    per_member: List[float] = []
    for traj in rows:
        a = traj[year]["a"]
        vals = [a[aid][nid] for aid in focus if aid in a]
        if not vals:
            per_member.append(0.0)
        else:
            per_member.append(sum(vals) if agg == "sum" else sum(vals) / len(vals))
    return _med(per_member)


def _value_at(rows: List[List[Dict[str, Any]]], year: int, nid: str, meta: Dict[str, Any],
              focus: Sequence[str]) -> float:
    scope = meta["scope"]
    if scope == "global":
        return _med([traj[year]["g"][nid] for traj in rows])
    if scope == "relation":
        return _med([traj[year]["r"][nid] for traj in rows])
    return _agent_value(rows, year, nid, meta.get("agg", "mean"), focus)


def _top_affected(base, scen, agent_ids: List[str], horizon: int, k: int) -> List[str]:
    scored: List[tuple] = []
    for aid in agent_ids:
        peak = 0.0
        for y in range(horizon):
            b = _med([traj[y]["a"][aid]["gdp"] for traj in base if aid in traj[y]["a"]])
            s = _med([traj[y]["a"][aid]["gdp"] for traj in scen if aid in traj[y]["a"]])
            peak = max(peak, abs(s - b))
        scored.append((aid, peak))
    scored.sort(key=lambda kv: kv[1], reverse=True)
    return [aid for aid, _ in scored[:k]]


def _format_node(nid: str, meta: Dict[str, Any], year: int, delta: float, base: float,
                 focus_scope: str) -> Dict[str, Any]:
    kind = meta["kind"]
    if kind in ("price", "sum"):
        pct = round(delta / base * 100.0, 1) if abs(base) > 1e-12 else None
        shown = f"{pct:+.1f}%" if pct is not None else f"{delta:+.3g}"
    elif kind == "rate":
        pct = None
        shown = f"{delta * 100:+.2f} пп"
    else:  # level / count
        pct = None
        shown = f"{delta:+.3g}"
    direction = "up" if delta > 1e-9 else "down" if delta < -1e-9 else "flat"
    return {"id": nid, "label": meta["label"], "kind": kind, "scope": meta["scope"],
            "focus_scope": focus_scope, "year": year,
            "base": round(base, 4), "delta": round(delta, 4), "pct": pct,
            "shown": shown, "direction": direction}


def _peak(base, scen, horizon, nid, meta, focus):
    peak_year, peak_delta, peak_base = 0, 0.0, _value_at(base, 0, nid, meta, focus)
    for y in range(horizon):
        b = _value_at(base, y, nid, meta, focus)
        d = _value_at(scen, y, nid, meta, focus) - b
        if abs(d) >= abs(peak_delta):
            peak_year, peak_delta, peak_base = y, d, b
    return peak_year, peak_delta, peak_base


@dataclass
class ActorRun:
    """One base+scenario pair captured with the per-agent collector, shared by the
    cascade and the per-actor states views so ``/run/answer`` runs it only once."""

    selection: "L.LeverSelection"
    base: List[List[Dict[str, Any]]]
    scen: List[List[Dict[str, Any]]]
    world: Any
    horizon: int
    selection_focus: List[str]
    relation_scope: Optional[Set[str]]
    affected: List[str] = field(default_factory=list)

    def names(self, ids: Sequence[str]) -> List[str]:
        return [self.world.agents[a].name for a in ids if a in self.world.agents]


def run_actor_pair(
    *, state_csv=None, selection: "L.LeverSelection", years=10, max_agents=100, seed=2026, members=24, top_k=3,
) -> ActorRun:
    config = build_config(state_csv=state_csv, members=members, years=years,
                          max_agents=max_agents, seed=seed, prior_set="key", jobs=1)
    world = load_world_for(config.state_csv, config.max_agents)
    selection_focus = L.resolve_actors(world, selection.actors) if selection.actors else []
    relation_scope: Optional[Set[str]] = set(selection_focus) if selection_focus else None
    coll = _make_collector(relation_scope)
    base = [L.run_member(config, L.LeverSelection(), index=i, collector=coll) for i in range(members)]
    scen = [L.run_member(config, selection, index=i, collector=coll) for i in range(members)]
    horizon = config.years + 1
    affected = _top_affected(base, scen, list(world.agents.keys()), horizon, top_k)
    return ActorRun(selection, base, scen, world, horizon, selection_focus, relation_scope, affected)


def build_cascade(run: ActorRun) -> Dict[str, Any]:
    chain = _chain_with_levers(run.selection)
    if not chain or run.selection.is_empty:
        return {"nodes": [], "affected": [], "selection_actors": []}
    nodes: List[Dict[str, Any]] = []
    for nid, lever_id in chain:
        meta = CASCADE_NODES[nid]
        actor_lever = lever_id in L.GROUNDED_LEVERS and L.GROUNDED_LEVERS[lever_id].pulse_scope == "actors"
        if meta["scope"] == "global":
            focus, focus_scope = [], "global"
        elif meta["scope"] == "relation":
            focus, focus_scope = [], ("selection" if run.relation_scope else "global")
        elif actor_lever and run.selection_focus:
            focus, focus_scope = run.selection_focus, "selection"
        else:
            focus, focus_scope = run.affected, "most_affected"
        py, pd, pb = _peak(run.base, run.scen, run.horizon, nid, meta, focus)
        nodes.append(_format_node(nid, meta, py, pd, pb, focus_scope))
    return {"nodes": nodes, "affected": run.names(run.affected),
            "selection_actors": run.names(run.selection_focus)}


def compute_cascade(
    *, state_csv=None, selection: "L.LeverSelection", years=10, max_agents=100, seed=2026, members=24, top_k=3,
) -> Dict[str, Any]:
    if selection.is_empty:
        return {"nodes": [], "affected": [], "selection_actors": []}
    return build_cascade(run_actor_pair(state_csv=state_csv, selection=selection, years=years,
                                        max_agents=max_agents, seed=seed, members=members, top_k=top_k))


__all__ = ["compute_cascade", "run_actor_pair", "build_cascade", "ActorRun",
           "CASCADE_NODES", "LEVER_CHAINS", "_med"]
